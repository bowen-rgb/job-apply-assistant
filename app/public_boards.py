"""Bounded public listings; no form submissions, private APIs or reused login tabs."""
from __future__ import annotations
import re
import json
from urllib.parse import urlencode, urljoin, urlparse
from bs4 import BeautifulSoup
from .discovery_diagnostics import emit
from .providers import enabled_sources

BOARDS = {
    'hellowork': ('hellowork.com', r'^/fr-fr/emplois/\d+\.html$'),
    'jobteaser': ('jobteaser.com', r'^/(?:fr|en)/job-offers/[^/]+/?$'),
    '1jeune1solution': ('1jeune1solution.gouv.fr', r'^/stages/[^/]+/?$'),
    'apec': ('apec.fr', r'^/candidat/recherche-stage\.html/[^/]+/[^/]+/?$'),
    'wttj': ('welcometothejungle.com', r'^/(?:fr|en)/companies/[^/]+/jobs/[^/]+/?$'),
    'france_travail': ('francetravail.fr', r'^/offres/recherche/detail/[^/]+/?$'),
}


def detail_url(source: str, url: str) -> bool:
    if source not in BOARDS:return False
    host, pattern = BOARDS[source]
    parsed = urlparse(url)
    actual = (parsed.hostname or '').lower()
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and (actual == host or actual.endswith('.'+host))
            and bool(re.fullmatch(pattern, parsed.path)))


def source_for_url(url: str, fallback: str = '') -> str:
    """Use the actual destination for parsing, including PFE search-engine hits."""
    return next((key for key in BOARDS if detail_url(key,url)),fallback)


def listing_url(source: str, term: str, location: str, page: int = 1) -> str:
    if source == 'hellowork':
        return 'https://www.hellowork.com/fr-fr/emploi/recherche.html?'+urlencode({'k':term,'l':location,'c':'Stage','p':page})
    if source == 'jobteaser':
        return 'https://www.jobteaser.com/fr/job-offers?'+urlencode({'q':term,'contract':'internship','page':page})
    if source == '1jeune1solution':
        return 'https://www.1jeune1solution.gouv.fr/stages?'+urlencode({'offre-de-stage[query]':term,'offre-de-stage[page]':page})
    if source == 'apec':
        return 'https://www.apec.fr/candidat/recherche-stage.html/stage?'+urlencode({'motsCles':term,'page':page-1})
    if source == 'wttj':
        return 'https://www.welcometothejungle.com/fr/jobs?'+urlencode({'query':term,'refinementList[contract_type][]':'internship','page':page})
    if source == 'france_travail':
        return 'https://candidat.francetravail.fr/offres/recherche?'+urlencode({'motsCles':term,'range':f'{(page-1)*20}-{page*20-1}'})
    raise ValueError('Unknown public source')


def read_page(url: str, profile: dict, *, render: bool = False) -> tuple[str, str, str]:
    from .searcher import fetch_html, _looks_blocked
    from .pfe_discovery import validate_destination
    validate_destination(url)
    try:
        if render:raise ValueError('Rendered public content required')
        html, mode = fetch_html(url, dynamic_fallback=False)
        if mode == 'static-blocked' or _looks_blocked(html) or verification_gate(html):raise ValueError('Public page blocked')
        return html, mode, url
    except Exception:
        if not profile.get('dynamic_fetch_fallback', True):raise
        from .qr_browser_reader import read_rendered
        raw, _, final = read_rendered(url, search_filters=False)
        html = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw
        if _looks_blocked(html) or verification_gate(html):raise ValueError('Public page blocked or requires verification')
        path = urlparse(final).path.lower()
        if re.search(r'/(?:login|sign-in|users/sign_in|connexion|auth)(?:/|$)',path):
            raise ValueError('Login required; open the school portal explicitly')
        return html, 'public-chrome', final


def verification_gate(html: str) -> bool:
    soup = BeautifulSoup(html,'lxml')
    for node in soup.select('script,style'):node.decompose()
    text = soup.get_text(' ',strip=True).lower()
    return len(text)<2500 and any(sign in text for sign in ('verify your device','verifying your device','vérification de votre','验证设备','正在验证','验证进行中','checking your browser','verify you are human','access denied'))


def capability(source: str) -> dict:
    if source == 'hellowork':
        from .jobspy_provider import supported_sites
        supported = 'hellowork' in supported_sites()
        return {'methods':['jobspy','public-listing','web'] if supported else ['public-listing','web'], 'access_hint':'Collecte JobSpy et recherche web' if supported else 'Recherche web ; collecteur à mettre à jour'}
    if source in BOARDS:
        return {'methods':['public-listing','web'], 'access_hint':'Offres publiques ; accès école séparé' if source=='jobteaser' else 'Pages publiques et recherche web'}
    return {'methods':['web'],'access_hint':'Recherche web ciblée'}


