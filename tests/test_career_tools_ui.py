import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
from tests.ui_navigation import navigate

STATIC=Path(__file__).resolve().parents[1]/'static'


class CareerToolsUITests(unittest.TestCase):
    def test_native_tools_have_real_entries_statuses_and_approval_controls(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN');errors=[];writes=[];tasks={}
                page.on('pageerror',lambda error:errors.append(str(error)))
                job={'id':1,'company':'Example Lab','title':'Simulation internship','tracker_stage':'submitted','application_status':'submitted'}
                sources=[{'id':'adzuna','label':'Adzuna','keys':['app_id','app_key'],'credentials':{},'settings':{},'enabled':False,'configured':False}]
                def route(r):
                    path=urlparse(r.request.url).path;method=r.request.method
                    if path=='/':r.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):r.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    data={}
                    if path=='/api/candidates':data={'active_id':'default','items':[{'id':'default','name':'Test profile','identity':{}}]}
                    elif path=='/api/profile':data={'automation':{}}
                    elif path in {'/api/jobs','/api/pipeline'}:data=[job]
                    elif path in {'/api/sources','/api/resumes'}:data=[]
                    elif path=='/api/queue':data={'items':[],'counts':{}}
                    elif path=='/api/insights':data={'config':{},'followups':[],'mail_proposals':[]}
                    elif path=='/api/capabilities':data={'sources':sources,'models':{'configured':[],'agents':{}},'tasks':list(tasks.values()),'templates':[],'documents':[],'portals':[],'salary':[],'notion':{},'gmail_compose':{},'selected_backend':'chatgpt'}
                    elif path=='/api/capabilities/tasks' and method=='POST':
                        body=r.request.post_data_json;writes.append((path,body));identifier=len(tasks)+1
                        result={'sources':[{'url':'https://employer.test/source','text':'Original employer evidence'}]} if body['kind']=='research' else {'document':{'name':'Test'},'quality':{'passed':True},'artifact':'tasks/2/cv.pdf','needs_approval':True}
                        tasks[identifier]={'id':identifier,**body,'state':'ready','result':result,'error':''};data={'id':identifier,'state':'queued'}
                    elif path.startswith('/api/capabilities/tasks/'):
                        identifier=int(path.split('/')[4])
                        if path.endswith('/adopt-cv'):writes.append((path,{}));data={'resume_id':'approved'}
                        else:data=tasks[identifier]
                    elif path=='/api/capabilities/lint':writes.append((path,r.request.post_data_json));data={'issues':[],'stats':{'words':4}}
                    elif path.startswith('/api/capabilities/sources/'):
                        writes.append((path,r.request.post_data_json));data={'ok':True}
                    r.fulfill(json=data)
                page.route('**/*',route);page.goto('http://career-tools.test/');navigate(page,'tools')
                tools=page.locator('#careerTools');expect(page.locator('#toolsView h1')).to_have_text('材料与助手')
                expect(tools.locator('[data-tool-body]')).to_be_visible()
                self.assertFalse(writes)
                form=tools.locator('[data-task-form]');form.locator('[name=kind]').select_option('research');form.locator('[name=job]').select_option('1');form.locator('button[type=submit]').click()
                expect(tools.locator('[data-task-result]')).to_contain_text('已完成，请查看')
                tools.locator('[data-task-result] details summary').click();expect(tools.locator('[data-task-result]')).to_contain_text('Original employer evidence')
                self.assertEqual(writes[0][1]['job_id'],1)
                form.locator('[name=kind]').select_option('tailor_cv');form.locator('[name=job]').select_option('1');form.locator('button[type=submit]').click()
                expect(tools.locator('[data-tool=adopt-cv]')).to_be_visible()
                self.assertFalse(any(path.endswith('/adopt-cv') for path,_ in writes))
                tools.locator('[data-tool=adopt-cv]').click()
                expect(tools.locator('[data-tool=adopt-cv]')).to_be_enabled()
                self.assertTrue(any(path.endswith('/adopt-cv') for path,_ in writes))
                for width in (1280,375):
                    page.set_viewport_size({'width':width,'height':900});tools.scroll_into_view_if_needed()
                    page.screenshot(path=f'tmp/career-tools-{width}.png')
                    self.assertTrue(tools.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'))
                page.locator('#languageSelect').select_option('fr')
                expect(page.locator('#toolsView h1')).to_have_text('Documents et assistants')
                expect(tools.locator('[data-task-form]')).to_contain_text('Que souhaitez-vous faire ?')
                page.screenshot(path='tmp/career-tools-fr-375.png')
                self.assertFalse(errors,errors)
            finally:browser.close()


if __name__=='__main__':unittest.main()
