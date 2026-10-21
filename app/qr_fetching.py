"""Bounded public GETs: ordinary HTTP, then Scrapling's Chrome TLS client.

Scrapling is already an optional installed runtime dependency. This adapter does
not use its browser launcher, candidate cookies, proxies or application actions.
"""
from urllib.parse import urljoin
from .pfe_discovery import read_public as ordinary_read, validate_destination
from .worker_runtime import check_cancelled

MAX_BYTES = 8 * 1024 * 1024


def checked_result(result):
    body, content_type, final = result
    text = body.decode('utf-8', 'replace').lower()
    challenges = ('verify you are human', '<title>access denied', '<title>just a moment', 'robot check', 'anomaly.js')
    if 'html' in content_type.lower() and any(sign in text for sign in challenges):
        raise OSError('Recruitment page returned an access challenge')
    return result


def read_scrapling(url):
    from scrapling.fetchers import Fetcher
    # Validate every redirect ourselves, even when the library's defaults change.
    for _ in range(6):
        check_cancelled()
        validate_destination(url)
        chunks = []
        size = 0
        overflow = False

        def receive(chunk):
            nonlocal size, overflow
            size += len(chunk)
            if size > MAX_BYTES:
                overflow = True
                return 0
            chunks.append(chunk)
            return len(chunk)

        try:
            response = Fetcher.get(
                url, impersonate='chrome', stealthy_headers=False, follow_redirects=False,
                timeout=20, retries=1, verify=True, content_callback=receive,
                headers={'Accept': 'text/html,application/json,application/pdf'},
            )
        except Exception as exc:
            check_cancelled()
            if overflow:
                raise ValueError('Document exceeds 8 MB') from exc
            raise OSError('Scrapling read failed: ' + str(exc)[:200]) from exc
        check_cancelled()
        if overflow:
            raise ValueError('Document exceeds 8 MB')
        headers = {str(k).lower(): v for k, v in response.headers.items()}
        if response.status in {301, 302, 303, 307, 308}:
            if not headers.get('location'):
                raise OSError('Scrapling redirect has no destination')
            url = urljoin(url, headers['location'])
            continue
        if not 200 <= response.status < 300:
            raise OSError(f'Scrapling HTTP {response.status}')
        return checked_result((b''.join(chunks), headers.get('content-type', ''), url))
    raise OSError('Too many recruitment page redirects')


def read_public(url):
    """Leave unsafe/oversized destinations as errors; fallback only on read failures."""
    try:
        return checked_result(ordinary_read(url))
    except OSError as first:
        try:
            return read_scrapling(url)
        except ImportError as exc:
            raise OSError(f'{first}; Scrapling unavailable (requirements-scrapling.txt)') from exc
        except OSError as second:
            raise OSError(f'{str(first)[:200]}; {second}') from second
