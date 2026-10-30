"""Public ATS feeds ported from Apply-Pilot src/scan/portals.mjs (MIT).

One local reader, no upstream server, CLI, agent, or second database. Search POSTs
are confined to the three documented read-only ATS search paths below.
"""
import json
import re
from urllib.parse import urlsplit, urljoin, quote, urlencode
from urllib.request import Request, build_opener
from bs4 import BeautifulSoup
from .worker_runtime import check_cancelled

PROVIDERS = frozenset({'workday', 'smartrecruiters', 'eightfold', 'phenom', 'successfactors',
                       'personio', 'greenhouse', 'lever', 'ashby', 'teamtailor', 'recruitee', 'workable'})


def detect(url):
    host = (urlsplit(url).hostname or '').lower()
    domains = {'myworkdayjobs.com': 'workday', 'smartrecruiters.com': 'smartrecruiters',
               'eightfold.ai': 'eightfold', 'successfactors.eu': 'successfactors',
               'successfactors.com': 'successfactors', 'personio.de': 'personio', 'personio.com': 'personio',
               'greenhouse.io': 'greenhouse', 'lever.co': 'lever', 'ashbyhq.com': 'ashby',
               'teamtailor.com': 'teamtailor', 'recruitee.com': 'recruitee', 'workable.com': 'workable'}
    return next((provider for domain, provider in domains.items() if host == domain or host.endswith('.'+domain)), '')


def request(url, body=None):
    from .pfe_discovery import validate_destination, CheckedRedirect, read_public
    parsed = urlsplit(url)
    if parsed.scheme != 'https':
        raise ValueError('ATS feeds require HTTPS')
    if body is None:
        raw, _, _ = read_public(url)
    else:
        # No arbitrary browser actions or form POSTs are permitted by this reader.
        if not (re.fullmatch(r'/wday/cxs/[\w.-]+/[\w.-]+/jobs', parsed.path)
                or parsed.path in {'/widgets', '/services/recruiting/v1/jobs'}):
            raise ValueError('Unsupported read-only ATS search endpoint')
        validate_destination(url)
        req = Request(url, data=json.dumps(body).encode(), headers={
            'Content-Type': 'application/json', 'User-Agent': 'JobApplyAssistant/public-ATS-search'})
        with build_opener(CheckedRedirect()).open(req, timeout=20) as response:
            raw = response.read(8*1024*1024+1)
        if len(raw) > 8*1024*1024:
            raise ValueError('ATS response exceeds 8 MB')
    text = raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else raw
    try:
        return json.loads(text)
    except ValueError:
        return text


