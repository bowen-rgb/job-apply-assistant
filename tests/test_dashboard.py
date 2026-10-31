from tests.ui_navigation import navigate, set_appearance
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


STATIC = Path(__file__).resolve().parents[1] / 'static'


class DashboardMetricTests(unittest.TestCase):
    def test_manual_submission_from_failed_focus_completes_queue_and_removes_handoff(self):
        job=dict(id=56,title='VIP reception',url='https://example.test/job',company='Profil',tracker_stage='saved',application_status='error',application_error='Le formulaire de candidature n’est pas encore accessible.')
        item=dict(job,job_id=56,status='error',note=job['application_error'])
        posts=[]
        with sync_playwright() as p,ExitStack() as cleanup:
            browser=p.chromium.launch(headless=True);cleanup.callback(browser.close)
            page=browser.new_page(locale='zh-CN');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script("window===window.top&&localStorage.setItem('jaa-ui-mode', 'full')")
            page.on('dialog',lambda d:d.accept())
            def respond(route):
                path=urlparse(route.request.url).path
                if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html')
                elif path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')))
                elif path in {'/api/jobs','/api/pipeline'}:route.fulfill(json=[job])
                elif path=='/api/queue':route.fulfill(json={'items':[item],'counts':{item['status']:1},'running':False,'paused':True,'last_job_id':56})
                elif path.endswith('/application-status'):
                    posts.append(json.loads(route.request.post_data));job.update(application_status='submitted',tracker_stage='submitted');item.update(application_status='submitted',status='done');route.fulfill(json={'ok':True})
                elif path.endswith('/applications'):route.fulfill(json=[{'status':'apply_error','note':'Previous failure retained'}])
                elif path.endswith('/stage-events') or path.endswith('/human-review-events'):route.fulfill(json=[])
                else:route.fulfill(json=[] if path=='/api/sources' else {})
            page.route('**/*',respond);page.goto('http://dashboard.test/');navigate(page,'jobs');navigate(page,'pipelineNav')
            expect(page.locator('#queueFocus')).to_contain_text('VIP reception')
            expect(page.locator('#queueFocus')).to_contain_text('我已手动投递完成')
            expect(page.locator('#queueFocus')).to_contain_text('页面已关闭')
            expect(page.locator('#queueFocus a')).to_have_attribute('href',job['url'])
            page.locator('#queueFocus button[onclick="confirmQueueSubmitted(56)"]').click()
            expect(page.locator('#queueFocus')).not_to_contain_text('VIP reception')
            expect(page.locator('#queueList .application-error')).to_have_count(0)
            expect(page.locator('#queueList button[onclick="takeOverApplication(56)"]')).to_have_count(0)
            expect(page.locator('#queueCounts')).to_contain_text('已完成 1')
            expect(page.locator('#pipelineBoard .pipeline-card')).to_contain_text('已投递')
            page.locator('#pipelineBoard details summary').click()
            expect(page.locator('#pipelineBoard .history-content')).to_contain_text('过去的准备失败记录')
            self.assertEqual(posts,[{'status':'submitted'}]);self.assertEqual(errors,[])

    def test_queue_current_task_failures_filter_and_takeover_are_visible(self):
        jobs=[dict(id=i,title=f'Reception {i}',company='Hotel',url=f'https://example.test/{i}',tracker_stage='queued' if i<3 else 'saved',application_status='preparing_letter' if i==1 else 'error' if i==3 else '',application_error='Le formulaire de candidature n’est pas encore accessible. Aucun document n’a été joint.' if i==3 else '') for i in [1,2,3]]
        items=[dict(j,job_id=j['id'],status='running' if j['id']==1 else 'error' if j['id']==3 else 'queued',application_step='letter' if j['id']==1 else 'finding_form',note=j['application_error']) for j in jobs]
        queue=dict(items=items,counts={'running':1,'queued':1,'error':1},current_job_id=1,running=True)
        requests=[]
        with sync_playwright() as p,ExitStack() as cleanup:
            browser=p.chromium.launch(headless=True);cleanup.callback(browser.close)
            page=browser.new_page(locale='zh-CN');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script("window===window.top&&localStorage.setItem('jaa-ui-mode', 'full')")
            def respond(route):
                path=urlparse(route.request.url).path
                if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html')
                elif path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')))
                elif path in {'/api/jobs','/api/pipeline'}:route.fulfill(json=jobs)
                elif path=='/api/queue':route.fulfill(json=queue)
                elif path.endswith('/take-over'):
                    requests.append(path);route.fulfill(json={'message':'Onglet activé. Vérifiez les documents et réponses, puis envoyez sur le site et confirmez ici.'})
                else:route.fulfill(json=[] if path=='/api/sources' else {})
            page.route('**/*',respond);page.goto('http://dashboard.test/');navigate(page,'jobs');navigate(page,'pipelineNav')
            expect(page.locator('#queueFocus')).to_contain_text('当前正在处理')
            expect(page.locator('#queueFocus')).to_contain_text('Reception 1')
            expect(page.locator('#queueFocus')).to_contain_text('正在撰写求职信')
            expect(page.locator('#queueFocus button')).to_have_text('先停止，再接管')
            page.locator('#queueFilter').select_option('error')
            expect(page.locator('#queueList [data-queue-job]')).to_have_count(1)
            expect(page.locator('#queueList')).to_contain_text('没有找到可填写的申请表')
            expect(page.locator('#queueList')).to_contain_text('不代表招聘方拒绝')
            page.locator('#queueList details summary').click()
            page.evaluate('loadPipeline()')
            expect(page.locator('#queueList details')).to_have_attribute('open','')
            page.locator('#queueList button[onclick="takeOverApplication(3)"]').click()
            expect(page.locator('#pipelineStatus')).to_contain_text('已切换到申请页面')
            self.assertEqual(requests,['/api/jobs/3/take-over'])
            expect(page.locator('#pipelineBoard .pipeline-card').filter(has_text='Reception 3')).to_contain_text('自动准备失败')
            queue.update(running=False,paused=True,last_job_id=1,current_job_id=None,counts={'waiting_user':1,'queued':1,'error':1})
            items[0].update(status='waiting_user',application_status='needs_human',application_step='handoff')
            jobs[0]['application_status']='needs_human';page.evaluate('loadPipeline()')
            expect(page.locator('#queueFocus')).to_contain_text('下一步需要你处理')
            expect(page.locator('#queueFocus')).to_contain_text('Reception 1')
            expect(page.locator('#queueFocus')).to_contain_text('页面已关闭')
            self.assertEqual(errors,[])

    def test_review_export_controls_language_filtered_scope_download_and_cancel(self):
        jobs=[dict(id=1,title='One',url='https://example.test/1',decision='keep',review_verdict='APPLY',human_review_status='pending',provider_key='one',score=90),
              dict(id=2,title='Two',url='https://example.test/2',decision='review',review_verdict='HUMAN_REVIEW',human_review_status='pending',provider_key='two',score=50),
              dict(id=3,title='Done',decision='keep',review_verdict='APPLY',human_review_status='pending',application_status='submitted',score=90)]
        state={'id':'a'*32,'status':'ready','format':'xlsx','language':'fr','message':'Export prêt.','total':1,'completed':1}
        payloads=[]
        with sync_playwright() as p,ExitStack() as cleanup:
            browser=p.chromium.launch(headless=True);cleanup.callback(browser.close)
            page=browser.new_page(locale='zh-CN')
            page.add_init_script("window===window.top&&localStorage.setItem('jaa-ui-mode', 'full')")
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            def respond(route):
                path=urlparse(route.request.url).path
                if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html')
                elif path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')))
                elif path=='/api/jobs':route.fulfill(json=jobs)
                elif path=='/api/sources':route.fulfill(json=[dict(key='one',label='Source one',enabled=True),dict(key='two',label='Source two',enabled=True)])
                elif path=='/api/review-exports':payloads.append(json.loads(route.request.post_data));route.fulfill(json=state)
                elif path.endswith('/cancel'):state.update(status='cancelled',message='Export annulé.');route.fulfill(json=state)
                elif path.startswith('/api/review-exports/'):route.fulfill(json=state)
                else:route.fulfill(json={})
            page.route('**/*',respond)
            page.goto('http://dashboard.test/');navigate(page,'jobs')
            page.locator('.review-export-panel summary').click()
            expect(page.locator('#reviewExportCount')).to_have_text('2 个岗位将导出')
            navigate(page,'jobs')
            page.locator('[data-metric-filter="decide"]').click()
            page.locator('#sourceSelect').select_option('one')
            page.locator('#reviewExportScope').select_option('visible')
            expect(page.locator('#reviewExportCount')).to_have_text('1 个岗位将导出')
            page.locator('#reviewExportLanguage').select_option('fr')
            page.locator('#reviewExportFormat').select_option('xlsx')
            page.locator('#reviewExportTranslate').uncheck()
            page.locator('#reviewExportBtn').click()
            expect(page.locator('#reviewExportDownload')).to_be_visible()
            self.assertEqual(payloads[0],dict(scope='visible',job_ids=[1],format='xlsx',language='fr',translate_text=False))
            expect(page.locator('#reviewExportDownload')).to_have_attribute('href',f'/api/review-exports/{"a"*32}/download')
            expect(page.locator('#reviewExportDownload')).to_contain_text('FR · XLSX')
            state.update(status='running',message='Traduction des textes de revue via ChatGPT…')
            page.locator('#reviewExportBtn').click()
            expect(page.locator('#reviewExportCancelBtn')).to_be_visible()
            expect(page.locator('#reviewExportBtn')).to_be_disabled()
            page.locator('#reviewExportCancelBtn').click()
            expect(page.locator('#reviewExportStatus')).to_have_text('导出已取消。')
            expect(page.locator('#reviewExportDownload')).to_be_hidden()
            expect(page.locator('#reviewExportBtn')).to_be_enabled()
            self.assertEqual(errors,[])

    def test_queue_requests_automatic_review_without_separate_human_controls(self):
        jobs=[dict(id=i,title=f'Review {i}',url=f'https://example.test/{i}',decision='keep',
                   review_verdict='APPLY' if i==1 else 'HUMAN_REVIEW',score=90) for i in [1,2]]
        posts=[]
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN');errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    if route.request.method=='POST':
                        posts.append((route.request.url,json.loads(route.request.post_data or '{}')))
                        if path=='/api/queue':jobs[0]['queue_status']='queued'
                    data={}
                    if path=='/api/jobs':data=jobs
                    elif path=='/api/queue':data={'items':[],'counts':{'queued':2},'running':False}
                    elif path in ['/api/pipeline','/api/sources']:data=[]
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://dashboard.test/');navigate(page,'jobs')
                expect(page.locator('[data-human-review], #batchBtn, #queueReviewPanel')).to_have_count(0)
                page.locator('button[onclick="queueJob(1)"]').click()
                expect(page.locator('#status')).to_contain_text('队列')
                self.assertTrue(any(body.get('auto_review') and body['job_ids']==[1] for _,body in posts))
                navigate(page,'pipeline');page.locator('#queueRunBtn').click()
                self.assertTrue(any('auto_review=true' in url for url,_ in posts))
                self.assertEqual(errors,[])
            finally:browser.close()

    def test_every_filter_uses_its_own_state_and_search_metrics_match_cards(self):
        jobs = [dict(id=i, title=f'Job {i}', url=f'https://example.test/{i}', decision='low',
                     application_status='', user_action='', review_verdict='', queue_status='',
                     tracker_stage='', score=20, provider_key='one') for i in range(1, 11)]
        jobs[0].update(decision='reject', review_verdict='SKIP')
        jobs[1].update(decision='expired', valid_through='2000-01-01')
        jobs[2].update(tracker_stage='rejected', application_status='submitted', tracker_source='email', tracker_note='2026-10-03 rejection received')
        jobs[3].update(decision='keep', user_action='liked', review_verdict='APPLY')
        jobs[4].update(decision='review', review_verdict='HUMAN_REVIEW')
        jobs[5].update(queue_status='waiting_user', application_status='prefilled')
        jobs[6].update(user_action='skipped', decision='keep')
        jobs[7].update(application_status='withdrawn', tracker_stage='withdrawn')
        jobs[8].update(queue_status='error')
        jobs[9].update(application_status='submitted', user_action='skipped', provider_key='two')
        expected = {'all':[1,2,3,4,5,6,8,9], 'keep':[4], 'review':[5], 'liked':[4],
                    'approved':[4], 'queued':[6], 'submitted':[3,10],
                    'skipped':[7,10], 'expired':[2], 'rejected':[3], 'unsuitable':[1],
                    'reviewer_skip':[1], 'withdrawn':[8]}
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = playwright.chromium.launch(headless=True)
            cleanup.callback(browser.close)
            page = browser.new_page(locale='zh-CN')
            page.add_init_script("window===window.top&&localStorage.setItem('jaa-ui-mode', 'full')")
            errors=[]
            page.on('pageerror', lambda error: errors.append(str(error)))
            def respond(route):
                path=urlparse(route.request.url).path
                if path=='/': route.fulfill(path=str(STATIC/'index.html'), content_type='text/html')
                elif path.startswith('/static/'): route.fulfill(path=str(STATIC/path.removeprefix('/static/')))
                elif path=='/api/jobs': route.fulfill(json=jobs)
                elif path=='/api/sources': route.fulfill(json=[dict(key='one',label='Source one',enabled=True),dict(key='two',label='Source two',enabled=True)])
                else: route.fulfill(json={})
            page.route('**/*',respond)
            page.goto('http://dashboard.test/');navigate(page,'jobs')
            for name, ids in expected.items():
                with self.subTest(filter=name):
                    page.locator('#jobFilterSelect').select_option(name)
                    expect(page.locator('#cards .card')).to_have_count(len(ids))
                    for job_id in ids:
                        expect(page.locator('#cards .card').filter(has=page.locator(f'button[onclick="openLetter({job_id})"]'))).to_have_count(1)
            page.locator('#jobFilterSelect').select_option('rejected')
            expect(page.locator('#cards')).to_contain_text('招聘方邮件')
            expect(page.locator('#cards .apply')).to_be_disabled()
            page.locator('#jobFilterSelect').select_option('expired')
            expect(page.locator('#cards')).to_contain_text('2000-01-01')
            expect(page.locator('#cards .apply')).to_be_disabled()
            for metric in ['waiting','responses','decide','rejected']:
                page.locator(f'[data-metric-filter="{metric}"]').click()
                expect(page.locator('#cards .card')).to_have_count(len({'waiting':[10],'responses':[],'decide':[4,5],'rejected':[3]}[metric]))
                expect(page.locator(f'[data-metric-filter="{metric}"] b')).to_have_text(str(len({'waiting':[10],'responses':[],'decide':[4,5],'rejected':[3]}[metric])))
            page.locator('[data-metric-filter=waiting]').click()
            page.locator('#sourceSelect').select_option('two')
            expect(page.locator('[data-metric-filter="waiting"] b')).to_have_text('1')
            expect(page.locator('#cards .card')).to_have_count(1)
            page.locator('#q').fill('no such job')
            expect(page.locator('[data-metric-filter="waiting"] b')).to_have_text('1')
            expect(page.locator('#cards .card')).to_have_count(0)
            self.assertEqual(errors,[])

    def test_failed_submission_and_review_do_not_claim_success_and_saving_toggles(self):
        job=dict(id=1,title='One',url='https://example.test/1',decision='keep',score=90,user_action='',application_status='')
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser=playwright.chromium.launch(headless=True)
            cleanup.callback(browser.close)
            page=browser.new_page(locale='zh-CN')
            page.add_init_script("window===window.top&&localStorage.setItem('jaa-ui-mode', 'full')")
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('dialog',lambda dialog:dialog.accept())
            def respond(route):
                path=urlparse(route.request.url).path
                if path=='/': route.fulfill(path=str(STATIC/'index.html'),content_type='text/html')
                elif path.startswith('/static/'): route.fulfill(path=str(STATIC/path.removeprefix('/static/')))
                elif path=='/api/jobs': route.fulfill(json=[job])
                elif path.endswith('/decision'):
                    action=json.loads(route.request.post_data)['decision']
                    job['user_action']='' if action=='clear_user_action' else action
                    route.fulfill(json={'ok':True})
                elif route.request.method=='POST': route.fulfill(status=409,json={'detail':'Server rejected this action'})
                else: route.fulfill(json=[] if path=='/api/sources' else {})
            page.route('**/*',respond)
            page.goto('http://dashboard.test/');navigate(page,'jobs')
            page.locator('#cards .like').click()
            expect(page.locator('#cards .like')).to_have_text('取消收藏')
            page.locator('#cards .like').click()
            page.locator('#jobFilterSelect').select_option('liked')
            expect(page.locator('#cards .card')).to_have_count(0)
            page.locator('#jobFilterSelect').select_option('all')
            page.locator('button[onclick="markApplication(1,\'submitted\')"]').click()
            expect(page.locator('#status')).to_have_text('Server rejected this action')
            expect(page.locator('[data-metric-filter="waiting"] b')).to_have_text('0')
            self.assertEqual(errors,[])

    def test_skip_restore_preserves_submission_history_and_decision_counts(self):
        jobs=[dict(id=i,title=f'Job {i}',url=f'https://example.test/{i}',decision='keep',score=90,
                   application_status='submitted' if i==1 else '',user_action='') for i in [1,2]]
        from app.application_overview import snapshot
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale='zh-CN');errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                def respond(route):
                    path=urlparse(route.request.url).path
                    if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html');return
                    if path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')));return
                    data={}
                    if path=='/api/jobs':data=jobs
                    elif path=='/api/insights':data={'summary':snapshot(jobs,[],[])}
                    elif path.endswith('/decision'):
                        action=json.loads(route.request.post_data)['decision']
                        next(j for j in jobs if j['id']==int(path.split('/')[3]))['user_action']='' if action=='clear_user_action' else action
                    route.fulfill(json=data)
                page.route('**/*',respond);page.goto('http://dashboard.test/');navigate(page,'jobs')
                page.locator('[data-metric-filter=decide]').click()
                expect(page.locator('#cards .card')).to_have_count(1)
                page.locator('#cards .skip').click()
                expect(page.locator('[data-metric-filter=decide] b')).to_have_text('0')
                expect(page.locator('[data-metric-filter=waiting] b')).to_have_text('1')
                page.locator('#jobFilterSelect').select_option('skipped')
                expect(page.locator('#cards .card')).to_have_count(1)
                page.locator('#cards .skip').click()
                expect(page.locator('[data-metric-filter=decide] b')).to_have_text('1')
                page.locator('[data-metric-filter=waiting]').click()
                expect(page.locator('#cards')).to_contain_text('Job 1')
                self.assertEqual(errors,[])
            finally:browser.close()

    def test_queue_explains_handoff_and_batch_retry_submission_actions(self):
        preparation = dict(audit_available=True, form_url='https://recruiter.test/prepared',
                           documents={'resume_attached': True, 'letter_attached': False},
                           required_unanswered=1, missing_fields=['Availability date'])
        items = [dict(job_id=1, title='Needs input', status='waiting_user',
                      application_status='needs_human', preparation=preparation),
                 dict(job_id=2, title='Prepared', status='waiting_user',
                      application_status='prefilled', preparation={'audit_available': False}),
                 dict(job_id=3, title='Next job', status='queued')]
        posts = []
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = playwright.chromium.launch(headless=True)
            cleanup.callback(browser.close)
            page = browser.new_page(locale='zh-CN')
            page.add_init_script("window===window.top&&localStorage.setItem('jaa-ui-mode', 'full')")
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def respond(route):
                path = urlparse(route.request.url).path
                if path == '/':
                    route.fulfill(path=str(STATIC / 'index.html'), content_type='text/html')
                elif path.startswith('/static/'):
                    route.fulfill(path=str(STATIC / path.removeprefix('/static/')))
                elif route.request.method == 'POST':
                    posts.append(route.request.url)
                    if path.endswith('/application-status'):
                        items[0]['status'] = 'done'
                        items[0]['application_status'] = 'submitted'
                    route.fulfill(json={'ok': True})
                elif path == '/api/queue':
                    route.fulfill(json={'items': items, 'counts': {'queued': 1}, 'running': False})
                elif path == '/api/analytics':
                    route.fulfill(json={'totals': {}})
                else:
                    route.fulfill(json=[] if path in {'/api/jobs', '/api/sources', '/api/pipeline'} else {})

            page.route('**/*', respond)
            page.goto('http://dashboard.test/');navigate(page,'jobs')
            navigate(page,'pipelineNav')
            first = page.locator('[data-queue-job="1"]')
            expect(first).to_contain_text('需在招聘网站补充')
            expect(first).to_contain_text('简历已附上')
            expect(first).to_contain_text('尚未填写的必填项： 1')
            expect(first).to_contain_text('Availability date')
            expect(first.locator('a')).to_have_attribute('href', preparation['form_url'])
            expect(page.locator('[data-queue-job="2"]')).to_contain_text('准备记录不可用')
            with page.expect_request('**/api/queue/start?mode=batch&auto_review=true'):
                page.locator('#queueBatchBtn').click()
            self.assertTrue(any('/api/queue/start?mode=batch' in url for url in posts))
            first.locator('button[onclick="retryQueue(1)"]').click()
            expect(first).to_be_visible()
            self.assertTrue(any('/api/queue/1/retry' in url for url in posts))
            page.on('dialog', lambda dialog: dialog.accept())
            first.locator('button[onclick="confirmQueueSubmitted(1)"]').click()
            expect(first.locator('.queue')).to_have_text('已完成')
            expect(first.locator('button[onclick="confirmQueueSubmitted(1)"]')).to_have_count(0)
            self.assertEqual(errors, [])

    def test_source_diagnostics_distinguish_empty_failed_and_omitted_searches(self):
        diagnostics = [dict(source='hellowork', campaign='Paris', method='web:bing', state='empty', attempts=1, results=0, errors=0),
                       dict(source='france_travail', campaign='Paris', method='web:duckduckgo', state='failed', attempts=1, results=0, errors=1, last_error='Verification required'),
                       dict(source='staffme', campaign='Paris', method='web', state='not_run', attempts=0, results=0, errors=0)]
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = playwright.chromium.launch(headless=True)
            cleanup.callback(browser.close)
            page = browser.new_page(locale='zh-CN')
            page.add_init_script("window===window.top&&localStorage.setItem('jaa-ui-mode', 'full')")
            def respond(route):
                path = urlparse(route.request.url).path
                if path == '/':
                    route.fulfill(path=str(STATIC / 'index.html'), content_type='text/html')
                elif path.startswith('/static/'):
                    route.fulfill(path=str(STATIC / path.removeprefix('/static/')))
                elif path == '/api/search/status':
                    route.fulfill(json=dict(scan_id=1, running=False, source_diagnostics=diagnostics, found=0, fetched=0, inserted=0, updated=0, errors=1))
                else:
                    route.fulfill(json=[] if path in {'/api/jobs', '/api/sources'} else {})
            page.route('**/*', respond)
            page.goto('http://dashboard.test/');navigate(page,'jobs')
            page.locator('#scanPanel summary').click()
            panel = page.locator('#sourceDiagnostics')
            expect(panel).to_contain_text('搜索已完成，未发现岗位')
            expect(panel).to_contain_text('请求失败或被拦截')
            expect(panel).to_contain_text('未执行：达到查询数量上限')
            expect(panel).to_contain_text('Verification required')
            with page.expect_request('**/api/jobs/rescore'):
                page.locator('#rescoreBtn').click()
            expect(page.locator('#status')).to_have_text('匹配已重新计算。')
