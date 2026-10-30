import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
from tests.ui_navigation import navigate

STATIC=Path(__file__).resolve().parents[1]/'static'


class ApplicationInsightsUITests(unittest.TestCase):
    def test_native_pipeline_can_review_evidence_and_followups_without_sending(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN'); errors=[]; mutations=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                pending=[dict(message_id='m1',company='Example Lab',title='Simulation internship',signal='rejected',evidence='not selected',sender='hr@lab.test',subject='Application reply',received_at='2026-10-01',reason='')]
                def respond(route):
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):
                        route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    data={}
                    if path=='/api/candidates':data={'active_id':'default','items':[{'id':'default','name':'Test profile','identity':{}}]}
                    elif path=='/api/profile':data={'automation':{}}
                    elif path in {'/api/jobs','/api/sources','/api/resumes','/api/pipeline'}:data=[]
                    elif path=='/api/queue':data={'counts':{},'items':[]}
                    elif path=='/api/insights':data={'config':{'follow_up':{'after_days':14,'max_followups':1},'dimensions':[]},'followups':[],'mail_proposals':pending}
                    elif path=='/api/insights/gmail-sync':mutations.append(path);data={'read':1,'proposed':1}
                    elif path=='/api/insights/mail-confirm':
                        mutations.append((path,route.request.post_data_json));pending.clear();data={'ok':True}
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://insights.test/')
                navigate(page,'pipeline')
                expect(page.locator('#applicationInsights')).to_contain_text('招聘反馈与下一步')
                expect(page.locator('[data-mail-proposals]')).to_contain_text('not selected')
                self.assertFalse(mutations)
                page.locator('[data-insight="confirm"]').click()
                expect(page.locator('[data-insight-status]')).to_contain_text('请先核对')
                self.assertFalse(mutations)
                for width in [1280,375]:
                    page.set_viewport_size({'width':width,'height':900})
                    page.locator('#applicationInsights').scroll_into_view_if_needed()
                    page.screenshot(path=f'tmp/application-insights-{width}.png')
                    self.assertTrue(page.locator('#applicationInsights').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'))
                page.locator('[data-mail-id]').check()
                page.locator('[data-insight="confirm"]').click()
                expect(page.locator('[data-mail-proposals]')).to_contain_text('暂无待确认反馈')
                self.assertEqual(mutations[0][1],{'message_ids':['m1'],'accept':True})
                self.assertFalse(errors,errors)
            finally:browser.close()


if __name__=='__main__':unittest.main()
