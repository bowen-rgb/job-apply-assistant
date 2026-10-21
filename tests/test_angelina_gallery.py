import json
import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect

STATIC=Path(__file__).resolve().parents[1]/'static'

class AngelinaGalleryTests(unittest.TestCase):
    def test_all_48_assets_preview_page_selection_reset_and_persistence(self):
        catalog=json.loads((STATIC/'artwork/angelina/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(len(catalog),48)
        self.assertEqual({kind:sum(x['kind']==kind for x in catalog) for kind in ['character','animation','sticker']},{'character':10,'animation':10,'sticker':28})
        self.assertTrue(all((STATIC/'artwork/angelina'/asset['file']).is_file() for asset in catalog))
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN',viewport={'width':1280,'height':900});errors=[];writes=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    path=urlparse(route.request.url).path
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if route.request.method!='GET':writes.append(path)
                    route.fulfill(content_type='text/html',body='''<html><meta charset="utf-8"><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/workbench.css"><link rel="stylesheet" href="/static/reference-system.css"><link rel="stylesheet" href="/static/angelina-ui.css"><div class="shell"><aside><nav class="primary-nav"><button id="jobsNav">岗位</button></nav></aside><main><section id="jobsView"><header class="surface-heading"><div><h1>Jobs</h1><p>Find one suitable application.</p></div></header></section></main></div><script src="/static/locale.js"></script><script>window.Accounts={key:s=>'test:'+s}</script><script src="/static/angelina-gallery.js"></script><script src="/static/angelina-ui.js"></script><script>Locale.ready.then(()=>AngelinaUI.init())</script></html>''')
                page.route('**/*',respond);page.goto('http://gallery.test/')
                page.locator('#angelinaGalleryOpen').click()
                expect(page.locator('#angelinaGallery')).to_be_visible()
                expect(page.locator('[data-aa-choose]')).to_have_count(10)
                page.locator('[data-aa-choose=beach-png]').click()
                expect(page.locator('#jobsView .aa-scene')).to_have_attribute('src','/static/artwork/angelina/beach.png')
                page.locator('[data-aa-tab=sticker]').click()
                expect(page.locator('[data-aa-choose]')).to_have_count(28)
                page.locator('[data-aa-choose=ui-22]').click()
                expect(page.locator('#jobsView .aa-ornament')).to_have_attribute('src','/static/artwork/angelina/stars.png')
                page.locator('[data-aa-tab=animation]').click()
                expect(page.locator('[data-aa-choose]')).to_have_count(10)
                page.locator('[data-aa-preview=sit-gif]').click()
                expect(page.locator('.aa-gallery-image img').first).to_have_attribute('src', '/static/artwork/angelina/sit.gif')
                for width in [1280,375]:
                    page.set_viewport_size({'width':width,'height':900})
                    self.assertTrue(page.locator('#angelinaGallery').evaluate('e=>e.scrollWidth<=e.clientWidth+1'))
                    page.screenshot(path=f'tmp/angelina-gallery-{width}.png',animations='disabled')
                page.locator('#aaGalleryClose').click();page.set_viewport_size({'width':1280,'height':900});page.reload()
                expect(page.locator('#jobsView .aa-scene')).to_have_attribute('src','/static/artwork/angelina/beach.png')
                page.locator('#angelinaGalleryOpen').click();page.locator('#aaGalleryReset').click()
                expect(page.locator('#jobsView .aa-scene')).to_have_attribute('src','/static/artwork/angelina/explore.png')
                self.assertEqual(errors,[]);self.assertEqual(writes,[])
            finally:browser.close()
