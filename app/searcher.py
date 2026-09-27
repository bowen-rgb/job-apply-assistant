from __future__ import annotations
import re
import urllib.parse
from dataclasses import dataclass
from typing import Iterable, Any
from bs4 import BeautifulSoup

from .providers import build_queries, source_map, enabled_direct_seeds
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
    signs = ('captcha', 'verify you are human', 'access denied', 'just a moment', 'enable javascript', 'robot check')
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
            if dyn:
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


def _dedupe_key(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        qs = [(k, v) for k, v in qs if k.lower() not in TRACKING_PARAMS]
        clean = p._replace(query=urllib.parse.urlencode(qs), fragment='')
        return urllib.parse.urlunparse(clean).rstrip('/').lower()
    except Exception:
        return re.sub(r'[?#].*$', '', url).rstrip('/').lower()


def discover_direct(profile: dict) -> Iterable[Hit]:
    """Discover offer URLs from a small set of public first-party listing pages."""
    global_pages = max(1, int(profile.get('direct_source_pages', 3)))
    dynamic = bool(profile.get('dynamic_fetch_fallback', True))

    for spec in enabled_direct_seeds(profile):
        pages = min(global_pages, max(1, int(profile.get(f'{spec.provider_key}_direct_pages', spec.default_pages))))
        seen_here: set[str] = set()
        for page_no in range(1, pages + 1):
            url = spec.page_url.format(page=page_no)
            try:
                html, _ = fetch_html(url, dynamic_fallback=dynamic)
            except Exception:
                continue
            soup = BeautifulSoup(html, 'lxml')
            rx = re.compile(spec.link_pattern, re.I)
            for a in soup.select('a[href]'):
                href = urllib.parse.urljoin(url, a.get('href', '').strip())
                if not _allowed_url(href) or not rx.search(href):
                    continue
                key = _dedupe_key(href)
                if key in seen_here:
                    continue
                seen_here.add(key)
                title = a.get_text(' ', strip=True)
                yield Hit(
                    href,
                    title[:400],
                    '',
                    _host(href),
                    spec.provider_key,
                    f'direct:{spec.provider_key}:page:{page_no}',
                )


def search_bing(query: str, limit: int = 12, provider_key: str = 'global', market: str = '') -> list[Hit]:
    params = {'q': query, 'count': limit}
    if market:
        params['setlang'] = market
    url = 'https://www.bing.com/search?' + urllib.parse.urlencode(params)
    html, _ = fetch_html(url, dynamic_fallback=False)
    soup = BeautifulSoup(html, 'lxml')
    hits = []
    for li in soup.select('li.b_algo'):
        a = li.select_one('h2 a')
        if not a or not a.get('href'):
            continue
        href = a['href']
        if not _allowed_url(href):
            continue
        sn = li.select_one('.b_caption p') or li.select_one('p')
        hits.append(Hit(
            href,
            a.get_text(' ', strip=True),
            sn.get_text(' ', strip=True) if sn else '',
            _host(href),
            _provider_for_host(_host(href), provider_key),
            query,
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


def search_duckduckgo(query: str, limit: int = 12, provider_key: str = 'global', market: str = '') -> list[Hit]:
    params = {'q': query}
    if market:
        params['kl'] = market.lower()
    url = 'https://html.duckduckgo.com/html/?' + urllib.parse.urlencode(params)
    html, _ = fetch_html(url, dynamic_fallback=False)
    soup = BeautifulSoup(html, 'lxml')
    hits = []
    for result in soup.select('.result'):
        a = result.select_one('.result__a')
        if not a or not a.get('href'):
            continue
        href = _ddg_target(a['href'])
        if not _allowed_url(href):
            continue
        sn = result.select_one('.result__snippet')
        hits.append(Hit(
            href,
            a.get_text(' ', strip=True),
            sn.get_text(' ', strip=True) if sn else '',
            _host(href),
            _provider_for_host(_host(href), provider_key),
            query,
        ))
        if len(hits) >= limit:
            break
    return hits


def search_web(query: str, limit: int, provider_key: str, engines: list[str], market: str = '') -> list[Hit]:
    errors = []
    for engine in engines:
        try:
            if engine == 'bing':
                hits = search_bing(query, limit, provider_key, market)
            elif engine in {'ddg', 'duckduckgo'}:
                hits = search_duckduckgo(query, limit, provider_key, market)
            else:
                continue
            if hits:
                return hits
        except Exception as exc:
            errors.append(f'{engine}:{exc}')
    if errors:
        raise RuntimeError('; '.join(errors))
    return []


def discover(profile: dict) -> Iterable[Hit]:
    seen: set[str] = set()

    # Public ATS board APIs configured by the user. This mirrors the robust scouting
    # pattern used by mature open-source auto-apply projects, while keeping the board
    # identifiers explicit and local rather than scraping private endpoints.
    for row in discover_boards(profile.get('company_boards', [])):
        hit = Hit(**row)
        key = _dedupe_key(hit.url)
        if key in seen:
            continue
        seen.add(key)
        yield hit

    # Direct adapters first: faster, fresher, and less dependent on search indexing.
    for hit in discover_direct(profile):
        key = _dedupe_key(hit.url)
        if key in seen:
            continue
        seen.add(key)
        yield hit

    # JobSpy aggregates several major boards concurrently.  It is optional at
    # runtime and all results still pass through the same local scoring/dedupe
    # pipeline as search-engine and first-party discoveries.
    if profile.get('jobspy_enabled', True) and jobspy_available():
        try:
            for row in discover_jobspy(profile):
                hit = Hit(
                    url=row.url, title=row.title, snippet=row.snippet, source=row.source,
                    provider_key=row.provider_key, query=row.query, prefetched=row.prefetched,
                )
                key = _dedupe_key(hit.url)
                if key in seen:
                    continue
                seen.add(key)
                yield hit
        except Exception:
            # Discovery should degrade gracefully if one external provider is
            # rate-limited or temporarily unavailable.
            pass

    engines = profile.get('search_engines', ['bing', 'duckduckgo'])
    limit = int(profile.get('max_results_per_query', 10))
    market = str(profile.get('search_market', '') or '').strip()
    for provider_key, query in build_queries(profile):
        try:
            hits = search_web(query, limit, provider_key, engines, market)
        except Exception:
            continue
        for hit in hits:
            key = _dedupe_key(hit.url)
            if key in seen:
                continue
            seen.add(key)
            yield hit
