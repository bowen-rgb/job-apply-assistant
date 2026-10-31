"""Logged-in jobs/posts discovery ported from Apply-Pilot scan/linkedin.mjs.

Uses the existing dedicated Chrome session; never reloads a user's tab.
"""
from urllib.parse import urlencode,urlsplit
from .browser_control import require_connection,local_endpoint
from .profile_store import runtime_profile
from .worker_runtime import check_cancelled

GEO={'FR':'105015875','DE':'101282230','BE':'100565514','CH':'106693272','DK':'104514075','SE':'105117694','UK':'101165590','US':'103644278'}
EXTRACT=r'''(kind) => {
  const column=document.querySelector('[data-testid="lazy-column"]');
  const nodes=column?[...column.children]:[...document.querySelectorAll(kind==='jobs'?'.jobs-search-results__list-item,.job-card-container,.base-card':'.feed-shared-update-v2')];
  return nodes.filter(el=>(el.innerText||'').trim().length>40).slice(0,40).map(el=>{
    const text=(el.innerText||'').replace(/\s+/g,' ').trim();
    const links=[...new Set([...el.querySelectorAll('a[href]')].map(a=>a.href.split('?')[0]))].slice(0,20);
    const tagged=el.getAttribute('componentkey')?.startsWith('job-card-component-ref-')?el:el.querySelector('[componentkey^="job-card-component-ref-"]');
    const jobId=tagged?tagged.getAttribute('componentkey').replace('job-card-component-ref-',''):el.getAttribute('data-job-id')||el.querySelector('[data-job-id]')?.getAttribute('data-job-id');
    const title=el.querySelector('.job-card-list__title,.job-card-list__title--link,.base-search-card__title,h3')?.innerText?.trim()||'';
    const company=el.querySelector('.job-card-container__primary-description,.artdeco-entity-lockup__subtitle,.base-search-card__subtitle')?.innerText?.trim()||'';
    return {kind,job_id:jobId||null,url:jobId?`https://www.linkedin.com/jobs/view/${jobId}/`:links.find(u=>u.includes('/feed/update/')||u.includes('/posts/'))||'',title,company,body:text.slice(0,12000),links};
  });
}'''


def login():
    from playwright.sync_api import sync_playwright
    profile=runtime_profile();require_connection(profile)
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp(local_endpoint(profile))
        if not browser.contexts:raise ValueError('Open the platform Chrome first')
        context=browser.contexts[0]
        page=next((tab for tab in context.pages if not tab.is_closed() and urlsplit(tab.url).hostname in {'www.linkedin.com','linkedin.com'}),None)
        if page is None:
            page=context.new_page();page.goto('https://www.linkedin.com/login',wait_until='domcontentloaded',timeout=45000)
        page.bring_to_front()
        return {'url':page.url,'message':'Sign in in this existing tab. It will not be refreshed.'}


def scan(queries,location='Île-de-France, France',country='FR',only='all',days=14):
    from playwright.sync_api import sync_playwright
    profile=runtime_profile();require_connection(profile)
    queries=queries or (profile.get('preferred_roles') or ['stage ingénieur'])[:3]
    if not isinstance(queries,list) or len(queries)>3 or any(not isinstance(q,str) or len(q)>300 for q in queries):raise ValueError('Use up to three search queries')
    if only not in {'all','jobs','posts'}:raise ValueError('Choose jobs, posts or all')
    result={'rows':[],'queries':queries,'requires_login':False,'errors':[]};seen=set()
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp(local_endpoint(profile))
        if not browser.contexts:raise ValueError('Open the platform Chrome first')
        context=browser.contexts[0];page=context.new_page();preserve=False
        try:
            for query in queries:
                for kind in (['jobs','posts'] if only=='all' else [only]):
                    check_cancelled();params={'keywords':query}
                    if kind=='jobs':
                        params.update(location=location,geoId=GEO.get(country.upper(),country),f_TPR='r'+str(max(1,min(90,int(days)))*86400))
                        url='https://www.linkedin.com/jobs/search-results/?'+urlencode(params)
                    else:
                        params.update(datePosted='"past-week"',sortBy='"date_posted"');url='https://www.linkedin.com/search/results/content/?'+urlencode(params)
                    page.goto(url,wait_until='domcontentloaded',timeout=45000)
                    if any(part in page.url for part in ('/login','/authwall','/checkpoint','/uas/')):
                        preserve=True;page.bring_to_front();result.update(requires_login=True,login_url=page.url);return result
                    for _ in range(2):
                        check_cancelled();page.wait_for_timeout(1200);page.mouse.wheel(0,1200)
                    rows=page.evaluate(EXTRACT,kind)
                    if not rows:result['errors'].append(kind+': no readable cards; sign-in, layout or search results may need checking')
                    for row in rows:
                        key=row.get('url') or row.get('body','')
                        if key and key not in seen:seen.add(key);result['rows'].append({**row,'query':query})
        finally:
            if not preserve and not page.is_closed():page.close()
    return result


def triage(task_id,backend,workspace):
    from . import capability_store as store
    from .career_intelligence import model
    source=store.task(task_id)
    if source['kind']!='linkedin_scan' or source['state']!='ready':raise ValueError('Run a LinkedIn search first')
    rows=source['result'].get('rows',[])
    result=model('Triage observed LinkedIn jobs/posts. Return {"opportunities":[{"source_index":0,"company":"exact observed name","title":"exact observed role","url":"one observed URL","evidence_quote":"exact observed quote","reason":"..."}],"questions":[]}. A post is not a confirmed vacancy. Never invent employer, role or URL.',
                 {'candidate':runtime_profile(),'rows':rows},backend,workspace,'linkedin-triage')
    for row in result.get('opportunities',[]):
        index=row.get('source_index')
        if type(index) is not int or not 0<=index<len(rows):raise ValueError('Unknown LinkedIn source')
        source=rows[index];body=' '.join(source.get('body','').split())
        if row.get('url') not in [source.get('url'),*source.get('links',[])]:raise ValueError('Unobserved application link')
        if any(not row.get(key) or ' '.join(row[key].split()) not in body for key in ('company','title','evidence_quote')):raise ValueError('Employer/role needs manual identification from the original post')
        if urlsplit(row['url']).scheme!='https':raise ValueError('Use an observed HTTPS application URL')
        row['body']=source['body'];row['source_kind']=source['kind']
    return result


def accept(identifier,indexes):
    from . import capability_store as store
    from .tracker_exchange import import_rows,preview
    from .db import connect
    task=store.task(identifier)
    if task['kind']!='linkedin_triage' or task['state']!='ready':raise ValueError('Triage the search results first')
    rows=task['result'].get('opportunities',[])
    if any(not 0<=i<len(rows) for i in indexes):raise ValueError('Invalid selection')
    chosen=[rows[i] for i in sorted(set(indexes))];before=preview(chosen);result=import_rows(chosen)
    with connect() as c:
        for row,item in zip(chosen,before):
            if not item['duplicate'] and not item['errors']:
                c.execute("UPDATE jobs SET body=?,source='LinkedIn discovery',provider_key='linkedin_discovery',reason=? WHERE url=? AND source='Imported ledger'",
                          (row['body'],'Unverified opportunity from '+row.get('source_kind','post')+'; verify the original vacancy before applying',row['url']))
    return result
