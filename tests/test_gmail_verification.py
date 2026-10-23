import base64
import time
import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock, patch
from app import gmail_verification as mail
from app.browser_sessions import inspection_context


class EmailVerificationTests(unittest.TestCase):
    def message(self, text='Your login code: 123456', sender='no-reply@recruiter.test'):
        return {'internalDate': str(int(time.time()*1000)), 'payload': {
            'mimeType': 'text/plain', 'headers': [
                {'name': 'From', 'value': sender}, {'name': 'To', 'value': 'alice@example.test'},
                {'name': 'Authentication-Results', 'value': 'mx.google.com; dmarc=pass header.from=recruiter.test;'}],
            'body': {'data': base64.urlsafe_b64encode(text.encode()).decode()}}}

    def test_only_recent_authenticated_login_code_for_current_recipient(self):
        message = self.message()
        self.assertEqual(mail.extract_code(message,'recruiter.test','alice@example.test',time.time()-60),'123456')
        for domain, mailbox, since in [('other.test','alice@example.test',time.time()-60),
                ('recruiter.test','bob@example.test',time.time()-60),
                ('recruiter.test','alice@example.test',time.time()+1)]:
            self.assertIsNone(mail.extract_code(message,domain,mailbox,since))
        message['payload']['headers'].pop()
        self.assertIsNone(mail.extract_code(message,'recruiter.test','alice@example.test',time.time()-60))

    def test_reset_payment_and_multiple_codes_are_never_used(self):
        for text in ['Reset your password login code: 123456','Payment login code: 123456',
                     'Your login code: 123456 or code: 654321', 'Order 123456']:
            self.assertIsNone(mail.extract_code(self.message(text),'recruiter.test','alice@example.test',time.time()-60))

    def test_disabled_mailbox_never_makes_network_request(self):
        with patch.object(mail.secret_store,'read',return_value={}),patch.object(mail,'urlopen') as request:
            self.assertIsNone(mail.wait_for_code('https://recruiter.test/login','alice@example.test',time.time()))
            request.assert_not_called()

    def test_setting_does_not_destroy_oauth_connection(self):
        data={'gmail_connection':{'refresh_token':'fake'},'gmail_config':{'client_id':'fake'}}
        with patch.object(mail.secret_store,'update',side_effect=lambda f:f(data)):
            mail.configure(True)
        self.assertEqual(data['gmail_connection']['refresh_token'],'fake')
        self.assertTrue(data['gmail_auto_codes'])
        with self.assertRaises(ValueError):mail.configure('true')

    def test_one_matching_code_is_consumed_without_writing_mail(self):
        data={'gmail_auto_codes':True,'gmail_config':{'client_id':'fake','client_secret':'fake'},
              'gmail_connection':{'refresh_token':'fake','email':'alice@example.test'}}
        responses=[{'access_token':'fake'}, {'messages':[{'id':'message-1'}]}, self.message()]
        def response(request, **kwargs):
            import io,json
            return io.BytesIO(json.dumps(responses.pop(0)).encode())
        with patch.object(mail.secret_store,'read',side_effect=lambda:data),patch.object(mail.secret_store,'update',side_effect=lambda f:f(data)),patch.object(mail,'urlopen',side_effect=response) as requests:
            result=mail.wait_for_code('https://recruiter.test/login','alice@example.test',time.time()-60,wait_seconds=0)
        self.assertEqual(result,'123456')
        self.assertEqual(data['gmail_used_codes'],['message-1'])
        self.assertEqual([call.args[0].get_method() for call in requests.call_args_list],['POST','GET','GET'])
        self.assertFalse(any('123456' in str(value) for value in data.values()))


class HiddenInspectionTests(unittest.TestCase):
    def test_background_owns_hidden_chrome_and_closes_it_even_on_failure(self):
        p=MagicMock(); browser=p.chromium.launch.return_value
        with patch('app.browser_control.chrome_executable',return_value='chrome.exe'),patch('app.secret_store.read',return_value={}):
            with self.assertRaisesRegex(RuntimeError,'failed'):
                with inspection_context(p) as context:
                    self.assertEqual(context,browser.new_context.return_value)
                    raise RuntimeError('failed')
        p.chromium.launch.assert_called_once_with(executable_path='chrome.exe',headless=True)
        browser.close.assert_called_once()

    def test_borrowed_login_context_is_never_closed(self):
        p=MagicMock();context=MagicMock()
        with patch('app.browser_control.require_connection'),patch('app.profile_store.runtime_profile',return_value={}),patch('app.apply_worker._open_browser',return_value=(None,context,'cdp')):
            with inspection_context(p,'existing-tab') as borrowed:self.assertIs(borrowed,context)
        context.close.assert_not_called()
