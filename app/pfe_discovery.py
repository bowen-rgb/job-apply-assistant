"""Public PFE channels, bounded PDF reading and optional self-hosted search."""
from __future__ import annotations
import html
import io
import json
import re
import socket
import ipaddress
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from .pfe import public_url,norm,settings,save_lead,remember_source,board_from_url
from .discovery_diagnostics import emit

SEEDS=[('ABG','https://www.abg.asso.fr/fr/candidatOffres'),('Inria','https://jobs.inria.fr/public/classic/fr/offres'),('CEA','https://www.emploi.cea.fr/offre-de-emploi/liste-offres.aspx'),('GDR-IHM','https://gdr-ihm.fr/category/emploi/stage/')]

def searx_endpoint(url):
 p=urllib.parse.urlparse(url or '')
 if p.username or p.password or p.query or p.fragment:raise ValueError('Search endpoint must not contain credentials or query parameters')
 local=p.hostname in {'127.0.0.1','localhost','::1'}
 if not ((local and p.scheme in {'http','https'}) or (public_url(url) and p.scheme=='https')):raise ValueError('Use HTTPS or an explicitly configured local SearXNG instance')
 return url.rstrip('/')+'/search'

def searx_search(endpoint,query,limit,provider_key):
 from .searcher import Hit
 url=searx_endpoint(endpoint)+'?'+urllib.parse.urlencode(dict(q=query,format='json',language='fr'))
 req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'JobApplyAssistant/8.4'})
 with urllib.request.urlopen(req,timeout=15) as response:data=json.load(response)
 return [Hit(r['url'],str(r.get('title',''))[:500],str(r.get('content',''))[:3000],urllib.parse.urlparse(r['url']).hostname,provider_key,query) for r in data.get('results',[]) if public_url(r.get('url'))][:limit]

class CheckedRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  validate_destination(newurl)
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def validate_destination(url):
 if not public_url(url):raise ValueError('Only public job URLs are supported')
 host=urllib.parse.urlparse(url).hostname
 addresses=socket.getaddrinfo(host,None)
 if any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('A job URL must not resolve to a private network')

def read_public(url):
 validate_destination(url)
 req=urllib.request.Request(url,headers={'User-Agent':'JobApplyAssistant/8.4 (public job discovery)','Accept':'text/html,application/pdf'})
 opener=urllib.request.build_opener(CheckedRedirect())
 with opener.open(req,timeout=20) as response:
  data=response.read(8*1024*1024+1)
  if len(data)>8*1024*1024:raise ValueError('Document exceeds 8 MB')
  return data,response.headers.get('Content-Type',''),response.geturl()

def fetch_document(url,title):
 data,ctype,final=read_public(url)
 if data.startswith(b'%PDF'):
  from pypdf import PdfReader
  pdf=PdfReader(io.BytesIO(data));text='\n'.join(page.extract_text() or '' for page in pdf.pages[:20])[:200000]
  if not text.strip():raise ValueError('PDF has no readable text; manual verification required')
  return '<html><head><title>'+html.escape(title)+'</title></head><body><main><h1>'+html.escape(title)+'</h1><pre>'+html.escape(text)+'</pre></main></body></html>','pdf'
 text=BeautifulSoup(data,'lxml').decode()
 from .searcher import _looks_blocked
 if _looks_blocked(text):raise ValueError('Original page blocked or incomplete; manual verification required')
 return text,'static'

def pdf_html(url,title):
 text,mode=fetch_document(url,title)
 if mode!='pdf':raise ValueError('The source is not a PDF document')
 return text,mode


def research_hits(profile,report=None):
 from .searcher import Hit
 if not settings(profile)['research_sources']:return
 for name,url in SEEDS:
  emit(report,'pfe_research','research:'+name,'running',query=url)
  try:
   text,mode=fetch_document(url,name)
   seen=set();count=0
   for link in BeautifulSoup(text,'lxml').select('a[href]'):
    href=urllib.parse.urljoin(url,link['href']);label=link.get_text(' ',strip=True);key=href.split('#')[0]
    if key in seen or not public_url(href):continue
    if not re.search(r'stage|internship|stagiaire',norm(label+' '+href)):continue
    if urllib.parse.urlparse(href).path.rstrip('/') in {'','/fr/candidatOffres','/public/classic/fr/offres'}:continue
    seen.add(key);count+=1
    yield Hit(href,label or name+' stage','',urllib.parse.urlparse(href).hostname,'pfe_research','research:'+name)
    if count>=min(12,int(profile.get('max_results_per_query',10))):break
   emit(report,'pfe_research','research:'+name,'success' if count else 'empty',results=count)
  except Exception as exc:emit(report,'pfe_research','research:'+name,'failed',error=str(exc))

