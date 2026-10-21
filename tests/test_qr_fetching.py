import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app import qr_fetching as fetch


class FetchingTests(unittest.TestCase):
    def response(self, status=200, headers=None, body=b'<html>Careers</html>'):
        def request(url, **kwargs):
            self.assertFalse(kwargs['follow_redirects'])
            self.assertEqual(kwargs['retries'], 1)
            kwargs['content_callback'](body)
            return SimpleNamespace(status=status, headers=headers or {'Content-Type':'text/html'})
        return request

    def test_ordinary_success_does_not_use_fallback(self):
        result=(b'<html>Careers</html>', 'text/html', 'https://example.com')
        with patch.object(fetch, 'ordinary_read', return_value=result), patch.object(fetch, 'read_scrapling') as fallback:
            self.assertEqual(fetch.read_public(result[2]),result)
            fallback.assert_not_called()

    def test_blocked_http_uses_scrapling(self):
        with patch.object(fetch, 'ordinary_read', side_effect=OSError('403')), patch.object(fetch, 'validate_destination'), patch('scrapling.fetchers.Fetcher.get', side_effect=self.response()):
            self.assertEqual(fetch.read_public('https://example.com')[0],b'<html>Careers</html>')

    def test_private_redirect_is_rejected_before_second_request(self):
        def validate(url):
            if '127.0.0.1' in url:raise ValueError('private network')
        with patch.object(fetch, 'validate_destination', side_effect=validate), patch('scrapling.fetchers.Fetcher.get', side_effect=self.response(302, {'Location':'http://127.0.0.1/jobs'})) as request:
            with self.assertRaises(ValueError):fetch.read_scrapling('https://example.com')
            self.assertEqual(request.call_count,1)

    def test_oversize_and_unsafe_original_do_not_become_fallbacks(self):
        with patch.object(fetch, 'ordinary_read', side_effect=ValueError('unsafe')), patch.object(fetch, 'read_scrapling') as fallback:
            with self.assertRaises(ValueError):fetch.read_public('http://127.0.0.1')
            fallback.assert_not_called()
        with patch.object(fetch, 'MAX_BYTES', 5), patch.object(fetch, 'validate_destination'), patch('scrapling.fetchers.Fetcher.get', side_effect=self.response()):
            with self.assertRaisesRegex(ValueError,'8 MB'):fetch.read_scrapling('https://example.com')

    def test_repeated_block_is_an_error(self):
        with patch.object(fetch, 'validate_destination'), patch('scrapling.fetchers.Fetcher.get', side_effect=self.response(403)):
            with self.assertRaisesRegex(OSError,'403'):fetch.read_scrapling('https://example.com')
