from tests.ui_navigation import navigate, set_appearance
import json, unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
from app.profile_store import default_profile
STATIC=Path(__file__).resolve().parents[1]/'static'

class DirectoryUITests(unittest.TestCase):
    def test_filters_unknowns_persist_across_poll_choose_target_and_no_dispatch(self):
        jobs=[{'url':'https://employer.test/job/robot','title':'Stage robotique','location':'Paris','start_date':'2027-02-01','directions':['control'],'verified':True},
              {'url':'https://employer.test/job/design','title':'Stage conception mecanique','location':'Lyon','start_date':'2027-04-01','directions':['mechanical'],'verified':True},
              {'url':'https://employer.test/job/unknown','title':'Stage a verifier','location':'','start_date':'','directions':[],'verified':False}]
        row={'id':'a'*32,'state':'draft','job_id':None,'resumes':[{'id':'robot','label':'CV Robotique'}],
             'preview':{'url':'https://employer.test/','final_url':'https://employer.test/','kind':'entry','company':'Example','company_quote':'Example employer careers','source_name':'a'*120+'.jpg','tasks':[],'opportunities':jobs,'resume_id':'robot','readiness':{'ready':False},'crawl':{'status':'partial','discovered':3,'pages_read':4,'remaining':2}}}
        writes=[];errors=[];profile=default_profile()
        with sync_playwright() as p:
            b=p.chromium.launch(headless=True)
            try:
                page=b.new_page(locale='zh-CN',viewport={'width':1280,'height':1000})
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    path=urlparse(route.request.url).path;method=route.request.method
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if method!='GET':writes.append(path)
                    if path=='/api/qr':route.fulfill(json=[row]);return
                    if path.startswith('/api/qr/'):
                        if path.endswith('/crawl'):row['state']='crawling';row['inspection_running']=True
                        elif path.endswith('/crawl-stop'):row['state']='draft';row['preview']['crawl']['status']='paused'
                        elif path.endswith('/target'):
                            row['preview'].update(kind='vacancy',role_title='Stage robotique',title='Stage robotique',tasks=['Design and validate robot control.'],readiness={'ready':True},final_url='https://employer.test/job/robot')
                        route.fulfill(json=row);return
                    data={}
                    if path=='/api/candidates':data={'active_id':'default','items':[{'id':'default','name':'Example Candidate','active':True,'identity':{}}]}
                    elif path=='/api/profile':data=profile
                    elif path in {'/api/jobs','/api/resumes','/api/accounts','/api/sources','/api/pipeline'}:data=[]
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://directory.test/');navigate(page,'qrNav')
                expect(page.locator('.qr-role-cards article')).to_have_count(3)
                page.locator('#qrRoleDirection').select_option('control');page.locator('#qrRolePlace').fill('Paris')
                page.locator('#qrRoleFrom').fill('2027-02');page.locator('#qrRoleTo').fill('2027-03')
                expect(page.locator('.qr-role-cards article')).to_have_count(2)
                page.locator('#qrRoleUnknown').uncheck();expect(page.locator('.qr-role-cards article')).to_have_count(1)
                page.locator('#qrCrawl').click();expect(page.locator('#qrCrawlStop')).to_be_visible()
                expect(page.locator('#qrRolePlace')).to_have_value('Paris');expect(page.locator('#qrRoleUnknown')).not_to_be_checked()
                page.locator('#qrCrawlStop').click();expect(page.locator('[data-qr-pick-role]').first).to_be_enabled()
                for width in [1280,375]:
                    page.set_viewport_size({'width':width,'height':1000})
                    self.assertTrue(page.locator('#qrApplicationDialog').evaluate('e=>e.scrollWidth<=e.clientWidth+1'))
                    page.locator('#qrRoleResults').scroll_into_view_if_needed()
                    page.screenshot(path=f'docs/assets/angelina/qr-directory-{width}.png',animations='disabled')
                page.locator('[data-qr-pick-role]').first.click();expect(page.locator('.qr-job')).to_have_text('Stage robotique')
                expect(page.locator('#qrSend')).to_be_enabled();expect(page.locator('[data-qr-select]')).to_have_count(1)
                self.assertFalse(any(x.endswith('/start') for x in writes));self.assertEqual(errors,[])
            finally:b.close()
