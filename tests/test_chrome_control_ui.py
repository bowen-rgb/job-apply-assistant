import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

STATIC=Path(__file__).resolve().parents[1]/'static'


class ChromeControlUITests(unittest.TestCase):
    def test_platform_controls_require_explicit_actions_and_report_old_server(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN')
                page.add_init_script("localStorage.setItem('jaa-ui-mode','full')")
                writes=[]
                unavailable=False
                ready=False
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    nonlocal ready
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):
                        route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if route.request.method!='GET':writes.append(path)
                    if path in {'/api/browser','/api/browser/start'}:
                        if unavailable:route.fulfill(status=404,json={'detail':'Not Found'});return
                        if path.endswith('/start'):ready=True
                        route.fulfill(json={'ready':ready,'state':'ready' if ready else 'disconnected','message':'Chrome dédié connecté. Ouvrir Chrome ne lance aucune candidature. Vérifiez votre connexion à ChatGPT.' if ready else 'Ouvrez Chrome depuis la plateforme, puis vérifiez la connexion. Aucun remplacement par Edge.'});return
                    data={}
                    if path=='/api/candidates':data={'active_id':'default','items':[dict(id='default',name='Test',identity={},active=True)]}
                    elif path=='/api/profile':data={'automation':{}}
                    elif path in {'/api/jobs','/api/sources','/api/pipeline','/api/accounts','/api/resumes'}:data=[]
                    route.fulfill(json=data)
                page.route('**/*',respond)
                page.goto('http://chrome-ui.test/')
                page.locator('#pipelineNav').click()
                status=page.locator('[data-chrome-status]')
                expect(status).to_contain_text('请从平台打开 Chrome')
                self.assertEqual(writes,[])
                page.locator('#browserOpenChrome').click()
                expect(status).to_contain_text('专用 Chrome 已连接')
                expect(page.locator('#browserOpenChrome')).to_be_disabled()
                self.assertEqual(writes,['/api/browser/start'])
                for width in [320,768,1440]:
                    page.set_viewport_size({'width':width,'height':900})
                    self.assertTrue(page.locator('#managedBrowserPanel').evaluate('node=>node.scrollWidth<=node.clientWidth+1'))
                unavailable=True
                page.locator('#browserCheckChrome').click()
                expect(status).to_contain_text('请重新启动求职平台')
                expect(page.locator('#browserOpenChrome')).to_be_disabled()
                self.assertEqual(writes,['/api/browser/start'])
                self.assertEqual(errors,[])
            finally:browser.close()
