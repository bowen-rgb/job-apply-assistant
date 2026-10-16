import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
from app.profile_store import default_profile
from app.account_guide import render as connection_guide

STATIC=Path(__file__).resolve().parents[1]/'static'

class SurfaceTests(unittest.TestCase):
    def test_all_views_dialog_sections_and_connection_guide_share_chrome(self):
        writes=[]
        profile=default_profile();profile['identity'].update(first_name='Example',last_name='Candidate')
        job=dict(id=1,title='Example application',company='Example employer',url='https://example.test/job',decision='keep',review_verdict='HUMAN_REVIEW',human_review_status='pending',review_summary='Check the working hours',queue_status='error',application_status='error',application_error='Le formulaire de candidature n’est pas encore accessible.',tracker_stage='saved')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN',viewport={'width':1440,'height':1000});errors=[]
                page.add_init_script("localStorage.setItem('jaa-ui-mode','full')")
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if path=='/api/gmail/guide':route.fulfill(body=connection_guide('zh'),content_type='text/html');return
                    if route.request.method!='GET' and path!='/api/jobs/translate-titles':writes.append(path)
                    data={}
                    if path=='/api/candidates':data={'active_id':'default','items':[dict(id='default',name='Example Candidate',active=True,identity={})]}
                    elif path=='/api/jobs/translate-titles':data={'translations':{'1':{'original':job['title'],'title':job['title'],'status':'unavailable'}}}
                    elif path=='/api/profile':data=profile
                    elif path in {'/api/jobs','/api/pipeline'}:data=[job]
                    elif path=='/api/accounts':data=[dict(site_name='Example portal',origin='https://example.test',login_url='https://example.test/login',username='example@example.test',enabled=True,has_password=True)]
                    elif path=='/api/pending-tasks':data={'items':[dict(id='a',title='Example to-do',url='https://example.test/research',kind='vacancy',note='Check the deadline before applying',source='Personal list',status='pending')]}
                    elif path=='/api/queue':data={'items':[dict(job,job_id=1,status='error',attempts=1,note=job['application_error'])],'counts':{'error':1},'paused':True}
                    elif path=='/api/analytics':data={'totals':{'total':1},'queue':[{'status':'error','n':1}]}
                    elif path in {'/api/sources','/api/resumes'} or path.endswith('events'):data=[]
                    elif path=='/api/health':data={'resume_ok':False,'cdp_ok':False}
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://surfaces.test/')
                output=Path('data/surface-previews');output.mkdir(parents=True,exist_ok=True)
                for nav,view in [('jobsNav','jobsView'),('profileNav','profileView'),('pipelineNav','pipelineView'),('guideNav','guideView')]:
                    page.locator('#'+nav).click()
                    expect(page.locator('#'+view+' > header')).to_have_class('surface-heading')
                    for width in [320,768,1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                        if width==320:
                            menu=page.locator('#mobileNavToggle')
                            expect(menu).to_be_visible()
                            expect(page.locator('.primary-nav')).not_to_be_visible()
                            menu.click()
                            expect(menu).to_have_attribute('aria-expanded','true')
                            expect(page.locator('.primary-nav')).to_be_visible()
                            self.assertTrue(page.locator('.primary-nav button').evaluate_all('(nodes)=>nodes.every(n=>!n.getClientRects().length || n.clientWidth>=120)'))
                            page.keyboard.press('Escape')
                            expect(menu).to_have_attribute('aria-expanded','false')
                            expect(menu).to_be_focused()
                    page.evaluate('window.scrollTo(0,0)')
                    page.screenshot(path=str(output/(view+'.png')))
                page.locator('#profileNav').click()
                expect(page.locator('#profileView > .surface-jumps button').first).to_be_visible()
                page.locator('#profileView > .surface-jumps button').first.focus();page.keyboard.press('Enter')
                expect(page.locator('#profileForm > .settings-card h2').first).to_be_focused()
                expect(page.locator('#first_name')).to_have_value('Example')
                page.locator('#accountsNav').click()
                expect(page.locator('#accountsDialog > .surface-account-section')).to_have_count(5)
                expect(page.locator('#accountsDialog > .surface-jumps button')).to_have_count(5)
                page.locator('#accountsDialog > .surface-jumps button').last.click()
                expect(page.locator('#accountSection4 > h3')).to_be_focused()
                page.locator('[data-edit-account]').click()
                expect(page.locator('#accountEditor')).to_have_attribute('open','')
                expect(page.locator('#accountPassword')).to_have_value('')
                for width in [320,768,1440]:
                    page.set_viewport_size({'width':width,'height':1000})
                    self.assertTrue(page.locator('#accountsDialog').evaluate('node=>node.scrollWidth<=node.clientWidth+1'))
                page.locator('#accountsDialog').evaluate('(node)=>node.scrollTop=0')
                page.screenshot(path=str(output/'accountsDialog.png'))
                page.locator('#accountsClose').click();page.locator('#pendingTasksNav').click()
                expect(page.locator('#pendingTasksDialog')).to_have_attribute('aria-labelledby','pendingTasksDialogTitle')
                for width in [320,768,1440]:
                    page.set_viewport_size({'width':width,'height':1000})
                    self.assertTrue(page.locator('#pendingTasksDialog').evaluate('node=>node.scrollWidth<=node.clientWidth+1'))
                page.screenshot(path=str(output/'pendingTasksDialog.png'))
                page.locator('#pendingClose').click();page.locator('#pipelineNav').click()
                expect(page.locator('#queueFilter option[value=all]')).to_have_text('全部状态')
                page.locator('[data-error-job] summary').first.click()
                expect(page.locator('.application-error pre').first).to_be_visible()
                for language in ['en','fr','de','es','pt','zh']:
                    page.locator('#languageSelect').select_option(language)
                    expect(page.locator('#pipelineView h1')).not_to_have_text('undefined')
                page.goto('http://surfaces.test/api/gmail/guide')
                expect(page.locator('main h1')).to_contain_text('连接 Gmail')
                for width in [320,768,1440]:
                    page.set_viewport_size({'width':width,'height':1000})
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                page.screenshot(path=str(output/'gmailGuide.png'))
                self.assertEqual(writes,[]);self.assertEqual(errors,[])
            finally:browser.close()