def extract_links(source: str, html: str, base: str) -> list[dict]:
    from .searcher import _dedupe_key
    soup = BeautifulSoup(html, 'lxml')
    rows, seen = [], set()
    for link in soup.select('a[href]'):
        url = urljoin(base, link.get('href',''))
        key = _dedupe_key(url)
        if key in seen or not detail_url(source,url):continue
        title = link.get_text(' ',strip=True) or link.get('aria-label','')
        if len(title)<4:continue
        heading = link.select_one('h1,h2,h3,h4')
        seen.add(key)
        rows.append({'url':url,'title':heading.get_text(' ',strip=True) if heading else title[:400],'snippet':title[:1200]})
    return rows


def extract_document(source: str, html: str, url: str, **fallback):
    from .extractor import extract_job_document
    if source != '1jeune1solution':return extract_job_document(html,url,**fallback)
    soup=BeautifulSoup(html,'lxml')
    script=soup.select_one('script#__NEXT_DATA__')
    try:
        offer=json.loads(script.string or '{}')['props']['pageProps']['offreDeStage'] if script else None
    except (ValueError,KeyError,TypeError):offer=None
    if not isinstance(offer,dict) or not offer.get('titre'):
        raise ValueError('Internship detail incomplete; employer and timing must be verified')
    employer=offer.get('employeur') or {};place=offer.get('localisation') or {}
    start=offer.get('dateDeDebutMin') or '';end=offer.get('dateDeDebutMax') or ''
    posting={'@context':'https://schema.org','@type':'JobPosting','title':offer['titre'],
             'hiringOrganization':{'@type':'Organization','name':employer.get('nom','')},
             'jobLocation':{'@type':'Place','address':{'addressLocality':place.get('ville',''),'addressRegion':place.get('region',''),'postalCode':place.get('codePostal',''),'addressCountry':place.get('pays','')}},
             'description':offer.get('description',''),'employmentType':'INTERN',
             'jobStartDate':start if start==end else '',
             'url':url,'applicationUrl':offer.get('urlDeCandidature',''),
             'source':offer.get('source',''),'availabilityWindow':{'min':start,'max':end},
             'durationDays':{'min':offer.get('dureeEnJour'),'max':offer.get('dureeEnJourMax')}}
    encoded=json.dumps(posting,ensure_ascii=False).replace('<','\\u003c')
    doc=extract_job_document('<html><script type="application/ld+json">'+encoded+'</script><body></body></html>',url,**fallback)
    metadata=json.loads(doc.structured_json or '{}')
    metadata.update(applicationUrl=posting['applicationUrl'],source=posting['source'],availabilityWindow=posting['availabilityWindow'],durationDays=posting['durationDays'],originalListingUrl=url)
    doc.structured_json=json.dumps(metadata,ensure_ascii=False)
    if any(detail_url(key,posting['applicationUrl']) for key in BOARDS):
        from .extractor import canonicalize_url
        doc.canonical_url=canonicalize_url(posting['applicationUrl'])
    return doc


def discover(profile: dict, report=None):
    from .searcher import Hit
    from .pfe import settings, DIRECTIONS
    enabled = {source.key for source in enabled_sources(profile)}
    cfg = settings(profile)
    is_pfe = cfg['enabled']
    terms = [DIRECTIONS[key][0] for key in cfg['directions']] if is_pfe else list(profile.get('preferred_roles') or [])
    if not terms:return
    # General employment profiles must not be silently restricted to internship-only boards.
    if not is_pfe and not any('stage' in str(x).lower() or 'intern' in str(x).lower() for x in profile.get('contracts',[])):return
    locations = cfg['locations'] if is_pfe else profile.get('locations',[])
    location = ', '.join(locations[:2])
    limit = max(1,min(6,int(profile.get('public_board_queries',6))))
    pages = max(1,min(3,int(profile.get('public_board_pages',1))))
    boards = [key for key in BOARDS if key in enabled]
    seen = set()
    for index in range(min(limit,len(terms))):
        for source in boards[:]:
            for page in range(1,pages+1):
                url = listing_url(source,terms[index],location,page)
                emit(report,source,'public-listing','running',query=url)
                try:
                    html,mode,final = read_page(url,profile)
                    rows = extract_links(source,html,final)
                    if not rows and mode!='public-chrome' and profile.get('dynamic_fetch_fallback',True):
                        html,mode,final=read_page(url,profile,render=True)
                        rows=extract_links(source,html,final)
                    if not rows and not re.search(r'aucun(?:e)? (?:offre|r[eé]sultat)|no (?:jobs|results) found',BeautifulSoup(html,'lxml').get_text(' ',strip=True),re.I):
                        raise ValueError('Listing content incomplete; targeted web search remains available')
                    emit(report,source,'public-listing','success' if rows else 'empty',results=len(rows),query=url)
                except Exception as exc:
                    emit(report,source,'public-listing','failed',error=str(exc)[:600],query=url)
                    boards.remove(source) # one inaccessible site must not consume the whole scan
                    break
                added = 0
                for row in rows[:max(1,min(50,int(profile.get('max_results_per_query',10))))]:
                    key = row['url'].split('#')[0]
                    if key in seen:continue
                    seen.add(key);added+=1
                    yield Hit(row['url'],row['title'],row['snippet'],BOARDS[source][0],source,url)
                if not added:break
