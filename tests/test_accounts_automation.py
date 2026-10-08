import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
from app import workspaces, secret_store, site_accounts, gmail_connection, db
from app.profile_store import load_profile_raw, save_profile_raw, active_resume_path
from app.main import app
from app.login_flow import login_if_needed, dismiss_optional_popups
from app.auto_submission import submit_complete_form


class CandidateTests(unittest.TestCase):
    def test_auto_enqueue_does_not_restart_a_paused_queue(self):
        client=TestClient(app)
        with patch('app.main.load_profile_raw',return_value={'automation':{'auto_start_queue':True}}),patch('app.main.queue_enqueue',return_value={'paused':True}),patch('app.main.queue_start') as start:
            self.assertEqual(client.post('/api/queue',json={'job_ids':[1]}).status_code,200)
            start.assert_not_called()
        with patch('app.main.load_profile_raw',return_value={'automation':{'auto_start_queue':True}}),patch('app.main.queue_enqueue',return_value={'paused':False}),patch('app.main.queue_start') as start:
            self.assertEqual(client.post('/api/queue',json={'job_ids':[1]}).status_code,200)
            start.assert_called_once_with('batch')

    @unittest.skipUnless(sys.platform=='win32','Actual credential encryption uses Windows DPAPI')
    def test_profile_db_resume_and_secrets_are_owned_and_new_profile_is_empty(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(workspaces,'ROOT',Path(folder)):
            token=workspaces.CURRENT.set('default')
            try:
                save_profile_raw({'identity':{'first_name':'Alice'},'application':{'legacy_resume_path':''}})
                db.init_db()
                with db.connect() as c: c.execute("INSERT INTO jobs(url,title) VALUES('https://example.test/1','Alice job')")
                site_accounts.save_account({'login_url':'https://example.test/login','username':'alice','password':'secret-alice','enabled':True})
                identifier=workspaces.create('Bob')
                workspaces.CURRENT.set(identifier)
                db.init_db()
                self.assertEqual(load_profile_raw()['identity']['first_name'],'')
                self.assertIsNone(active_resume_path())
                self.assertEqual(site_accounts.list_accounts(),[])
                with db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
                save_profile_raw({'identity':{'first_name':'Bob'}})
                workspaces.CURRENT.set('default')
                self.assertEqual(load_profile_raw()['identity']['first_name'],'Alice')
                self.assertNotIn('password',site_accounts.list_accounts()[0])
                self.assertNotIn(b'secret-alice',(workspaces.data_dir()/'secrets.dpapi').read_bytes())
                self.assertEqual(site_accounts.account_for('https://example.test/apply')['password'],'secret-alice')
                self.assertIsNone(site_accounts.account_for('https://evil.test/login'))
            finally:workspaces.CURRENT.reset(token)

    def test_busy_switch_and_stale_client_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(workspaces,'ROOT',Path(folder)):
            identifier=workspaces.create('Bob')
            with patch('app.worker_runtime.any_running',return_value=True):
                with self.assertRaises(ValueError):workspaces.activate(identifier)
            self.assertEqual(workspaces.active_id(),'default')
            client=TestClient(app)
            self.assertEqual(client.put('/api/profile',json={},headers={'X-Candidate-ID':identifier}).status_code,409)
            with patch('app.worker_runtime.any_running',return_value=False),patch('app.scan_manager.status',return_value={}),patch('app.queue_manager.status',return_value={}):
                workspaces.activate(identifier)
            self.assertEqual(workspaces.active_id(),identifier)
            self.assertEqual(client.get('/api/profile',headers={'X-Candidate-ID':'default'}).status_code,409)

    def test_gmail_requires_config_and_rejects_changed_profile_and_expired_state(self):
        config={'gmail_config':{'client_id':'client.apps.googleusercontent.com','client_secret':'test-secret'}}
        with patch.object(secret_store,'read',return_value={}):
            with self.assertRaises(ValueError):gmail_connection.begin()
        with patch.object(secret_store,'read',return_value=config),patch.object(gmail_connection,'candidate_id',return_value='default'),patch.object(gmail_connection,'active_id',return_value='default'):
            query=parse_qs(urlparse(gmail_connection.begin()['authorization_url']).query)
            self.assertEqual(query['scope'],[gmail_connection.SCOPE])
            self.assertEqual(query['code_challenge_method'],['S256'])
            self.assertNotIn('client_secret',query)
            state=query['state'][0]
            with patch.object(gmail_connection,'active_id',return_value='000000000001'),patch.object(gmail_connection,'urlopen') as network:
                with self.assertRaises(ValueError):gmail_connection.finish(state,'code')
                network.assert_not_called()
            query=parse_qs(urlparse(gmail_connection.begin()['authorization_url']).query)
            state=query['state'][0];gmail_connection._pending[state]['expires']=0
            with self.assertRaises(ValueError):gmail_connection.finish(state,'code')

    def test_gmail_callback_saves_only_verified_refresh_token_and_is_single_use(self):
        config={'gmail_config':{'client_id':'client.apps.googleusercontent.com','client_secret':'test-secret'}}
        import io
        with patch.object(secret_store,'read',return_value=config),patch.object(gmail_connection,'candidate_id',return_value='default'),patch.object(gmail_connection,'active_id',return_value='default'):
            state=parse_qs(urlparse(gmail_connection.begin()['authorization_url']).query)['state'][0]
            responses=[io.BytesIO(json.dumps({'access_token':'access','refresh_token':'refresh','scope':gmail_connection.SCOPE}).encode()),io.BytesIO(b'{"emailAddress":"alice@example.test"}')]
            with patch.object(gmail_connection,'urlopen',side_effect=responses),patch.object(secret_store,'update',side_effect=lambda fn:fn(config)):
                self.assertEqual(gmail_connection.finish(state,'code'),'alice@example.test')
            self.assertEqual(config['gmail_connection'],{'refresh_token':'refresh','email':'alice@example.test'})
            with self.assertRaises(ValueError):gmail_connection.finish(state,'code')
            with patch.object(secret_store,'read',return_value=config):
                self.assertNotIn('refresh_token',gmail_connection.status())

    def test_uncertain_dispatch_persists_and_worker_refuses_to_send_again(self):
        from app.apply_worker import main
        import app.db as database
        with tempfile.TemporaryDirectory() as folder,patch.object(database,'DB_PATH',Path(folder)/'jobs.db'):
            database.init_db()
            audit=Path(folder)/'audit.json'
            audit.write_text(json.dumps({'submission':{'status':'dispatching'}}),encoding='utf-8')
            with database.connect() as c:
                c.execute("INSERT INTO jobs(id,url,title,application_step,fill_audit_path) VALUES(1,'https://example.test/job','Job','submission_check',?)",(str(audit),))
            with patch('app.apply_worker.load_profile_raw',return_value={}),patch('app.apply_worker.runtime_profile',return_value={}),patch('app.apply_worker.sync_playwright') as browser:
                main(1)
                browser.assert_not_called()
            with database.connect() as c:
                self.assertEqual(c.execute('SELECT application_status FROM jobs WHERE id=1').fetchone()[0],'needs_human')


class AutomationBrowserTests(unittest.TestCase):
    def test_login_password_never_goes_to_foreign_action_signup_or_duplicate_button(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page()
                page.route('https://recruiter.test/**',lambda r:r.fulfill(content_type='text/html',body='<form action="https://evil.test/steal"><input type=email><input type=password><button>Sign in</button></form>'))
                page.goto('https://recruiter.test/login')
                account={'origin':'https://recruiter.test','username':'alice@example.test','password':'private'}
                with patch('app.login_flow.account_for',return_value=account):
                    self.assertEqual(login_if_needed(page)['status'],'handoff')
                    self.assertEqual(page.locator('input[type=password]').input_value(),'')
                    page.set_content('<form><input type=email><input type=password><input type=password><button>Sign in</button></form>')
                    self.assertEqual(login_if_needed(page)['status'],'handoff')
                    page.set_content('<form><input type=email><input type=password><button>Sign in</button><button>Sign in</button></form>')
                    self.assertEqual(login_if_needed(page)['status'],'handoff')
                    self.assertEqual(page.locator('input[type=password]').input_value(),'')
                    page.set_content('<form onsubmit="event.preventDefault();document.body.innerHTML=\'<input autocomplete=one-time-code>\'"><input type=email><input type=password><button>Sign in</button></form>')
                    self.assertEqual(login_if_needed(page)['status'],'handoff')
                    page.set_content('<form onsubmit="event.preventDefault();document.body.innerHTML=\'<h1>My applications</h1>\'"><input type=email><input type=password><button>Sign in</button></form>')
                    self.assertEqual(login_if_needed(page)['status'],'logged_in')
            finally:browser.close()

    def test_popup_handler_leaves_application_dialog_open(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page();page.set_content('<div role=dialog><form><input><button onclick="window.closed=true">Close</button></form></div><button onclick="window.rejected=true">Reject all</button>')
                dismiss_optional_popups(page)
                self.assertTrue(page.evaluate('Boolean(window.rejected)'))
                self.assertFalse(page.evaluate('Boolean(window.closed)'))
            finally:browser.close()

    def test_final_submit_guard_and_verified_success(self):
        audit={'documents':{'resume_attached':True,'letter_generated':False},'required_unanswered_count':0,'sensitive_or_legal_unanswered_count':0,'report':{}}
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page();page.set_content('<form onsubmit="event.preventDefault();window.sent=(window.sent||0)+1;document.body.innerHTML=\'<p>We have received your application</p>\'"><button>Submit application</button></form>')
                audit['required_unanswered_count']=1
                self.assertEqual(submit_complete_form(page,page,audit)['status'],'blocked')
                self.assertEqual(page.evaluate('window.sent||0'),0)
                audit['required_unanswered_count']=0;calls=[]
                self.assertEqual(submit_complete_form(page,page,audit,before_click=lambda:calls.append('persist'))['status'],'verified')
                self.assertEqual(calls,['persist'])
                self.assertEqual(page.evaluate('window.sent'),1)
                self.assertEqual(submit_complete_form(page,page,audit)['status'],'blocked')
                self.assertEqual(page.evaluate('window.sent'),1)
            finally:browser.close()

    def test_accounts_ui_six_languages_redaction_and_candidate_header(self):
        static=Path(__file__).resolve().parents[1]/'static'
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page();errors=[];requests=[];writes=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                def respond(route):
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(static/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):route.fulfill(path=str(static/path.removeprefix('/static/')));return
                    requests.append((path,route.request.headers))
                    if route.request.method=='POST':writes.append((path,route.request.post_data))
                    data=[]
                    if path=='/api/candidates':data={'active_id':'default','items':[{'id':'default','name':'Alice','identity':{},'active':True}]}
                    elif path=='/api/profile':data={'automation':{'auto_submit':True,'auto_start_queue':True}}
                    elif path=='/api/jobs':data=[{'id':8,'title':'Reception','company':'Hotel','url':'https://recruiter.test/8','decision':'keep','score':95}]
                    elif path=='/api/health':data={'resume_ok':True,'cdp_ok':True}
                    elif path=='/api/gmail':data={'configured':False,'connected':False}
                    elif path not in {'/api/accounts','/api/jobs','/api/sources','/api/resumes','/api/pipeline'}:data={}
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://ui.test/')
                page.locator('#accountsNav').wait_for()
                for language in ['zh','fr','en','de','es','pt']:
                    page.evaluate('(language)=>Locale.setLanguage(language)',language)
                    page.locator('#accountsNav').click()
                    page.locator('#accountPassword').wait_for()
                    self.assertEqual(page.locator('#accountPassword').get_attribute('type'),'password')
                    self.assertEqual(page.locator('#accountPassword').input_value(),'')
                    self.assertFalse(page.locator('#gmailConnect').is_enabled())
                    self.assertEqual(page.evaluate('Accounts.words[Locale.language].length'),34)
                    page.locator('#accountsClose').click()
                page.locator('#coachAutomate').click()
                page.wait_for_function('!document.getElementById("pipelineView").classList.contains("hidden")')
                self.assertEqual(writes,[('/api/queue',json.dumps({'job_ids':[8]},separators=(',',':')))])
                self.assertEqual(errors,[])
                self.assertTrue(all(headers.get('x-candidate-id')=='default' for path,headers in requests if path!='/api/candidates'))
            finally:browser.close()
