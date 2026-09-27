import unittest

from app.ats import detect_ats
from app.profile_store import default_profile, runtime_profile
from app.providers import build_queries, enabled_sources
from app.ats_adapters import get_adapter, adapter_catalog
from app.scoring import evaluate
from app.job_identity import build_job_dedupe_key, merge_variants, load_variants
from app.search_profiles import expand_runtime_profile


class CoreTests(unittest.TestCase):
    def test_default_profile_is_not_candidate_specific(self):
        p = default_profile()
        self.assertEqual(p['identity']['first_name'], '')
        self.assertEqual(p['preferences']['roles'], [])
        self.assertEqual(p['preferences']['locations'], [])
        self.assertEqual(p['preferences']['contracts'], [])
        self.assertEqual(p['availability']['end_date'], '')

    def test_runtime_profile_flattens_dashboard_schema(self):
        p = default_profile()
        p['identity']['first_name'] = 'Ada'
        p['preferences']['roles'] = ['Engineer']
        p['availability']['end_date'] = '2030-01-31'
        r = runtime_profile(p)
        self.assertEqual(r['first_name'], 'Ada')
        self.assertEqual(r['preferred_roles'], ['Engineer'])
        self.assertEqual(r['max_end_date'], '2030-01-31')

    def test_no_end_date_constraint_means_no_end_date_rejection(self):
        profile = {
            'preferred_roles': ['Engineer'],
            'contracts': ['CDI'],
            'locations': ['Lyon'],
            'max_end_date': '',
            'availability': {'holiday_work': 'flexible'},
            'exclude_terms': [],
            'include_terms': [],
            'industries': [],
        }
        job = {
            'title': 'Engineer',
            'body': 'CDI à Lyon',
            'employment_type': 'CDI',
            'location': 'Lyon',
            'end_date': '',
        }
        score, decision, reason, _ = evaluate(job, profile)
        self.assertNotEqual(decision, 'reject')
        self.assertNotIn('end_after_max', reason)
        self.assertGreater(score, 0)

    def test_end_date_constraint_rejects_confirmed_conflict(self):
        profile = {
            'preferred_roles': ['Engineer'],
            'contracts': ['CDD'],
            'locations': ['Paris'],
            'max_end_date': '2027-03-01',
            'availability': {'holiday_work': 'flexible'},
            'exclude_terms': [],
            'include_terms': [],
            'industries': [],
        }
        job = {
            'title': 'Engineer',
            'body': 'CDD Paris',
            'employment_type': 'CDD',
            'location': 'Paris',
            'end_date': '2027-04-01',
        }
        _, decision, reason, _ = evaluate(job, profile)
        self.assertEqual(decision, 'reject')
        self.assertIn('end_after_max', reason)

    def test_ats_detection(self):
        self.assertEqual(detect_ats('https://jobs.lever.co/acme/123'), 'lever')
        self.assertEqual(detect_ats('https://job-boards.greenhouse.io/acme/jobs/123'), 'greenhouse')
        self.assertEqual(detect_ats('https://acme.wd5.myworkdayjobs.com/jobs'), 'workday')

    def test_query_builder_uses_user_preferences(self):
        p = runtime_profile(default_profile())
        p['preferred_roles'] = ['Data analyst']
        p['contracts'] = ['CDI']
        p['locations'] = ['Lille']
        q = build_queries(p)
        self.assertTrue(any('Data analyst' in query and 'Lille' in query for _, query in q))

    def test_v8_profile_has_resume_routing_disabled_by_default(self):
        p = default_profile()
        self.assertEqual(p['schema_version'], 8)
        self.assertFalse(p['application']['auto_resume_routing'])
        self.assertTrue(p['automation']['agent_fallback']['enabled'])
        self.assertEqual(p['automation']['company_boards'], [])

    def test_v8_has_jobspy_and_scheduler_config(self):
        p = default_profile()
        self.assertTrue(p['automation']['jobspy_enabled'])
        self.assertIn('indeed', p['automation']['jobspy_sites'])
        self.assertEqual(p['automation']['dedupe_scope'], 'title_company_location')
        self.assertEqual(p['automation']['auto_scan_interval_minutes'], 0)

    def test_search_profiles_expand_campaigns(self):
        p = runtime_profile(default_profile())
        p['search_profiles'] = [
            {'id': 'retail', 'label': 'Retail', 'roles': ['Seller'], 'locations': ['Paris'], 'enabled': True},
            {'id': 'off', 'label': 'Disabled', 'roles': ['X'], 'enabled': False},
        ]
        rows = expand_runtime_profile(p)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['search_profile_id'], 'retail')
        self.assertEqual(rows[0]['preferred_roles'], ['Seller'])

    def test_cross_source_dedupe_and_variants(self):
        a = build_job_dedupe_key(title=' Data Analyst ', company='ACME', location='Paris, France')
        b = build_job_dedupe_key(title='data analyst', company='acme', location='Paris, France')
        c = build_job_dedupe_key(title='data analyst', company='acme', location='Lyon, France')
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        raw = merge_variants('[]', {'provider_key':'indeed','source':'indeed','url':'https://a'}, {'provider_key':'jobspy_indeed','source':'indeed','url':'https://b'})
        self.assertEqual(len(load_variants(raw)), 2)

    def test_adapter_registry_routes_known_ats(self):
        self.assertEqual(get_adapter('greenhouse').info.key, 'greenhouse')
        self.assertEqual(get_adapter('lever').info.key, 'lever')
        self.assertEqual(get_adapter('workday').info.mode, 'agent-assisted')
        self.assertEqual(get_adapter('unknown').info.key, 'generic')
        self.assertGreaterEqual(len(adapter_catalog()), 8)

    def test_custom_sources_make_discovery_portable(self):
        p = runtime_profile(default_profile())
        p['enabled_sources'] = []
        p['custom_sources'] = [{'label': 'Example Careers', 'domain': 'careers.example.com'}]
        sources = enabled_sources(p)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].domain, 'careers.example.com')
        q = build_queries(p)
        self.assertTrue(any('site:careers.example.com' in query for _, query in q))

    def test_empty_enabled_source_list_really_disables_builtins(self):
        p = runtime_profile(default_profile())
        p['enabled_sources'] = []
        p['custom_sources'] = []
        self.assertEqual(enabled_sources(p), [])

    def test_query_builder_adds_negative_terms(self):
        p = runtime_profile(default_profile())
        p['preferred_roles'] = ['Receptionist']
        p['locations'] = ['Paris']
        p['exclude_terms'] = ['night shift']
        q = build_queries(p)
        self.assertTrue(any('-"night shift"' in query for _, query in q))


if __name__ == '__main__':
    unittest.main()
