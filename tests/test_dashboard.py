import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


STATIC = Path(__file__).resolve().parents[1] / 'static'


class DashboardMetricTests(unittest.TestCase):
    def test_review_export_controls_language_filtered_scope_download_and_cancel(self):
        jobs=[dict(id=1,title='One',url='https://example.test/1',decision='keep',review_verdict='APPLY',human_review_status='pending',provider_key='one',score=90),
              dict(id=2,title='Two',url='https://example.test/2',decision='review',review_verdict='HUMAN_REVIEW',human_review_status='pending',provider_key='two',score=50),
              dict(id=3,title='Done',decision='keep',review_verdict='APPLY',human_review_status='pending',application_status='submitted',score=90)]
        state={'id':'a'*32,'status':'ready','format':'xlsx','language':'fr','message':'Export prêt.','total':1,'completed':1}
        payloads=[]
        with sync_playwright() as p,ExitStack() as cleanup:
            browser=p.chromium.launch(headless=True);cleanup.callback(browser.close)
            page=browser.new_page(locale='zh-CN')
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
            page.goto('http://dashboard.test/')
            page.locator('.review-export-panel summary').click()
            expect(page.locator('#reviewExportCount')).to_have_text('2 个岗位将导出')
            page.locator('[data-metric-filter="human"]').click()
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

    def test_human_confirmation_covers_both_ai_results_and_bulk_queues_only_confirmed_jobs(self):
        from app.human_review import annotate, review_token
        jobs=[dict(id=i,title=f'Review {i}',url=f'https://example.test/{i}',decision='keep' if i==1 else 'review',
                   user_action='',application_status='',review_verdict='APPLY' if i==1 else 'HUMAN_REVIEW',
                   review_revision='first',score=90,body='Check schedule',queue_status='') for i in [1,2]]
        queued=[]
        requests=[]
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser=playwright.chromium.launch(headless=True)
            cleanup.callback(browser.close)
            page=browser.new_page(locale='zh-CN')
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def respond(route):
                path=urlparse(route.request.url).path
                if path=='/':route.fulfill(path=str(STATIC/'index.html'),content_type='text/html')
                elif path.startswith('/static/'):route.fulfill(path=str(STATIC/path.removeprefix('/static/')))
                elif path=='/api/jobs':route.fulfill(json=[annotate(j) for j in jobs])
                elif path.endswith('/human-review'):
                    id=int(path.split('/')[3]);job=next(j for j in jobs if j['id']==id)
                    payload=json.loads(route.request.post_data)
                    self.assertEqual(payload['review_token'],review_token(job))
                    job.update(human_review_status=payload['status'],human_review_fingerprint=payload['review_token'],human_reviewed_at='2026-10-05 10:00:00')
                    route.fulfill(json={'ok':True})
                elif path=='/api/queue':
                    if route.request.method=='POST':
                        payload=json.loads(route.request.post_data);requests.append(payload['job_ids'])
                        for id in payload['job_ids']:
                            job=next(j for j in jobs if j['id']==id);job['queue_status']='queued';queued.append(id)
                    route.fulfill(json={'items':[dict(annotate(next(j for j in jobs if j['id']==id)),job_id=id,status='queued') for id in queued],'counts':{'queued':len(queued)},'running':False})
                elif path=='/api/analytics':route.fulfill(json={'totals':{}})
                else:route.fulfill(json=[] if path in {'/api/sources','/api/pipeline'} else {})
            page.route('**/*',respond)
            page.goto('http://dashboard.test/')
            page.locator('[data-metric-filter="human"]').click()
            expect(page.locator('#cards .card')).to_have_count(2)
            expect(page.locator('#cards .apply:disabled')).to_have_count(2)
            page.locator('button[onclick="confirmHumanReview(1,\'approved\')"]').click()
            expect(page.locator('[data-metric-filter="human"] b')).to_have_text('1')
            page.locator('.filter[data-filter="confirmed"]').click()
            expect(page.locator('#cards .apply')).to_be_enabled()
            page.locator('button[onclick="confirmHumanReview(1,\'pending\')"]').click()
            expect(page.locator('#cards .card')).to_have_count(0)
            page.locator('[data-metric-filter="human"]').click()
            expect(page.locator('#cards .card')).to_have_count(2)
            page.locator('button[onclick="confirmHumanReview(1,\'declined\')"]').click()
            expect(page.locator('#cards .card')).to_have_count(1)
            page.locator('button[onclick="confirmHumanReview(2,\'approved\')"]').click()
            expect(page.locator('[data-metric-filter="human"] b')).to_have_text('0')
            page.locator('.filter[data-filter="human_declined"]').click()
            expect(page.locator('#cards')).to_contain_text('Review 1')
            expect(page.locator('#cards .apply')).to_be_disabled()
            page.locator('#pipelineNav').click()
            page.locator('#queueAddMatchesBtn').click()
            expect(page.locator('#queueList')).to_contain_text('Review 2')
            self.assertEqual(requests,[[2]])  # Orange accepted by the user, not the unconfirmed strong match.
            jobs[1]['review_revision']='second'
            page.reload()
            page.locator('[data-metric-filter="human"]').click()
            expect(page.locator('#cards')).to_contain_text('Review 2')
            expect(page.locator('#cards .apply')).to_be_disabled()
            self.assertEqual(errors,[])

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
                    'approved':[4], 'human':[4,5], 'confirmed':[], 'human_declined':[], 'queued':[6], 'submitted':[3,10],
                    'skipped':[7,10], 'expired':[2], 'rejected':[3], 'unsuitable':[1],
                    'reviewer_skip':[1], 'withdrawn':[8]}
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = playwright.chromium.launch(headless=True)
            cleanup.callback(browser.close)
            page = browser.new_page(locale='zh-CN')
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
            page.goto('http://dashboard.test/')
            for name, ids in expected.items():
                with self.subTest(filter=name):
                    page.locator(f'.filter[data-filter="{name}"]').click()
                    expect(page.locator('#cards .card')).to_have_count(len(ids))
                    for job_id in ids:
                        expect(page.locator('#cards .card').filter(has=page.locator(f'button[onclick="openLetter({job_id})"]'))).to_have_count(1)
            page.locator('.filter[data-filter="rejected"]').click()
            expect(page.locator('#cards')).to_contain_text('招聘方邮件')
            expect(page.locator('#cards .apply')).to_be_disabled()
            page.locator('.filter[data-filter="expired"]').click()
            expect(page.locator('#cards')).to_contain_text('2000-01-01')
            expect(page.locator('#cards .apply')).to_be_disabled()
            for metric in ['all','keep','liked','human','submitted']:
                page.locator(f'[data-metric-filter="{metric}"]').click()
                expect(page.locator('#cards .card')).to_have_count(len(expected[metric]))
                expect(page.locator(f'[data-metric-filter="{metric}"] b')).to_have_text(str(len(expected[metric])))
            page.locator('#sourceSelect').select_option('two')
            expect(page.locator('[data-metric-filter="submitted"] b')).to_have_text('1')
            expect(page.locator('#cards .card')).to_have_count(1)
            page.locator('#q').fill('no such job')
            expect(page.locator('[data-metric-filter="submitted"] b')).to_have_text('0')
            expect(page.locator('#cards .card')).to_have_count(0)
            self.assertEqual(errors,[])

    def test_failed_submission_and_review_do_not_claim_success_and_saving_toggles(self):
        job=dict(id=1,title='One',url='https://example.test/1',decision='keep',score=90,user_action='',application_status='')
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser=playwright.chromium.launch(headless=True)
            cleanup.callback(browser.close)
            page=browser.new_page(locale='zh-CN')
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
            page.goto('http://dashboard.test/')
            page.locator('#cards .like').click()
            expect(page.locator('#cards .like')).to_have_text('取消收藏')
            page.locator('#cards .like').click()
            expect(page.locator('[data-metric-filter="liked"] b')).to_have_text('0')
            page.locator('button[onclick="markApplication(1,\'submitted\')"]').click()
            expect(page.locator('#status')).to_have_text('Server rejected this action')
            expect(page.locator('[data-metric-filter="submitted"] b')).to_have_text('0')
            page.locator('#cards .reviewbtn').click()
            expect(page.locator('#status')).to_have_text('Server rejected this action')
            self.assertEqual(errors,[])

    def test_skip_and_restore_update_metrics_with_the_card_filters(self):
        jobs = [dict(id=i, title=f'Job {i}', url=f'https://example.test/{i}',
                     decision='keep', review_verdict='HUMAN_REVIEW',
                     user_action='skipped' if i > 2 else '', score=100,
                     application_status='submitted' if i == 1 else '')
                for i in range(1, 8)]
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = playwright.chromium.launch(headless=True)
            cleanup.callback(browser.close)
            page = browser.new_page(locale='fr-FR')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def respond(route):
                path = urlparse(route.request.url).path
                if path == '/':
                    route.fulfill(path=str(STATIC / 'index.html'), content_type='text/html')
                elif path.startswith('/static/'):
                    route.fulfill(path=str(STATIC / path.removeprefix('/static/')))
                elif path == '/api/jobs':
                    route.fulfill(json=jobs)
                elif path.endswith('/decision'):
                    job_id = int(path.split('/')[3])
                    action = json.loads(route.request.post_data)['decision']
                    next(job for job in jobs if job['id'] == job_id)['user_action'] = (
                        '' if action == 'clear_user_action' else action)
                    route.fulfill(json={'ok': True})
                elif path == '/api/sources':
                    route.fulfill(json=[])
                else:
                    route.fulfill(json={})

            page.route('**/*', respond)
            page.goto('http://dashboard.test/')
            human = page.locator('[data-metric-filter="human"]')
            human.click()

            def check_metrics(count, keep, submitted):
                expect(human.locator('b')).to_have_text(str(count))
                expect(page.locator('[data-metric-filter="keep"] b')).to_have_text(str(keep))
                expect(page.locator('[data-metric-filter="submitted"] b')).to_have_text(str(submitted))
                expect(page.locator('#cards .card')).to_have_count(count)

            check_metrics(1, 2, 1)  # Skipped and already-submitted reviews need no new confirmation.
            page.locator('[data-metric-filter="keep"]').click()
            page.locator('#cards .card').filter(has_text='Job 1').locator('.skip').click()
            human.click()
            check_metrics(1, 1, 1)
            page.reload()
            page.locator('[data-metric-filter="human"]').click()
            check_metrics(1, 1, 1)
            page.locator('#cards .skip').click()
            check_metrics(0, 0, 1)  # Ignoring a listing must preserve submission history.
            expect(page.locator('#cards .empty')).to_be_visible()

            page.locator('.filter[data-filter="skipped"]').click()
            expect(page.locator('#cards .card')).to_have_count(7)
            page.locator('#cards .card').filter(has_text='Job 1').locator('.skip').click()
            expect(page.locator('#cards .card')).to_have_count(6)
            human.click()
            check_metrics(0, 1, 1)
            self.assertEqual(errors, [])

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
            page.goto('http://dashboard.test/')
            page.locator('#pipelineNav').click()
            first = page.locator('[data-queue-job="1"]')
            expect(first).to_contain_text('需在招聘网站补充')
            expect(first).to_contain_text('简历已附上')
            expect(first).to_contain_text('尚未填写的必填项： 1')
            expect(first).to_contain_text('Availability date')
            expect(first.locator('a')).to_have_attribute('href', preparation['form_url'])
            expect(page.locator('[data-queue-job="2"]')).to_contain_text('准备记录不可用')
            with page.expect_request('**/api/queue/start?mode=batch'):
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
            page.goto('http://dashboard.test/')
            page.locator('#scanPanel summary').click()
            panel = page.locator('#sourceDiagnostics')
            expect(panel).to_contain_text('搜索已完成，未发现岗位')
            expect(panel).to_contain_text('请求失败或被拦截')
            expect(panel).to_contain_text('未执行：达到查询数量上限')
            expect(panel).to_contain_text('Verification required')
            with page.expect_request('**/api/jobs/rescore'):
                page.locator('#rescoreBtn').click()
            expect(page.locator('#status')).to_have_text('匹配已重新计算。')
