import base64
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from app import db, jobspy_provider, scan_manager, searcher


class DiscoveryTests(unittest.TestCase):
    def test_bing_redirects_are_decoded_and_listing_pages_are_not_jobs(self):
        target = 'https://candidat.francetravail.fr/offres/recherche/detail/123ABC'
        encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip('=')
        html = f'<li class="b_algo"><h2><a href="https://www.bing.com/ck/a?u=a1{encoded}">Réceptionniste</a></h2></li>'
        html += '<li class="b_algo"><h2><a href="https://fr.indeed.com/Paris-Emplois">500 emplois</a></h2></li>'
        with patch.object(searcher, 'fetch_html', return_value=(html, 'static')):
            hits = searcher.search_bing('Reception Paris', 10)
        self.assertEqual([hit.url for hit in hits], [target])
        self.assertEqual(hits[0].provider_key, 'france_travail')

    def test_captcha_is_a_failure_and_search_fallback_reports_both_engines(self):
        events = []
        def report(*args, **kwargs):
            events.append((args, kwargs))
        hit = searcher.Hit('https://jobs.test/1', 'Job', '', 'test')
        with patch.object(searcher, 'search_bing', side_effect=RuntimeError('timeout')), patch.object(searcher, 'search_duckduckgo', return_value=[hit]):
            result = searcher.search_web('jobs', 10, 'global', ['bing', 'duckduckgo'], report=report)
        self.assertEqual(result, [hit])
        self.assertIn(('global', 'web:bing', 'failed'), [event[0] for event in events])
        with patch.object(searcher, 'fetch_html', return_value=('<script src="anomaly.js"></script>', 'static-blocked')):
            with self.assertRaises(RuntimeError):
                searcher.search_duckduckgo('jobs')

    def test_site_specific_search_does_not_claim_another_board_as_success(self):
        hit = searcher.Hit('https://fr.indeed.com/viewjob?jk=1', 'Job', '', 'indeed')
        with patch.object(searcher, 'search_bing', return_value=[hit]):
            self.assertEqual(searcher.search_web('site:francetravail.fr jobs', 10, 'france_travail', ['bing']), [])

    def test_cityone_current_links_are_discovered_and_failures_are_reported(self):
        url = 'https://www.cityone.fr/rejoignez-nous/hote-accueil-paris-12345'
        events = []
        profile = dict(enabled_sources=['cityone'], direct_source_pages=1)
        report = lambda *args, **kwargs: events.append(args)
        with patch.object(searcher, 'fetch_html', return_value=(f'<a href="{url}">Job</a>', 'static')):
            self.assertEqual([hit.url for hit in searcher.discover_direct(profile, report=report)], [url])
        with patch.object(searcher, 'fetch_html', side_effect=RuntimeError('403 denied')):
            self.assertEqual(list(searcher.discover_direct(profile, report=report)), [])
        self.assertIn(('cityone', 'direct', 'failed'), events)

    def test_public_listings_expand_to_details_instead_of_becoming_fake_jobs(self):
        listing = searcher.Hit('https://candidat.francetravail.fr/offres/emploi/receptionniste/paris', 'Jobs', '',
                               'francetravail', 'france_travail', prefetched={'discovery_listing': True})
        target = 'https://candidat.francetravail.fr/offres/recherche/detail/123ABC'
        html = f'<a href="{target}">Job</a><a href="{target}">Duplicate</a><a href="/offres/emploi/paris">Listing</a>'
        with patch.object(searcher, 'search_bing', return_value=[listing]), patch.object(searcher, 'fetch_html', return_value=(html, 'static')):
            hits = searcher.search_web('site:francetravail.fr jobs', 10, 'france_travail', ['bing'])
        self.assertEqual([hit.url for hit in hits], [target])

    def test_jobspy_one_site_failure_does_not_hide_other_site_results(self):
        events = []
        profile = dict(jobspy_enabled=True, jobspy_sites=['google', 'indeed'], preferred_roles=['Réceptionniste'], locations=['Paris'])
        row = dict(title='Réceptionniste', job_url='https://indeed.test/1', site='indeed')
        with patch.object(jobspy_provider, 'available', return_value=True), patch.object(jobspy_provider, '_run_retry', side_effect=[RuntimeError('google blocked'), [row]]) as invoke:
            found = list(jobspy_provider.discover(profile, report=lambda *args, **kwargs: events.append(args)))
        self.assertEqual(found[0].provider_key, 'jobspy_indeed')
        self.assertEqual(invoke.call_args_list[0].args[0]['sites'], ['google'])
        self.assertIn(('jobspy_google', 'jobspy', 'failed'), events)
        self.assertIn(('jobspy_indeed', 'jobspy', 'success'), events)

    def test_other_sources_are_checked_before_detail_consumption(self):
        events = []
        profile = dict(enabled_sources=['cityone'], jobspy_enabled=False, search_engines=['bing'])
        hit = searcher.Hit('https://www.cityone.fr/job/1', 'Job', '', 'cityone', 'cityone')
        with patch.object(searcher, 'discover_boards', return_value=[]), patch.object(searcher, 'discover_direct', return_value=[hit]), patch.object(searcher, 'search_web', return_value=[]) as search:
            discovered = searcher.discover(profile, report=lambda *args, **kwargs: events.append(args))
            self.assertEqual(next(discovered), hit)
            self.assertGreaterEqual(search.call_count, 1)

    def test_repeated_jobspy_failure_suspends_only_that_site_for_this_scan(self):
        calls, events = [], []
        def invoke(payload, timeout):
            site = payload['sites'][0]
            calls.append(site)
            if site == 'google':
                raise RuntimeError('blocked')
            return []
        profile = dict(jobspy_enabled=True, jobspy_sites=['google', 'indeed'], preferred_roles=['A', 'B', 'C', 'D'], locations=['Paris'])
        with patch.object(jobspy_provider, 'available', return_value=True), patch.object(jobspy_provider, '_run_retry', side_effect=invoke):
            list(jobspy_provider.discover(profile, report=lambda *args, **kwargs: events.append(args)))
        self.assertEqual(calls.count('google'), 3)
        self.assertEqual(calls.count('indeed'), 4)
        self.assertIn(('jobspy_google', 'jobspy', 'suspended'), events)

    def test_scan_diagnostics_survive_restart_and_count_errors(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(db, 'DB_PATH', Path(folder) / 'jobs.db'), patch.object(scan_manager, '_state', deepcopy(scan_manager._state)):
            db.init_db()
            scan_id = scan_manager._insert_scan()
            scan_manager._set(scan_id=scan_id, running=False, errors=0, source_diagnostics=[])
            scan_manager._source_event('Paris', 'cityone', 'direct', 'failed', error='403 denied')
            scan_manager._source_event('Paris', 'cityone', 'direct', 'success', results=2)
            state = scan_manager.status()
            self.assertEqual(state['errors'], 1)
            self.assertEqual(state['source_diagnostics'][0]['state'], 'partial')
            scan_manager._finish_scan(scan_id, state)
            scan_manager._set(scan_id=None, source_diagnostics=[])
            restored = scan_manager.status()
            self.assertEqual(restored['errors'], 1)
            self.assertEqual(restored['source_diagnostics'][0]['results'], 2)
