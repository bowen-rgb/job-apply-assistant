import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
from app.profile_store import default_profile
from fastapi.testclient import TestClient
from app.main import app

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
   if path=='/' or path.startswith('/static/'):
    response=TestClient(app).get(path)
    r.fulfill(status=response.status_code,body=response.content,headers=dict(response.headers));return
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
  self.page.locator('#workspaceMenuButton').click()
  frame.locator('#efMenu').evaluate('(e)=>e.dispatchEvent(new MouseEvent("click",{bubbles:true}))')
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
 def test_tab_toggles_from_page_and_scene_preserving_inputs_and_camera_moves(self):
  from tests.ui_navigation import navigate
  navigate(self.page,'profile')
  self.page.locator('#first_name').fill('Unsaved name')
  self.page.keyboard.press('Tab')
  expect(self.page.locator('#profileView')).to_be_visible()
  self.page.evaluate('document.activeElement.blur()');self.page.keyboard.press('Tab')
  expect(self.page.locator('#mainMenuView')).to_be_visible()
  frame=self.page.frame_locator('#menuScene');expect(frame.locator('.jaa-center-widget')).to_be_visible()
  self.page.wait_for_timeout(1000)
  world=frame.locator('#efWorld');before=world.evaluate('(e)=>getComputedStyle(e).transform')
  frame.locator('.jaa-menu-clock').hover(force=True);self.page.wait_for_timeout(300)
  self.assertNotEqual(before,world.evaluate('(e)=>getComputedStyle(e).transform'))
  frame.locator('body').evaluate('(e)=>e.focus()');self.page.locator('#menuScene').focus();self.page.keyboard.press('Tab')
  expect(self.page.locator('#profileView')).to_be_visible();expect(self.page.locator('#first_name')).to_have_value('Unsaved name')
  self.assertEqual(self.writes,[])
 def test_clock_local_playlist_and_map_are_opt_in_and_stats_do_not_restart_animation(self):
  import struct,io,wave
  frame=self.page.frame_locator('#menuScene');expect(frame.locator('#menuClock')).to_contain_text(':')
  self.page.wait_for_timeout(1100)
  self.page.evaluate('WorkspaceMenu.refresh()')
  expect(frame.locator('body')).not_to_have_class(__import__('re').compile(r'\bef-in\b'))
  output=io.BytesIO()
  with wave.open(output,'wb') as wav:
   wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000);wav.writeframes(struct.pack('<h',0)*8000)
  frame.locator('#widgetMusicFiles').set_input_files([{'name':'Test track.wav','mimeType':'audio/wav','buffer':output.getvalue()},{'name':'Next track.wav','mimeType':'audio/wav','buffer':output.getvalue()}])
  expect(frame.locator('#widgetTrack')).to_have_text('Test track.wav');frame.locator('#widgetNext').click();expect(frame.locator('#widgetTrack')).to_have_text('Next track.wav')
  self.assertTrue(frame.locator('#widgetAudio').evaluate('(e)=>e.src.startsWith("blob:")'))
  frame.locator('[data-widget=map]').click();expect(frame.locator('#widgetLocate')).to_be_visible()
  expect(frame.locator('#widgetMapCanvas iframe')).to_have_count(0)
  self.assertEqual(self.remote,[]);self.assertEqual(self.writes,[])
 def test_map_requests_location_only_after_click_and_can_clear_it(self):
  frame=self.page.frame_locator('#menuScene');expect(frame.locator('[data-widget=map]')).to_be_visible();self.page.wait_for_timeout(1000)
  self.page.evaluate("Object.defineProperty(navigator,'geolocation',{configurable:true,value:{getCurrentPosition:ok=>{window.geoCalls=(window.geoCalls||0)+1;ok({coords:{latitude:48.85,longitude:2.35}})}}})")
  frame.locator('[data-widget=map]').click();self.assertEqual(self.page.evaluate('window.geoCalls||0'),0)
  frame.locator('#widgetLocate').click();expect(frame.locator('#widgetMapCanvas iframe')).to_have_count(1)
  self.assertEqual(self.page.evaluate('window.geoCalls'),1)
  expect(frame.locator('#widgetGoogleMap')).to_have_attribute('href',__import__('re').compile(r'https://www.google.com/maps/search/\?api=1&query=48.85'))
  frame.locator('#widgetClearLocation').click();expect(frame.locator('#widgetMapCanvas iframe')).to_have_count(0)
  expect(frame.locator('#widgetGoogleMap')).to_be_hidden()
  self.page.evaluate("()=>{navigator.geolocation.getCurrentPosition=(ok,fail)=>fail({code:1});}")
  frame.locator('#widgetLocate').click();expect(frame.locator('#widgetLocationStatus')).to_contain_text('无法定位')
  frame.locator('#widgetRotate').check()
  frame.locator('body').evaluate('()=>{const original=Date.now;Date.now=()=>original()+31000;}')
  expect(frame.locator('#musicWidget')).to_be_visible(timeout=3000)
  self.assertEqual(self.writes,[])
 def test_blocked_scene_falls_back_to_working_page_cards(self):
  self.page.route('**/static/vendor/endfield-menu/index.html*',lambda r:r.abort())
  self.page.reload();expect(self.page.locator('#menuPageGrid')).to_be_visible(timeout=8000)
  self.page.locator('[data-menu-page=jobs]').click();expect(self.page.locator('#jobsView')).to_be_visible()
  self.assertEqual(self.writes,[])
 def test_original_palette_and_official_art_reach_menu_and_work_pages(self):
  frame=self.page.frame_locator('#menuScene');expect(frame.locator('.ef-core')).to_be_visible()
  self.assertEqual(frame.locator('html').evaluate('(e)=>getComputedStyle(e).getPropertyValue("--ef-yellow").trim()'),'#ffde00')
  self.assertEqual(self.page.locator('#workspaceHeader').evaluate('(e)=>getComputedStyle(e).backgroundColor'),'rgb(25, 28, 31)')
  from tests.ui_navigation import navigate
  navigate(self.page,'jobs')
  self.assertEqual(self.page.locator('#searchBtn').evaluate('(e)=>getComputedStyle(e).backgroundColor'),'rgb(255, 222, 0)')
  self.assertIn('keyvisual.jpg',self.page.locator('#jobsView>header').evaluate('(e)=>getComputedStyle(e,"::after").backgroundImage'))
  self.assertEqual(self.writes,[])
 def test_menu_labels_fit_and_bottom_labels_are_centered_in_six_languages(self):
  frame=self.page.frame_locator('#menuScene');expect(frame.locator('.ef-core')).to_be_visible()
  self.page.wait_for_timeout(1100)
  for language in ['zh','en','fr','de','es','pt']:
   self.page.evaluate('(language)=>Locale.setLanguage(language)',language)
   expect(frame.locator('html')).to_have_attribute('lang',language)
   labels=frame.locator('.ef-rtile text[data-menu-label]').evaluate_all('(nodes)=>nodes.map(e=>({x:e.getBBox().x,w:e.getBBox().width,y:e.getBBox().y,h:e.getBBox().height,c:Number(e.getAttribute("x"))}))')
   for label in labels:
    self.assertLessEqual(label['w'],95.5,(language,label));self.assertLess(abs(label['x']+label['w']/2-label['c']),1.5,(language,label))
    self.assertLessEqual(label['y']+label['h'],104.5,(language,label))
   left=frame.locator('.ef-card text[data-menu-label]').evaluate_all('(nodes)=>nodes.map(e=>({x:e.getBBox().x,w:e.getBBox().width,y:e.getBBox().y,h:e.getBBox().height}))')
   for label,(a,b) in zip(left,[(168.99,-.03362),(170.39,-.03319),(175.66,-.0329),(153.99,-.03242)]):
    self.assertGreaterEqual(label['x'],149,(language,label));self.assertLessEqual(label['x']+label['w'],311,(language,label))
    self.assertLess(label['y']+label['h'],a+b*(label['x']+label['w'])-1,(language,label))
   for action,center in [('overview',826),('guide',1126)]:
    label=frame.locator(f'[data-label-route={action}] text[data-menu-label]').last.evaluate('(e)=>({x:e.getBBox().x,w:e.getBBox().width})')
    self.assertLess(abs(label['x']+label['w']/2-center),1.5,(language,action,label));self.assertLessEqual(label['w'],209)
   if language in ['zh','fr']:self.page.screenshot(path=f'tmp/endfield-menu-aligned-{language}.png',full_page=True)
