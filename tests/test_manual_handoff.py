import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from app import db
from app import queue_manager as queue
from app.apply_worker import _update_status
from app.main import app
from app.manual_handoff import focus_existing, take_over
from app.repositories.jobs import JobRepository


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, 'DB_PATH', Path(self.temp.name) / 'jobs.db')
        self.db_patch.start(); db.init_db()
        with db.connect() as c:
            c.execute("INSERT INTO jobs(id,title,url,application_status) VALUES(1,'Reception','https://example.test/job','needs_human')")

    def tearDown(self):
        self.db_patch.stop(); self.temp.cleanup()

    def test_focus_uses_recorded_target_after_redirect_without_reload_or_submission(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                page = context.new_page(); page.goto('about:blank')
                page.set_content('<form><input name="answer"><button>Send</button></form>')
                page.locator('input').fill('Unsent human answer')
                page.evaluate('() => {window.submits=0;document.querySelector("form").onsubmit=e=>{e.preventDefault();window.submits++}}')
                other = context.new_page()
                session = context.new_cdp_session(page)
                target = session.send('Target.getTargetInfo')['targetInfo']['targetId']; session.detach()
                focus_existing(context, {'url':'https://example.test/previous-url','application_tab_id':target})
                self.assertEqual(page.locator('input').input_value(),'Unsent human answer')
                self.assertEqual(page.evaluate('window.submits'),0)
                self.assertEqual(len(context.pages),2)
                with self.assertRaises(ValueError): focus_existing(context, {'url':page.url})  # Ambiguous legacy tabs.
                with self.assertRaises(ValueError): focus_existing(context, {'url':page.url,'application_tab_id':'closed-target'})
            finally: browser.close()

    def test_active_worker_and_running_queue_cannot_be_taken_over(self):
        with patch('app.manual_handoff.is_running',return_value=True),patch('app.manual_handoff.sync_playwright') as browser:
            self.assertEqual(TestClient(app).post('/api/jobs/1/take-over').status_code,409)
            browser.assert_not_called()
        with db.connect() as c:
            c.execute("INSERT INTO application_queue(job_id,status) VALUES(1,'running')")
        with patch('app.manual_handoff.is_running',return_value=False),patch('app.manual_handoff.sync_playwright') as browser:
            with self.assertRaises(ValueError): take_over(1)
            browser.assert_not_called()
        self.assertEqual(TestClient(app).post('/api/jobs/999/take-over').status_code,404)

    def test_closed_tab_reopens_job_then_reuses_new_tab_without_automated_submission(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                context=browser.new_context()
                context.route('https://example.test/**',lambda route:route.fulfill(content_type='text/html',body='<form onsubmit="event.preventDefault();window.submitted=true"><input name="answer"><button>Send</button></form>'))
                old=context.new_page();old.goto('https://example.test/job');old.locator('input').fill('Old unsent data')
                session=context.new_cdp_session(old);target=session.send('Target.getTargetInfo')['targetInfo']['targetId'];session.detach();old.close()
                with db.connect() as c:c.execute('UPDATE jobs SET application_tab_id=? WHERE id=1',(target,))
                created=[]
                create_context=browser.new_context
                def isolated_context(**kwargs):
                    owned=create_context(**kwargs)
                    owned.route('https://example.test/**',lambda route:route.fulfill(content_type='text/html',body='<form onsubmit="event.preventDefault();window.submitted=true"><input name="answer"><button>Send</button></form>'))
                    created.append(owned)
                    return owned
                with patch.object(browser,'new_context',side_effect=isolated_context),patch('app.secret_store.read',return_value={}),patch('app.manual_handoff.sync_playwright') as fake,patch('app.manual_handoff.runtime_profile',return_value={'browser_mode':'cdp'}):
                    fake.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value=browser
                    result=take_over(1)
                    self.assertEqual(result['action'],'opened')
                    self.assertEqual(len(context.pages),0)
                    owned=created[0]
                    new=owned.pages[0]
                    self.assertEqual(new.url,'https://example.test/job')
                    self.assertEqual(new.locator('input').input_value(),'')
                    self.assertFalse(new.evaluate('Boolean(window.submitted)'))
                    self.assertIn('ne sont pas restaurées',result['message'])
                    self.assertEqual(take_over(1)['action'],'focused')
                    self.assertEqual(len(owned.pages),1)
                self.assertEqual(JobRepository().list()[0]['application_status'],'needs_human')
            finally:browser.close()

    def test_manual_submission_resolves_failed_or_running_queue_and_resists_late_worker(self):
        with db.connect() as c:
            c.execute("UPDATE jobs SET application_status='error' WHERE id=1")
            c.execute("INSERT INTO application_queue(job_id,status,note) VALUES(1,'running','old failure')")
            c.execute("INSERT INTO applications(job_id,status,note) VALUES(1,'apply_error','Old failure preserved')")
        with patch('app.main.cancel_worker') as cancel:
            self.assertEqual(TestClient(app).post('/api/jobs/1/application-status',json={'status':'submitted'}).status_code,200)
            cancel.assert_called_with('app.apply_worker',1)
        for late in ['error','prefilled','cancelled']:_update_status(1,late,application_step='handoff')
        job=JobRepository().list()[0]
        self.assertEqual(job['application_status'],'submitted')
        self.assertEqual(job['tracker_stage'],'submitted')
        self.assertEqual(queue.status()['counts'],{'done':1})
        self.assertIn('Old failure preserved',[e['note'] for e in JobRepository().history(1)])
        with patch('app.manual_handoff.sync_playwright') as browser:
            self.assertEqual(TestClient(app).post('/api/jobs/1/take-over').status_code,409)
            browser.assert_not_called()
        with self.assertRaises(ValueError):queue.retry(1)
        JobRepository().track(1,'interview',note='Recruiter call',source='phone')
        with db.connect() as c:c.execute("UPDATE application_queue SET status='error' WHERE job_id=1")
        JobRepository().set_application_status(1,'submitted')
        self.assertEqual(queue.status()['counts'],{'done':1})
        self.assertEqual(JobRepository().list()[0]['tracker_stage'],'interview')
        with db.connect() as c:
            c.execute("INSERT INTO jobs(id,title,url,application_status) VALUES(2,'Still failed','https://example.test/2','error')")
            c.execute("INSERT INTO application_queue(job_id,status) VALUES(2,'error')")
        queue.clear_finished()
        self.assertEqual(queue.status()['counts'],{'error':1})
        self.assertEqual(queue.status()['items'][0]['job_id'],2)

    def test_disconnected_browser_reports_actionable_error_without_changing_submission(self):
        with patch('app.manual_handoff.runtime_profile',return_value={'browser_mode':'cdp'}),patch('app.manual_handoff.sync_playwright',side_effect=RuntimeError('offline')):
            result=TestClient(app).post('/api/jobs/1/take-over')
        self.assertEqual(result.status_code,409)
        self.assertIn('start.bat',result.json()['detail'])
        self.assertEqual(JobRepository().list()[0]['application_status'],'needs_human')

    def test_actual_failure_and_last_step_are_available_in_queue_and_pipeline(self):
        _update_status(1,'preparing',application_step='finding_form')
        _update_status(1,'error')
        with db.connect() as c:
            c.execute("INSERT INTO application_queue(job_id,status,note) VALUES(1,'error','error')")
            c.execute("INSERT INTO applications(job_id,status,note) VALUES(1,'apply_error','Form unavailable')")
        item=queue.status()['items'][0]
        self.assertEqual(item['application_step'],'finding_form')
        self.assertTrue(item['application_step_at'])
        self.assertEqual(item['note'],'Form unavailable')
        self.assertNotIn('fill_audit_path',item)
        self.assertEqual(JobRepository().pipeline()[0]['application_error'],'Form unavailable')
