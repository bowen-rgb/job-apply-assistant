import unittest
from playwright.sync_api import expect
from tests import test_workspace_menu as fixture
from tests.ui_navigation import navigate


class MatchAutomationUITests(unittest.TestCase):
    setUp=fixture.WorkspaceMenuTests.setUp
    tearDown=fixture.WorkspaceMenuTests.tearDown

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
