"""User-visible feature parity: old services must remain reachable after UI work."""
import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

STATIC=Path(__file__).resolve().parents[1]/'static'


class WorkflowParityTests(unittest.TestCase):
    def setUp(self):
        self.p=sync_playwright().start();self.browser=self.p.chromium.launch(headless=True)
        self.page=self.browser.new_page(viewport={'width':1280,'height':1000})
        self.errors=[];self.writes=[]
        self.page.on('pageerror',lambda error:self.errors.append(str(error)))
        self.jobs=[{'id':1,'title':'Stage simulation','company':'Example','provider_key':'archived','score':85,'decision':'keep','url':'https://employer.test/1','reason':'Relevant tasks','tracker_stage':'saved'},
                   {'id':2,'title':'Submitted role','provider_key':'active','decision':'keep','application_status':'submitted','tracker_stage':'submitted'},
                   {'id':3,'title':'Skipped role','decision':'keep','user_action':'skipped'}]
        self.sources=[{'key':'archived','label':'Previous source','enabled':False},{'key':'active','label':'Active source','enabled':True}]
        def respond(route):
            path=urlparse(route.request.url).path
            if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
            if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
            if route.request.method!='GET':self.writes.append(path)
            value={}
            if path=='/api/candidates':value={'active_id':'default','items':[{'id':'default','name':'Test','identity':{},'active':True}]}
            elif path=='/api/profile':value={'automation':{}}
            elif path=='/api/jobs':value=self.jobs
            elif path=='/api/pipeline':value=[self.jobs[0]]
            elif path=='/api/sources':value=self.sources
            elif path=='/api/queue':value={'counts':{},'items':[],'running':False}
            elif path in ['/api/accounts','/api/resumes','/api/platform-logins'] or path.endswith(('/stage-events','/human-review-events','/applications')):value=[]
            elif path.endswith('/letter'):value={'status':'ready','letter':'Test letter'}
            elif path=='/api/pfe':value={'settings':{},'jobs':[],'leads':[],'sources':[],'plan':[]}
            route.fulfill(json=value)
        self.page.route('**/*',respond)
        self.page.goto('http://parity.test/')
        expect(self.page.locator('#simpleModeToggle')).to_be_visible()
        self.page.evaluate("showView('jobs')")
        expect(self.page.locator('#cards .card')).to_have_count(2)

    def tearDown(self):
        self.browser.close();self.p.stop()

    def test_archived_source_and_selection_survive_source_refresh(self):
        expect(self.page.locator('#sourceSelect option[value=archived]')).to_have_count(1)
        self.page.select_option('#sourceSelect','archived')
        self.page.evaluate('loadSources()')
        expect(self.page.locator('#sourceSelect')).to_have_value('archived')
        expect(self.page.locator('#cards .card')).to_have_count(1)

    def test_export_unsubmitted_is_available_without_ai_review(self):
        self.page.locator('.review-export-panel summary').click()
        self.page.select_option('#reviewExportScope','unsubmitted')
        expect(self.page.locator('#reviewExportBtn')).to_be_enabled()
        expect(self.page.locator('#reviewExportCount')).to_contain_text('1 ')

    def test_queue_history_stays_open_during_background_refresh(self):
        self.page.evaluate("showView('pipeline')")
        detail=self.page.locator('#pipelineBoard details').last
        detail.locator('summary').click()
        self.page.evaluate('loadPipeline()')
        expect(detail).to_have_attribute('open','')
        self.assertEqual(self.errors,[])

    def test_job_details_stay_open_when_live_data_changes(self):
        detail=self.page.locator('#cards .card').first.locator('details.match-details')
        detail.locator('summary').click()
        self.jobs[0]['score']=90
        self.page.evaluate('load()')
        expect(detail).to_have_attribute('open','')
        self.assertEqual(self.errors,[])

    def test_full_status_filter_and_export_shortcut_are_visible_on_mobile(self):
        self.page.set_viewport_size({'width':375,'height':1000})
        expect(self.page.locator('#jobFilterSelect')).to_be_visible()
        self.page.select_option('#jobFilterSelect','skipped')
        expect(self.page.locator('#cards')).to_contain_text('Skipped role')
        expect(self.page.locator('#jobExportShortcut')).to_be_visible()
        self.page.locator('#jobExportShortcut').click()
        self.assertTrue(self.page.locator('.review-export-panel').evaluate('(e)=>e.open'))
        self.page.screenshot(path='tmp/workflow-parity-mobile.png',full_page=True)
        self.assertEqual(self.writes,[])

    def test_old_queue_controls_and_source_settings_remain_reachable(self):
        self.page.locator('#jobSourcesShortcut').click()
        expect(self.page.locator('#profileView')).to_be_visible()
        expect(self.page.locator('#search_queries_per_run')).to_be_focused()
        self.page.evaluate("showView('pipeline')")
        for identifier in ['queueReviewScope','queueReviewBtn','queueBatchBtn','queueRunBtn','queueStopBtn','queueClearBtn','queueAddMatchesBtn','queueFilter']:
            expect(self.page.locator('#'+identifier)).to_be_visible()
        self.page.evaluate("showView('jobs')")
        self.page.locator('#jobHealthShortcut').click()
        self.assertEqual(self.writes,[])
        self.assertEqual(self.errors,[])

    def test_letter_disclosure_and_translation_keep_the_selected_status(self):
        detail=self.page.locator('#cards .card').first.locator('.letter-panel')
        detail.locator('summary').click()
        expect(self.page.locator('#letter-1')).to_contain_text('Test letter')
        self.jobs[0]['score']=91
        self.page.evaluate('load()')
        expect(detail).to_have_attribute('open','')
        expect(self.page.locator('#letter-1')).to_contain_text('Test letter')
        self.page.select_option('#jobFilterSelect','skipped')
        self.page.evaluate("Locale.setLanguage('zh')")
        expect(self.page.locator('#jobFilterSelect')).to_have_value('skipped')
        expect(self.page.locator('#cards')).to_contain_text('Skipped role')
        self.page.screenshot(path='tmp/workflow-parity-desktop.png',full_page=True)
        self.assertEqual(self.errors,[])

    def test_source_failure_preserves_historical_filter(self):
        self.page.select_option('#sourceSelect','archived')
        self.sources={'detail':'Unavailable'}
        self.page.evaluate('loadSources()')
        expect(self.page.locator('#sourceSelect')).to_have_value('archived')
        expect(self.page.locator('#cards .card')).to_have_count(1)
        self.assertEqual(self.errors,[])

    def test_search_label_does_not_change_research_company_type_translation(self):
        self.page.evaluate("Locale.setLanguage('zh')")
        self.assertEqual(self.page.evaluate("Locale.t('Recherche')"),'科研机构')
