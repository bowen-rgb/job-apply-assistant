"""Evidence from real career pages, separate from QR decoding and submission."""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from urllib.parse import urljoin, urlparse, urlencode
from bs4 import BeautifulSoup
from .extractor import extract_job_document
from .pfe import norm, public_url

PROVIDERS={'workday','successfactors','sap successfactors','greenhouse','lever','smartrecruiters','jobteaser','recruitee','jobs','careers','career opportunities'}


def usable_company(name):
    return bool(name and len(name.strip())>=2 and norm(name.strip()) not in PROVIDERS)


def page_context(html,url):
    soup=BeautifulSoup(html,'lxml')
    document=asdict(extract_job_document(html,url))
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    company=document.get('company','');source='JobPosting.hiringOrganization';quote=company
    if not usable_company(company):
        company='';source='';quote=''
        # Organization (not the recruiting software's WebSite) can identify an employer.
        for script in soup.select('script[type="application/ld+json"]'):
            try:data=json.loads(script.get_text())
            except (ValueError,TypeError):continue
            def walk(value):
                if isinstance(value,dict):
                    yield value
                    for child in value.values():yield from walk(child)
                elif isinstance(value,list):
                    for child in value:yield from walk(child)
            for item in walk(data):
                if item.get('@type') in ('Organization','Corporation') and usable_company(str(item.get('name') or '')):
                    company=str(item['name']);source='Organization.name';quote=company;break
            if company:break
    if not company:
        match=re.search(r'(?:careers?(?: opportunities)?\s+(?:at|in|with)|emplois? chez|recrutement chez|rejoignez|join)\s+(.{2,90}?)(?:\s*[|–—]|$)',title,re.I)
        if match and usable_company(match[1]):company=match[1].strip();source='page_title';quote=title
    if not company:
        for element in soup.select('footer, [class*=copyright], [id*=copyright]'):
            text=element.get_text(' ',strip=True)
            match=re.search(r'(?:©|copyright)\s*(?:\d{4}(?:\s*[-–]\s*\d{4})?\s*)?([\wÀ-ÿ][\wÀ-ÿ &.,-]{1,65}?)(?:\s*[-|·]|all rights|tous droits|$)',text,re.I)
            if match and usable_company(match[1]):company=match[1].strip();source='footer';quote=match[0].strip();break
    if not company:
        for element in soup.select('header img[alt], [class*=logo] img[alt], img[class*=logo][alt]'):
            name=re.sub(r'\blogo\b','',element.get('alt',''),flags=re.I).strip(' -|')
            if usable_company(name) and len(name)<90:company=name;source='logo_alt';quote=element.get('alt');break
    if not company:
        meta=soup.select_one('meta[property="og:site_name"]')
        name=meta.get('content','').strip() if meta else ''
        if usable_company(name):company=name;source='og:site_name';quote=name
    headings=[h.get_text(' ',strip=True) for h in soup.select('h1,h2')]
    structured=bool(document.get('structured_json') and 'JobPosting' in document['structured_json'])
    heading=next((h for h in headings if re.search(r'\bstage\b|\binternship\b|ing[eé]nieur|engineer',h,re.I)), '')
    # A non-JSON-LD vacancy must still expose an actual role and duties.
    duties=[]
    for group in soup.select('[class*=mission], [id*=mission], [class*=responsibil], [id*=responsibil], [class*=jobdescription], [class*=job-description], [itemprop=description]'):
        text=group.get_text(' ',strip=True)
        if len(text)>35:duties.append(text[:2500])
    description=document.get('description','')
    if structured and len(description.strip())>35:duties.insert(0,description[:8000])
    if not duties:
        for header in soup.select('h2,h3,h4,strong'):
            if not re.search(r'mission|responsibil|what you.ll do|vos activit|your role',header.get_text(' ',strip=True),re.I):continue
            chunks=[]
            for sibling in header.next_siblings:
                if getattr(sibling,'name',None) in {'h1','h2','h3','h4'}:break
                if getattr(sibling,'get_text',None):chunks.append(sibling.get_text(' ',strip=True))
                if len(' '.join(chunks))>5000:break
            if len(' '.join(chunks))>35:duties.append(' '.join(chunks)[:5000])
    form=bool(soup.select('input[type=file]'))
    kind='vacancy' if (structured or (heading and duties)) else 'general' if form and re.search(r'spontan|talent pool|talent community|cv bank|déposez.*cv|submit your (?:cv|resume)',document['text'],re.I) else 'entry'
    role_title=document['title'] if structured else heading if kind=='vacancy' else ''
    links=[];seen=set()
    for a in soup.select('a[href]'):
        target=urljoin(url,a['href']);label=a.get_text(' ',strip=True)
        if target in seen or not public_url(target):continue
        seen.add(target)
        if re.search(r'/jobs?/[^/]+',urlparse(target).path,re.I) and len(label)>6:
            links.append({'url':target,'title':label[:300]})
    search=next((urljoin(url,a['href']) for a in soup.select('a[href]') if urlparse(urljoin(url,a['href'])).hostname==urlparse(url).hostname and re.search(r'/(?:search|offres|jobs)/?$',urlparse(urljoin(url,a['href'])).path,re.I)), '')
    return {'company':company,'company_evidence':source,'company_quote':quote,'company_source_url':url,
            'title':role_title or document['title'],'kind':kind,'tasks':list(dict.fromkeys(duties))[:4],
            'role_title':role_title,'body':description or document['text'], 'opportunities':links[:40],
            'search_url':search,'document':document,'page_title':title,'page_text':document['text'][:45000]}


def discover_roles(context,read_page):
    result=list(context['opportunities'])
    search=context.get('search_url')
    if search and len(result)<4:
        try:
            raw,_,final=read_page(search)
            soup=BeautifulSoup(raw,'lxml')
            # Only use a search parameter exposed by the actual site's GET form.
            form=next((f for f in soup.select('form') if f.get('method','get').lower()=='get' and f.select_one('input[name=q],input[name=keywords]')),None)
            if form:
                field=form.select_one('input[name=q],input[name=keywords]')['name']
                action=urljoin(final,form.get('action') or final)
                params={field:'stage'}
                if form.select_one('[name=locationsearch]'):params['locationsearch']='France'
                if urlparse(action).hostname==urlparse(final).hostname:
                    raw,_,final=read_page(action+('&' if '?' in action else '?')+urlencode(params))
            result+=page_context(raw,final)['opportunities']
        except (ValueError,OSError):pass
    unique={r['url']:r for r in result}
    def score(role):
        title=norm(role['title'])
        return (4*bool(re.search(r'stage|internship',title))+2*bool(re.search(r'ingenieur|engineer|data|simulation|robot|digital|mecani|automat',title)))
    return sorted(unique.values(),key=score,reverse=True)[:20]


def readiness(payload):
    missing=[]
    if not usable_company(payload.get('company','')):missing.append('company')
    if payload.get('kind')!='vacancy' or not payload.get('role_title'):missing.append('role')
    if not payload.get('tasks'):missing.append('tasks')
    return {'ready':not missing,'missing':missing,'letter_allowed':not missing}
