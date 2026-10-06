import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

from app import db, review_exports as exports, review_export_worker as worker
from app.main import app
from app.repositories.jobs import JobRepository
from app.review_report import report_row, render_html, render_xlsx, safe_url


def job(id=1,verdict='HUMAN_REVIEW'):
    return dict(id=id,title='Accueil <script>alert(1)</script>',company='Company & Co',location='Paris',url='https://example.test/job',
                review_verdict=verdict,review_confidence=95,human_review_status='pending',review_summary='Vérifier 20 heures.',
                review_json=json.dumps({'reasons':['CDD pertinent'],'risks':['Durée inconnue'],'manual_questions':['Quel horaire ?'],
                                        'facts':{'schedule':'Travail en journée'}},ensure_ascii=False),
                employment_type='CDD',reviewed_at='2026-10-06 10:00:00',source='Example',
                body='PRIVATE FULL BODY',fill_audit_path='PRIVATE LOCAL PATH',email='private@example.test')


class ReportTests(unittest.TestCase):
    def test_translation_batches_cache_results_and_only_sends_review_strings(self):
        def translate(context,prompt,cfg,purpose):
            self.assertEqual(purpose,'review-export-translation')
            self.assertNotIn('PRIVATE FULL BODY',prompt)
            self.assertNotIn('private@example.test',prompt)
            values=json.loads(prompt.split('INPUT_TEXTS=',1)[1])
            return {'translations':{key:'译文：'+text for key,text in values.items()}}
        with tempfile.TemporaryDirectory() as folder,patch.object(worker,'CACHE',Path(folder)),patch('playwright.sync_api.sync_playwright') as playwright,patch.object(worker,'ask_chatgpt_json',side_effect=translate) as ask:
            playwright.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value.contexts=[MagicMock()]
            rows=[report_row(job())]
            worker.translate_rows(rows,'zh',{'enabled':True})
            self.assertEqual(rows[0]['translation'],'translated')
            self.assertTrue(rows[0]['display']['questions'][0].startswith('译文：'))
            self.assertEqual(ask.call_count,1)
            worker.translate_rows([report_row(job())],'zh',{'enabled':True})
            self.assertEqual(ask.call_count,1)

    def test_xlsx_marks_text_truncation_instead_of_silently_losing_content(self):
        value=job();value['review_summary']='a'*40000
        data=render_xlsx([report_row(value)],{'language':'en','created_at':'2026-10-06'})
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            self.assertIn('Text exceeds the Excel cell limit',book.read('xl/sharedStrings.xml').decode())
    def test_html_is_standalone_readable_and_safe_with_review_details_and_originals(self):
        row=report_row(job())
        worker.apply_translations(row,{'title':'接待岗位','summary':'核实每周 20 小时。','reasons.0':'固定期限合同相关',
                                       'risks.0':'时长未知','questions.0':'具体上班时间？','facts.schedule':'白天上班'})
        report=render_html([row],{'language':'zh','created_at':'2026-10-06T10:00:00+00:00'})
        self.assertIn('岗位人工核验报告',report)
        self.assertIn('具体上班时间？',report)
        self.assertIn('Quel horaire ?',report)
        self.assertIn('复核原文',report)
        for private in ['PRIVATE FULL BODY','PRIVATE LOCAL PATH','private@example.test']:
            self.assertNotIn(private,report)
        self.assertNotIn('<script>',report)
        self.assertIn('&lt;script&gt;',report)
        self.assertNotIn('/api/',report)
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page()
            page.set_content(report)
            expect(page.locator('article')).to_have_count(1)
            expect(page.locator('h1')).to_have_text('岗位人工核验报告')
            expect(page.locator('article a')).to_have_attribute('href','https://example.test/job')
            self.assertEqual(page.locator('script,link[rel="stylesheet"],img').count(),0)
            browser.close()

    def test_xlsx_has_filter_freeze_notes_dropdown_and_no_injected_formulas(self):
        value=job();value.update(title='=HYPERLINK("https://bad.test")',company='+cmd',review_summary='@SUM(1,2)')
        data=render_xlsx([report_row(value)],{'language':'en','created_at':'2026-10-06T10:00:00+00:00'})
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            root=ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
            self.assertEqual(root.findall('.//x:f',ns),[])
            self.assertEqual(root.find('.//x:pane',ns).get('state'),'frozen')
            self.assertIsNotNone(root.find('.//x:dataValidation',ns))
            table=ET.fromstring(book.read('xl/tables/table1.xml'))
            self.assertIsNotNone(table.find('x:autoFilter',ns))
            texts=book.read('xl/sharedStrings.xml').decode()
            self.assertIn('Questions to verify',texts)
            self.assertIn('Reviewer comments',texts)
            self.assertIn('HYPERLINK',texts)
            self.assertNotIn('PRIVATE FULL BODY',texts)

    def test_malformed_review_and_urls_do_not_create_active_content(self):
        value=job();value.update(review_json='[]',url='javascript:alert(1)')
        row=report_row(value)
        self.assertEqual(row['url'],'')
        self.assertEqual(row['original']['questions'],[])
        for url in ['file:///private','https://user:password@example.test','http://[invalid']:
            self.assertEqual(safe_url(url),'')

    def test_partial_or_numerically_changed_translation_keeps_original_and_warns(self):
        row=report_row(job())
        result=worker.validate_translations({'translations':{'title':'接待','summary':'每周 40 小时','extra':'invented'}},worker.row_texts(row))
        self.assertNotIn('summary',result)
        self.assertNotIn('extra',result)
        worker.apply_translations(row,result)
        self.assertEqual(row['display']['summary'],'Vérifier 20 heures.')
        self.assertEqual(row['translation'],'unavailable')
        report=render_html([row],{'language':'zh','created_at':'2026-10-06'})
        self.assertIn('部分内容未能翻译',report)
        from app.chatgpt_bridge import _extract_json_for_purpose
        self.assertIsNone(_extract_json_for_purpose('{"verdict":"APPLY"}','review-export-translation'))
        self.assertEqual(_extract_json_for_purpose('{"translations":{"t0":"你好"}}','review-export-translation'),{'translations':{'t0':'你好'}})


class ExportApiTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.db_patch=patch.object(db,'DB_PATH',Path(self.folder.name)/'jobs.db');self.db_patch.start();db.init_db()
        self.export_patch=patch.object(exports,'EXPORT_ROOT',Path(self.folder.name)/'exports');self.export_patch.start()
        self.launch_patch=patch.object(exports,'launch');self.launch=self.launch_patch.start()
        self.client=TestClient(app)
        with db.connect() as c:
            for id in range(1,6):
                c.execute("INSERT INTO jobs(id,url,title,review_verdict) VALUES(?,?,?,'APPLY')",(id,f'https://example.test/{id}',f'Job {id}'))
            c.execute("UPDATE jobs SET user_action='skipped' WHERE id=3")
            c.execute("UPDATE jobs SET application_status='submitted' WHERE id=4")
            c.execute("UPDATE jobs SET decision='expired' WHERE id=5")

    def tearDown(self):
        self.launch_patch.stop();self.export_patch.stop();self.db_patch.stop();self.folder.cleanup()

    def test_pending_snapshot_selection_download_and_no_approval_mutations(self):
        result=self.client.post('/api/review-exports',json={'language':'fr','format':'html','scope':'pending'}).json()
        self.assertEqual(result['status'],'queued')
        folder=exports.directory(result['id'])
        snapshot=json.loads((folder/'snapshot.json').read_text(encoding='utf-8'))
        self.assertEqual([r['id'] for r in snapshot['rows']],[1,2])
        with db.connect() as c:c.execute("UPDATE jobs SET title='Changed after export' WHERE id=1")
        self.assertEqual(self.client.get(f'/api/review-exports/{result["id"]}/download').status_code,409)
        worker.main(result['id'])
        download=self.client.get(f'/api/review-exports/{result["id"]}/download')
        self.assertEqual(download.status_code,200)
        self.assertIn('attachment',download.headers['content-disposition'])
        self.assertIn('Job 1',download.text)
        self.assertNotIn('Changed after export',download.text)
        self.assertEqual(JobRepository().human_review_history(1),[])
        self.assertEqual(JobRepository().list()[0]['human_review_status'],'pending')

    def test_visible_scope_is_exact_and_contracts_reject_invalid_requests(self):
        result=self.client.post('/api/review-exports',json={'scope':'visible','job_ids':[2,2,1],'format':'xlsx','language':'en','translate_text':False}).json()
        snapshot=json.loads((exports.directory(result['id'])/'snapshot.json').read_text(encoding='utf-8'))
        self.assertEqual([r['id'] for r in snapshot['rows']],[2,1])
        worker.main(result['id'])
        self.assertTrue(self.client.get(f'/api/review-exports/{result["id"]}/download').content.startswith(b'PK'))
        for payload in [{'language':'xx'},{'format':'csv'},{'scope':'visible','job_ids':list(range(1001))}]:
            self.assertEqual(self.client.post('/api/review-exports',json=payload).status_code,422)
        self.assertEqual(self.client.post('/api/review-exports',json={'scope':'visible','job_ids':[100]}).status_code,409)
        self.assertEqual(self.client.post('/api/review-exports',json={'scope':'visible'}).status_code,400)
        self.assertEqual(self.client.get('/api/review-exports/not-an-id').status_code,404)

    def test_cancelled_export_cannot_be_marked_ready_later(self):
        result=self.client.post('/api/review-exports',json={}).json()
        with patch.object(exports,'cancel'):
            self.assertEqual(self.client.post(f'/api/review-exports/{result["id"]}/cancel').json()['status'],'cancelled')
        self.assertFalse(exports.update_state(result['id'],status='ready'))
        worker.main(result['id'])
        self.assertEqual(exports.read_state(result['id'])['status'],'cancelled')
        self.assertEqual(self.client.get(f'/api/review-exports/{result["id"]}/download').status_code,409)

    def test_offline_translation_still_exports_with_explicit_original_warning(self):
        result=self.client.post('/api/review-exports',json={'language':'zh','translate_text':True}).json()
        with patch.object(worker,'runtime_profile',return_value={'chatgpt_web_reviewer':{'enabled':False}}):worker.main(result['id'])
        state=exports.read_state(result['id'])
        self.assertEqual(state['status'],'ready')
        self.assertEqual(state['untranslated'],2)
        self.assertIn('部分内容未能翻译',exports.download(result['id'])[0].read_text(encoding='utf-8'))
