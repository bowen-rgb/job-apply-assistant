"""France PFE discovery and evidence-based matching, separate from short-term jobs."""
from __future__ import annotations
import hashlib
import ipaddress
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from urllib.parse import urlparse, parse_qs
from .db import connect

DIRECTIONS = {
 'mechanical': ('mécanique simulation', 'mechanical simulation', ['mecanique','mechanical','elements finis','finite element','calcul de structures','structural','fluidique','cfd','thermique','multiphys']),
 'control': ('automatique commande', 'control systems', ['automatique','commande','control system','model predictive','mpc','system identification','asservissement','regulation']),
 'robotics': ('robotique', 'robotics', ['robotique','robotic','navigation autonome','slam','motion planning','planification de mouvement','manipulation']),
 'digital_twin': ('jumeau numérique', 'digital twin', ['jumeau numerique','digital twin','co-simulation','cosimulation','modelisation','modelling','modeling']),
 'instrumentation': ('instrumentation capteurs', 'instrumentation sensors', ['instrumentation','capteur','sensor','signal processing','traitement du signal','metrologie','mesure physique']),
 'embodied_ai': ('intelligence artificielle incarnée', 'embodied AI', ['embodied','incarnee','reinforcement learning','apprentissage par renforcement','sim-to-real','vision-language-action','robot learning']),
}
MONTHS={'janvier':1,'january':1,'fevrier':2,'february':2,'mars':3,'march':3,'avril':4,'april':4,'mai':5,'may':5,'juin':6,'june':6,'juillet':7,'july':7,'aout':8,'august':8,'septembre':9,'september':9,'octobre':10,'october':10,'novembre':11,'november':11,'decembre':12,'december':12}

def norm(text):
 return ''.join(c for c in unicodedata.normalize('NFD',str(text or '')) if unicodedata.category(c)!='Mn').lower().replace('’',"'")

def public_url(url):
 try:
  p=urlparse(url);host=(p.hostname or '').lower()
  if p.scheme not in {'https','http'} or not host or p.username or p.password or p.port not in {None,80,443}:return False
  if host=='localhost' or host.endswith(('.localhost','.local','.internal')):return False
  try:return ipaddress.ip_address(host).is_global
  except ValueError:return '.' in host
 except (ValueError,TypeError):return False

def settings(raw):
 defaults=dict(enabled=False,use_jobspy=True,directions=[],locations=['France'],start_month='',duration_months=6,start_flexibility_months=1,phd_goal=False,skills=[],school_portal_url='',searxng_url='',research_sources=True,team_discovery=True)
 defaults.update(raw.get('pfe') or {})
 return defaults

