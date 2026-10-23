import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
STATIC=Path(__file__).resolve().parents[1]/'static'
class PlatformLoginUITests(unittest.TestCase):
 def test_open_then_save_and_mobile_layout(self):
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True)
   try:
    for width in [1280,375]:
     page=browser.new_page(viewport={'width':width,'height':1000});calls=[];state={'state':'not_connected','window_open':False}
     def respond(route):
      url=route.request.url;method=route.request.method
      if method=='POST':
       calls.append(url)
       if url.endswith('/open'):state.update(state='waiting',window_open=True)
       if url.endswith('/save'):state.update(state='saved',window_open=False,saved_at='2026-01-01T12:00:00Z')
       route.fulfill(json={'ok':True});return
      route.fulfill(json=[{'key':'jobteaser','label':'JobTeaser','verified':False,**state}])
     page.route('**/api/platform-logins**',respond)
     page.set_content('<dialog id="accountsDialog" open><h4>Saved accounts</h4><div id="savedAccounts"></div></dialog>')
     page.add_style_tag(path=str(STATIC/'accounts.css'))
     # Give relative API calls a fixed origin without accessing any real website.
     page.add_script_tag(content="window.Locale={language:'zh'};const nativeFetch=window.fetch.bind(window);window.fetch=(url,opt)=>nativeFetch('http://test.local'+url,opt);")
     page.add_script_tag(path=str(STATIC/'platform-logins.js'))
     page.evaluate("PlatformLogins.mount(document.querySelector('dialog'))")
     expect(page.get_by_role('button',name='去登录',exact=True)).to_be_visible()
     page.get_by_role('button',name='去登录',exact=True).click()
     page.get_by_role('button',name='已登录，保存会话',exact=True).click()
     expect(page.get_by_text('会话已保存 · 未确认登录成功，投递时再核验',exact=True)).to_be_visible()
     self.assertEqual(len(calls),2)
     self.assertTrue(calls[0].endswith('/jobteaser/open'));self.assertTrue(calls[1].endswith('/jobteaser/save'))
     page.screenshot(path=f'tmp/platform-login-{width}.png')
     page.close()
   finally:browser.close()
