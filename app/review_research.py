"""Bounded source collection before a repeat review; cache public pages, never home addresses."""
import hashlib
import json
import time
from .workspaces import data_dir
from .qr_fetching import read_public
from .searcher import search_web
from .vendor.job_search.posting_guard import guard
from .worker_runtime import check_cancelled


def collect(job):
    # Changes in the posting invalidate its source cache; no candidate data enters a search.
    key=hashlib.sha256(json.dumps([job.get(k,'') for k in ('url','title','company','location','body')],ensure_ascii=False).encode()).hexdigest()
    folder=data_dir()/'review-research';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(key+'.json')
    try:
        cached=json.loads(path.read_text(encoding='utf-8'))
        ttl=86400 if cached.get('pages') else 900
        if 0<=time.time()-cached['collected_at']<ttl:return cached
    except (OSError,ValueError,KeyError,TypeError):pass
    result={'pages':[],'errors':[],'collected_at':time.time(),'status':'unavailable'}
    urls=[job.get('url','')]
    # Search names, not links embedded in untrusted posting bodies or applicant details.
    query=' '.join(str(job.get(k,'')).strip()[:180] for k in ('company','location'))+' adresse site accès transports'
    if job.get('company'):
        check_cancelled()
        try:
            hits=search_web(query,2,'pfe_review',['bing','duckduckgo'],market='fr-FR')
            urls.extend(hit.url for hit in hits[:2])
        except (OSError,ValueError,RuntimeError) as exc:result['errors'].append('Public search: '+str(exc)[:200])
    for url in dict.fromkeys(urls):
        if not url:continue
        check_cancelled()
        try:
            body,ctype,final=read_public(url)
            if 'html' not in ctype.lower() and 'text/plain' not in ctype.lower():
                raise ValueError('Unsupported research page type')
            text,findings=guard(body.decode('utf-8','replace'),'html' if 'html' in ctype.lower() else 'text')
            if len(text.strip())<60:raise ValueError('Insufficient readable source text')
            result['pages'].append({'url':final,'text':text[:7000],'content_warning':findings.get('verdict','')})
        except (OSError,ValueError) as exc:result['errors'].append(str(exc)[:250])
        if len(result['pages'])==2:break
    if result['pages']:result['status']='sources_collected'
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');temporary.replace(path)
    return result
