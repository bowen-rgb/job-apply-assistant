"""Native ports of Apply-Pilot boards/websearch and ai-job-search portal skills.

MIT attribution and pinned originals: docs/third-party/INTEGRATION.md. Every
adapter returns the existing Hit contract; no additional crawler application.
"""
import json
import re
from urllib.parse import urlencode,urlsplit,urljoin,quote
from urllib.request import Request,build_opener,HTTPRedirectHandler
from bs4 import BeautifulSoup
from . import secret_store
from .worker_runtime import check_cancelled

CATALOG={
 'brave':{'label':'Brave Search','domain':'search.brave.com','keys':['api_key'],'guide':'https://api-dashboard.search.brave.com/'},
 'mojeek':{'label':'Mojeek Search','domain':'mojeek.com','keys':['api_key'],'guide':'https://www.mojeek.com/services/search/web-search-api/'},
 'adzuna':{'label':'Adzuna','domain':'adzuna.fr','keys':['app_id','app_key'],'guide':'https://developer.adzuna.com/'},
 'jooble':{'label':'Jooble','domain':'jooble.org','keys':['api_key'],'guide':'https://jooble.org/api/about'},
 'careerjet':{'label':'Careerjet','domain':'careerjet.fr','keys':['affid'],'guide':'https://www.careerjet.com/partners/api/'},
 'francetravail_api':{'label':'France Travail API','domain':'francetravail.fr','keys':['client_id','client_secret'],'guide':'https://francetravail.io/'},
 'jobtech':{'label':'JobTech Sweden','domain':'jobtechdev.se','keys':[]},
 'euraxess':{'label':'Euraxess','domain':'euraxess.ec.europa.eu','keys':[]},
 'freehire':{'label':'freehire','domain':'freehire.me','keys':[]},
 'jobbank':{'label':'Akademikernes Jobbank','domain':'jobbank.dk','keys':[]},
 'jobdanmark':{'label':'Jobdanmark','domain':'jobdanmark.dk','keys':[]},
 'jobindex':{'label':'Jobindex','domain':'jobindex.dk','keys':[]},
 'jobnet':{'label':'Jobnet','domain':'jobnet.dk','keys':[]},
 'linkedin_guest':{'label':'LinkedIn public jobs','domain':'linkedin.com','keys':[]},
}


def configuration():return secret_store.read().get('extended_sources',{})


def status():
    from .source_selection import enabled
    configs=configuration();out=[]
    for key,meta in CATALOG.items():
        cfg=configs.get(key,{})
        out.append({'id':key,**meta,'enabled':enabled(key,fallback=cfg.get('enabled')),
                    'configured':all(cfg.get(field) for field in meta['keys']),
                    'settings':{field:cfg[field] for field in ('country','location','base_url','query') if cfg.get(field)},
                    'credentials':{field:bool(cfg.get(field)) for field in meta['keys']}})
    return out


def configure(key,payload):
    if key not in CATALOG:raise ValueError('Unknown source')
    clean={}
    for field in [*CATALOG[key]['keys'],'country','location','base_url','query']:
        if field in payload and str(payload[field]).strip():clean[field]=str(payload[field]).strip()[:2000]
    if 'enabled' in payload:
        if type(payload['enabled']) is not bool:raise ValueError('Choose enabled or disabled')
        clean['enabled']=payload['enabled']
    if clean.get('base_url'):
        from .pfe_discovery import validate_destination
        validate_destination(clean['base_url'])
        if urlsplit(clean['base_url']).scheme!='https':raise ValueError('Source base URL must use HTTPS')
    if clean.get('country') and not re.fullmatch('[a-zA-Z]{2}',clean['country']):raise ValueError('Use a two-letter country code')
    secret_store.update(lambda data:data.setdefault('extended_sources',{}).setdefault(key,{}).update(clean))
    if 'enabled' in clean:
        from .source_selection import select
        select(key,clean['enabled'])


def request(url,body=None,headers=None,form=None):
    from .pfe_discovery import validate_destination
    validate_destination(url)
    if urlsplit(url).scheme!='https':raise ValueError('Source requires HTTPS')
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise ValueError('Source redirected; update its endpoint')
    encoded=json.dumps(body).encode() if body is not None else urlencode(form).encode() if form is not None else None
    req=Request(url,data=encoded,headers={'User-Agent':'bowen-rgb/job-apply-assistant/1.0','Accept':'application/json,text/html,*/*',
                **({'Content-Type':'application/json'} if body is not None else {'Content-Type':'application/x-www-form-urlencoded'} if form else {}),**(headers or {})})
    with build_opener(NoRedirect()).open(req,timeout=20) as response:
        raw=response.read(8_000_001)
    if len(raw)>8_000_000:raise ValueError('Source response too large')
    text=raw.decode('utf-8',errors='replace')
    try:return json.loads(text)
    except ValueError:return text


