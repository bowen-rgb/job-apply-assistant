import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import zxingcpp
from fastapi.testclient import TestClient

from app import workspaces, db, profile_store as store, qr_application as qr, application_safety as safety
from app.main import app
from playwright.sync_api import sync_playwright
from unittest.mock import MagicMock

class QRTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.patch=patch.object(workspaces,'ROOT',self.root);self.patch.start()
        self.token=workspaces.CURRENT.set('default')
        db.init_db()
        raw=store.default_profile()
        raw['identity'].update(first_name='Test',last_name='Candidate',email='test@example.invalid')
        raw['application'].update(generate_cover_letter=False,auto_resume_routing=True)
        store.save_profile_raw(raw)
        for name,tags in [('A_Simulation',['simulation']),('D_Robotique',['robotique','commande']),('Forum',[])]:
            from reportlab.pdfgen.canvas import Canvas
            path=self.root/(name+'.pdf');canvas=Canvas(str(path))
            canvas.drawString(40,780,name)
            canvas.drawString(40,750,{'A_Simulation':'Simulation numerique et validation de modeles Python',
                                    'D_Robotique':'Robotique commande PID et simulation du quadrirotor',
                                    'Forum':'Profil generaliste et accueil de projets industriels'}[name])
            canvas.save()
            row=store.add_resume(path,path.name,name);store.update_resume_metadata(row['id'],tags=tags)
        self.page=b'''<html><head><script type="application/ld+json">{"@type":"JobPosting","title":"Stage robotique commande","hiringOrganization":{"name":"Test Robotics"},"description":"Simulation et commande robotique pour un projet industriel."}</script></head><body><input type=file></body></html>'''
    def tearDown(self):
        workspaces.CURRENT.reset(self.token);self.patch.stop();self.temp.cleanup()
    def preview(self):
        with patch.object(qr,'validate_destination'),patch.object(qr,'read_public',return_value=(self.page,'text/html','https://employer.test/apply')):
            return qr.create_request('https://short.test/qr')


    def test_draft_collection_remove_and_candidate_isolation(self):
        first=self.preview();second=self.preview()
        self.assertEqual(len(qr.list_requests()),2)
        client=TestClient(app)
        self.assertEqual(client.delete('/api/qr/'+first['id']).status_code,200)
        self.assertEqual(len(client.get('/api/qr').json()),1)
        with self.assertRaises(KeyError):qr.get_request(first['id'])
        other=workspaces.create('Other');workspaces.CURRENT.set(other);db.init_db()
        self.assertEqual(qr.list_requests(),[])
        with patch.object(workspaces,'active_id',return_value=other):
            self.assertEqual(client.delete('/api/qr/'+second['id']).status_code,404)
        workspaces.CURRENT.set('default')
        with db.connect() as c:c.execute("UPDATE qr_requests SET state='authorized' WHERE id=?",(second['id'],))
        self.assertEqual(client.delete('/api/qr/'+second['id']).status_code,409)
        self.assertEqual(len(qr.list_requests()),1)

    def test_removing_running_inspection_cancels_reader_and_deletes_only_draft(self):
        item=self.preview()
        with patch('app.worker_runtime.is_running',return_value=True),patch('app.worker_runtime.cancel') as cancel:
            qr.remove_request(item['id'])
            cancel.assert_called_once_with('app.qr_inspect_worker',item['id'])
        with self.assertRaises(KeyError):qr.get_request(item['id'])

    def test_portal_never_authorizes_or_generates_letter(self):
        from app.cover_letter import generation_payload
        from app.application_target import requires_letter
        with patch.object(qr,'validate_destination'),patch.object(qr,'read_public',return_value=(b'<html><title>Careers opportunities in CMA CGM Group</title><body>Find a job<input type=file></body></html>','text/html','https://employer.test/')):
            item=qr.create_request('https://employer.test/')
        self.assertEqual(item['preview']['company'],'CMA CGM Group')
        self.assertFalse(item['preview']['readiness']['ready'])
        with patch('app.browser_control.require_connection'),patch('app.worker_runtime.any_running',return_value=False),patch('app.browser.launch_apply') as launch:
            with self.assertRaisesRegex(ValueError,'qr_context_incomplete'):qr.start_request(item['id'],store.list_resumes()[0]['id'],'CMA CGM Group')
            launch.assert_not_called()
        with self.assertRaises(ValueError):generation_payload({'provider_key':'qr','application_context_json':json.dumps(item['preview'])},{},None)
        self.assertFalse(requires_letter({'application_context_json':json.dumps({'kind':'general'})},{'application':{'generate_cover_letter':True}}))

    def test_edited_company_stays_consistent_in_material_context(self):
        item=self.preview()
        with patch('app.browser_control.require_connection'),patch('app.worker_runtime.any_running',return_value=False),patch.object(qr,'validate_destination'),patch('app.browser.launch_apply'):
            result=qr.start_request(item['id'],item['preview']['resume_id'],'Confirmed Robotics')
        job=safety.get_job(result['job_id'])
        self.assertEqual(job['company'],'Confirmed Robotics')
        self.assertEqual(json.loads(job['application_context_json'])['company'],job['company'])


    def test_draft_resume_and_company_selection_persist_without_application(self):
        item=self.preview();rid=store.list_resumes()[0]['id']
        updated=qr.save_selection(item['id'],rid,'Confirmed Employer')
        reread=qr.request_status(item['id'])
        self.assertEqual(reread['preview']['resume_id'],rid)
        self.assertEqual(reread['preview']['user_resume_id'],rid)
        self.assertEqual(reread['preview']['company'],'Confirmed Employer')
        self.assertEqual(reread['state'],'draft');self.assertIsNone(reread['job_id'])
        with db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)


    def test_role_selection_updates_the_same_card_and_preserves_import_name(self):
        with patch.object(qr,'validate_destination'),patch.object(qr,'read_public',return_value=(self.page,'text/html','https://employer.test/apply')):
            item=qr.create_request('https://short.test/qr','C:/photos/stand.png')
        rid=item['preview']['resume_id'];qr.save_selection(item['id'],rid,'Test Robotics')
        with patch.object(qr,'validate_destination'),patch.object(qr,'read_public',return_value=(self.page.replace(b'Stage robotique commande',b'Stage commande simulation'),'text/html','https://employer.test/job/second')):
            result=qr.set_target(item['id'],'https://employer.test/job/second')
        self.assertEqual(result['id'],item['id'])
        self.assertEqual(len(qr.list_requests()),1)
        self.assertEqual(result['preview']['source_name'],'stand.png')
        self.assertEqual(result['preview']['original_qr_url'],'https://short.test/qr')
        self.assertEqual(result['preview']['resume_id'],rid)
        self.assertEqual(result['state'],'draft');self.assertIsNone(result['job_id'])
        with db.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
            c.execute("UPDATE qr_requests SET state='authorized' WHERE id=?",(item['id'],))
        with self.assertRaisesRegex(ValueError,'qr_already_started'):qr.set_target(item['id'],'https://employer.test/job/no')


    def test_company_edit_does_not_freeze_automatically_chosen_resume(self):
        item=self.preview();rid=item['preview']['resume_id']
        qr.save_selection(item['id'],rid,'Confirmed Robotics',False)
        self.assertNotIn('user_resume_id',qr.request_status(item['id'])['preview'])
        qr.save_selection(item['id'],rid,'Confirmed Robotics',True)
        self.assertEqual(qr.request_status(item['id'])['preview']['user_resume_id'],rid)

    def test_real_qr_decoder_and_multiple_codes_blank_and_bad_inputs(self):
        def code(text):return Image.fromarray(zxingcpp.create_barcode(text,zxingcpp.BarcodeFormat.QRCode).to_image(scale=5)).convert('RGB')
        first=code('https://example.org/first');second=code('https://example.org/second')
        canvas=Image.new('RGB',(first.width+second.width+60,max(first.height,second.height)+40),'white')
        canvas.paste(first,(10,10));canvas.paste(second,(first.width+40,10))
        output=io.BytesIO();canvas.save(output,format='PNG')
        self.assertEqual(set(qr.decode_image(output.getvalue())),{'https://example.org/first','https://example.org/second'})
        blank=io.BytesIO();Image.new('RGB',(100,100),'white').save(blank,format='PNG')
        for content,error in [(blank.getvalue(),'qr_no_code'),(b'not an image','qr_image_format'),(b'x'*(qr.MAX_IMAGE+1),'qr_image_size')]:
            with self.assertRaisesRegex(ValueError,error):qr.decode_image(content)

    def test_page_company_evidence_and_job_resume_routing(self):
        result=self.preview()
        p=result['preview']
        self.assertEqual(p['company'],'Test Robotics')
        self.assertEqual(p['company_evidence'],'JobPosting.hiringOrganization')
        self.assertEqual(p['kind'],'vacancy')
        self.assertEqual(next(r['label'] for r in result['resumes'] if r['id']==p['resume_id']),'D_Robotique')
        with patch.object(qr,'validate_destination'),patch.object(qr,'read_public',return_value=(b'<html><head><title>Careers</title></head><body><input type=file>Mechanical company</body></html>','text/html','https://employer.test/general')):
            p=qr.create_request('https://employer.test/general')['preview']
            self.assertEqual(p['kind'],'entry')
            self.assertEqual(next(r['label'] for r in store.list_resumes() if r['id']==p['resume_id']),'Forum')
            self.assertEqual(p['company'],'')
        with patch.object(qr,'validate_destination'),patch.object(qr,'read_public',return_value=(b'<html><head><title>Robotics careers</title></head><body><input type=file>robotics control systems</body></html>','text/html','https://employer.test/general')):
            p=qr.create_request('https://employer.test/general')['preview']
            self.assertEqual(p['resume_reason'],'qr_resume_sector')
            self.assertEqual(next(r['label'] for r in store.list_resumes() if r['id']==p['resume_id']),'D_Robotique')

    def test_unsafe_mobile_and_expired_links(self):
        for url in ['weixin://profile/a','https://weixin.qq.com/a']:
            with self.assertRaisesRegex(ValueError,'qr_mobile_only'):qr.inspect_url(url)
        for url in ['file:///local/cv','javascript:alert(1)','http://127.0.0.1/a']:
            with self.assertRaises(ValueError):qr.inspect_url(url)
        with patch.object(qr,'validate_destination'),patch.object(qr,'read_public',return_value=(b'<html>QR code expired</html>','text/html','https://employer.test/old')):
            with self.assertRaisesRegex(ValueError,'qr_expired'):qr.inspect_url('https://employer.test/old')

    def test_scoped_start_never_enables_global_queue_and_replay_is_rejected(self):
        result=self.preview();identifier=result['id'];rid=result['preview']['resume_id']
        with patch('app.browser_control.require_connection'),patch('app.worker_runtime.any_running',return_value=False),patch.object(qr,'validate_destination'),patch('app.browser.launch_apply') as launch:
            started=qr.start_request(identifier,rid,'Test Robotics')
            launch.assert_called_once_with(started['job_id'],qr_request_id=identifier)
            self.assertEqual(started['state'],'authorized')
            with self.assertRaisesRegex(ValueError,'qr_already_started'):qr.start_request(identifier,rid,'Test Robotics')
        self.assertFalse(store.load_profile_raw()['automation']['auto_submit'])
        self.assertFalse(store.load_profile_raw()['automation']['auto_start_queue'])
        with db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM application_queue').fetchone()[0],0)
        job=safety.get_job(started['job_id']);raw=store.load_profile_raw()
        qr.validate_intent(identifier,job,raw)
        resume,_=store.select_resume_for_job(job,raw)
        snapshot=safety.freeze_materials(job,raw,resume)
        qr.authorize_materials(identifier,job,raw,snapshot)
        self.assertTrue(safety.is_approved(job,raw,snapshot))
        raw['identity']['email']='other@example.invalid'
        with self.assertRaisesRegex(ValueError,'qr_materials_changed'):qr.validate_intent(identifier,job,raw)
        resume.write_bytes(b'changed CV')
        with self.assertRaisesRegex(ValueError,'qr_materials_changed'):qr.validate_intent(identifier,job,store.load_profile_raw())

    def test_candidate_isolation_and_oversize_api(self):
        result=self.preview()
        other=workspaces.create('Other')
        workspaces.CURRENT.set(other);db.init_db()
        with self.assertRaises(KeyError):qr.get_request(result['id'])
        workspaces.CURRENT.set('default')
        client=TestClient(app)
        self.assertEqual(client.post('/api/qr/decode',files={'image':('fake.png',b'bad','image/png')}).status_code,400)
        self.assertEqual(client.get('/api/qr/unknown').status_code,404)

    def test_browser_failure_keeps_request_draft(self):
        result=self.preview()
        with patch('app.browser_control.require_connection',side_effect=ValueError('Chrome missing')),patch('app.browser.launch_apply') as launch:
            with self.assertRaisesRegex(ValueError,'Chrome missing'):qr.start_request(result['id'],result['preview']['resume_id'],'Test')
            launch.assert_not_called()
        self.assertEqual(qr.get_request(result['id'])['state'],'draft')

    def test_qr_authorization_cannot_skip_letter_policy_checks(self):
        raw=store.load_profile_raw();raw['application']['generate_cover_letter']=True;store.save_profile_raw(raw)
        result=self.preview()
        with patch('app.browser_control.require_connection'),patch('app.worker_runtime.any_running',return_value=False),patch.object(qr,'validate_destination'),patch('app.browser.launch_apply'):
            started=qr.start_request(result['id'],result['preview']['resume_id'],'Test Robotics')
        job=safety.get_job(started['job_id']);raw=store.load_profile_raw();resume,_=store.select_resume_for_job(job,raw)
        letter=self.root/'letter.pdf';letter.write_bytes(b'%PDF-draft')
        metadata=self.root/'letter.json';metadata.write_text(json.dumps({'status':'ready','policy_version':'old'}),encoding='utf-8')
        snapshot=safety.freeze_materials(job,raw,resume,letter,inline_text='Old draft')
        with patch('app.cover_letter.letter_paths',return_value=(metadata,letter)),patch.object(safety,'validate_materials'):
            with self.assertRaisesRegex(ValueError,'qr_letter_not_checked'):qr.authorize_materials(result['id'],job,raw,snapshot)
        with db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM material_approvals').fetchone()[0],0)

    def test_system_worker_uploads_and_submits_simulated_form_once_without_old_queue(self):
        from app import apply_worker
        with db.connect() as c:
            old=c.execute("INSERT INTO jobs(url,title) VALUES('https://old.test/queued','Old queued job')").lastrowid
            c.execute("INSERT INTO application_queue(job_id,status) VALUES(?,'queued')",(old,))
        preview=self.preview()
        with patch('app.browser_control.require_connection'),patch('app.worker_runtime.any_running',return_value=False),patch.object(qr,'validate_destination'),patch('app.browser.launch_apply'):
            state=qr.start_request(preview['id'],preview['preview']['resume_id'],'Test Robotics')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            context=browser.new_context()
            context.route('https://employer.test/**',lambda route:route.fulfill(content_type='text/html',body='''<html><body><form onsubmit="event.preventDefault();window.sends=(window.sends||0)+1;document.body.innerHTML='<p>We have received your application</p>'">
                <label>Email<input type=email name=email required></label>
                <label>CV<input type=file name=resume accept=.pdf required></label>
                <button type=submit>Submit application</button></form></body></html>'''))
            try:
                with patch.object(apply_worker,'sync_playwright',return_value=MagicMock()),patch.object(apply_worker,'_open_browser',return_value=(browser,context,'cdp')),patch('app.secret_store.update'):
                    apply_worker.main(state['job_id'],qr_request_id=preview['id'])
                self.assertEqual(context.pages[0].evaluate('window.sends'),1)
                job=safety.get_job(state['job_id'])
                self.assertEqual(job['application_status'],'submitted_verified')
                self.assertIsNotNone(safety.submission_receipt(job['id']))
                with self.assertRaisesRegex(ValueError,'qr_already_started'):qr.resume_request(preview['id'])
                with db.connect() as c:
                    self.assertEqual(c.execute('SELECT COUNT(*) FROM submission_attempts').fetchone()[0],1)
                    self.assertEqual(c.execute('SELECT status FROM application_queue WHERE job_id=?',(old,)).fetchone()[0],'queued')
                self.assertFalse(store.load_profile_raw()['automation']['auto_submit'])
            finally:browser.close()


    def test_crawl_is_idempotent_discovery_only_and_cancelable(self):
        preview=self.preview();identifier=preview['id']
        with patch('app.worker_runtime.any_running',return_value=False),patch('app.worker_runtime.launch') as launch:
            state=qr.crawl_request(identifier)
        self.assertEqual(state['state'],'crawling');launch.assert_called_once_with('app.qr_crawl_worker',identifier)
        with patch('app.worker_runtime.is_running',return_value=True),patch('app.worker_runtime.launch') as launch:
            self.assertEqual(qr.crawl_request(identifier)['state'],'crawling');launch.assert_not_called()
        with patch('app.worker_runtime.cancel') as cancel:qr.stop_crawl(identifier)
        cancel.assert_called_once_with('app.qr_crawl_worker',identifier)
        with db.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM application_queue').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM submission_attempts').fetchone()[0],0)
