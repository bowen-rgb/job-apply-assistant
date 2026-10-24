import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
from app.profile_store import default_profile

STATIC=Path(__file__).resolve().parents[1]/'static'
class WorkspaceMenuTests(unittest.TestCase):
 def setUp(self):
  self.p=sync_playwright().start();self.browser=self.p.chromium.launch(headless=True,args=getattr(self,'browser_args',[]))
  self.page=self.browser.new_page(viewport={'width':1440,'height':1000});self.errors=[];self.writes=[];self.remote=[];self.queue_unavailable=False
  self.page.on('pageerror',lambda e:self.errors.append(str(e)))
  self.page.add_init_script("window===window.top&&localStorage.setItem('jaa-ui-language','zh')")
  profile=default_profile();profile['identity'].update(first_name='Example',last_name='Candidate',email='private@example.test')
  job={'id':1,'title':'Example job','display_title':'Example job','company':'Example','decision':'keep','score':90,'review_verdict':'HUMAN_REVIEW','human_review_status':'pending','url':'https://employer.test/1'}
  def respond(r):
   path=urlparse(r.request.url).path
   if urlparse(r.request.url).hostname!='menu.test':self.remote.append(r.request.url)
   if path=='/':r.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
   if path.startswith('/static/'):
    r.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
   if r.request.method!='GET':self.writes.append(path)
   data={}
   if path=='/api/candidates':data={'active_id':'default','items':[{'id':'default','name':'Example Candidate','identity':{},'active':True}]}
   elif path=='/api/profile':data=profile
   elif path in ['/api/jobs','/api/pipeline']:data=[job,dict(job,id=2,review_verdict='',application_status='submitted',tracker_stage='submitted')]
   elif path=='/api/queue':
    if self.queue_unavailable:r.fulfill(status=503,json={'detail':'Unavailable'});return
    data={'items':[dict(job,job_id=1,status='queued')],'counts':{'queued':1},'running':False}
   elif path in ['/api/accounts','/api/resumes','/api/platform-logins','/api/sources','/api/qr']:data=[]
   elif path=='/api/pending-tasks':data={'items':[]}
   elif path=='/api/pfe':data={'settings':{},'jobs':[],'leads':[],'sources':[],'plan':[]}
   elif path.endswith(('/human-review-events','/stage-events','/applications')):data=[]
   elif path=='/api/jobs/translate-titles':data={'translations':{}}
   r.fulfill(json=data)
  self.page.route('**/*',respond);self.page.goto('http://menu.test/')
  expect(self.page.locator('#workspaceMenuButton')).to_be_visible()
  expect(self.page.locator('#mainMenuView')).to_be_visible()
 def tearDown(self):self.browser.close();self.p.stop()
 def test_scene_and_mobile_menu_have_real_navigation_without_sidebar(self):
  for width in [1440,768,375]:
   self.page.set_viewport_size({'width':width,'height':1000})
   expect(self.page.locator('aside')).to_be_hidden()
   expect(self.page.locator('#candidateSelect')).to_be_visible();expect(self.page.locator('#languageSelect')).to_be_visible()
   if width>1100:
    frame=self.page.frame_locator('#menuScene')
    expect(frame.locator('.ef-core')).to_be_visible()
    expect(frame.locator('#sceneStats')).to_contain_text('待你确认')
    expect(frame.locator('body')).not_to_contain_text('private@example.test')
    self.page.wait_for_timeout(1100)
   else:expect(self.page.locator('#menuPageGrid button')).to_have_count(18)
   self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)
   self.page.screenshot(path=f'tmp/endfield-menu-{width}.png',full_page=True)
  self.assertEqual(self.remote,[]);self.assertEqual(self.writes,[]);self.assertEqual(self.errors,[])
 def test_every_menu_entry_routes_to_existing_function_without_writes(self):
  self.page.set_viewport_size({'width':768,'height':1000})
  destinations={'jobs':'jobsView','pipeline':'pipelineView','profile':'profileView','qr':'qrApplicationDialog','overview':'overviewView','guide':'guideView','accounts':'accountsDialog','logins':'accountsDialog','pending':'pendingTasksDialog','pfe':'pfeView','liked':'jobsView','human':'jobsView','confirmed':'jobsView','submitted':'jobsView','export':'jobsView','sources':'profileView','resumes':'profileView','appearance':'profileView'}
  for action,target in destinations.items():
   with self.subTest(action=action):
    self.page.locator('#workspaceMenuButton').click()
    self.page.locator('#menuSearch').fill(action)
    self.page.locator(f'[data-menu-page="{action}"]').click()
    expect(self.page.locator('#'+target)).to_be_visible()
    for dialog in self.page.locator('dialog[open]').all():dialog.evaluate('(d)=>d.close()')
  self.assertEqual(self.writes,[]);self.assertEqual(self.errors,[])
 def test_scene_uses_existing_page_handlers_and_reopens_without_reloading(self):
  frame=self.page.frame_locator('#menuScene')
  expect(frame.locator('[data-action=profile]').first).to_be_visible()
  self.page.wait_for_timeout(1100)
  stamp=frame.locator('body').evaluate('()=>performance.timeOrigin')
  frame.locator('.ef-card[data-action=profile]').click()
  expect(self.page.locator('#profileView')).to_be_visible()
  self.page.locator('#first_name').fill('Unsaved value')
  self.page.locator('#workspaceMenuButton').click()
  expect(self.page.locator('#mainMenuView')).to_be_visible()
  self.assertEqual(frame.locator('body').evaluate('()=>performance.timeOrigin'),stamp)
  self.page.keyboard.press('Escape')
  expect(self.page.locator('#profileView')).to_be_visible()
  expect(self.page.locator('#first_name')).to_have_value('Unsaved value')
  self.assertEqual(self.writes,[]);self.assertEqual(self.errors,[])
 def test_stats_failure_preserves_navigation_and_forged_messages_do_nothing(self):
  self.queue_unavailable=True;self.page.evaluate('WorkspaceMenu.refresh()')
  expect(self.page.locator('#menuRetry')).to_be_visible()
  self.page.evaluate("window.postMessage({type:'jaa-menu:navigate',action:'jobs'},'*')")
  expect(self.page.locator('#mainMenuView')).to_be_visible()
  self.page.locator('#menuSearch').fill('jobs');self.page.locator('[data-menu-page=jobs]').click()
  expect(self.page.locator('#jobsView')).to_be_visible()
  self.assertEqual(self.writes,[])
