from __future__ import annotations
import re
import base64
import urllib.parse
from dataclasses import dataclass
from typing import Iterable, Any
from bs4 import BeautifulSoup

from .providers import build_queries, source_map, enabled_direct_seeds, enabled_sources
from .discovery_diagnostics import emit
from .ats_boards import discover_boards
from .jobspy_provider import discover as discover_jobspy, available as jobspy_available

try:
    from scrapling.fetchers import Fetcher, DynamicFetcher
except Exception:
    Fetcher = None
    DynamicFetcher = None


@dataclass
class Hit:
    url: str
    title: str
    snippet: str
    source: str
    provider_key: str = 'global'
    query: str = ''
    prefetched: dict[str, Any] | None = None


BLOCKED_DOMAINS = {
    'facebook.com', 'instagram.com', 'youtube.com', 'tiktok.com',
    'pinterest.com', 'wikipedia.org'
}

TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'gclid', 'fbclid', 'msclkid', 'ref', 'referrer'
}


def _response_html(page) -> str:
    for attr in ('html_content', 'text'):
        try:
            val = getattr(page, attr)
            if callable(val):
                val = val()
            if val:
                return str(val)
        except Exception:
            pass
    return str(page)


def _fetch_static(url: str) -> str:
    if Fetcher is None:
        raise RuntimeError('Scrapling is not installed')
    page = Fetcher.get(url, stealthy_headers=True, follow_redirects=True, timeout=25)
    return _response_html(page)


def _looks_blocked(html: str) -> bool:
    s = (html or '').lower()
    signs = ('verify you are human', 'access denied', '<title>just a moment', 'robot check', 'anomaly.js')
    return len(s) < 2200 or any(x in s for x in signs)


def fetch_html(url: str, dynamic_fallback: bool = True) -> tuple[str, str]:
    """Return (html, fetch_mode). No CAPTCHA/MFA bypass is attempted."""
    first_error = ''
    try:
        html = _fetch_static(url)
        if not _looks_blocked(html) or not dynamic_fallback:
            return html, 'static'
    except Exception as exc:
        first_error = str(exc)
        html = ''

    if dynamic_fallback and DynamicFetcher is not None:
        try:
            page = DynamicFetcher.fetch(
                url,
                headless=True,
                timeout=35000,
                network_idle=False,
                disable_resources=True,
            )
            dyn = _response_html(page)
            if dyn and not _looks_blocked(dyn):
                return dyn, 'dynamic'
        except Exception as exc:
            if first_error:
                raise RuntimeError(f'static={first_error}; dynamic={exc}') from exc
            raise

    if html:
        return html, 'static-blocked'
    raise RuntimeError(first_error or 'Unable to fetch page')