def collect(provider, url, company='', *, read=request, max_pages=3):
    if provider not in PROVIDERS:
        raise ValueError('Unsupported ATS')
    u = urlsplit(url)
    if u.scheme != 'https' or u.username or u.password:
        raise ValueError('ATS feeds require a public HTTPS URL')
    origin = f'https://{u.netloc}'
    parts = [p for p in u.path.split('/') if p and not re.fullmatch(r'[a-z]{2}[-_][A-Za-z]{2}', p)]
    token = quote(parts[0], safe='') if parts else ''
    rows, seen = [], set()
    capped = False
    sf_offset = 0
    sf_json = False
    for page in range(max(1, min(5, max_pages))):
        check_cancelled()
        offset = page*100
        endpoint, body = '', None
        if provider == 'workday':
            if not parts:
                raise ValueError('Workday board URL must include its site name')
            tenant = (u.hostname or '').split('.')[0]
            endpoint = f'{origin}/wday/cxs/{tenant}/{token}/jobs'
            body = {'appliedFacets': {}, 'limit': 20, 'offset': page*20, 'searchText': ''}
        elif provider == 'greenhouse':
            endpoint = f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true'
        elif provider == 'lever':
            region = 'eu.' if '.eu.' in (u.hostname or '') else ''
            endpoint = f'https://api.{region}lever.co/v0/postings/{token}?mode=json'
        elif provider == 'ashby':
            endpoint = f'https://api.ashbyhq.com/posting-api/job-board/{token}'
        elif provider == 'smartrecruiters':
            endpoint = f'https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={offset}'
        elif provider == 'workable':
            endpoint = f'https://apply.workable.com/api/v1/widget/accounts/{token}'
        elif provider == 'recruitee':
            endpoint = origin+'/api/offers/'
        elif provider == 'eightfold':
            from urllib.parse import parse_qs
            domain = parse_qs(u.query).get('domain', [''])[0]
            endpoint = origin+'/api/apply/v2/jobs?'+urlencode({'start': page*10, 'num': 10, 'domain': domain})
        elif provider == 'phenom':
            prefix = '/'.join(parts[:2]) or 'global/en'
            endpoint = origin+'/widgets'
            body = {'lang': 'en_global', 'deviceType': 'desktop', 'country': 'global',
                    'pageName': 'search-results', 'ddoKey': 'refineSearch', 'from': offset,
                    'size': 100, 'jobs': True, 'keywords': '', 'selected_fields': {}, 'global': True}
        elif provider == 'successfactors':
            if sf_json:
                endpoint = origin+'/services/recruiting/v1/jobs'
                body = {'keywords':'','locale':'fr_FR','location':'','pageNumber':page,'sortBy':'recent'}
            else:
                endpoint = origin+'/tile-search-results/?'+urlencode({'q': '', 'startrow': sf_offset})
        elif provider == 'personio':
            endpoint = origin+'/xml'
        elif provider == 'teamtailor':
            endpoint = origin+'/jobs.rss'
        data = read(endpoint, body)
        if isinstance(data, str):
            soup = BeautifulSoup(data, 'xml' if provider in {'personio', 'teamtailor'} else 'lxml')
            if provider in {'personio', 'teamtailor'}:
                items = soup.find_all('position' if provider == 'personio' else 'item')
                batch = []
                for item in items:
                    def tag(name):
                        node = item.find(name)
                        return node.get_text(' ', strip=True) if node else ''
                    batch.append({'title': tag('name') if provider == 'personio' else tag('title'),
                                  'url': origin+'/job/'+tag('id') if provider == 'personio' else tag('link'),
                                  'location': tag('office') or ', '.join(filter(None, [tag('city'), tag('country')])),
                                  'posted': tag('createdAt') or tag('pubDate')})
            elif provider == 'successfactors':
                batch = [{'title': (item.select_one('a.jobTitle-link') or item).get_text(' ', strip=True),
                          'url': urljoin(origin, item['data-url']),
                          'location': (item.select_one('[id*="section-location-value"]') or BeautifulSoup('', 'lxml')).get_text(' ', strip=True)}
                         for item in soup.select('li.job-tile[data-url]')]
                if not batch and page == 0:
                    result = read(origin+'/services/recruiting/v1/jobs', {'keywords': '', 'locale': 'fr_FR', 'location': '', 'pageNumber': 0, 'sortBy': 'recent'})
                    if isinstance(result, dict):
                        sf_json = True
                        batch = [{'title': j.get('unifiedStandardTitle'), 'url': origin+'/job/'+str(j.get('unifiedUrlTitle', ''))+'/'+str(j['id'])+'-fr_FR',
                                  'location': '; '.join(j.get('jobLocationShort') or [])}
                                 for entry in result.get('jobSearchResult', []) if (j := entry.get('response')) and j.get('id')]
            else:
                raise ValueError('ATS returned HTML instead of its public feed')
        elif isinstance(data, (dict, list)):
            if provider == 'workday':
                items = data.get('jobPostings', [])
            elif provider == 'smartrecruiters':
                items = data.get('content', [])
            elif provider == 'eightfold':
                items = data.get('positions', [])
            elif provider == 'phenom':
                items = data.get('refineSearch', {}).get('data', {}).get('jobs', [])
            elif provider == 'successfactors':
                items = [entry['response'] for entry in data.get('jobSearchResult', []) if entry.get('response')]
            else:
                items = data if isinstance(data, list) else data.get('offers' if provider == 'recruitee' else 'jobs', [])
            batch = []
            for j in items:
                if j.get('isListed') is False:
                    continue
                href = j.get('absolute_url') or j.get('hostedUrl') or j.get('jobUrl') or j.get('careers_url') or j.get('url') or j.get('shortlink') or j.get('canonicalPositionUrl')
                if provider == 'workday' and j.get('externalPath'):
                    href = f'{origin}/en-US/{token}'+j['externalPath']
                if provider == 'smartrecruiters' and j.get('id'):
                    href = f'https://jobs.smartrecruiters.com/{token}/'+quote(str(j['id']), safe='')
                if provider == 'eightfold' and not href and j.get('id'):
                    href = origin+'/careers/job/'+quote(str(j['id']), safe='')
                if provider == 'phenom' and not href and j.get('jobId'):
                    href = origin+'/'+prefix+'/job/'+quote(str(j['jobId']), safe='')
                if provider == 'successfactors' and j.get('id'):
                    href = origin+'/job/'+quote(str(j.get('unifiedUrlTitle') or ''), safe='')+'/'+str(j['id'])+'-fr_FR'
                location = j.get('location') or j.get('locationsText') or (j.get('categories') or {}).get('location') or ', '.join(str(j.get(k) or '') for k in ('city', 'country')).strip(', ')
                if isinstance(location, dict):
                    location = location.get('name') or ', '.join(str(location.get(k) or '') for k in ('city', 'country')).strip(', ')
                batch.append({'title': j.get('title') or j.get('text') or j.get('name') or j.get('posting_name') or j.get('unifiedStandardTitle'), 'url': href,
                              'location': str(location), 'body': j.get('descriptionPlain') or j.get('descriptionHtml') or j.get('content') or '',
                              'posted': j.get('publishedAt') or j.get('releasedDate') or j.get('postedOn') or ''})
        else:
            raise ValueError('Invalid ATS response')
        for row in batch:
            href = urljoin(origin, str(row.get('url') or '')) if row.get('url') else ''
            if not href or not row.get('title') or href in seen or urlsplit(href).scheme != 'https':
                continue
            seen.add(href)
            row.update(url=href, company=company, source='public_'+provider, verified=bool(row.get('body')))
            row['body'] = BeautifulSoup(str(row.get('body') or ''), 'lxml').get_text(' ', strip=True)[:16000]
            rows.append(row)
        limit = 20 if provider == 'workday' else 10 if provider == 'eightfold' else 100
        paged = provider in {'workday', 'eightfold', 'phenom', 'successfactors', 'smartrecruiters'}
        sf_offset += len(batch)
        if not paged or not batch or (provider != 'successfactors' and len(batch) < limit):
            break
        capped = page == max(1, min(5, max_pages))-1
    return {'rows': rows, 'capped': capped, 'provider': provider}