def _html_rows(markup,base,selectors):
    soup=BeautifulSoup(markup,'lxml');rows=[]
    for node in soup.select(selectors):
        a=node if node.name=='a' else node.select_one('a[href]')
        if not a:continue
        title=a.get_text(' ',strip=True)
        if len(title)<4:continue
        company=node.select_one('.company,.company-name,.base-search-card__subtitle,[class*=employer]')
        location=node.select_one('.location,[class*=location]')
        rows.append({'title':title,'company':company.get_text(' ',strip=True) if company else '',
                     'location':location.get_text(' ',strip=True) if location else '',
                     'url':urljoin(base,a.get('href','')),'body':node.get_text(' ',strip=True)[:12000]})
    return rows


def search(key,query,location='',limit=20,*,config=None,read=request,page=1):
    if key not in CATALOG:raise ValueError('Unknown source')
    cfg=config if config is not None else configuration().get(key,{})
    if any(not cfg.get(field) for field in CATALOG[key]['keys']):raise ValueError('Configure source credentials first')
    limit=max(1,min(100,int(limit)));country=cfg.get('country','fr').lower();location=cfg.get('location') or location
    rows=[];q=urlencode
    if key=='brave':
        data=read('https://api.search.brave.com/res/v1/web/search?'+q({'q':query,'count':min(limit,20),'country':country,'search_lang':'fr'}),headers={'X-Subscription-Token':cfg['api_key']})
        rows=[{'title':r['title'],'url':r['url'],'body':r.get('description','')} for r in data.get('web',{}).get('results',[])]
    elif key=='mojeek':
        data=read('https://api.mojeek.com/search?'+q({'q':query,'api_key':cfg['api_key'],'fmt':'json','t':min(limit,40)}))
        rows=[{'title':r['title'],'url':r['url'],'body':r.get('desc','')} for r in data.get('response',{}).get('results',[])]
    elif key=='adzuna':
        data=read(f'https://api.adzuna.com/v1/api/jobs/{country}/search/{page}?'+q({'app_id':cfg['app_id'],'app_key':cfg['app_key'],'what':query,'where':location,'results_per_page':min(limit,50)}))
        rows=[{'title':r['title'],'url':r['redirect_url'],'company':r.get('company',{}).get('display_name',''),'location':r.get('location',{}).get('display_name',''),'body':r.get('description',''),'date_posted':r.get('created','')} for r in data.get('results',[])]
    elif key=='jooble':
        data=read('https://jooble.org/api/'+quote(cfg['api_key'],safe=''),body={'keywords':query,'location':location,'page':str(page)})
        rows=[{'title':r['title'],'url':r['link'],'company':r.get('company',''),'location':r.get('location',''),'body':r.get('snippet','')} for r in data.get('jobs',[])]
    elif key=='careerjet':
        data=read('https://public.api.careerjet.net/search?'+q({'locale_code':{'fr':'fr_FR','gb':'en_GB','us':'en_US','de':'de_DE','dk':'da_DK','se':'sv_SE','be':'fr_BE','ca':'en_CA'}.get(country,'en_'+country.upper()),'keywords':query,'location':location,'affid':cfg['affid'],'pagesize':min(limit,50),'page':page,'user_ip':'127.0.0.1','user_agent':'JobApplyAssistant'}))
        rows=[{'title':r['title'],'url':r['url'],'company':r.get('company',''),'location':r.get('locations',''),'body':r.get('description','')} for r in data.get('jobs',[])]
    elif key=='francetravail_api':
        token=read('https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire',form={'grant_type':'client_credentials','client_id':cfg['client_id'],'client_secret':cfg['client_secret'],'scope':'api_offresdemploiv2 o2dsoffre'})
        data=read('https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search?'+q({'motsCles':query,'range':f'{(page-1)*limit}-{page*limit-1}'}),headers={'Authorization':'Bearer '+token['access_token']})
        rows=[{'title':r['intitule'],'url':r.get('origineOffre',{}).get('urlOrigine') or 'https://candidat.francetravail.fr/offres/recherche/detail/'+r['id'],'company':r.get('entreprise',{}).get('nom',''),'location':r.get('lieuTravail',{}).get('libelle',''),'body':r.get('description',''),'date_posted':r.get('dateCreation','')} for r in (data or {}).get('resultats',[])]
    elif key=='jobtech':
        data=read('https://jobsearch.api.jobtechdev.se/search?'+q({'q':query,'limit':limit,'offset':(page-1)*limit}))
        rows=[{'title':r['headline'],'url':r.get('webpage_url') or 'https://arbetsformedlingen.se/platsbanken/annonser/'+str(r['id']),'company':r.get('employer',{}).get('name',''),'location':r.get('workplace_address',{}).get('municipality',''),'body':r.get('description',{}).get('text','')} for r in data.get('hits',[])]
    elif key=='freehire':
        base=cfg.get('base_url','https://freehire.me').rstrip('/')
        data=read(base+'/api/v1/agent/jobs/search?'+q({'q':query,'limit':limit,'offset':(page-1)*limit,'description_format':'plain'}))
        for r in data.get('data',[]):
            company=r.get('company') or {};company=company.get('name','') if isinstance(company,dict) else str(company)
            rows.append({'title':r.get('title') or r.get('name'),'url':r.get('apply_url') or r.get('url') or r.get('source_url'),
                         'company':company,'location':str(r.get('location') or ''),'body':r.get('description') or '', 'date_posted':r.get('posted_at','')})
    elif key=='linkedin_guest':
        base='https://www.linkedin.com'
        markup=read(base+'/jobs-guest/jobs/api/seeMoreJobPostings/search?'+q({'keywords':query,'location':location,'start':(page-1)*25}))
        rows=_html_rows(markup,base,'li,.base-card')
    elif key=='euraxess':
        base='https://euraxess.ec.europa.eu'
        markup=read(base+'/jobs/search?'+q({'keywords':query,'page':page-1}))
        rows=_html_rows(markup,base,'article,.views-row,a[href*="/jobs/"]')
        rows=[r for r in rows if re.search(r'/jobs/\d+',r['url'])]
    elif key=='jobbank':
        markup=read('https://jobbank.dk/job/rss?'+q({'key':query,'page':page}))
        soup=BeautifulSoup(markup,'xml')
        rows=[{'title':r.title.get_text() if r.title else '', 'url':r.link.get_text() if r.link else '',
               'body':r.description.get_text() if r.description else ''} for r in soup.find_all('item')]
    elif key=='jobindex':
        base='https://'+CATALOG[key]['domain']
        markup=read(base+('/job/' if key=='jobbank' else '/jobsoegning')+'?'+q({'q':query,'page':page}))
        rows=_html_rows(markup,base,'.job,.jobsearch-result,.PaidJob,.jobResult,a[href*="/jobannonce/"],a[href*="/vis-job/"]')
    elif key=='jobdanmark':
        data=read(f'https://jobdanmark.dk/api/jobsearch/search/{page}',body={'filters':[{'type':'freetext','value':query,'displayText':query}],'jobTypes':[],'locationMode':'Text','distance':50})
        rows=[{'title':r['title'],'url':urljoin('https://jobdanmark.dk',r['url']),'company':r.get('companyName',''),'location':r.get('companyAddress','')} for r in data.get('items',[])]
    elif key=='jobnet':
        data=read('https://jobnet.dk/bff/FindJob/Search?'+q({'searchString':query,'pageNumber':page,'orderType':'BestMatch'}))
        rows=[{'title':r.get('title') or r.get('headline'),'url':'https://jobnet.dk/soeg-job/soegning?jobid='+str(r.get('id') or r.get('jobAdId')),'company':r.get('hiringOrgName',''),'location':r.get('municipality') or r.get('postalDistrictName') or ''} for r in data.get('jobAds',[])]
    from .vendor.job_search.posting_guard import guard
    result=[];seen=set()
    for r in rows:
        if not r.get('url') or not r.get('title') or urlsplit(r['url']).scheme not in {'http','https'} or r['url'] in seen:continue
        seen.add(r['url']);body,_=guard(str(r.get('body') or ''),'html')
        result.append({'url':r['url'],'title':BeautifulSoup(str(r['title']),'lxml').get_text(' ',strip=True),
                       'company':r.get('company',''),'location':r.get('location',''),'body':body,
                       'date_posted':r.get('date_posted',''),'source':key})
    return result[:limit]