def query_plan(profile):
 cfg=settings(profile);locations=' OR '.join(cfg['locations'][:3]) or 'France'
 directions=cfg['directions'] or list(DIRECTIONS)
 groups={k:[] for k in ['research','global','ats','student','team']}
 research=['abg.asso.fr','jobs.inria.fr','emploi.cea.fr','cnrs.fr']
 ats=['jobs.smartrecruiters.com','jobs.lever.co','jobs.ashbyhq.com','myworkdayjobs.com','job-boards.greenhouse.io']
 for i,key in enumerate(directions):
  fr,en,_=DIRECTIONS[key]
  groups['global'].extend([dict(channel='global',direction=key,query=f'stage fin études {fr} {locations}'),dict(channel='global',direction=key,query=f'research internship {en} {locations}')])
  if cfg['research_sources']:
   groups['research'].append(dict(channel='research',direction=key,query=f'site:{research[i%len(research)]} stage M2 {fr}'))
   groups['research'].append(dict(channel='research',direction=key,query=f'stage recherche {fr} {locations} filetype:pdf'))
  groups['ats'].append(dict(channel='ats',direction=key,query=f'site:{ats[i%len(ats)]} internship {en} {locations}'))
  groups['student'].append(dict(channel='student',direction=key,query=f'site:jobteaser.com stage ingénieur {fr} {locations}'))
  if cfg['team_discovery']:groups['team'].append(dict(channel='team',direction=key,query=f'laboratoire équipe recherche {fr} {locations} encadrement stage'))
 # Round-robin channels AND directions: the first queries cannot be consumed by a website list.
 out=[]
 for i in range(max(map(len,groups.values()),default=0)):
  for channel,rows in groups.items():
   if i<len(rows):out.append(rows[i])
 # Revisit a bounded selection of discovered sites within the same query budget.
 # Keeping the first five slots guarantees every discovery channel gets a turn.
 import sqlite3
 try:
  with connect() as c:
   learned=[dict(row) for row in c.execute("SELECT domain FROM discovery_sources WHERE ats='' ORDER BY last_seen_at DESC LIMIT 4")]
 except sqlite3.OperationalError:learned=[]
 for index,row in enumerate(learned):
  key=directions[index%len(directions)]
  out.insert(5+index*6,dict(channel='learned',direction=key,query=f"site:{row['domain']} stage {DIRECTIONS[key][0]} {locations}"))
 from .providers import enabled_sources
 # Reserve in-budget searches for explicitly selected boards, not unreachable tail entries.
 platforms=[s for s in enabled_sources(profile) if s.key in {'jobteaser','1jeune1solution','apec','hellowork','wttj','france_travail'}]
 for index,source in enumerate(platforms):
  key=directions[index%len(directions)]
  out.insert(5+index*4,dict(channel=source.key,direction=key,query=f'site:{source.domain} stage {DIRECTIONS[key][0]} {locations}'))
 out.extend(dict(channel='supplement',direction='',query=f'site:{s.domain} stage {locations}') for s in enabled_sources(profile) if s not in platforms)
 return out[:max(1,min(120,int(profile.get('search_queries_per_run',36))))]

