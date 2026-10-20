"""Rank actual CV content against role duties, never choose the active CV by default."""
import math
import re
from .pfe import norm

STOP=set('avec dans pour votre notre vous nous une des les par aux sur sur son ses cette projet projets ingenieur stage internship company entreprise experience competences engineering'.split())
ALIASES={'mechanical':'mecanique','robotics':'robotique','robotic':'robotique','control':'commande','modelling':'modelisation','modeling':'modelisation','numerical':'numerique','design':'conception','sensors':'capteurs','digital':'numerique'}

def tokens(text):
    words=re.findall(r'[a-z0-9+#.]{3,}',norm(text))
    return {ALIASES.get(w,w) for w in words if w not in STOP}

def rank_resumes(payload,rows,read_text):
    if not payload.get('role_title') or not payload.get('tasks'):return []
    docs=[]
    for row in rows:
        try:text=read_text(row)
        except Exception:text=''
        heading=row.get('label','')+' '+text[:700]
        docs.append((row,text,tokens(text if text else ' '.join(row.get('tags',[]))),tokens(heading)))
    duties=' '.join(payload['tasks'])
    target=tokens(payload['role_title']+' '+duties)
    title=tokens(payload['role_title'])
    ranked=[]
    for row,text,terms,focus in docs:
        hits=target&terms
        def weight(term):return 1+math.log((len(docs)+1)/(1+sum(term in d[2] for d in docs)))
        score=sum(weight(term)*(3 if term in title else 1)*(2 if term in focus else 1) for term in hits)
        lines=[line.strip() for line in text.splitlines() if len(line.strip())>18 and tokens(line)&hits]
        lines.sort(key=lambda line:len(tokens(line)&hits)+2*bool(re.search(r'mis en|parametr|developp|concu|realise|mesure|construit|valide|implemented|developed|designed',norm(line))),reverse=True)
        evidence=lines[:4]
        ranked.append({'resume_id':row['id'],'label':row['label'],'score':round(score,2),
                       'matched_terms':sorted(hits)[:18],'evidence':evidence,
                       'task_evidence':payload['tasks'][0][:500],
                       'source':'cv_text' if text else 'tags_only','reason':'role_tasks_vs_cv'})
    ranked.sort(key=lambda r:r['score'],reverse=True)
    if not ranked or ranked[0]['score']<=0:return ranked
    margin=ranked[0]['score']-(ranked[1]['score'] if len(ranked)>1 else 0)
    ranked[0]['confidence']='high' if ranked[0]['score']>=12 and margin>=3 else 'medium' if margin>1 else 'ambiguous'
    return ranked