def discover(profile,report=None):
    from .searcher import Hit
    from .discovery_diagnostics import emit
    configs=configuration()
    from .source_selection import enabled
    queries=profile.get('preferred_roles') or ['internship']
    location=' '.join(profile.get('locations',[])[:2])
    for key,meta in CATALOG.items():
        cfg=configs.get(key,{})
        if profile.get('capability_source_filter') and key not in profile['capability_source_filter']:continue
        if not enabled(key,profile,cfg.get('enabled')):continue
        if any(not cfg.get(field) for field in meta['keys']):
            emit(report,key,'native-api','unavailable',error='Configure credentials in the integration settings');continue
        seen=set()
        for query in [cfg['query']] if cfg.get('query') else queries[:4]:
            check_cancelled()
            try:
                rows=search(key,query,location,config=cfg)
                emit(report,key,'native-api','success' if rows else 'empty',results=len(rows),query=query)
                for row in rows:
                    if row['url'] in seen:continue
                    seen.add(row['url'])
                    yield Hit(row['url'],row['title'],row['body'][:1200],meta['domain'],key,query,
                              {**row,'fetch_mode':'native-'+key})
            except Exception as exc:
                emit(report,key,'native-api','failed',error=f'Source request failed ({getattr(exc,"code",type(exc).__name__)})')
