import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

STATIC=Path(__file__).resolve().parents[1]/'static'

class MotionTests(unittest.TestCase):
    def test_explicit_navigation_disclosure_busy_and_motion_preferences(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1280,'height':900});errors=[];unexpected=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    path=urlparse(route.request.url).path
                    if path.startswith('/static/'):
                        route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if path!='/':unexpected.append(path)
                    route.fulfill(content_type='text/html',body='''<meta charset="utf-8"><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/angelina-ui.css"><link rel="stylesheet" href="/static/motion.css"><div class="shell"><aside><nav class="primary-nav"><button id="one" class="navmain active">One</button><button id="two" class="navmain">Two</button></nav></aside><main><section id="first">First</section><section id="second" class="hidden"><details><summary>Details</summary><label>Answer<input id="answer" value="Kept"></label><p>Useful content stays interactive.</p></details><details class="wb-data" style="max-height:100px;overflow:auto" open><summary>Data</summary><div style="height:500px">Rows</div></details><div id="cards" aria-busy="false">Results</div></section></main></div><script src="/static/interaction-refinements.js"></script><script>function go(id){document.querySelectorAll('.navmain').forEach(n=>n.classList.toggle('active',n.id===id));first.classList.toggle('hidden',id!=='one');second.classList.toggle('hidden',id!=='two');InteractionMotion.enterView(id==='one'?first:second)}one.onclick=()=>go('one');two.onclick=()=>go('two');</script>''')
                page.route('**/*',respond);page.goto('http://motion.test/')
                expect(page.locator('.primary-nav')).to_have_attribute('data-motion-selected','true')
                before=page.locator('.primary-nav').evaluate("e=>e.style.getPropertyValue('--nav-y')")
                page.locator('#two').click();expect(page.locator('#second')).to_be_visible()
                page.wait_for_function("document.querySelector('.primary-nav').style.getPropertyValue('--nav-y')!=="+repr(before))
                page.wait_for_function("second.getAnimations().length===0")
                page.evaluate("second.append(document.createTextNode('Background update'))")
                self.assertEqual(page.locator('#second').evaluate('e=>e.getAnimations().length'),0)
                summary=page.locator('#second details:not(.wb-data)>summary');summary.focus();page.keyboard.press('Enter')
                expect(page.locator('#answer')).to_be_visible();page.locator('#answer').fill('Still here')
                summary.click();summary.click();expect(page.locator('#answer')).to_have_value('Still here')
                page.locator('.wb-data').evaluate('e=>e.scrollTop=80')
                self.assertGreaterEqual(page.locator('.wb-data').evaluate('e=>e.scrollTop'),78)
                page.evaluate("cards.setAttribute('aria-busy','true')")
                self.assertTrue(page.locator('#cards').evaluate("e=>getComputedStyle(e,'::before').animationName==='motion-reading'"))
                page.evaluate("cards.setAttribute('aria-busy','false')")
                self.assertEqual(page.locator('#cards').evaluate("e=>getComputedStyle(e,'::before').animationName"),'none')
                page.emulate_media(reduced_motion='reduce')
                self.assertGreater(page.evaluate("()=>{go('one');return first.getAnimations().length}"),0)
                self.assertEqual(page.locator('.primary-nav').evaluate("e=>getComputedStyle(e,'::before').transitionDuration"),'0.18s, 0.18s, 0.18s')
                self.assertEqual(page.evaluate("()=>{go('two');go('one');return [first.getAnimations().length,second.getAnimations().length]}"),[1,0])
                if page.evaluate("CSS.supports('interpolate-size:allow-keywords')"):
                    self.assertIn('0.2s',page.locator('#second details:not(.wb-data)').evaluate("e=>getComputedStyle(e,'::details-content').transitionDuration"))
                page.emulate_media(reduced_motion='no-preference');page.evaluate("document.documentElement.dataset.angelinaMode='quiet'");page.locator('#two').click()
                self.assertEqual(page.locator('#second').evaluate('e=>e.getAnimations().length'),0)
                self.assertEqual(page.locator('#two').evaluate('e=>e.getAnimations().length'),0)
                page.emulate_media(reduced_motion='reduce');summary.click();summary.click();expect(page.locator('#answer')).to_have_value('Still here')
                self.assertEqual(unexpected,[]);self.assertEqual(errors,[])
            finally:browser.close()
