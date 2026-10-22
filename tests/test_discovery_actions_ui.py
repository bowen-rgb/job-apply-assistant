import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

STATIC = Path(__file__).resolve().parents[1] / 'static'


class DiscoveryActionsUITests(unittest.TestCase):
    def test_actions_remain_visible_in_simple_mode_and_call_existing_services(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(locale='zh-CN', viewport={'width': 1280, 'height': 1000})
                context.add_init_script("localStorage.setItem('jaa-ui-mode','simple');localStorage.setItem('jaa-ui-language','zh')")
                page = context.new_page()
                writes = []
                review_urls = []
                errors = []
                running = False
                fail_scan = False
                page.on('pageerror', lambda error: errors.append(str(error)))
                def respond(route):
                    nonlocal running
                    path = urlparse(route.request.url).path
                    if path == '/':
                        route.fulfill(path=str(STATIC / 'index.html'), content_type='text/html');return
                    if path.startswith('/static/'):
                        route.fulfill(path=str(STATIC / path.removeprefix('/static/')));return
                    if route.request.method != 'GET':
                        writes.append(path)
                        if path == '/api/review/batch':review_urls.append(route.request.url)
                    data = {}
                    if path == '/api/candidates':
                        data = {'active_id':'default','items':[dict(id='default',name='Test',identity={},active=True)]}
                    elif path == '/api/profile':
                        data = {'automation':{}}
                    elif path == '/api/pfe':
                        data = dict(settings={}, jobs=[], leads=[], sources=[], plan=[])
                    elif path in {'/api/jobs','/api/sources','/api/pipeline','/api/accounts','/api/resumes'}:
                        data = []
                    elif path == '/api/search':
                        if fail_scan:
                            route.fulfill(status=503, json={'detail':'Test scan unavailable'});return
                        running = True
                    elif path == '/api/search/status':
                        data = dict(running=running,scan_id=1,found=3,fetched=2,inserted=1,updated=0,errors=0)
                    route.fulfill(json=data)
                context.route('**/*', respond)
                page.goto('http://discovery-ui.test/')
                expect(page.locator('#batchBtn')).to_have_text('让 ChatGPT 复核岗位')
                expect(page.locator('body')).to_have_class(__import__('re').compile('simple-mode'))
                for view in ['overview', 'pfe', 'profile', 'pipeline', 'jobs']:
                    page.evaluate('(view)=>showView(view)', view)
                    expect(page.locator('#searchBtn')).to_be_visible()
                    expect(page.locator('#batchBtn')).to_be_visible()
                self.assertEqual(writes, [])
                for width in [1280, 375]:
                    page.set_viewport_size({'width':width,'height':1000})
                    expect(page.locator('#searchBtn')).to_be_visible()
                    expect(page.locator('#batchBtn')).to_be_visible()
                    self.assertTrue(page.locator('#discoveryActions').evaluate('n=>n.scrollWidth<=n.clientWidth+1'))
                    page.screenshot(path=f'tmp/discovery-actions-{width}.png', full_page=True)
                other = context.new_page()
                other.goto('http://discovery-ui.test/')
                expect(other.locator('#searchBtn')).to_be_enabled()
                page.bring_to_front()
                page.locator('#searchBtn').click()
                expect(page.locator('#searchBtn')).to_be_disabled()
                expect(page.locator('#searchBtn')).to_have_text('正在扫描岗位…')
                self.assertEqual(writes, ['/api/search'])
                other.bring_to_front()
                expect(other.locator('#searchBtn')).to_be_disabled(timeout=10000)
                page.bring_to_front()
                page.on('dialog', lambda dialog: dialog.accept())
                page.locator('#batchBtn').click()
                expect(page.locator('#queueReviewPanel')).to_be_visible()
                expect(page.locator('#queueReviewScope')).to_have_value('queued')
                for width in [1280, 375]:
                    page.set_viewport_size({'width':width,'height':1000})
                    self.assertTrue(page.locator('#queueReviewPanel').evaluate('n=>n.scrollWidth<=n.clientWidth+1'))
                    page.locator('#queueReviewPanel').screenshot(path=f'tmp/queue-review-{width}.png')
                self.assertEqual(writes, ['/api/search'])
                page.locator('#queueReviewBtn').click()
                expect(page.locator('#queueReviewStatus')).to_contain_text('批量')
                self.assertEqual(writes, ['/api/search','/api/review/batch'])
                self.assertTrue(review_urls[0].endswith('?mode=queued'))
                running = False
                page.evaluate('pollScan()')
                expect(page.locator('#searchBtn')).to_be_enabled()
                fail_scan = True
                page.locator('#searchBtn').click()
                expect(page.locator('#discoveryActionStatus')).to_contain_text('Test scan unavailable')
                expect(page.locator('#searchBtn')).to_be_enabled()
                self.assertEqual(errors, [])
            finally:
                browser.close()
