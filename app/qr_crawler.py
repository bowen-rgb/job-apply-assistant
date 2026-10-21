"""Resumable employer discovery: public ATS APIs, HTML lists, pagination, details.
Pattern references: Crawlee request queues and interninbox's API-first discovery.
All reads pass the project's public-network checks. No application form actions.
"""
from collections import deque
from datetime import datetime, timezone
from dataclasses import asdict
from urllib.parse import urlsplit,urlunsplit,urljoin,parse_qsl,urlencode,quote
import json,re,time
from bs4 import BeautifulSoup
from .pfe import norm,public_url
from .extractor import extract_job_document
from .qr_context import page_context
from .worker_runtime import check_cancelled,Cancelled

ATS_HOSTS=('greenhouse.io','lever.co','ashbyhq.com','smartrecruiters.com')
JOB_PATH=re.compile(r'/(?:jobs?|offres?|vacanc(?:y|ies)|positions?|requisition|offre-de-emploi|jobdetail|job-detail)(?:/|[?_-])|/cwr/|/rc-\w+',re.I)
JOB_TEXT=re.compile(r'\b(?:intern(?:ship)?|stage|engineer|ingenieur|technicien|manager|researcher|scientist|developer|assistant|analyst|chercheur|concepteur)\b',re.I)
DIRECTIONS={'mechanical':r'mecani|mechanic|conception|catia|solidworks|结构|机械','simulation':r'simulat|finite element|elements finis|numerique|numerical|仿真','control':r'robot|automat|commande|control|pid|mpc|机器人|控制','digital':r'digital twin|jumeau|software|logiciel|data|python|numerique|数字','research':r'research|recherche|laborato|phd|doctor|科研'}

def canonical(url):
    p=urlsplit(url)
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in {'gclid','fbclid'}]
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or '/',urlencode(query),p.fragment if re.search('job|position|requisition',p.fragment,re.I) else ''))

def same_host(url,base):return urlsplit(url).hostname==urlsplit(base).hostname

def ats_host(url):
    host=urlsplit(url).hostname or ''
    return any(host==end or host.endswith('.'+end) for end in ATS_HOSTS)

def directions(text):return [key for key,pattern in DIRECTIONS.items() if re.search(pattern,norm(text))]

