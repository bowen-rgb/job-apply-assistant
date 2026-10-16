import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import db, application_safety as safety
from app.apply_worker import _update_status
from app.main import app
from app.repositories.jobs import JobRepository


class ApplicationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = {'identity': {'name': 'Candidate'}, 'application': {}}
        self.cv = self.root / 'cv.pdf'
        self.cv.write_bytes(b'CV version one')
        for target, value in [('app.db.DB_PATH', self.root / 'jobs.db'),
                              ('app.main.data_dir', lambda: self.root),
                              ('app.application_safety.data_dir', lambda: self.root),
                              ('app.application_safety.load_profile_raw', lambda: self.raw),
                              ('app.application_safety.select_resume_for_job', lambda *args: (self.cv, {}))]:
            p = patch(target, value); p.start(); self.addCleanup(p.stop)
        db.init_db()
        with db.connect() as c:
            c.execute("INSERT INTO jobs(id,url,title,body,application_status) VALUES(1,'https://recruiter.test/job','Reception','Original JD','needs_human')")
        self.jobs = JobRepository()
        self.client = TestClient(app)
        self.prepare()

    def prepare(self, **kwargs):
        self.snapshot = safety.freeze_materials(safety.get_job(1), self.raw, self.cv, **kwargs)
        audit = self.root / 'application_audits' / 'job_1.json'
        audit.parent.mkdir(exist_ok=True)
        audit.write_text(json.dumps({'job_id': 1, 'materials': self.snapshot}), encoding='utf-8')
        with db.connect() as c:
            c.execute('UPDATE jobs SET fill_audit_path=? WHERE id=1', (str(audit),))

    def approve(self):
        safety.approve_materials(1, self.snapshot['token'])

    def result(self):
        return {'status': 'verified', 'reason': 'confirmation_text:we have received your application',
                'confirmation_text': 'We have received your application.', 'confirmation_url': 'https://recruiter.test/thanks'}

    def test_generic_api_repository_and_worker_cannot_fabricate_verification(self):
        self.assertEqual(self.client.post('/api/jobs/1/application-status', json={'status': 'submitted_verified'}).status_code, 422)
        for setter in (self.jobs.set_application_status, _update_status):
            with self.assertRaises(ValueError): setter(1, 'submitted_verified')
        with self.assertRaises(ValueError): safety.record_verified(1, 'invented', self.result())
        self.assertEqual(safety.get_job(1)['application_status'], 'needs_human')

    def test_approval_requires_acknowledgment_and_current_token(self):
        url = '/api/jobs/1/materials/approve'
        self.assertEqual(self.client.post(url, json={'token': self.snapshot['token']}).status_code, 422)
        self.assertEqual(self.client.post(url, json={'token': self.snapshot['token'], 'acknowledged': False}).status_code, 422)
        self.assertEqual(self.client.post(url, json={'token': '0'*64, 'acknowledged': True}).status_code, 409)
        self.assertEqual(self.client.post(url, json={'token': self.snapshot['token'], 'acknowledged': True}).status_code, 200)
        self.assertEqual(self.client.get('/api/jobs/1/materials').json()['status'], 'approved')
        self.assertFalse(safety.has_dispatch(1))

    def test_approval_is_required_before_dispatch_and_dispatch_is_never_retried(self):
        with self.assertRaises(ValueError): safety.begin_dispatch(1, self.snapshot)
        self.approve()
        attempt = safety.begin_dispatch(1, self.snapshot)
        self.assertTrue(attempt)
        _update_status(1, 'error', application_step='handoff')
        with self.assertRaises(ValueError): safety.begin_dispatch(1, self.snapshot)
        from app import apply_worker
        with patch.object(apply_worker, 'load_profile_raw', return_value=self.raw), patch.object(apply_worker, 'runtime_profile', return_value={}), patch.object(apply_worker, 'can_prepare', return_value=True), patch.object(apply_worker, '_open_browser') as browser:
            apply_worker.main(1)
            browser.assert_not_called()
        self.assertEqual(safety.get_job(1)['application_step'], 'submission_check')

    def test_changed_cv_jd_and_profile_invalidate_approval(self):
        self.approve()
        self.cv.write_bytes(b'Changed CV')
        self.assertFalse(safety.is_approved(safety.get_job(1), self.raw, self.snapshot))
        self.assertEqual(self.client.get('/api/jobs/1/materials').json()['status'], 'stale')
        # The downloadable version remains the bytes actually used by the filler.
        self.assertEqual(self.client.get('/api/jobs/1/materials/resume').content, b'CV version one')
        self.prepare(); self.approve()
        with db.connect() as c: c.execute("UPDATE jobs SET body='New working hours' WHERE id=1")
        with self.assertRaises(ValueError): safety.begin_dispatch(1, self.snapshot)
        self.prepare(); self.approve()
        self.raw['identity']['name'] = 'Another candidate'
        with self.assertRaises(ValueError): safety.begin_dispatch(1, self.snapshot)

    def test_letter_packet_and_selected_cv_changes_require_new_approval(self):
        letter, packet = self.root/'letter.pdf', self.root/'packet.pdf'
        for changed in (letter, packet):
            letter.write_bytes(b'Letter'); packet.write_bytes(b'Packet')
            self.prepare(letter=letter, packet=packet); self.approve()
            changed.write_bytes(b'Edited')
            with self.assertRaises(ValueError): safety.begin_dispatch(1, self.snapshot)
        self.prepare(); self.approve()
        other = self.root/'other.pdf'; other.write_bytes(self.cv.read_bytes())
        with patch.object(safety, 'select_resume_for_job', return_value=(other, {})):
            with self.assertRaises(ValueError): safety.begin_dispatch(1, self.snapshot)

    def test_stable_material_versions_allow_preparation_after_approval(self):
        self.approve()
        original = self.snapshot['token']
        self.prepare()
        self.assertEqual(self.snapshot['token'], original)
        self.assertTrue(safety.is_approved(safety.get_job(1), self.raw, self.snapshot))

    def test_stale_approval_and_modified_sealed_document_are_rejected(self):
        self.approve()
        sealed = Path(self.snapshot['documents'][0]['path'])
        sealed.write_bytes(b'Tampered sealed copy')
        self.assertEqual(self.client.get('/api/jobs/1/materials/resume').status_code, 404)
        self.assertEqual(self.client.post('/api/jobs/1/materials/approve', json={'token': self.snapshot['token'], 'acknowledged': True}).status_code, 409)
        with self.assertRaises(ValueError): safety.begin_dispatch(1, self.snapshot)

    def test_receipt_requires_observation_and_detects_tampering(self):
        with db.connect() as c:
            c.execute("INSERT INTO application_queue(job_id,status) VALUES(1,'running')")
        self.approve(); attempt = safety.begin_dispatch(1, self.snapshot)
        result = self.result(); result['confirmation_text'] = 'The form is still open'
        with self.assertRaises(ValueError): safety.record_verified(1, attempt, result)
        safety.record_verified(1, attempt, self.result())
        job = self.jobs.list()[0]
        self.assertEqual(job['application_status'], 'submitted_verified')
        self.assertEqual(job['verification_state'], 'verified')
        audit = self.client.get('/api/jobs/1/audit').json()
        self.assertEqual(audit['verification_state'], 'verified')
        self.assertEqual(audit['submission_receipt']['attempt_id'], attempt)
        from app.queue_manager import status
        queued = status()['items'][0]
        self.assertEqual(queued['verification_state'], 'verified')
        self.assertEqual(queued['status'], 'done')
        other = self.root/'other-candidate'; other.mkdir()
        with patch.object(safety, 'data_dir', return_value=other):
            self.assertEqual(self.jobs.list()[0]['verification_state'], 'unverified')
        receipt = next((self.root/'submission_receipts').glob('*.json'))
        receipt.write_text('{}', encoding='utf-8')
        self.assertEqual(self.jobs.list()[0]['verification_state'], 'unverified')

    def test_legacy_status_is_not_presented_as_verified(self):
        with db.connect() as c: c.execute("UPDATE jobs SET application_status='submitted_verified' WHERE id=1")
        self.assertEqual(self.jobs.list()[0]['verification_state'], 'unverified')
        self.assertEqual(self.jobs.pipeline()[0]['verification_state'], 'unverified')

    def test_terminal_status_and_recruiter_response_survive_late_workers(self):
        self.approve(); attempt = safety.begin_dispatch(1, self.snapshot)
        self.jobs.set_application_status(1, 'submitted')
        self.jobs.track(1, 'interview', 'Interview confirmed', source='email')
        safety.record_verified(1, attempt, self.result())
        self.assertEqual(safety.get_job(1)['tracker_stage'], 'interview')
        self.jobs.track(1, 'submitted')
        self.assertEqual(safety.get_job(1)['tracker_stage'], 'interview')
        self.assertEqual(self.client.post('/api/jobs/1/application-status', json={'status': ''}).status_code, 409)
        with self.assertRaises(ValueError): self.jobs.track(1, 'saved')

    def test_cross_candidate_snapshot_and_download_are_rejected(self):
        other = self.root/'other-candidate'; other.mkdir()
        with patch.object(safety, 'data_dir', return_value=other):
            self.assertEqual(self.client.get('/api/jobs/1/materials').json()['status'], 'missing')
            self.assertEqual(self.client.get('/api/jobs/1/materials/resume').status_code, 404)
            with self.assertRaises(ValueError): safety.begin_dispatch(1, self.snapshot)
        self.assertEqual(self.client.get('/api/jobs/1/materials/../../cv.pdf').status_code, 404)


