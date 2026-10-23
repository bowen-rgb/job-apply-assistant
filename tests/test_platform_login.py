import unittest
from unittest.mock import Mock,patch
from app.browser_sessions import merge_states,save_context
from app.platform_login import page_state,identifier,status

class PlatformLoginTests(unittest.TestCase):
 def test_removed_cookies_are_not_restored_and_unvisited_origins_are_kept(self):
  old={'cookies':[{'name':'session','domain':'.example.test','path':'/'}],'origins':[{'origin':'https://one.test','localStorage':[]}]}
  merged=merge_states(old,{'cookies':[],'origins':[{'origin':'https://two.test','localStorage':[]}]})
  self.assertEqual(merged['cookies'],[]);self.assertEqual(len(merged['origins']),2)
 def test_capture_never_calls_storage_state_or_navigates(self):
  page=Mock(url='https://example.test/account');page.is_closed.return_value=False
  page.evaluate.return_value={'origin':'https://example.test','localStorage':[]}
  context=Mock(pages=[page]);context.cookies.return_value=[]
  data={}
  with patch('app.secret_store.update',side_effect=lambda f:f(data)):save_context(context)
  context.storage_state.assert_not_called();page.goto.assert_not_called();page.reload.assert_not_called()
  self.assertEqual(data['browser_state']['cookies'],[])
 def test_password_and_auth_redirect_do_not_claim_login_success(self):
  page=Mock(url='https://www.jobteaser.com/fr/users/sign_in');page.locator.return_value.count.return_value=1
  self.assertEqual(page_state(page,'jobteaser.com'),('needs_login',False))
  page.url='https://accounts.google.com/login'
  self.assertEqual(page_state(page,'jobteaser.com'),('needs_login',False))
 def test_no_account_signal_is_saved_as_unverified_not_connected(self):
  page=Mock(url='https://www.jobteaser.com/fr/account');page.locator.return_value.count.return_value=0
  page.locator.return_value.inner_text.return_value='My account'
  page.get_by_text.return_value.all.return_value=[]
  self.assertEqual(page_state(page,'jobteaser.com'),('saved',False))
 def test_gate_is_human_verification(self):
  page=Mock(url='https://www.apec.fr/account');page.locator.return_value.count.return_value=0
  page.locator.return_value.inner_text.return_value='正在验证设备'
  self.assertEqual(page_state(page,'apec.fr'),('verification',False))
 def test_unknown_platform_rejected_and_status_has_no_credentials(self):
  with self.assertRaises(ValueError):identifier('https://evil.test')
  with patch('app.platform_login.read',return_value={'jobteaser':{'password':'secret','cookies':'secret','state':'saved'}}),patch('app.platform_login.is_running',return_value=False):
   row=status()[0];self.assertNotIn('password',row);self.assertNotIn('cookies',row)
