import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


STATIC = Path(__file__).resolve().parents[1] / 'static'


class DashboardMetricTests(unittest.TestCase):
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

            def check_metrics(count, submitted):
                expect(human.locator('b')).to_have_text(str(count))
                expect(page.locator('[data-metric-filter="keep"] b')).to_have_text(str(count))
                expect(page.locator('[data-metric-filter="submitted"] b')).to_have_text(str(submitted))
                expect(page.locator('#cards .card')).to_have_count(count)

            check_metrics(2, 1)  # Five skipped reviews must not inflate the count to seven.
            page.locator('#cards .card').filter(has_text='Job 1').locator('.skip').click()
            check_metrics(1, 0)
            page.reload()
            page.locator('[data-metric-filter="human"]').click()
            check_metrics(1, 0)
            page.locator('#cards .skip').click()
            check_metrics(0, 0)
            expect(page.locator('#cards .empty')).to_be_visible()

            page.locator('.filter[data-filter="skipped"]').click()
            expect(page.locator('#cards .card')).to_have_count(7)
            page.locator('#cards .card').filter(has_text='Job 1').locator('.skip').click()
            expect(page.locator('#cards .card')).to_have_count(6)
            human.click()
            check_metrics(1, 1)
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