class MaterialReviewUITests(unittest.TestCase):
    def test_review_dialog_is_explicit_safe_and_responsive(self):
        from playwright.sync_api import sync_playwright, expect
        root = Path(__file__).resolve().parents[1]
        posts = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            def respond(route):
                from urllib.parse import urlparse
                path = urlparse(route.request.url).path
                if path == '/': route.fulfill(path=str(root/'static/index.html'), content_type='text/html')
                elif path.startswith('/static/'): route.fulfill(path=str(root/path.lstrip('/')))
                elif path == '/api/jobs/1/materials':
                    route.fulfill(json={'status': 'approved' if posts else 'pending', 'token': 'a'*64,
                        'documents': [{'role': 'resume', 'name': '<img src=x onerror=alert(1)>.pdf'}], 'inline_text': 'A reviewed cover letter.'})
                elif path == '/api/jobs/1/materials/approve':
                    posts.append(json.loads(route.request.post_data)); route.fulfill(json={'ok': True})
                else: route.fulfill(json=[] if path in {'/api/jobs','/api/pipeline','/api/sources'} else {})
            page.route('**/*', respond)
            page.goto('http://dashboard.test/')
            page.evaluate('window.openMaterials(1)')
            dialog = page.locator('#materialReviewDialog')
            expect(dialog).to_be_visible()
            expect(dialog.locator('#approveMaterials')).to_be_disabled()
            self.assertEqual(dialog.locator('img').count(), 0)
            for width in (1280, 390):
                page.set_viewport_size({'width': width, 'height': 900})
                self.assertLessEqual(dialog.bounding_box()['width'], width-20)
                page.screenshot(path=str(root/'data'/f'material-review-{width}.png'))
            dialog.locator('#materialAcknowledged').check()
            bounds = dialog.locator('#materialAcknowledged').bounding_box()
            self.assertGreaterEqual(bounds['height'], 18)
            dialog.locator('#approveMaterials').click()
            expect(dialog.locator('#approveMaterials')).to_have_count(0)
            self.assertEqual(posts, [{'token': 'a'*64, 'acknowledged': True}])
            page.keyboard.press('Escape')
            expect(dialog).not_to_be_visible()
            browser.close()


if __name__ == '__main__':
    unittest.main()
