import unittest
from unittest.mock import MagicMock
from playwright.sync_api import sync_playwright
from app.auto_submission import submit_complete_form
from app.inmind_flow import prepare_registration


class InmindFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=sync_playwright().start();cls.browser=cls.p.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.p.stop()

    def setUp(self):
        self.page=self.browser.new_page()
        self.page.route('**/*',lambda route:route.fulfill(body='<html><body></body></html>',content_type='text/html'))
        self.page.goto('https://cv.inmind.fr/example')

    def tearDown(self):self.page.close()

    def audit(self):
        return {'documents':{'resume_attached':True,'letter_generated':False},
                'required_unanswered_count':0,'sensitive_or_legal_unanswered_count':0,
                'report':{'filled':['resume','civility'],'errors':[]}}

    def test_cv_import_validate_never_counts_as_final_submission(self):
        self.page.set_content('<input type="file" id="upload_applicant_resume_upload"><button>VALIDER</button>')
        send=MagicMock()
        self.assertEqual(submit_complete_form(self.page,self.page,self.audit(),send)['status'],'blocked')
        send.assert_not_called()

    def test_complete_identity_validate_is_dispatched_once_and_requires_receipt(self):
        fields=''.join('<input id="'+key+'" value="confirmed">' for key in ['firstname','lastname','email','phone'])
        self.page.set_content(fields+'<button onclick="document.body.textContent=\'Votre candidature est envoyée\'">VALIDER</button>')
        send=MagicMock()
        result=submit_complete_form(self.page,self.page,self.audit(),send)
        self.assertEqual(result['status'],'verified');send.assert_called_once()

    def test_missing_identity_is_not_dispatched(self):
        self.page.set_content('<input id="firstname" value="confirmed"><button>VALIDER</button>')
        send=MagicMock()
        self.assertEqual(submit_complete_form(self.page,self.page,self.audit(),send)['status'],'blocked')
        send.assert_not_called()

    def test_explicit_terms_confirmation_is_required(self):
        self.page.set_content('<input id="upload_applicant_resume_upload" type="file"><button>VALIDER</button>')
        report={'filled':['resume'],'actions':[],'errors':[]}
        result=prepare_registration(self.page,{},report)
        self.assertIn('confirm',result['errors'][0])

    def test_personal_cv_qr_is_not_a_delivery_receipt(self):
        self.page.set_content('<p>Présentez ce QR Code aux recruteurs pour transmettre votre CV</p>')
        send=MagicMock()
        self.assertEqual(submit_complete_form(self.page,self.page,self.audit(),send)['status'],'blocked')
        send.assert_not_called()

    def test_terms_authorisation_cannot_cross_employer_paths(self):
        report={'filled':[],'actions':[],'errors':[]}
        result=prepare_registration(self.page,{'invocation_privacy_confirmed':True},report,{'url':'https://cv.inmind.fr/another-employer'})
        self.assertIn('recipient path changed',result['errors'][0])
