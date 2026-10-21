"""Optional maintainer diagnostic: REA observes one public page in dedicated Chrome.

Run: python -m scripts.inspect_qr_source URL [--sources]
No form actions, profile setup changes, candidate documents or application dispatch.
"""
import argparse,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from app.apply_worker import _open_browser
from app.profile_store import runtime_profile,data_directory
from app.pfe_discovery import validate_destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url');parser.add_argument('--sources',action='store_true')
    args=parser.parse_args();validate_destination(args.url)
    executable=shutil.which('npx.cmd' if sys.platform=='win32' else 'npx')
    if not executable:raise RuntimeError('Node.js/npm is required for optional REA diagnostics')
    with sync_playwright() as p:
        _,context,mode=_open_browser(p,runtime_profile())
        if mode!='cdp':context.close();raise RuntimeError('Dedicated Chrome CDP required')
        checked=set()
        def guard(route):
            target=route.request.url
            if target.startswith(('data:','blob:')):route.fallback();return
            try:
                host=urlparse(target).hostname
                if host not in checked:validate_destination(target);checked.add(host)
                route.fallback()
            except Exception:route.abort()
        context.route('**/*',guard)
        try:
            page=context.new_page();page.goto(args.url,wait_until='domcontentloaded',timeout=35000)
            try:page.wait_for_load_state('networkidle',timeout=6000)
            except Exception:pass
            validate_destination(page.url)
            session=context.new_cdp_session(page);target=session.send('Target.getTargetInfo')['targetInfo']['targetId'];session.detach()
            command=[executable,'--yes','rea-agents@6.7.0','inspect-web-page',runtime_profile().get('chrome_cdp_endpoint','http://127.0.0.1:9222'),target,'--observation-ms','500','--format','json']
            if args.sources:command.append('--include-script-sources')
            result=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
            if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace')[-700:])
            evidence=json.loads(result.stdout)
            directory=data_directory()/'diagnostics'/'rea';directory.mkdir(parents=True,exist_ok=True)
            output=directory/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.json');output.write_bytes(result.stdout)
            print(json.dumps({'evidence_id':evidence.get('evidence_id'),'saved_to':str(output),'bytes':len(result.stdout)}))
        finally:context.close()

if __name__=='__main__':main()
