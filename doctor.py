from __future__ import annotations
import json
import urllib.request
from pathlib import Path

from app.profile_store import load_profile_raw, runtime_profile, active_resume_path
from app.jobspy_provider import available as jobspy_available
from app.search_profiles import expand_runtime_profile
from app.queue_manager import status as queue_status
from app.scheduler import status as scheduler_status
from app.db import init_db


def pkg(name):
    try:
        __import__(name); return True
    except Exception:
        return False


def main():
    init_db()
    raw=load_profile_raw(); p=runtime_profile(raw); resume=active_resume_path(raw)
    cdp=p.get('chrome_cdp_endpoint','http://127.0.0.1:9222').rstrip('/')
    try:
        with urllib.request.urlopen(cdp+'/json/version',timeout=1.5) as r:
            browser=json.loads(r.read().decode()).get('Browser','')
        cdp_ok=True
    except Exception:
        cdp_ok=False; browser=''
    checks={
        'Profile schema V8': int(raw.get('schema_version',0))==8,
        'FastAPI': pkg('fastapi'),
        'Playwright': pkg('playwright'),
        'Scrapling': pkg('scrapling'),
        'JobSpy': jobspy_available(),
        'Active CV': bool(resume and resume.exists()),
        'Chrome CDP': cdp_ok,
        'Search campaigns': len(expand_runtime_profile(p))>=1,
        'Agent fallback': bool(p.get('agent_fallback',{}).get('enabled',True)),
        'ChatGPT reviewer': bool(p.get('chatgpt_web_reviewer',{}).get('enabled',True)),
    }
    print('Job Apply Assistant V8 — local doctor')
    print('='*44)
    for k,v in checks.items(): print(f'{k:24} {"OK" if v else "MISSING/OFF"}')
    print(f'Chrome: {browser or "not connected"}')
    print(f'Queue: {queue_status().get("counts",{})}')
    print(f'Auto scan: {scheduler_status()}')
    print(f'JobSpy sites: {p.get("jobspy_sites",[])}')
    print(f'Dedupe scope: {p.get("dedupe_scope","")}')

if __name__=='__main__': main()
