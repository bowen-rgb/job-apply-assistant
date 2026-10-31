import unittest
from types import SimpleNamespace
from app.job_board_worker import collect
from app.vendor.jobspy.model import JobPost, Location, JobType


class NativeJobBoardTests(unittest.TestCase):
    payload = dict(sites=['indeed'], search_term='robotique', location='Paris',
                   country_indeed='france', results_wanted=5, job_type='internship')

    def test_native_records_keep_location_contract_and_original_employer(self):
        seen=[]
        def scrape(request):
            seen.append(request)
            return [JobPost(title='Stage robotique',company='Example Robotics',
                            job_url='https://example.test/offer',
                            location=Location(city='Paris',country='France'),
                            job_type=[JobType.INTERNSHIP])]
        rows=collect(self.payload,lambda site:SimpleNamespace(scrape=scrape,error=None))
        self.assertEqual(rows[0]['site'],'indeed')
        self.assertEqual(rows[0]['company'],'Example Robotics')
        self.assertIn('Paris',rows[0]['location'])
        self.assertEqual(rows[0]['job_type'],'internship')
        self.assertEqual(seen[0].job_type,JobType.INTERNSHIP)

    def test_blocked_source_is_not_reported_as_successful_empty_scan(self):
        with self.assertRaisesRegex(RuntimeError,'captcha'):
            collect(self.payload,lambda site:SimpleNamespace(scrape=lambda request:[],error='captcha'))

    def test_partial_results_survive_scraper_warning(self):
        record=JobPost(title='Stage',job_url='https://example.test/offer')
        rows=collect(self.payload,lambda site:SimpleNamespace(scrape=lambda request:[record],error='page 2 timeout'))
        self.assertEqual(len(rows),1)

    def test_unknown_board_never_loads_a_scraper(self):
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            collect({**self.payload,'sites':['other']},lambda site:self.fail('loaded unknown adapter'))
