"""Read-only, opt-in email login codes. Never send mail or follow recovery links."""
import base64
import json
import re
import time
from email.utils import parseaddr, getaddresses
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from . import secret_store
from .worker_runtime import check_cancelled


def configure(enabled):
    if type(enabled) is not bool:
        raise ValueError('Choose whether email login codes may be read automatically.')
    secret_store.update(lambda data: data.update(gmail_auto_codes=enabled))


def extract_code(message, domain, mailbox, since):
    """Reject unrelated, old, ambiguous and recovery/payment messages."""
    timestamp = int(message.get('internalDate', 0)) / 1000
    if not since <= timestamp <= time.time() + 60:
        return None
    payload = message.get('payload', {})
    headers = {h['name'].lower(): h['value'] for h in payload.get('headers', [])}
    sender = parseaddr(headers.get('from', ''))[1].lower().rsplit('@', 1)[-1]
    if sender != domain and not sender.endswith('.' + domain):
        return None
    authentication = headers.get('authentication-results', '')
    if not re.search(r'dmarc=pass\b', authentication, re.I) or not re.search(
            r'header\.from=' + re.escape(sender) + r'(?:[;\s]|$)', authentication, re.I):
        return None
    recipients = {address.casefold() for _, address in getaddresses([headers.get('to', '')])}
    if mailbox.casefold() not in recipients:
        return None
    def bodies(part):
        if part.get('mimeType') in ('text/plain', 'text/html'):
            encoded = part.get('body', {}).get('data', '')
            if len(encoded) <= 150000:
                yield base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode('utf-8', errors='replace')
        for child in part.get('parts', []):
            yield from bodies(child)
    text = headers.get('subject', '') + '\n' + BeautifulSoup('\n'.join(bodies(payload)), 'html.parser').get_text(' ')
    if re.search(r'reset|recover|réinitialis|récupér|payment|paiement|purchase|transaction|password change', text, re.I):
        return None
    # Require login context as well as a code label, not a random six-digit number.
    if not re.search(r'log.?in|sign.?in|connexion|authenticat', text, re.I):
        return None
    codes = set(re.findall(r'(?:code|otp)\s*(?:de (?:connexion|vérification)\s*)?[:：\-]?\s*(\d{6})(?!\d)', text, re.I))
    return codes.pop() if len(codes) == 1 else None


def wait_for_code(url, username, since, wait_seconds=30):
    data = secret_store.read()
    connection = data.get('gmail_connection', {})
    config = data.get('gmail_config', {})
    domain = urlparse(url).hostname or ''
    # Never consume Google/SSO MFA or codes for another remembered account.
    if (not data.get('gmail_auto_codes') or not connection.get('refresh_token')
            or username.casefold() != connection.get('email', '').casefold()
            or urlparse(url).scheme != 'https' or not domain
            or domain in {'accounts.google.com', 'login.microsoftonline.com'}):
        return None
    def request_json(request):
        with urlopen(request, timeout=10) as response:
            return json.load(response)
    token = request_json(Request('https://oauth2.googleapis.com/token', data=urlencode({
        **config, 'refresh_token': connection['refresh_token'], 'grant_type': 'refresh_token'}).encode()))
    def get(path):
        return request_json(Request('https://gmail.googleapis.com/gmail/v1/users/me/' + path,
                                   headers={'Authorization': 'Bearer ' + token['access_token']}))
    deadline = time.monotonic() + min(max(wait_seconds, 0), 30)
    while True:
        check_cancelled()
        if not secret_store.read().get('gmail_auto_codes'):
            return None
        query = urlencode({'q': f'after:{int(since)} from:({domain})', 'maxResults': 10})
        messages = get('messages?' + query).get('messages', [])
        used = set(secret_store.read().get('gmail_used_codes', []))
        found = []
        for item in messages:
            check_cancelled()
            if time.monotonic() > deadline and wait_seconds > 0:
                # Do not select from an incomplete set of candidate messages.
                return None
            if item['id'] in used:
                continue
            code = extract_code(get('messages/' + item['id'] + '?format=full'), domain, username, since)
            if code:
                found.append((item['id'], code))
        if len(found) == 1:
            identifier, code = found[0]
            secret_store.update(lambda current: current.update(gmail_used_codes=(current.get('gmail_used_codes', []) + [identifier])[-100:]))
            return code
        if len(found) > 1 or time.monotonic() >= deadline:
            return None
        time.sleep(2)