def api_for(url):
    p=urlsplit(url);parts=[x for x in p.path.split('/') if x];host=p.hostname or ''
    if not parts or not re.fullmatch(r'[\w.-]{1,100}',parts[0]):return None
    token=quote(parts[0],safe='')
    if host in {'boards.greenhouse.io','job-boards.greenhouse.io','boards.eu.greenhouse.io'}:return ('greenhouse',f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true')
    if host in {'jobs.lever.co','jobs.eu.lever.co'}:return ('lever',f'https://api.lever.co/v0/postings/{token}?mode=json')
    if host=='jobs.ashbyhq.com':return ('ashby',f'https://api.ashbyhq.com/posting-api/job-board/{token}')
    if host in {'jobs.smartrecruiters.com','careers.smartrecruiters.com'}:return ('smartrecruiters',f'https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset=0')

def api_rows(kind,data):
    rows=data if isinstance(data,list) else data.get('content' if kind=='smartrecruiters' else 'jobs',[])
    for row in rows:
        if not isinstance(row,dict) or row.get('isListed') is False:continue
        loc=row.get('location') or (row.get('categories') or {}).get('location','')
        if isinstance(loc,dict):loc=loc.get('name') or ', '.join(str(loc.get(k) or '') for k in ('city','region','country')).strip(', ')
        url=row.get('absolute_url') or row.get('hostedUrl') or row.get('jobUrl') or row.get('postingUrl')
        if kind=='smartrecruiters' and not url:
            company=row.get('company',{}).get('identifier','');identifier=row.get('id')
            if company and identifier:url=f'https://jobs.smartrecruiters.com/{quote(str(company),safe="")}/{quote(str(identifier),safe="")}'
        if not url:continue
        body=BeautifulSoup(str(row.get('content') or row.get('descriptionPlain') or row.get('descriptionHtml') or ''),'lxml').get_text(' ',strip=True)
        yield {'url':url,'title':row.get('title') or row.get('text') or row.get('name') or '', 'location':str(loc),'body':body[:14000], 'start_date':str(row.get('jobStartDate') or '')[:10], 'company':(row.get('company') or {}).get('name','') if isinstance(row.get('company'),dict) else '', 'source':'public_'+kind,'verified':bool(body)}

def links_from(html,url):
    soup=BeautifulSoup(html,'lxml');roles={};pages={}
    for a in soup.select('a[href]'):
        target=urljoin(url,a['href']);label=a.get_text(' ',strip=True)
        if not public_url(target) or re.search(r'\.(pdf|png|jpg|zip|gif|css|js)(?:[?#]|$)',target,re.I):continue
        label_norm=norm(label);path=urlsplit(target).path
        if re.search(r'login|sign.?in|logout|privacy|cookie|apply|candidater|postuler|/application',path,re.I):continue
        if (JOB_PATH.search(path) or JOB_TEXT.search(label_norm)) and len(label)>7 and not re.search(r'\(\d+\)\s*$',label):
            if norm(label) not in {'see the opening','voir offre','view job','learn more'}:
                roles[canonical(target)]={'url':target,'title':label[:400],'source_url':url,'verified':False}
        rel=a.get('rel') or []
        if ('next' in rel or re.search(r'^(next|suivant|weiter|suivante|next page|[›»→])$',label_norm) or 'pager' in ' '.join(a.get('class') or [])
            or re.search(r'[?&](page|offset|startrow)=\d+',target,re.I) or re.search(r'/(search|careers|carriere|recrutement|offres|jobs)/?$',path,re.I) or ats_host(target)):
            pages[canonical(target)]={'url':target,'title':label[:300],'pagination':('next' in rel or bool(re.search(r'[?&](page|offset|startrow)=\d+',target,re.I)) or bool(re.search(r'^(next|suivant|weiter|suivante|next page|[›»→])$',label_norm)))}
    # JobPosting lists expose absolute URLs even if links are rendered by JavaScript.
    def walk(value):
        if isinstance(value,dict):
            yield value
            for child in value.values():yield from walk(child)
        elif isinstance(value,list):
            for child in value:yield from walk(child)
    for script in soup.select('script[type="application/ld+json"]'):
        try:items=walk(json.loads(script.get_text()))
        except (ValueError,TypeError):continue
        for item in items:
            if 'JobPosting' not in str(item.get('@type')):continue
            target=urljoin(url,str(item.get('url') or ''))
            if target!=url and public_url(target):roles[canonical(target)]={'url':target,'title':str(item.get('title') or '')[:400],'source_url':url,'verified':False}
    for frame in soup.select('iframe[src]'):
        target=urljoin(url,frame['src'])
        if ats_host(target):pages[canonical(target)]={'url':target,'title':'Embedded careers'}
    return list(roles.values()),list(pages.values())

def crawl(payload,reader,rendered=None,semantic=None,persist=lambda p:None,*,page_budget=30,seconds=120):
    root=payload.get('portal_url') or payload['final_url'];old=payload.get('crawl') or {};seen=set(old.get('seen',[]));queue=deque(old.get('frontier') or [])
    if not queue:
        queue.extend({'url':x['url'],'depth':0} for x in old.get('errors',[]) if x.get('url'))
        if not queue and not old.get('finished'):queue.append({'url':root,'depth':0})
    roles={canonical(x['url']):dict(x) for x in payload.get('opportunities',[]) if x.get('url')}
    errors=list(old.get('errors',[]));total=int(old.get('pages_read',0));started=time.monotonic();count=0;browser_reads=0;capped=bool(old.get('capped'))
    allowed_hosts={urlsplit(root).hostname,urlsplit(payload['url']).hostname};api_seen=set(old.get('api_seen',[]));ai_attempted=False
    def save(status):
        payload['opportunities']=list(roles.values())
        payload['crawl']={'status':status,'pages_read':total,'discovered':len(roles),'remaining':len(queue),'frontier':list(queue),'seen':list(seen),'api_seen':list(api_seen),'errors':errors[-50:],'finished':status=='complete','updated_at':datetime.now(timezone.utc).isoformat(),'page_budget':page_budget,'capped':capped}
        persist(payload)
    def add(row):
        nonlocal capped
        if not row.get('url') or not public_url(row['url']) or not row.get('title'):return
        key=canonical(row['url']);previous=roles.get(key,{})
        if len(roles)>=1500 and key not in roles:capped=True;return
        merged={**previous,**row};merged['directions']=directions(merged.get('title','')+' '+merged.get('body',''))
        merged['body']=str(merged.get('body') or '')[:1200]
        roles[key]=merged
    def enqueue(url,depth,kind='page',front=False):
        nonlocal capped
        if depth>5:capped=True;return
        if not public_url(url):return
        if kind=='page' and urlsplit(url).hostname not in allowed_hosts and not ats_host(url):return
        url=canonical(url);key=url
        if key in seen or any(canonical(x['url'])==key for x in queue):return
        if len(queue)>=2000:capped=True;return
        item={'url':url,'depth':depth,'kind':kind}
        queue.appendleft(item) if front else queue.append(item)
    root_api=api_for(root)
    if root_api and root_api[1] not in api_seen:
        api_seen.add(root_api[1]);enqueue(root_api[1],0,root_api[0],True)
    save('running')
    try:
        while queue and count<page_budget and time.monotonic()-started<seconds:
            check_cancelled();item=queue.popleft();url=item['url'];key=canonical(url)
            if key in seen:continue
            count+=1
            try:
                rendered_here=False
                try:raw,ctype,final=reader(url)
                except OSError:
                    if not rendered or browser_reads>=3:raise
                    browser_reads+=1;raw,ctype,final=rendered(url);rendered_here=True
                errors[:]=[e for e in errors if canonical(e.get('url',''))!=key]
                total+=1
                kind=item.get('kind','page')
                if kind!='page':
                    data=json.loads(raw)
                    for row in api_rows(kind,data):
                        row['source_url']=final;add(row);enqueue(row['url'],1)
                    if kind=='smartrecruiters':
                        params=dict(parse_qsl(urlsplit(url).query));offset=int(params.get('offset',0))+100
                        if offset<int(data.get('totalFound',0)):
                            params['offset']=offset;p=urlsplit(url);enqueue(urlunsplit((p.scheme,p.netloc,p.path,urlencode(params),'')),item.get('depth',0),kind,True)
                    seen.add(key);save('running');continue
                html=raw.decode('utf-8','replace') if isinstance(raw,bytes) else raw
                ctx=page_context(html,final);found,pages=links_from(html,final)
                if rendered and not rendered_here and not found and ctx['kind']=='entry' and browser_reads<3:
                    browser_reads+=1
                    try:
                        raw,_,final=rendered(url);html=raw.decode('utf-8','replace') if isinstance(raw,bytes) else raw
                        ctx=page_context(html,final);found,pages=links_from(html,final)
                    except Exception as exc:errors.append({'url':url,'error':'Chrome: '+str(exc)[:250]})
                if same_host(url,root) and ctx.get('company') and not payload.get('company'):
                    for field in ('company','company_quote','company_evidence','company_source_url'):payload[field]=ctx[field]
                if semantic and not ai_attempted and (not payload.get('company') or (not found and not roles)) and item.get('depth',0)==0:
                    ai_attempted=True
                    packet={**payload,'body':ctx['body'][:30000],'page_title':ctx['page_title'],'observed_links':ctx['observed_links'],'kind':'entry'}
                    try:
                        packet=semantic(packet)
                        for field in ('company','company_quote','company_evidence','company_source_url','ai_explanation','ai_explanation_verified'):
                            if packet.get(field):payload[field]=packet[field]
                        for row in packet.get('opportunities',[]):
                            if row.get('url') in {x['url'] for x in ctx['observed_links']} or row.get('source')=='chatgpt_suggestion':found.append(row)
                    except Exception as exc:payload['ai_error']=str(exc)[:400]
                document=ctx['document']
                if ctx['kind']=='vacancy' and len(found)<2:
                    add({k:document.get(k,'') for k in ('title','company','location','employment_type','start_date','end_date','valid_through') }|{'url':final,'body':ctx['body'][:14000],'source_url':final,'verified':True})
                for row in found:
                    if urlsplit(row['url']).hostname in allowed_hosts or ats_host(row['url']):add(row);enqueue(row['url'],item.get('depth',0)+1)
                for row in reversed(pages):enqueue(row['url'],item.get('depth',0)+(0 if row.get('pagination') else 1),front=True)
                for candidate in [final]+[x['url'] for x in pages]+[x['url'] for x in found]:
                    api=api_for(candidate)
                    if api and api[1] not in api_seen:
                        api_seen.add(api[1]);enqueue(api[1],0,api[0],True)
                soup=BeautifulSoup(html,'lxml')
                if any(re.search(r'^(next|suivant|suivante|load more|voir plus|afficher plus)$',norm(b.get_text(' ',strip=True))) and not b.has_attr('disabled') and b.get('aria-disabled')!='true' for b in soup.select('button')):
                    errors.append({'url':url,'error':'JavaScript pagination detected; additional results may remain.'})
                seen.add(key);save('running')
            except Cancelled:
                queue.appendleft(item);raise
            except Exception as exc:
                errors.append({'url':url,'error':str(exc)[:400]})
                if semantic and not ai_attempted and item.get('depth',0)==0:
                    ai_attempted=True
                    try:
                        answer=semantic({**payload,'kind':'entry'})
                        payload['ai_explanation']=answer.get('ai_explanation','')
                        payload['ai_explanation_verified']=False
                        for suggested in answer.get('opportunities',[]):
                            if suggested.get('source')=='chatgpt_suggestion':
                                add(suggested);enqueue(suggested['url'],1)
                    except Exception as ai_exc:payload['ai_error']=str(ai_exc)[:400]
                save('running')
        save('partial' if queue or errors or capped else 'complete' if roles else 'empty')
    except Cancelled:save('paused')
    return payload
