import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.extractor import extract_job_document, extract_date_range
from app.matching_service import clean_stored_job, rescore_jobs
from app.providers import build_queries
from app.reviewer import build_prompt
from app.scoring import evaluate


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.profile = dict(preferred_roles=['Hôtesse d’accueil', 'Serveuse'], contracts=['CDD', 'Intérim'],
                            locations=['Paris'], max_end_date='2030-12-10', exclude_terms=['CDI'],
                            include_terms=['CDD'], availability={'weekends': 'yes', 'night_shifts': 'yes'})

    def test_cdd_is_not_rejected_because_navigation_mentions_cdi(self):
        job = dict(title='Serveur CDD', location='Paris', employment_type='CDD',
                   body='Service à Paris. Navigation: CDI CDD.')
        self.assertNotEqual(evaluate(job, self.profile)[1], 'reject')
        job['employment_type'] = 'CDI'
        self.assertEqual(evaluate(job, self.profile)[1], 'reject')

    def test_feminine_role_matches_masculine_listing_without_restricting_daytime(self):
        job = dict(title='Serveur CDD Paris', employment_type='CDD', location='Paris',
                   body='Travail de jour du lundi au vendredi.', salary='12 EUR')
        day = evaluate(job, self.profile)
        self.assertEqual(day[1], 'keep')
        self.assertIn('end_date_missing', day[3])
        job['body'] = 'Travail de nuit et le week-end.'
        self.assertEqual(evaluate(job, self.profile)[0:2], day[0:2])
        self.assertIn('do not exclude daytime or weekdays', build_prompt({}))

    def test_unknown_dates_do_not_hide_relevance_but_confirmed_conflicts_still_reject(self):
        job = dict(title='Serveur CDD Paris', employment_type='CDD', location='Paris', salary='12 EUR')
        self.assertEqual(evaluate(job, self.profile)[1], 'keep')
        job['end_date'] = '2030-12-31'
        self.assertEqual(evaluate(job, self.profile)[1], 'reject')

    def test_unmatched_location_cannot_be_a_strong_match(self):
        job = dict(title='Serveur CDD', location='Bordeaux', employment_type='CDD',
                   body='CDD intérim extra. Notre siège est à Paris.', salary='12 EUR', end_date='2030-11-01')
        self.assertNotEqual(evaluate(job, self.profile)[1], 'keep')

    def test_experience_months_are_not_contract_duration(self):
        job = dict(title='Serveur CDD Paris', body='Expérience : 6 mois', employment_type='CDD')
        self.assertNotIn('duration_risk', evaluate(job, self.profile)[3])
        job['body'] = 'Contrat de 6 mois'
        self.assertIn('duration_risk', evaluate(job, self.profile)[3])

    def test_structured_description_excludes_navigation_and_related_dates(self):
        html = '<nav>CDI Bordeaux</nav><main><h1>Serveur Paris</h1><p>Related role: CDI Lyon jusqu’au 31 décembre 2030</p></main>'
        html += '<script type="application/ld+json">' + json.dumps({
            '@type': 'JobPosting', 'title': 'Serveur Paris', 'employmentType': 'TEMPORARY',
            'description': 'CDD Paris du 5 October 2030 au 6 October 2030',
        }) + '</script>'
        result = extract_job_document(html, 'https://jobs.test/1')
        self.assertNotIn('CDI', result.text)
        self.assertEqual((result.start_date, result.end_date), ('2030-10-05', '2030-10-06'))
        self.assertEqual(extract_date_range('Du 12 au 15 octobre 2030'), ('2030-10-12', '2030-10-15'))

    def test_search_prefers_source_coverage_and_does_not_require_all_wanted_terms(self):
        profile = dict(self.profile, enabled_sources=['france_travail', 'cityone'], search_queries_per_run=2,
                       include_terms=['disponible immédiatement', 'CDD', 'intérim'])
        queries = build_queries(profile)
        self.assertEqual([key for key, _ in queries], ['france_travail', 'cityone'])
        self.assertTrue(all('disponible immédiatement' not in query for _, query in queries))
        self.assertTrue(all('-"CDI"' not in query for _, query in queries))

    def test_rescore_repairs_legacy_page_without_changing_user_actions(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(db, 'DB_PATH', Path(folder) / 'jobs.db'):
            db.init_db()
            body = 'Navigation CDI\nMétier :\nServeur\nType de contrat :\nCDD\nDu 03/10/2030 au 04/10/2030\nParis\nCes offres pourraient aussi t’intéresser\nCDI Lyon'
            with db.connect() as c:
                c.execute("INSERT INTO jobs(url,title,body,provider_key,location,user_action,application_status,review_verdict,tracker_stage) VALUES(?,?,?,?,?,?,?,?,?)",
                          ('https://job.test/1', 'Serveur CDD Paris', body, 'plany', 'Paris', 'liked', 'submitted', 'HUMAN_REVIEW', 'submitted'))
            self.assertEqual(rescore_jobs(self.profile)['updated'], 1)
            with db.connect() as c:
                job = dict(c.execute('SELECT * FROM jobs').fetchone())
            self.assertNotIn('Navigation', job['body'])
            self.assertEqual(job['end_date'], '2030-10-04')
            self.assertEqual((job['user_action'], job['application_status'], job['review_verdict'], job['tracker_stage']),
                             ('liked', 'submitted', 'HUMAN_REVIEW', 'submitted'))
