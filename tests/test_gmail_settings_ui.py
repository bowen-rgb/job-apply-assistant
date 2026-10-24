from tests.ui_navigation import navigate, set_appearance
import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect


class GmailSettingsUITests(unittest.TestCase):
    def test_optional_code_switch_preserves_authorization_and_layout(self):
        static=Path(__file__).resolve().parents[1]/'static'
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                for width in [1280,375]:
                    page=browser.new_page(viewport={'width':width,'height':1000})
                    writes=[]
                    def route(r):
                        path=urlparse(r.request.url).path
                        if path=='/':r.fulfill(path=str(static/'index.html'),content_type='text/html');return
                        if path.startswith('/static/'):r.fulfill(path=str(static/path.removeprefix('/static/')));return
                        if r.request.method=='PUT':writes.append((path,r.request.post_data_json));r.fulfill(json={'ok':True});return
                        data=[]
                        if path=='/api/candidates':data={'active_id':'default','items':[{'id':'default','name':'Test profile','identity':{},'active':True}]}
                        elif path=='/api/profile':data={}
                        elif path=='/api/health':data={'resume_ok':True,'cdp_ok':True}
                        elif path=='/api/gmail':data={'configured':True,'connected':True,'auto_codes':False,'email':'alice@example.test'}
                        elif path not in {'/api/accounts','/api/jobs','/api/sources','/api/resumes','/api/pipeline','/api/platform-logins'}:data={}
                        r.fulfill(json=data)
                    page.route('**/*',route);page.goto('http://ui.test/')
                    page.evaluate("Locale.setLanguage('zh')")
                    if width<600:page.locator('#workspaceMenuButton').click()
                    navigate(page,'accountsNav')
                    switch=page.locator('#gmailAutoCodes')
                    expect(switch).to_be_enabled();expect(switch).not_to_be_checked()
                    switch.check()
                    expect(page.locator('#accountsNotice')).to_have_text('已保存')
                    self.assertEqual(writes,[('/api/gmail/verification',{'enabled':True})])
                    switch.scroll_into_view_if_needed()
                    self.assertTrue(page.locator('#accountsDialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+2'))
                    page.screenshot(path=f'tmp/gmail-settings-{width}.png')
                    page.close()
            finally:browser.close()
