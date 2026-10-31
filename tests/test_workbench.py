from tests.ui_navigation import navigate, set_appearance
import json
import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

STATIC=Path(__file__).resolve().parents[1]/'static'

class WorkbenchTests(unittest.TestCase):
    def test_live_owner_snapshot_charts_navigation_offline_and_responsive(self):
        jobs=[dict(id=1,title='Research internship',source='CEA',provider_key='pending_tasks',decision='review',first_seen_at='2026-10-15 10:00:00',queue_status='queued'),dict(id=2,title='Already applied',source='CEA',provider_key='pending_tasks',decision='keep',application_status='submitted')]
        tasks=[dict(id="contact",title="Contact",kind="contact",status="pending"),dict(id="vacancy",title="Pending vacancy",kind="vacancy",status="pending",url="https://lab.test/job")]
        mutations=[]
        offline=False
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN');errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if offline:route.fulfill(status=503,json={'detail':'offline'});return
                    data={}
                    if path=='/api/candidates':data={'active_id':'default','items':[dict(id='default',name='Bowen Li',identity={})]}
                    elif path=='/api/profile':data={'automation':{}}
                    elif path=='/api/jobs':data=jobs
                    elif path=='/api/insights':
                        from app.application_overview import snapshot
                        data={'summary':snapshot(jobs,[],[]),'config':{'follow_up':{'after_days':14,'max_followups':1},'dimensions':[]},'mail_proposals':[],'followups':[]}
                    elif path=='/api/pending-tasks':data={'items':tasks}
                    elif path=='/api/pending-tasks/vacancy/queue':
                        mutations.append(path);tasks[1]['queue_status']='queued';data={'job_id':1,'queue_status':'queued'}
                    elif path=='/api/queue':data={'counts':{'queued':1},'items':[dict(job_id=1,title='Research internship',status='queued')]}
                    elif path=='/api/resumes':data=[]
                    elif path in {'/api/sources','/api/pipeline'}:data=[]
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://workbench.test/')
                navigate(page,'overviewNav')
                expect(page.locator('[data-wb-filter=all] b')).to_have_text('2')
                expect(page.locator('[data-wb-outcome=waiting] b')).to_have_text('1')
                expect(page.locator('.wb-owner')).to_contain_text('Bowen Li')
                expect(page.locator('.wb-focus-title')).to_have_text('Research internship')
                self.assertEqual(page.locator('#overviewView svg rect').count(),7)
                series=page.evaluate("Workbench.daily([{first_seen_at:'2026-10-15 10:00:00'},{discovered_at:'2026-10-14T10:00:00Z'},{first_seen_at:'invalid'}],7,new Date('2026-10-15T12:00:00Z'))")
                self.assertEqual(sum(row['n'] for row in series),2)
                self.assertEqual(series[-1]['n'],1)
                page.locator('#wbPeriod').select_option('30')
                self.assertEqual(page.locator('#overviewView svg rect').count(),30)
                page.locator('.wb-data summary').first.click()
                expect(page.locator('.wb-data table').first).to_be_visible()
                page.locator('.wb-data').first.evaluate('(node)=>node.scrollTop=80')
                reading_position=page.evaluate('window.scrollY')
                jobs.append(dict(id=3,title='Third vacancy',source='Legacy source',provider_key='',decision='review'))
                expect(page.locator('[data-wb-filter=all] b')).to_have_text('3',timeout=8000)
                expect(page.locator('.wb-data table').first).to_be_visible()
                self.assertGreaterEqual(page.locator('.wb-data').first.evaluate('(node)=>node.scrollTop'),78)
                self.assertLessEqual(abs(page.evaluate('window.scrollY')-reading_position),2)
                offline=True;page.locator('#wbRefresh').click()
                expect(page.locator('#wbConnection')).to_contain_text('连接中断')
                expect(page.locator('[data-wb-filter=all] b')).to_have_text('3')
                offline=False
                page.locator('[data-wb-source=""]').click()
                expect(page.locator('#sourceSelect')).to_have_value('__unassigned__')
                expect(page.locator('#cards .card')).to_have_count(1)
                navigate(page,'overviewNav')
                page.locator('[data-wb-source=pending_tasks]').click()
                expect(page.locator('#sourceSelect')).to_have_value('pending_tasks')
                expect(page.locator('#jobsView')).to_be_visible()
                navigate(page,'overviewNav')
                for width in [320,768,1440]:
                    page.set_viewport_size({'width':width,'height':1000})
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                    if width==320:
                        page.screenshot(path='data/workbench-mobile-preview.png')
                for language in ['zh','fr']:
                    page.locator('#languageSelect').select_option(language)
                    expect(page.locator('#overviewTitle')).not_to_have_text('undefined')
                page.locator('#wbTasks').click()
                expect(page.locator('[data-queue-task]')).to_have_count(1)
                page.locator('#pendingQueueAll').click()
                expect(page.locator('[data-view-task-queue]')).to_have_count(1)
                self.assertEqual(mutations,['/api/pending-tasks/vacancy/queue'])
                page.locator('[data-view-task-queue]').click()
                expect(page.locator('#pipelineView')).to_be_visible()
                navigate(page,'overviewNav')
                page.locator('.wb-data').first.evaluate('(node)=>node.open=false')
                page.evaluate('window.scrollTo(0,0)')
                page.locator('#wbRefresh').focus()
                self.assertEqual(errors,[])
                Path('data').mkdir(exist_ok=True)
                page.set_viewport_size({'width':1440,'height':1100})
                expect(page.locator('#wbRefresh')).to_be_enabled()
                page.locator('#overviewView details').evaluate_all('(nodes)=>nodes.forEach(node=>node.open=false)')
                page.screenshot(path='data/workbench-preview.png',full_page=False)
                jobs[1].update(tracker_stage='rejected',tracker_note='HR: not selected',company='Rejected Employer')
                jobs.append(dict(id=4,title='Not suitable',company='Not a recruiter rejection',decision='reject',application_status='error'))
                page.locator('#languageSelect').select_option('zh')
                page.locator('#wbRefresh').click()
                expect(page.locator('[data-wb-outcome=rejected] b')).to_have_text('1')
                page.locator('[data-wb-outcome=rejected]').click()
                expect(page.locator('#trackingView')).to_be_visible()
                expect(page.locator('.tracker-result-list')).to_contain_text('Rejected Employer')
                expect(page.locator('.tracker-result-list')).not_to_contain_text('Not a recruiter rejection')
                for width in [1280,375]:
                    page.set_viewport_size({'width':width,'height':1000})
                    page.screenshot(path=f'tmp/outcomes-rejected-{width}.png',full_page=True)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                navigate(page,'overview')
                page.set_viewport_size({'width':1280,'height':1000});page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path='tmp/outcomes-dashboard-1280.png',full_page=True)
                self.assertEqual(errors,[])
            finally:browser.close()
