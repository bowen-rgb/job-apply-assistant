import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import review_research
from app.searcher import Hit


class ResearchTests(unittest.TestCase):
    def test_research_fetches_pages_not_snippets_and_reuses_public_cache(self):
        job={'url':'https://employer.test/role','company':'Example','location':'Saclay','title':'Simulation'}
        hit=Hit('https://employer.test/access','Access','Unverified snippet','Example')
        with tempfile.TemporaryDirectory() as folder,patch.object(review_research,'data_dir',return_value=Path(folder)),patch.object(review_research,'read_public',return_value=(b'<html><body>Official worksite address and public transport access information.</body></html>','text/html','https://employer.test/access')) as fetch,patch.object(review_research,'search_web',return_value=[hit]) as search:
            first=review_research.collect(job)
            self.assertIn('Official worksite',first['pages'][0]['text'])
            self.assertNotIn('Unverified snippet',str(first))
            count=fetch.call_count
            self.assertEqual(review_research.collect(job),first)
            self.assertEqual(fetch.call_count,count)
            self.assertNotIn('address_line1',str(search.call_args))

    def test_blocked_sources_are_recorded_as_unavailable_without_stopping_review(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(review_research,'data_dir',return_value=Path(folder)),patch.object(review_research,'read_public',side_effect=OSError('Blocked')),patch.object(review_research,'search_web',side_effect=RuntimeError('Search failed')):
            result=review_research.collect({'url':'https://employer.test/role','company':'Example'})
            self.assertEqual(result['pages'],[])
            self.assertEqual(result['status'],'unavailable')
            self.assertTrue(result['errors'])