def facts(job,profile):
 cfg=settings(profile);title=norm(job.get('title'));text='\n'.join(str(job.get(k) or '') for k in ('title','body','text','description','snippet','employment_type'))[:200000];t=norm(text)
 def evidence(pattern):
  m=re.search(pattern,t,re.I)
  return text[max(0,m.start()-45):min(len(text),m.end()+85)].strip() if m else ''
 # Numeric/technical labels are evidence of the advertised level, not claims about the candidate.
 internship=bool(re.search(r'\bstage\b|\bintern(?:ship)?\b|\bstagiaire\b',t))
 pfe=evidence(r'fin d[e’\x27 ]?etudes|\bpfe\b|\bm2\b|master\s*2|bac\s*\+\s*5|stage ingenieur|engineering internship')
 junior=evidence(r'(?:niveau|formation|etudiant|student)[^\n.!?]{0,35}(?:\bbac\s*\+\s*[123]\b|\bbts\b|\bbut\b|\blicence\b)') if not pfe else ''
 from .constraints import advertised_duration
 duration,duration_phrase=advertised_duration(text)
 duration_evidence=evidence(re.escape(duration_phrase)) if duration_phrase else ''
 start=str(job.get('start_date') or '')[:7]
 start_evidence='start_date: '+start if re.fullmatch(r'\d{4}-\d{2}',start) else ''
 if not start_evidence:
  month_expr='|'.join(MONTHS)
  m=re.search(r'(?:debut|demarrage|a partir|commenc|start|starting)[^\n.!?]{0,45}?\b('+month_expr+r')\s+(20\d{2})',t)
  if m:start=f'{m[2]}-{MONTHS[m[1]]:02d}';start_evidence=evidence(re.escape(m[0]))
  else:start=''
 flexible=bool(re.search(r'(?:debut|start|dates?)[^\n.!?]{0,50}(?:flexib|negoci|convenir|agreement)',t))
 desired=cfg['duration_months'];time_conflict=bool(duration and not duration[0]<=desired<=duration[1])
 if start and cfg['start_month'] and not flexible:
  y,mo=map(int,start.split('-'));ty,tm=map(int,cfg['start_month'].split('-'))
  time_conflict|=abs((y-ty)*12+mo-tm)>cfg['start_flexibility_months']
 hits={key:[word for word in DIRECTIONS[key][2] if re.search(r'(?<!\w)'+re.escape(word)+r'(?!\w)',t)] for key in (cfg['directions'] or list(DIRECTIONS))}
 hits={key:value for key,value in hits.items() if value}
 skills=[word for word in cfg['skills'] if norm(word) in t]
 research=evidence(r'publication|etat de l.art|state.of.the.art|experimental|experiment|validation|hypothes|benchmark|prototype|algorith|research|recherche')
 phd=evidence(r'(?:poursuite|possibilite|opportunite|continuation)[^\n.!?]{0,60}(?:these|doctorat|phd)|(?:phd|doctoral)[^\n.!?]{0,30}(?:opportunit|position|funding)')
 supervisor=evidence(r'encadrant|encadrement|supervis(?:or|ion)|directeur de recherche|responsable scientifique')
 eligibility='pending' # A verified personal academic profile still needs review against the original offer.
 axes=dict(eligibility=20 if pfe else 8 if internship else 0,time=20 if duration and start and not time_conflict else 10 if duration and not time_conflict else 0,technical=min(30,15*len(hits)+3*len(skills)),research=20 if research else 0,phd=10 if phd and cfg['phd_goal'] else 0)
 if phd and re.search(r'aucune|pas de|no (?:phd|doctoral)',norm(phd)):
  phd='';axes['phd']=0
 if not cfg['phd_goal'] and research:axes['research']=min(30,axes['research']+10)
 score=sum(axes.values());unknown=[]
 if not pfe:unknown.append('degree_level')
 if not start:unknown.append('start_month')
 if not duration:unknown.append('duration')
 location=norm(job.get('location') or '')
 requested=[norm(value) for value in cfg['locations'] if value]
 # Cities without country/geocoding stay unknown; do not guess a conflict.
 countries={'france':['france','fr'], 'germany':['germany','allemagne','deutschland','de'], 'united states':['united states','usa','etats-unis','us'], 'united kingdom':['united kingdom','royaume-uni','uk'], 'canada':['canada','ca'], 'switzerland':['switzerland','suisse','ch'], 'belgium':['belgium','belgique','be']}
 country=lambda value:next((key for key,aliases in countries.items() if any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',value) for alias in aliases)),None)
 advertised_country=country(location)
 allowed_countries={country(value) for value in requested if country(value)}
 location_conflict=bool(advertised_country and allowed_countries and advertised_country not in allowed_countries)
 # A known French region/postcode can establish a conflict; unknown towns remain unverified.
 region_locations={value.replace('-',' ') for value in requested}
 if 'ile de france' in region_locations and region_locations <= {'paris','paris france','ile de france'}:
  place=location.replace('-',' ').replace('’',"'")
  outside=('auvergne rhone alpes','bourgogne franche comte','bretagne','centre val de loire','corse','grand est','hauts de france','normandie','nouvelle aquitaine','occitanie','pays de la loire',"provence alpes cote d'azur")
  postcodes=re.findall(r'(?<!\d)(\d{2})\d{3}(?!\d)',location)
  location_conflict=location_conflict or any(region in place for region in outside) or bool(postcodes and all(code not in {'75','77','78','91','92','93','94','95'} for code in postcodes))
 if not location or (requested and not any(value in location for value in requested) and not (advertised_country and advertised_country in allowed_countries)):unknown.append('location')
 if not (profile.get('prepared_degree_level') or profile.get('education_level')):unknown.append('candidate_degree')
 return dict(version=1,kind='pfe' if pfe and internship else 'research_internship' if internship and research else 'internship' if internship else 'unclassified',score=score,axes=axes,directions=hits,skills=skills,eligibility=eligibility,start_month=start,duration_months=duration,flexible_start=flexible,time_conflict=time_conflict,location_conflict=location_conflict,junior_level=bool(junior),unknown=unknown,evidence=dict(level=pfe,junior=junior,duration=duration_evidence,start=start_evidence,research=research,phd=phd,supervisor=supervisor),phd_followup='explicit_opportunity' if phd else 'not_stated',requires_review=True)

def evaluate_pfe(job,profile):
 f=facts(job,profile);flags=list(f['unknown']);reason='pfe:'+json.dumps({'axes':f['axes'],'directions':list(f['directions']),'unknown':f['unknown']},ensure_ascii=False)
 if profile.get('max_end_date') and job.get('end_date') and str(job['end_date'])[:10]>str(profile['max_end_date'])[:10]:return -95,'reject','pfe_availability_end_conflict',['end_date_conflict']
 if f['location_conflict']:return -95,'reject','pfe_location_conflict; '+reason,['location_conflict']
 if f['time_conflict']:return -95,'reject','pfe_time_conflict; '+reason,['pfe_time_conflict']
 if f['junior_level']:return -80,'reject','pfe_junior_level; '+reason,['pfe_level_conflict']
 if re.search(r'\balternance\b|\bapprenti(?:ssage)?\b',norm(job.get('title') or '')) and not re.search(r'\bstage\b|\binternship\b',norm(job.get('title') or '')):return -90,'reject','pfe_apprenticeship_not_internship; '+reason,['pfe_not_internship']
 t=norm((job.get('title') or '')+' '+(job.get('employment_type') or ''))
 if not re.search(r'\bstage\b|\bintern(?:ship)?\b|stagiaire',t) and re.search(r'\bcdi\b|permanent|\bphd position\b|doctorant',t):return -90,'reject','pfe_not_internship; '+reason,['pfe_not_internship']
 score=min(100,f['score'])
 decision='keep' if score>=65 and f['directions'] and f['kind']!='unclassified' else 'review' if score>=35 else 'low'
 return score,decision,reason,flags

TABLES='''CREATE TABLE IF NOT EXISTS pfe_evidence(job_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, verification TEXT NOT NULL, checked_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS discovery_sources(key TEXT PRIMARY KEY,domain TEXT,ats TEXT,board TEXT,first_seen_at TEXT,last_seen_at TEXT,last_polled_at TEXT DEFAULT '',status TEXT DEFAULT 'observed');
CREATE TABLE IF NOT EXISTS opportunity_leads(id TEXT PRIMARY KEY,kind TEXT,title TEXT,url TEXT,contact TEXT DEFAULT '',evidence TEXT,status TEXT DEFAULT 'unconfirmed',created_at TEXT,updated_at TEXT);'''

def init_tables():
 with connect() as c:c.executescript(TABLES)

def board_from_url(url):
 if not public_url(url):return None
 p=urlparse(url);host=p.hostname.lower();parts=[x for x in p.path.split('/') if x]
 if host in {'boards.greenhouse.io','job-boards.greenhouse.io','boards.eu.greenhouse.io'} and parts:return ('greenhouse',parts[0])
 if host in {'jobs.lever.co','jobs.eu.lever.co'} and parts:return ('lever',parts[0])
 if host=='jobs.ashbyhq.com' and parts:return ('ashby',parts[0])
 from .portal_feeds import detect
 ats=detect(url)
 if ats:
  # Store the board, not each individual vacancy URL, for incremental polling.
  if ats=='workday':
   site=next((part for part in parts if not re.fullmatch(r'[a-z]{2}-[A-Za-z]{2}',part)),None)
   if not site:return None
   return (ats,f'https://{host}/{site}')
  if ats in {'personio','teamtailor','recruitee','successfactors'}:return (ats,f'https://{host}')
  if ats=='workable' and parts:return (ats,f'https://{host}/{parts[0]}')
  if ats=='eightfold':return (ats,f'https://{host}/careers?'+p.query)
  if ats=='smartrecruiters' and parts:return (ats,f'https://{host}/{parts[0]}')
 return None

def remember_source(url):
 if not public_url(url):return
 init_tables();p=urlparse(url);board=board_from_url(url);ats,slug=board or ('','');key=hashlib.sha256(f'{p.hostname}:{ats}:{slug}'.encode()).hexdigest()[:24];now=datetime.now(timezone.utc).isoformat()
 with connect() as c:c.execute('''INSERT INTO discovery_sources(key,domain,ats,board,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET last_seen_at=excluded.last_seen_at''',(key,p.hostname,ats,slug,now,now))

def remembered_boards():
 init_tables()
 with connect() as c:return [dict(ats=r['ats'],board=r['board'],company=r['domain']) for r in c.execute("SELECT * FROM discovery_sources WHERE ats<>'' AND (last_polled_at='' OR julianday('now')-julianday(last_polled_at)>1) ORDER BY last_polled_at LIMIT 10")]

def mark_polled(ats,board):
 with connect() as c:c.execute("UPDATE discovery_sources SET last_polled_at=? WHERE ats=? AND board=?",(datetime.now(timezone.utc).isoformat(),ats,board))

def save_lead(kind,title,url,evidence='',contact=''):
 if not title.strip() or kind not in {'team','student'} or not public_url(url):raise ValueError('Use a public opportunity link and a valid lead type')
 init_tables();identifier=hashlib.sha256((kind+':'+url.split('#')[0]).encode()).hexdigest()[:24];now=datetime.now(timezone.utc).isoformat()
 with connect() as c:c.execute('''INSERT INTO opportunity_leads(id,kind,title,url,contact,evidence,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,evidence=excluded.evidence,contact=CASE WHEN excluded.contact<>'' THEN excluded.contact ELSE opportunity_leads.contact END,updated_at=excluded.updated_at''',(identifier,kind,title[:500],url,contact[:300],evidence[:8000],now,now))
 return identifier

def record_evidence(job_id,job,profile,verified,url):
 init_tables();payload=facts(job,profile);now=datetime.now(timezone.utc).isoformat()
 state='closed' if verified and job.get('decision')=='expired' else 'detail_read' if verified else 'unverified'
 with connect() as c:c.execute('INSERT OR REPLACE INTO pfe_evidence VALUES(?,?,?,?)',(job_id,json.dumps(payload,ensure_ascii=False),state,now))
 if verified:remember_source(url)
 return payload

def overview(profile):
 init_tables()
 with connect() as c:
  rows=c.execute('SELECT j.*,p.payload,p.verification,p.checked_at FROM pfe_evidence p JOIN jobs j ON j.id=p.job_id ORDER BY j.score DESC,j.first_seen_at DESC').fetchall()
  jobs=[dict(id=r['id'],title=r['title'],company=r['company'],url=r['url'],location=r['location'],decision=r['decision'],application_status=r['application_status'],verification=r['verification'],checked_at=r['checked_at'],facts=json.loads(r['payload'])) for r in rows]
  leads=[dict(r) for r in c.execute('SELECT * FROM opportunity_leads ORDER BY created_at DESC')]
  sources=[dict(r) for r in c.execute('SELECT * FROM discovery_sources ORDER BY last_seen_at DESC')]
 for job in jobs:
  age=(datetime.now(timezone.utc)-datetime.fromisoformat(job['checked_at'])).total_seconds()
  job['stale']=age>14400
  if job['stale'] and job['verification']=='detail_read':job['verification']='stale'
 from .jobspy_provider import available
 return dict(settings=settings(profile),plan=query_plan(profile) if settings(profile)['enabled'] else [],jobs=jobs,leads=leads,sources=sources,jobspy_available=available(),readiness={'resume':bool(profile.get('resume_path')),'email':bool(profile.get('email')),'automatic_submission':bool(profile.get('auto_submit'))})


def analyze_saved(profile):
 from .scoring import evaluate
 init_tables()
 with connect() as c:rows=[dict(row) for row in c.execute('SELECT * FROM jobs')]
 count=0
 for row in rows:
  if row['application_status'] in {'opening','preparing','preparing_letter'}:continue
  result=facts(row,profile)
  if result['kind']=='unclassified':continue
  score,decision,reason,_=evaluate(row,profile)
  with connect() as c:
   c.execute('UPDATE jobs SET score=?,decision=?,reason=? WHERE id=?',(score,decision,reason,row['id']))
   old=c.execute('SELECT verification,checked_at FROM pfe_evidence WHERE job_id=?',(row['id'],)).fetchone()
   if old:c.execute('UPDATE pfe_evidence SET payload=? WHERE job_id=?',(json.dumps(result,ensure_ascii=False),row['id']))
   else:c.execute('INSERT INTO pfe_evidence VALUES(?,?,?,?)',(row['id'],json.dumps(result,ensure_ascii=False),'unverified',datetime.now(timezone.utc).isoformat()))
  count+=1
 return count
