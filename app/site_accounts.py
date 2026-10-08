from urllib.parse import urlparse
from . import secret_store


def origin(url):
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use an HTTPS login URL without credentials')
    return f'https://{parsed.hostname.lower()}'+(f':{parsed.port}' if parsed.port and parsed.port!=443 else '')


def list_accounts():
    rows = []
    for account in secret_store.read().get('accounts', {}).values():
        public = {k:v for k,v in account.items() if k!='password'}
        public['site_name'] = account.get('site_name') or urlparse(account['origin']).hostname
        public['has_password'] = bool(account.get('password'))
        rows.append(public)
    return sorted(rows, key=lambda row: row['site_name'].casefold())


def save_account(payload):
    target=origin(payload.get('login_url',''))
    username=str(payload.get('username','')).strip()
    if not username or len(username)>320:raise ValueError('Enter the account email or username')
    site_name = str(payload.get('site_name', '')).strip()
    if len(site_name)>80:raise ValueError('Website name must be at most 80 characters')
    def change(data):
        accounts=data.setdefault('accounts',{});previous=accounts.get(target,{})
        if previous and previous['username'] != username and not payload.get('password'):
            raise ValueError('Enter the password for the new username')
        password=payload.get('password') or previous.get('password','')
        if not isinstance(password,str) or not password or len(password)>1024:raise ValueError('Enter the password')
        accounts[target]={'origin':target,'login_url':payload['login_url'],'site_name':site_name or previous.get('site_name') or urlparse(target).hostname,'username':username,'password':password,'enabled':payload.get('enabled') is True}
    secret_store.update(change)


def account_for(url):
    try:account=secret_store.read().get('accounts',{}).get(origin(url))
    except ValueError:return None
    return account if account and account.get('enabled') else None


def delete_account(url):
    target=origin(url)
    secret_store.update(lambda data:data.setdefault('accounts',{}).pop(target,None))
