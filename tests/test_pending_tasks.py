import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
from fastapi.testclient import TestClient
from app import workspaces,pending_tasks
from app.main import app

STATIC=Path(__file__).resolve().parents[1]/'static'


class PendingTaskTests(unittest.TestCase):
    def test_queue_import_is_idempotent_and_contact_material_and_sent_jobs_are_blocked(self):
        from app import db
        with tempfile.TemporaryDirectory() as folder,patch.object(workspaces,'ROOT',Path(folder)):
            token=workspaces.CURRENT.set('default')
            try:
                db.init_db()
                pending_tasks.add([{'title':'Research vacancy','url':'https://lab.test/job','kind':'vacancy'},
                                   {'title':'Contact a professor','url':'https://lab.test/team','kind':'contact'},
                                   {'title':'Find CV','kind':'material'}])
                rows=pending_tasks.read()
                first=pending_tasks.queue_task(rows[0]['id'])
                self.assertEqual(first['queue_status'],'queued')
                self.assertTrue(pending_tasks.queue_task(rows[0]['id'])['already_queued'])
                for row in rows[1:]:
                    with self.assertRaises(ValueError):pending_tasks.queue_task(row['id'])
                with db.connect() as c:
                    self.assertEqual(c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],1)
                    self.assertEqual(c.execute('SELECT COUNT(*) FROM application_queue').fetchone()[0],1)
                    self.assertEqual(c.execute('SELECT COUNT(*) FROM applications').fetchone()[0],0)
                    c.execute("UPDATE jobs SET application_status='submitted' WHERE id=?",(first['job_id'],))
                with self.assertRaises(ValueError):pending_tasks.queue_task(rows[0]['id'])
                other=workspaces.create('Candidate C');workspaces.CURRENT.set(other)
                with self.assertRaises(KeyError):pending_tasks.queue_task(rows[0]['id'])
            finally:workspaces.CURRENT.reset(token)

    def test_tasks_are_isolated_idempotent_and_completion_is_not_submission(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(workspaces,'ROOT',Path(folder)):
            token=workspaces.CURRENT.set('default')
            try:
                row={'title':'Apply at a laboratory','url':'https://lab.test/job','kind':'vacancy'}
                pending_tasks.add([row,row]);self.assertEqual(len(pending_tasks.read()),1)
                item=pending_tasks.read()[0];pending_tasks.set_status(item['id'],'done')
                pending_tasks.add([row]);self.assertEqual(pending_tasks.read()[0]['status'],'done')
                other=workspaces.create('Candidate B');workspaces.CURRENT.set(other)
                self.assertEqual(pending_tasks.read(),[])
                with self.assertRaises(KeyError):pending_tasks.set_status(item['id'],'done')
                pending_tasks.add([{'title':'Find my CV','kind':'material'}])
                self.assertEqual(len(pending_tasks.read()),1)
                self.assertFalse((workspaces.data_dir()/'jobs.db').exists())
                with self.assertRaises(ValueError):pending_tasks.add([{'title':'Bad URL','url':'javascript:alert(1)'}])
                with self.assertRaises(ValueError):pending_tasks.set_status(pending_tasks.read()[0]['id'],'submitted')
            finally:workspaces.CURRENT.reset(token)

    def test_task_api_rejects_stale_profile_and_unknown_tasks(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(workspaces,'ROOT',Path(folder)):
            token=workspaces.CURRENT.set('default')
            try:pending_tasks.add([{'title':'Check whether already applied','kind':'vacancy'}])
            finally:workspaces.CURRENT.reset(token)
            client=TestClient(app);items=client.get('/api/pending-tasks').json()['items']
            identifier=items[0]['id']
            self.assertEqual(client.patch('/api/pending-tasks/'+identifier,json={'status':'done'}).status_code,200)
            self.assertEqual(client.get('/api/pending-tasks').json()['items'][0]['status'],'done')
            self.assertEqual(client.patch('/api/pending-tasks/'+identifier,json={'status':'submitted'}).status_code,400)
            self.assertEqual(client.patch('/api/pending-tasks/missing',json={'status':'done'}).status_code,404)
            self.assertEqual(client.get('/api/pending-tasks',headers={'X-Candidate-ID':'000000000001'}).status_code,409)

    def test_dropdown_switches_back_and_forth_and_keeps_pending_lists_owned(self):
        active='default';requests=[];tasks={'default':[],'000000000001':[dict(id='abc123',title='Research task B',kind='vacancy',url='https://lab.test/job',note='Submission unknown',source='Conversation',status='pending')]}
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN');errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    nonlocal active
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    requests.append((path,route.request.headers.get('x-candidate-id')))
                    data={}
                    if path=='/api/candidates':data={'active_id':active,'items':[dict(id='default',name='Candidate A',identity={},active=active=='default'),dict(id='000000000001',name='Candidate B',identity={},active=active!='default')]}
                    elif path.startswith('/api/candidates/') and path.endswith('/activate'):active=path.split('/')[3];data={'ok':True}
                    elif path=='/api/pending-tasks':data={'items':tasks[active]}
                    elif path=='/api/pending-tasks/abc123':tasks[active][0]['status']=json.loads(route.request.post_data)['status'];data={'ok':True}
                    elif path=='/api/profile':data={'automation':{}}
                    elif path in {'/api/jobs','/api/resumes','/api/sources','/api/pipeline'}:data=[]
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://profiles.test/')
                expect(page.locator('#candidateSelect')).to_have_value('default')
                page.locator('#pendingTasksNav').click()
                expect(page.locator('#pendingTasksDialog')).to_contain_text('Candidate A')
                expect(page.locator('.pending-task')).to_have_count(0)
                page.locator('#pendingClose').click()
                page.locator('#candidateSelect').select_option('000000000001')
                expect(page.locator('#candidateSelect')).to_have_value('000000000001')
                page.locator('#pendingTasksNav').click()
                expect(page.locator('#pendingTasksDialog')).to_contain_text('Candidate B')
                expect(page.locator('.pending-task')).to_contain_text('Research task B')
                page.locator('[data-task-id=abc123]').click()
                expect(page.locator('.pending-task')).to_have_count(0)
                page.locator('[data-task-filter=done]').click()
                expect(page.locator('.pending-task')).to_contain_text('Research task B')
                page.locator('#pendingClose').click()
                page.locator('#candidateSelect').select_option('default')
                expect(page.locator('#candidateSelect')).to_have_value('default')
                page.locator('#pendingTasksNav').click()
                expect(page.locator('.pending-task')).to_have_count(0)
                self.assertEqual(errors,[])
                self.assertIn(('/api/pending-tasks','000000000001'),requests)
                self.assertIn(('/api/pending-tasks','default'),requests)
                self.assertFalse(any('/application-status' in path or path=='/api/queue' for path,_ in requests))
            finally:browser.close()
