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
