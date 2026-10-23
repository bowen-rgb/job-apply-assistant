"""Candidate-scoped login windows. Only explicit user actions capture a session."""
import json,re,sys,time,uuid
from datetime import datetime,timezone
from urllib.parse import urlparse
from fastapi import APIRouter,HTTPException
from filelock import FileLock
from .workspaces import data_dir,candidate_id,active_id,LOCK
from .worker_runtime import launch,is_running,cancel,check_cancelled

SITES={
 'jobteaser':('JobTeaser','https://www.jobteaser.com/fr/users/sign_in','jobteaser.com'),
 'hellowork':('HelloWork','https://www.hellowork.com/fr-fr/candidat/connexion-inscription.html#connexion','hellowork.com'),
 'apec':('Apec','https://www.apec.fr/candidat/recherche-stage.html/stage','apec.fr'),
 'wttj':('Welcome to the Jungle','https://www.welcometothejungle.com/fr/authenticate/signin','welcometothejungle.com'),
 'france_travail':('France Travail','https://candidat.francetravail.fr/espacepersonnel/','francetravail.fr'),
 'linkedin':('LinkedIn','https://www.linkedin.com/login','linkedin.com'),
 'indeed':('Indeed','https://secure.indeed.com/account/login','indeed.com'),
}
MODULE='app.platform_login'
router=APIRouter(prefix='/api/platform-logins')


def identifier(site):
 if site not in SITES:raise ValueError('Unknown platform')
 return list(SITES).index(site)+1


def path():return data_dir()/'platform-logins.json'


def read():
 try:return json.loads(path().read_text(encoding='utf8'))
 except FileNotFoundError:return {}


def update(site,**values):
 folder=data_dir();folder.mkdir(parents=True,exist_ok=True)
 with FileLock(str(folder/'platform-logins.lock')):
  data=read();data[site]={**data.get(site,{}),**values};tmp=path().with_suffix('.tmp')
  tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');tmp.replace(path())


@router.get('')
def status():
 data=read();rows=[]
 for key,(label,url,domain) in SITES.items():
  row=data.get(key,{})
  running=is_running(MODULE,identifier(key))
  state=row.get('state','not_connected')
  if not running and state in {'opening','waiting','checking'}:state='closed'
  rows.append(dict(key=key,label=label,url=url,state=state,window_open=running,verified=bool(row.get('verified')),saved_at=row.get('saved_at',''),error=row.get('error','')))
 return rows


@router.post('/{site}/{action}')
def action(site:str,action:str):
 try:idx=identifier(site)
 except ValueError as exc:raise HTTPException(404,str(exc))
 with LOCK:
  if candidate_id()!=active_id():raise HTTPException(409,'Candidate changed. Reload before continuing.')
  if action=='open':
   from .queue_manager import status as queue_status
   if queue_status().get('running'):raise HTTPException(409,'Stop the application queue before connecting a platform.')
   if any(key!=site and is_running(MODULE,identifier(key)) for key in SITES):raise HTTPException(409,'Save or close the current platform login window first.')
   from .browser_control import start
   start()
   if is_running(MODULE,idx):update(site,command='focus',request=uuid.uuid4().hex)
   else:
    update(site,state='opening',command='',request='',error='')
    launch(MODULE,idx)
  elif action=='save':
   if not is_running(MODULE,idx):raise HTTPException(409,'Login window closed. Open it again before saving.')
   update(site,command='save',request=uuid.uuid4().hex,state='checking',error='')
  elif action=='disconnect':
   cancel(MODULE,idx)
   from . import secret_store
   domain=SITES[site][2]
   def clear(data):
    state=data.get('browser_state') or {}
    matches=lambda h:h.lstrip('.')==domain or h.lstrip('.').endswith('.'+domain)
    state['cookies']=[c for c in state.get('cookies',[]) if not matches(c.get('domain',''))]
    state['origins']=[x for x in state.get('origins',[]) if not matches(urlparse(x['origin']).hostname or '')]
    data['browser_state']=state
   secret_store.update(clear)
   update(site,state='not_connected',verified=False,saved_at='',command='')
  else:raise HTTPException(404,'Unknown action')
 return {'ok':True}


def page_state(page,domain):
 host=urlparse(page.url).hostname or ''
 if host!=domain and not host.endswith('.'+domain):return 'needs_login',False
 if page.locator('input[type=password]:visible,input[autocomplete="one-time-code"]:visible').count():return 'needs_login',False
 text=page.locator('body').inner_text(timeout=5000)
 if re.search(r'verify you are human|checking your browser|验证设备|正在验证|access denied',text,re.I):return 'verification',False
 if re.search(r'/(?:login|signin|sign-in|sign_in|authenticate|connexion)(?:/|$|[.#])',urlparse(page.url).path):return 'needs_login',False
 verified=any(item.is_visible() for item in page.get_by_text(re.compile(r'^(déconnexion|se déconnecter|sign out|log out)$',re.I)).all())
 return 'saved',verified


def run(idx):
 from playwright.sync_api import sync_playwright,TimeoutError as BrowserTimeout
 from .apply_worker import _open_browser
 from .profile_store import runtime_profile
 from .browser_sessions import save_context
 site=list(SITES)[int(idx)-1];owner=candidate_id();last='';next_check=0
 with sync_playwright() as p:
  _,context,mode=_open_browser(p,runtime_profile())
  if mode!='cdp':raise ValueError('Dedicated Chrome required')
  try:
   page=context.new_page()
   try:page.goto(SITES[site][1],wait_until='domcontentloaded',timeout=35000)
   except BrowserTimeout:pass # Keep verification and slow login pages open for the person.
   page.bring_to_front()
   update(site,state='waiting',error='')
   while active_id()==owner:
    pages=[tab for tab in context.pages if not tab.is_closed()]
    if not pages:break
    if page.is_closed():page=pages[-1]
    check_cancelled();row=read().get(site,{})
    # The optional manual window is a fallback. Once a definite signed-in
    # surface appears, save once and close; never navigate or refresh to check.
    if time.monotonic()>=next_check:
     next_check=time.monotonic()+3
     try:
      state,verified=page_state(page,SITES[site][2])
      if state=='saved' and verified:
       save_context(context);update(site,state='saved',verified=True,saved_at=datetime.now(timezone.utc).isoformat(),error='')
       break
     except Exception:pass
    request=row.get('request','')
    if request and request!=last:
     last=request
     if row.get('command')=='focus':page.bring_to_front()
     if row.get('command')=='save':
      try:
       # OAuth may return in another tab of this candidate-owned context.
       domain=SITES[site][2]
       matching=[tab for tab in pages if (urlparse(tab.url).hostname or '')==domain or (urlparse(tab.url).hostname or '').endswith('.'+domain)]
       if matching:page=matching[-1]
       state,verified=page_state(page,SITES[site][2])
       if state=='saved':
        save_context(context);update(site,state=state,verified=verified,saved_at=datetime.now(timezone.utc).isoformat(),error='')
        break
       else:update(site,state=state,verified=False,error='')
      except Exception:update(site,state='error',error='Could not save this session. Keep the login page open and try again.')
    page.wait_for_timeout(1000)
  except Exception:
   if read().get(site,{}).get('state') not in {'saved','not_connected'}:update(site,state='error',error='Login window unavailable. Reopen it explicitly; existing pages were not refreshed.')
  finally:
   context.close()
   if read().get(site,{}).get('state') in {'waiting','opening','checking'}:update(site,state='closed')

if __name__=='__main__':run(sys.argv[1])
