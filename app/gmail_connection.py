"""Candidate-bound native OAuth with PKCE; no mail sending or password resets."""
import base64
import hashlib
import json
import secrets
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from . import secret_store
from .workspaces import candidate_id, active_id

SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
REDIRECT = 'http://127.0.0.1:8765/api/gmail/callback'
_pending = {}
_lock = threading.Lock()


def status():
    data = secret_store.read()
    config = data.get('gmail_config', {})
    connection = data.get('gmail_connection', {})
    return {'configured': bool(config.get('client_id') and config.get('client_secret')),
            'connected': bool(connection.get('refresh_token')), 'email': connection.get('email', ''),
            'redirect_uri': REDIRECT, 'scope': SCOPE}


def configure(payload):
    client_id = str(payload.get('client_id', '')).strip()
    client_secret = str(payload.get('client_secret', '')).strip()
    if not client_id.endswith('.apps.googleusercontent.com') or not client_secret or len(client_secret) > 1024:
        raise ValueError('Enter the Desktop app client ID and client secret from Google Cloud.')
    def change(data):
        data['gmail_config'] = {'client_id': client_id, 'client_secret': client_secret}
        data.pop('gmail_connection', None)
    secret_store.update(change)


def begin():
    config = secret_store.read().get('gmail_config', {})
    if not config.get('client_id'): raise ValueError('Configure Google OAuth before connecting.')
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    with _lock:
        for key in list(_pending):
            if _pending[key]['expires'] < time.time(): _pending.pop(key)
        _pending[state] = {'owner': candidate_id(), 'verifier': verifier, 'expires': time.time()+600,
                           'client_id': config['client_id']}
    return {'authorization_url': 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
        'client_id': config['client_id'], 'redirect_uri': REDIRECT, 'response_type': 'code',
        'scope': SCOPE, 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256',
        'access_type': 'offline', 'prompt': 'consent select_account'})}


def finish(state, code, error=''):
    with _lock: pending = _pending.pop(state, None)
    if not pending or pending['expires'] < time.time() or pending['owner'] != candidate_id() or pending['owner'] != active_id():
        raise ValueError('Authorization expired or profile changed. Connect again from the correct profile.')
    if error or not code: raise ValueError('Google authorization cancelled. You can connect again.')
    config = secret_store.read()['gmail_config']
    if config['client_id'] != pending['client_id']: raise ValueError('OAuth configuration changed. Connect again.')
    request = Request('https://oauth2.googleapis.com/token', data=urlencode({
        **config, 'code': code, 'code_verifier': pending['verifier'],
        'redirect_uri': REDIRECT, 'grant_type': 'authorization_code'}).encode())
    with urlopen(request, timeout=20) as response: tokens = json.load(response)
    if not tokens.get('refresh_token'): raise ValueError('No offline authorization received. Connect again.')
    if SCOPE not in tokens.get('scope', '').split(): raise ValueError('Gmail read permission was not granted.')
    request = Request('https://gmail.googleapis.com/gmail/v1/users/me/profile',
                      headers={'Authorization': 'Bearer '+tokens['access_token']})
    with urlopen(request, timeout=20) as response: mailbox = json.load(response)
    email = mailbox.get('emailAddress', '')
    if not email: raise ValueError('Could not verify the connected mailbox.')
    secret_store.update(lambda data: data.update(gmail_connection={'refresh_token': tokens['refresh_token'], 'email': email}))
    return email


def disconnect():
    # Local unlink only; OAuth consent can also be revoked from Google Account.
    secret_store.update(lambda data: data.pop('gmail_connection', None))
