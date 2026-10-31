import unittest
from playwright.sync_api import expect
from tests import test_workspace_menu as fixture
from tests.ui_navigation import navigate


class MatchAutomationUITests(unittest.TestCase):
    setUp=fixture.WorkspaceMenuTests.setUp
    tearDown=fixture.WorkspaceMenuTests.tearDown

    def test_click_missing_information_save_candidate_fact_and_resume(self):
        self.page.route('**/api/matches/automation',lambda r:r.fulfill(json={'phase':'blocked','unresolved':1,'total':18,'completed':18}))
        self.page.route('**/api/matches/gaps',lambda r:r.fulfill(json={'candidate_id':'default','answers':[],'items':[{
            'id':1,'company':'Example','title':'Simulation','url':'https://employer.test/1','review_summary':'Missing Python evidence',
            'questions':[{'kind':'candidate','question':'Python project?','reason':'Required scripting','evidence':'Python required'},
                         {'kind':'posting','question':'Exact start?'}]}]}))
        writes=[]
        def save(r):writes.append(r.request.post_data_json);r.fulfill(json={'ok':True})
        self.page.route('**/api/matches/gaps/answers',save)
        navigate(self.page,'jobs');self.page.evaluate('MatchAutomation.refresh()')
        self.page.get_by_role('button',name='查看缺少什么 / 补全信息（1）').click()
        dialog=self.page.locator('.review-gaps-dialog')
        expect(dialog).to_be_visible();expect(dialog).to_contain_text('Python required')
        dialog.locator('textarea').first.fill('Personal simulation script')
        dialog.get_by_role('checkbox').first.check()
        expect(dialog.get_by_role('checkbox').nth(1)).to_be_disabled()
        dialog.get_by_role('button',name='保存这条信息').first.click()
        expect(dialog).to_contain_text('已保存到当前个人档案')
        self.assertEqual(writes[0]['candidate_id'],'default');self.assertTrue(writes[0]['reusable'])
        self.page.screenshot(path='tmp/review-gaps-desktop.png')
        dialog.get_by_role('button',name='继续批量复核',exact=True).click()
        expect(dialog).not_to_be_visible()
        self.assertEqual(self.errors,[])

    def test_blocked_batch_keeps_the_direct_retry_button_available(self):
        self.page.route('**/api/matches/automation',lambda route:route.fulfill(json={
            'phase':'blocked','total':116,'completed':16,'error':'No ChatGPT response detected for final-review'}))
        navigate(self.page,'jobs');self.page.evaluate('MatchAutomation.refresh()')
        expect(self.page.locator('#reviewMatchesBtn')).to_have_text('继续 / 重试批量处理')
        expect(self.page.locator('#reviewMatchesBtn')).to_be_enabled()
        expect(self.page.locator('#matchAutomationStatus')).to_contain_text('ChatGPT 没有返回有效回复')
        expect(self.page.locator('dialog[open]')).to_have_count(0)

    def test_native_job_workflow_progress_stop_and_queue_destination(self):
        state={'phase':'idle','eligible':116}
        writes=[]
        def respond(route):
            if route.request.method=='POST':
                writes.append(route.request.url)
                if route.request.url.endswith('/stop'):state.update(phase='stopped')
                else:state.update(phase='running',total=116,completed=5,enqueued=3,skipped=1,unresolved=1,current_title='Simulation example')
            route.fulfill(json=state)
        self.page.route('**/api/matches/automation**',respond)
        navigate(self.page,'jobs');self.page.evaluate('MatchAutomation.refresh()')
        for width in [1280]:
            self.page.set_viewport_size({'width':width,'height':1000})
            expect(self.page.locator('#reviewMatchesBtn')).to_be_visible()
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)
        self.page.locator('#reviewMatchesBtn').click()
        expect(self.page.locator('#reviewMatchesBtn')).to_be_disabled()
        expect(self.page.locator('#matchAutomationStatus')).to_contain_text('已复核 5/116')
        expect(self.page.locator('#matchAutomationStatus')).to_contain_text('已入队 3')
        expect(self.page.locator('#matchAutomationStatus')).to_contain_text('Simulation example')
        self.page.locator('#matchAutomationStatus button').filter(has_text='停止复核').click()
        self.page.evaluate('MatchAutomation.refresh()')
        expect(self.page.locator('#matchAutomationStatus')).to_contain_text('已停止')
        self.page.locator('#matchAutomationStatus button').filter(has_text='查看申请队列').click()
        expect(self.page.locator('#pipelineView')).to_be_visible()
        self.assertEqual(len(writes),2)
        self.assertEqual(self.errors,[])