def _host(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower().removeprefix('www.')


def _provider_for_host(host: str, fallback: str = 'global') -> str:
    for key, spec in source_map().items():
        d = spec.domain.lower().removeprefix('www.')
        if host == d or host.endswith('.' + d) or d.endswith('.' + host):
            return key
    return fallback


def _allowed_url(url: str) -> bool:
    if not url.startswith(('http://', 'https://')):
        return False
    host = _host(url)
    return bool(host) and not any(host == d or host.endswith('.' + d) for d in BLOCKED_DOMAINS)


def _job_detail_url(url: str) -> bool:
    host = _host(url)
    path = urllib.parse.urlparse(url).path
    if host.endswith('francetravail.fr'):
        return '/offres/recherche/detail/' in path
    if host.endswith('hellowork.com'):
        return bool(re.search(r'/emplois/\d+\.html', path))
    if host.endswith('indeed.com'):
        return any(x in path for x in ('viewjob', '/rc/clk', '/pagead/clk'))
    return True


def _dedupe_key(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        qs = [(k, v) for k, v in qs if k.lower() not in TRACKING_PARAMS]
        clean = p._replace(query=urllib.parse.urlencode(qs), fragment='')
        return urllib.parse.urlunparse(clean).rstrip('/').lower()
    except Exception:
        return re.sub(r'[?#].*$', '', url).rstrip('/').lower()


def discover_direct(profile: dict, report=None) -> Iterable[Hit]:
    """Discover offer URLs from a small set of public first-party listing pages."""
    global_pages = max(1, int(profile.get('direct_source_pages', 3)))
    dynamic = bool(profile.get('dynamic_fetch_fallback', True))

    for spec in enabled_direct_seeds(profile):
        pages = min(global_pages, max(1, int(profile.get(f'{spec.provider_key}_direct_pages', spec.default_pages))))
        seen_here: set[str] = set()
        for page_no in range(1, pages + 1):
            url = spec.page_url.format(page=page_no)
            emit(report, spec.provider_key, 'direct', 'running', query=url)
            try:
                html, mode = fetch_html(url, dynamic_fallback=dynamic)
                if mode == 'static-blocked':
                    raise RuntimeError('Listing page blocked or unreadable')
            except Exception as exc:
                emit(report, spec.provider_key, 'direct', 'failed', error=str(exc))
                continue
            soup = BeautifulSoup(html, 'lxml')
            rx = re.compile(spec.link_pattern, re.I)
            count = 0
            for a in soup.select('a[href]'):
                href = urllib.parse.urljoin(url, a.get('href', '').strip())
                if not _allowed_url(href) or not rx.search(href):
                    continue
                key = _dedupe_key(href)
                if key in seen_here:
                    continue
                seen_here.add(key)
                count += 1
                title = a.get_text(' ', strip=True)
                yield Hit(
                    href,
                    title[:400],
                    '',
                    _host(href),
                    spec.provider_key,
                    f'direct:{spec.provider_key}:page:{page_no}',
                )
            emit(report, spec.provider_key, 'direct', 'success' if count else 'empty', results=count)


def _bing_target(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if _host(url) in {'bing.com', 'www.bing.com'} and parsed.path == '/ck/a':
        value = urllib.parse.parse_qs(parsed.query).get('u', [''])[0]
        if value.startswith('a1'):
            try:
                return base64.urlsafe_b64decode(value[2:] + '=' * (-len(value[2:]) % 4)).decode('utf-8')
            except (ValueError, UnicodeError):
                return ''
    return url


def _check_search_response(html: str):
    text = (html or '').lower()
    if any(sign in text for sign in ('anomaly.js', 'bots use duckduckgo', 'verify you are human', 'access denied', 'unusual traffic')):
        raise RuntimeError('Search engine blocked the request or requires verification')


def search_bing(query: str, limit: int = 12, provider_key: str = 'global', market: str = '', include_listings: bool = False) -> list[Hit]:
    params = {'q': query, 'count': limit}
    if market:
        params['setlang'] = market
    url = 'https://www.bing.com/search?' + urllib.parse.urlencode(params)
    html, _ = fetch_html(url, dynamic_fallback=False)
    _check_search_response(html)
    soup = BeautifulSoup(html, 'lxml')
    hits = []
    for li in soup.select('li.b_algo'):
        a = li.select_one('h2 a')
        if not a or not a.get('href'):
            continue
        href = _bing_target(a['href'])
        if not _allowed_url(href) or (not include_listings and not _job_detail_url(href)):
            continue
        if _host(href).endswith('bing.com'):
            continue
        sn = li.select_one('.b_caption p') or li.select_one('p')
        hits.append(Hit(
            href,
            a.get_text(' ', strip=True),
            sn.get_text(' ', strip=True) if sn else '',
            _host(href),
            _provider_for_host(_host(href), provider_key),
            query,
            {'discovery_listing': True} if not _job_detail_url(href) else None,
        ))
        if len(hits) >= limit:
            break
    return hits


def _ddg_target(href: str) -> str:
    if href.startswith('//'):
        href = 'https:' + href
    try:
        p = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(p.query)
        if 'uddg' in qs and qs['uddg']:
            return urllib.parse.unquote(qs['uddg'][0])
    except Exception:
        pass
    return href


def search_duckduckgo(query: str, limit: int = 12, provider_key: str = 'global', market: str = '', include_listings: bool = False) -> list[Hit]:
    params = {'q': query}
    if market:
        params['kl'] = market.lower()
    url = 'https://html.duckduckgo.com/html/?' + urllib.parse.urlencode(params)
    html, _ = fetch_html(url, dynamic_fallback=False)
    _check_search_response(html)
    soup = BeautifulSoup(html, 'lxml')
    hits = []
    for result in soup.select('.result'):
        a = result.select_one('.result__a')
        if not a or not a.get('href'):
            continue
        href = _ddg_target(a['href'])
        if not _allowed_url(href) or (not include_listings and not _job_detail_url(href)):
            continue
        sn = result.select_one('.result__snippet')
        hits.append(Hit(
            href,
            a.get_text(' ', strip=True),
            sn.get_text(' ', strip=True) if sn else '',
            _host(href),
            _provider_for_host(_host(href), provider_key),
            query,
            {'discovery_listing': True} if not _job_detail_url(href) else None,
        ))
        if len(hits) >= limit:
            break
    return hits


def _expand_listing(hit: Hit, limit: int, report=None) -> list[Hit]:
    emit(report, hit.provider_key, 'listing', 'running', query=hit.url)
    try:
        html, mode = fetch_html(hit.url, dynamic_fallback=False)
        if mode == 'static-blocked':
            raise RuntimeError('Public listing page blocked or unreadable')
        hits, seen = [], set()
        for link in BeautifulSoup(html, 'lxml').select('a[href]'):
            url = urllib.parse.urljoin(hit.url, link.get('href', ''))
            if not _allowed_url(url) or not _job_detail_url(url) or _provider_for_host(_host(url)) != hit.provider_key:
                continue
            key = _dedupe_key(url)
            if key in seen:
                continue
            seen.add(key)
            hits.append(Hit(url, link.get_text(' ', strip=True)[:400], '', _host(url), hit.provider_key, hit.query))
            if len(hits) >= limit:
                break
        emit(report, hit.provider_key, 'listing', 'success' if hits else 'empty', results=len(hits))
        return hits
    except Exception as exc:
        emit(report, hit.provider_key, 'listing', 'failed', error=str(exc))
        return []


def search_web(query: str, limit: int, provider_key: str, engines: list[str], market: str = '', report=None) -> list[Hit]:
    errors = []
    for engine in engines:
        method = 'web:' + engine
        emit(report, provider_key, method, 'running', query=query)
        try:
            if engine == 'bing':
                hits = search_bing(query, limit, provider_key, market, include_listings=True)
            elif engine in {'ddg', 'duckduckgo'}:
                hits = search_duckduckgo(query, limit, provider_key, market, include_listings=True)
            else:
                emit(report, provider_key, method, 'unavailable', error='Unsupported search engine')
                continue
            site_filter = re.search(r'\bsite:([^\s]+)', query)
            if site_filter:
                domain = site_filter.group(1).lower().strip('"')
                hits = [hit for hit in hits if _host(hit.url) == domain or _host(hit.url).endswith('.' + domain)]
            listings = [hit for hit in hits if (hit.prefetched or {}).get('discovery_listing')]
            hits = [hit for hit in hits if not (hit.prefetched or {}).get('discovery_listing')]
            for listing in listings[:2]:
                hits.extend(_expand_listing(listing, max(1, limit - len(hits)), report=report))
                if len(hits) >= limit:
                    break
            hits = hits[:limit]
            emit(report, provider_key, method, 'success' if hits else 'empty', results=len(hits))
            if hits:
                return hits
        except Exception as exc:
            errors.append(f'{engine}:{exc}')
            emit(report, provider_key, method, 'failed', error=str(exc))
    if errors:
        raise RuntimeError('; '.join(errors))
    return []


def discover(profile: dict, report=None) -> Iterable[Hit]:
    seen: set[str] = set()
    early_hits: list[Hit] = []
    queries = build_queries(profile)
    planned = {key for key, _ in queries}
    for source in enabled_sources(profile):
        emit(report, source.key, 'web', 'pending' if source.key in planned else 'not_run')

    # Public ATS board APIs configured by the user. This mirrors the robust scouting
    # pattern used by mature open-source auto-apply projects, while keeping the board
    # identifiers explicit and local rather than scraping private endpoints.
    for row in discover_boards(profile.get('company_boards', []), report=report):
        hit = Hit(**row)
        key = _dedupe_key(hit.url)
        if key in seen:
            continue
        seen.add(key)
        early_hits.append(hit)

    # Direct adapters first: faster, fresher, and less dependent on search indexing.
    for hit in discover_direct(profile, report=report):
        key = _dedupe_key(hit.url)
        if key in seen:
            continue
        seen.add(key)
        early_hits.append(hit)

    # JobSpy aggregates several major boards concurrently.  It is optional at
    # runtime and all results still pass through the same local scoring/dedupe
    # pipeline as search-engine and first-party discoveries.
    engines = profile.get('search_engines', ['bing', 'duckduckgo'])
    limit = int(profile.get('max_results_per_query', 10))
    market = str(profile.get('search_market', '') or '').strip()
    for provider_key, query in queries:
        try:
            hits = search_web(query, limit, provider_key, engines, market, report=report)
        except Exception:
            continue  # Each engine failure has already been reported.
        for hit in hits:
            key = _dedupe_key(hit.url)
            if key not in seen:
                seen.add(key)
                early_hits.append(hit)

    # Test all configured discovery routes before serially fetching their details.
    # A large first-party board must not postpone other sources' diagnostics.
    yield from early_hits

    if profile.get('jobspy_enabled', True) and jobspy_available():
        try:
            for row in discover_jobspy(profile, report=report):
                hit = Hit(
                    url=row.url, title=row.title, snippet=row.snippet, source=row.source,
                    provider_key=row.provider_key, query=row.query, prefetched=row.prefetched,
                )
                key = _dedupe_key(hit.url)
                if key in seen:
                    continue
                seen.add(key)
                yield hit
        except Exception as exc:
            # Discovery should degrade gracefully if one external provider is
            # rate-limited or temporarily unavailable.
            emit(report, 'jobspy', 'jobspy', 'failed', error=str(exc))
    elif profile.get('jobspy_enabled', True):
        emit(report, 'jobspy', 'jobspy', 'unavailable', error='python-jobspy is not installed')
