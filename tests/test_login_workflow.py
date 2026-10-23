import unittest
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from app.login_flow import login_if_needed

ACCOUNT={'origin':'https://recruiter.test','username':'alice@example.test','password':'test-password'}
class LoginWorkflowTests(unittest.TestCase):
 def test_email_first_then_password_continues_without_manual_login_window(self):
  with sync_playwright() as p:
   b=p.chromium.launch(headless=True)
   try:
    page=b.new_page()
    html='''<form><input type=email><button>Continue</button></form><script>
    window.sends=0;document.querySelector('form').onsubmit=e=>{e.preventDefault();window.sends++;
    document.body.innerHTML='<form><input type=password autocomplete=current-password><button>Sign in</button></form>';
    document.querySelector('form').onsubmit=e=>{e.preventDefault();window.sends++;document.body.innerHTML='<h1>My applications</h1>';};};</script>'''
    page.route('https://recruiter.test/**',lambda r:r.fulfill(body=html,content_type='text/html'))
    page.goto('https://recruiter.test/login')
    with patch('app.login_flow.account_for',return_value=ACCOUNT):result=login_if_needed(page)
    self.assertEqual(result['status'],'logged_in');self.assertEqual(page.evaluate('window.sends'),2)
   finally:b.close()
 def test_application_email_is_never_treated_as_login(self):
  with sync_playwright() as p:
   b=p.chromium.launch(headless=True)
   try:
    page=b.new_page();page.route('https://recruiter.test/**',lambda r:r.fulfill(body='<form><input type=email><input type=file><button>Continue</button></form>',content_type='text/html'));page.goto('https://recruiter.test/apply')
    with patch('app.login_flow.account_for') as account:
     self.assertEqual(login_if_needed(page)['status'],'not_needed');account.assert_not_called()
    self.assertEqual(page.locator('input[type=email]').input_value(),'')
   finally:b.close()
 def test_empty_login_shell_does_not_claim_session_is_valid(self):
  with sync_playwright() as p:
   b=p.chromium.launch(headless=True)
   try:
    page=b.new_page();page.route('https://recruiter.test/**',lambda r:r.fulfill(body='<h1>Sign in</h1>',content_type='text/html'));page.goto('https://recruiter.test/login')
    self.assertEqual(login_if_needed(page)['status'],'handoff')
   finally:b.close()
 def test_invalid_password_is_sent_once_then_pauses(self):
  with sync_playwright() as p:
   b=p.chromium.launch(headless=True)
   try:
    page=b.new_page();page.route('https://recruiter.test/**',lambda r:r.fulfill(content_type='text/html',body='''<form><input type=email><input type=password><button>Sign in</button><p role=alert hidden>Incorrect password</p></form><script>window.sends=0;document.querySelector('form').onsubmit=e=>{e.preventDefault();window.sends++;document.querySelector('[role=alert]').hidden=false;};</script>'''));page.goto('https://recruiter.test/login')
    with patch('app.login_flow.account_for',return_value=ACCOUNT):result=login_if_needed(page)
    self.assertEqual(result['status'],'handoff');self.assertEqual(page.evaluate('window.sends'),1)
   finally:b.close()
 def test_session_survives_closed_login_context_without_password_reentry(self):
  from app.browser_sessions import save_context
  with sync_playwright() as p:
   b=p.chromium.launch(headless=True)
   try:
    first=b.new_context();tab=first.new_page();tab.route('https://recruiter.test/**',lambda r:r.fulfill(body='<h1>My applications</h1>',content_type='text/html'));tab.goto('https://recruiter.test/account')
    first.add_cookies([{'name':'session','value':'fake-session','url':'https://recruiter.test/','secure':True}]);vault={}
    with patch('app.secret_store.update',side_effect=lambda f:f(vault)):save_context(first)
    first.close()
    second=b.new_context(storage_state=vault['browser_state']);page=second.new_page()
    def route(r):r.fulfill(body='<h1>Application</h1><input type=file>' if 'session=fake-session' in r.request.headers.get('cookie','') else '<h1>Sign in</h1>',content_type='text/html')
    page.route('https://recruiter.test/**',route);page.goto('https://recruiter.test/apply')
    with patch('app.login_flow.account_for') as account:
     self.assertEqual(login_if_needed(page)['status'],'not_needed');account.assert_not_called()
    self.assertEqual(page.locator('input[type=file]').count(),1)
   finally:b.close()
 def test_account_landing_returns_to_job_but_open_form_is_never_reloaded(self):
  from app.login_flow import resume_application_after_login
  with sync_playwright() as p:
   b=p.chromium.launch(headless=True)
   try:
    page=b.new_page();page.route('https://recruiter.test/**',lambda r:r.fulfill(body='<h1>My applications</h1>' if r.request.url.endswith('/account') else '<input type=file>',content_type='text/html'));page.goto('https://recruiter.test/account')
    resume_application_after_login(page,'https://recruiter.test/job/123');self.assertTrue(page.url.endswith('/job/123'))
    stamp=page.evaluate('performance.timeOrigin');resume_application_after_login(page,'https://recruiter.test/job/other');self.assertEqual(page.evaluate('performance.timeOrigin'),stamp)
   finally:b.close()
 def test_application_contact_fields_after_login_are_not_another_login(self):
  with sync_playwright() as p:
   b=p.chromium.launch(headless=True)
   try:
    page=b.new_page();page.route('https://recruiter.test/**',lambda r:r.fulfill(content_type='text/html',body='''<form><input type=email><input type=password><button>Sign in</button></form><script>document.querySelector('form').onsubmit=e=>{e.preventDefault();history.pushState({},'','/apply');document.body.innerHTML='<form><input type=email><input type=file></form>';};</script>'''));page.goto('https://recruiter.test/login')
    with patch('app.login_flow.account_for',return_value=ACCOUNT):self.assertEqual(login_if_needed(page)['status'],'logged_in')
   finally:b.close()