def process_page(hit,payload,raw_html,verified):
 """Keep research leads and restricted campus entries out of application jobs."""
 # Unknown eligibility/date is preserved in vacancies; unknown vacancy existence is a separate lead.
 if hit.provider_key=='pfe_team':
  text=payload.get('text') or hit.snippet
  save_lead('team',payload.get('title') or hit.title,hit.url,text)
  return 'lead'
 text=norm((payload.get('title') or '')+' '+(payload.get('text') or ''))
 is_structured='JobPosting' in (payload.get('structured_json') or '')
 soup=BeautifulSoup(raw_html or '','lxml')
 title_intern=bool(re.search(r'\bstage\b|stagiaire|\bintern(?:ship)?\b',norm(payload.get('title') or hit.title)))
 has_apply=bool(re.search(r'postuler|candidatur|apply|encadrant|supervisor|@[\w.-]+',text))
 is_pdf=urllib.parse.urlparse(hit.url).path.lower().endswith('.pdf')
 prefetched=hit.prefetched or {}
 single=is_structured or (title_intern and has_apply and (verified or is_pdf)) or (title_intern and len(str(prefetched.get('body') or ''))>200 and bool(prefetched.get('company'))) or bool(prefetched.get('user_supplied_text'))
 if not single:
  if hit.provider_key=='pfe_student':save_lead('student',hit.title,hit.url,hit.snippet)
  elif any(x in text for x in ['laboratoire','research team','equipe de recherche']):save_lead('team',payload.get('title') or hit.title,hit.url,payload.get('text') or hit.snippet)
  return 'lead' if hit.provider_key=='pfe_student' or any(x in text for x in ['laboratoire','research team','equipe de recherche']) else 'ignored'
 if verified:
  # A bounded link pass learns reusable ATS boards without registering every unrelated link.
  for link in soup.select('a[href]')[:200]:
   url=urllib.parse.urljoin(hit.url,link['href'])
   if board_from_url(url):remember_source(url)
 return 'vacancy'

def verify(job,profile):
 from .extractor import extract_job_document
 from .pfe import record_evidence,init_tables
 from .scoring import evaluate
 from .db import connect
 from .application_safety import has_dispatch
 if has_dispatch(job['id']) or job.get('application_status') in {'opening','preparing','preparing_letter'}:raise ValueError('Finish the current application before refreshing this offer')
 init_tables()
 try:
  data,ctype,url=read_public(job['url'])
  if data.startswith(b'%PDF'):
   from pypdf import PdfReader
   text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(data)).pages[:20]);raw='<h1>'+html.escape(job['title'])+'</h1><main>'+html.escape(text)+'</main>'
  else:raw=data.decode('utf-8',errors='replace')
  from .searcher import _looks_blocked
  if _looks_blocked(raw) and not data.startswith(b'%PDF'):raise ValueError('Page blocked or incomplete')
  doc=extract_job_document(raw,url,fallback_title=job['title']);payload=doc.to_dict()
  from .searcher import Hit
  if process_page(Hit(url,job['title'],'','','pfe_global'),payload,raw,True)!='vacancy':
   raise ValueError('The source no longer provides a readable individual vacancy')
  score,decision,reason,_=evaluate(payload,profile)
  state='closed' if decision=='expired' else 'detail_read'
  with connect() as c:
   # Refresh public facts only, never submission history or recruiter outcomes.
   c.execute('UPDATE jobs SET body=?,structured_json=?,valid_through=?,start_date=?,end_date=?,score=?,decision=?,reason=?,availability_status=?,last_checked_at=CURRENT_TIMESTAMP WHERE id=?',(doc.text,doc.structured_json,doc.valid_through,doc.start_date,doc.end_date,score,decision,reason,'expired' if state=='closed' else 'unknown',job['id']))
  record_evidence(job['id'],payload,profile,True,url)
  if state=='closed':
   with connect() as c:c.execute("UPDATE pfe_evidence SET verification='closed' WHERE job_id=?",(job['id'],))
  return dict(state=state)
 except urllib.error.HTTPError as exc:
  state='closed' if exc.code in {404,410} else 'unverified'
 except Exception:
  state='unverified'
 with connect() as c:
  c.execute('UPDATE pfe_evidence SET verification=?,checked_at=? WHERE job_id=?',(state,datetime.now(timezone.utc).isoformat(),job['id']))
  if state=='closed':c.execute("UPDATE jobs SET availability_status='expired',decision='expired',last_checked_at=CURRENT_TIMESTAMP WHERE id=?",(job['id'],))
 return dict(state=state)
