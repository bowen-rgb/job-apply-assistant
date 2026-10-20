import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pypdf import PdfReader
from fastapi.testclient import TestClient

from app import cover_letter, letter_policy
from app.chatgpt_bridge import _matches_purpose
from app.letter_layout import correspondence, render_pdf
from tests.test_documents import LETTER_BODY, letter_review


class LetterQualityTests(unittest.TestCase):
    def test_notes_rules_cover_concrete_motivation_evidence_and_truth(self):
        for number in range(1,12):self.assertIn(f'LM{number:02d}.',letter_policy.RULES)
        prompt=letter_policy.draft_prompt({'cv':'untrusted text'})
        for rule in ['collectif','doctorat','B1','diplôme obtenu','objectif','visa','instructions']:
            self.assertIn(rule,prompt)
        self.assertEqual(letter_policy.local_issues(LETTER_BODY),[])
        self.assertTrue(letter_policy.local_issues('Je me permets de postuler pour [poste].'))

    def test_actual_chat_calls_both_contain_all_notes_rules(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(cover_letter,'LETTER_DIR',Path(folder)),patch.object(cover_letter,'resume_text',return_value='Experience accueil hôtel'):
            with patch.object(cover_letter,'ask_chatgpt_json',side_effect=[{'letter':LETTER_BODY},letter_review()]) as chat:
                cover_letter.generate_letter(None,{'id':1,'title':'Réceptionniste','company':'Example Hôtel'}, {'identity':{'first_name':'Test'}},None,{})
            self.assertEqual([call.kwargs['purpose'] for call in chat.call_args_list],['cover-letter','cover-letter-review'])
            for call in chat.call_args_list:
                self.assertIn(letter_policy.RULES,call.args[1])
                for number in range(1,12):self.assertIn(f'LM{number:02d}.',call.args[1])

    def test_review_requires_every_boolean_and_source_quotes(self):
        payload={'cv':'Experience accueil hôtel','candidate':{}}
        good=letter_review()
        self.assertTrue(_matches_purpose(good,'cover-letter-review'))
        self.assertFalse(_matches_purpose({'letter':LETTER_BODY},'cover-letter-review'))
        self.assertEqual(letter_policy.audit_issues(good,payload),[])
        for modified in [dict(good,checks={'factual_support':True}),dict(good,issues=['Unsupported claim']),dict(good,evidence=[]),
                         dict(good,evidence=[{'claim':'Expert','source':'job','quote':'Experience accueil hôtel'}]),
                         dict(good,evidence=[{'claim':'Expert','source':'cv','quote':'An invented achievement'}])]:
            self.assertTrue(letter_policy.audit_issues(modified,payload))

    def test_audit_failure_revises_once_and_never_publishes_bad_pdf(self):
        job={'id':1,'title':'Réceptionniste','company':'Example Hôtel'}
        raw={'identity':{'first_name':'Ada'}}
        bad=dict(letter_review(),issues=['La lettre exagère la contribution individuelle.'])
        with tempfile.TemporaryDirectory() as folder,patch.object(cover_letter,'LETTER_DIR',Path(folder)),patch.object(cover_letter,'resume_text',return_value='Experience accueil hôtel'):
            with patch.object(cover_letter,'ask_chatgpt_json',side_effect=[{'letter':LETTER_BODY},bad,{'letter':LETTER_BODY},bad]) as chat:
                with self.assertRaisesRegex(ValueError,'contribution individuelle'):
                    cover_letter.generate_letter(None,job,raw,None,{})
                self.assertEqual(chat.call_count,4)
                self.assertIn('revision_feedback',chat.call_args_list[2].args[1])
            metadata,pdf=cover_letter.letter_paths(1)
            self.assertFalse(pdf.exists())
            self.assertEqual(json.loads(metadata.read_text(encoding='utf-8'))['status'],'error')

    def test_successful_repair_records_audit_and_invalidates_old_rules_or_cv(self):
        job={'id':1,'title':'Réceptionniste','company':'Example Hôtel'}
        raw={'identity':{'first_name':'Ada'}}
        with tempfile.TemporaryDirectory() as folder,patch.object(cover_letter,'LETTER_DIR',Path(folder)),patch.object(cover_letter,'resume_text',return_value='Experience accueil hôtel'):
            with patch.object(cover_letter,'ask_chatgpt_json',side_effect=[{'letter':'Trop court'}, {'letter':LETTER_BODY},letter_review()]):
                state=cover_letter.generate_letter(None,job,raw,None,{})
            self.assertEqual(state['quality']['attempts'],2)
            self.assertTrue(state['quality']['human_review_required'])
            self.assertTrue(cover_letter.current_letter(state,job,raw,None))
            self.assertFalse(cover_letter.current_letter(dict(state,policy_version='old'),job,raw,None))
            with patch.object(cover_letter,'resume_text',return_value='Different CV'):
                self.assertFalse(cover_letter.current_letter(state,job,raw,None))
            self.assertEqual(len(PdfReader(cover_letter.letter_paths(1)[1]).pages),1)

    def test_fixed_a4_correspondence_has_real_headers_and_overflow_does_not_shrink(self):
        job={'title':'Ingénieur R&D','company':'Entreprise','location':'Fake vacancy location'}
        raw={'identity':{'first_name':'Ada','last_name':'Lovelace','city':'Paris','email':'ada@example.test','phone':'+33 123'}}
        document=correspondence(job,raw,LETTER_BODY)
        self.assertNotIn('Fake vacancy location',str(document['recipient']))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'letter.pdf'
            render_pdf(path,document)
            reader=PdfReader(path)
            self.assertEqual(len(reader.pages),1)
            self.assertAlmostEqual(float(reader.pages[0].mediabox.width),595.2756,places=2)
            text=reader.pages[0].extract_text()
            for value in ['Ada Lovelace','ada@example.test','Entreprise','Objet','Pièce jointe : CV']:
                self.assertIn(value,text)
            document['body']=LETTER_BODY*8
            with self.assertRaisesRegex(ValueError,'une page A4'):render_pdf(path,document)
            self.assertFalse(path.exists())

    def test_old_cached_pdf_is_not_served_as_current_material(self):
        from app.main import app, job_repository
        with tempfile.TemporaryDirectory() as folder:
            metadata=Path(folder)/'job_1.json'
            pdf=Path(folder)/'job_1.pdf'
            metadata.write_text(json.dumps({'status':'ready','letter':'Old draft'}),encoding='utf-8')
            pdf.write_bytes(b'old PDF')
            with patch('app.main.letter_paths',return_value=(metadata,pdf)),patch.object(job_repository,'exists',return_value=True),patch('app.application_safety.get_job',return_value={'id':1,'title':'Job'}),patch('app.main.load_profile_raw',return_value={}),patch('app.profile_store.select_resume_for_job',return_value=(None,None)):
                client=TestClient(app)
                response=client.get('/api/jobs/1/letter')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['status'],'stale')
                self.assertNotIn('letter',response.json())
                self.assertEqual(client.get('/api/jobs/1/letter/pdf').status_code,404)
