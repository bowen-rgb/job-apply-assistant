"""Keep a candidate-owned Chrome login window alive for a QR draft."""
import json,sys
from playwright.sync_api import sync_playwright
from . import qr_application as qr
from .profile_store import runtime_profile
from .apply_worker import _open_browser
from .workspaces import candidate_id,active_id
from .worker_runtime import check_cancelled


def run(identifier, owner_token='', foreground=True):
    row=qr.get_request(identifier);payload=json.loads(row['payload']);owner=candidate_id()
    url=payload.get('url') or payload['final_url'];qr.validate_destination(url)
    with sync_playwright() as p:
        _,context,mode=_open_browser(p,runtime_profile())
        if mode!='cdp':raise ValueError('Dedicated Chrome required')
        try:
            page=context.new_page();page.goto(url,wait_until='domcontentloaded',timeout=35000)
            session=context.new_cdp_session(page);target=session.send('Target.getTargetInfo')['targetInfo']['targetId'];session.detach()
            if foreground:page.bring_to_front()
            payload.update(handoff_tab_id=target,handoff_url=page.url,handoff_owner=owner_token,handoff_error='')
            with qr.connect() as c:
                c.execute('UPDATE qr_requests SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),identifier))
                if row.get('job_id'):c.execute('UPDATE jobs SET application_tab_id=? WHERE id=?',(target,row['job_id']))
            while not page.is_closed() and active_id()==owner:
                check_cancelled();page.wait_for_timeout(2000)
                # storage_state() can create/navigate temporary tabs for previous
                # origins. Never collect it on a timer while a person is logging in.
        except Exception as exc:
            with qr.connect() as c:
                current=c.execute('SELECT payload FROM qr_requests WHERE id=?',(identifier,)).fetchone()
                if current:
                    value=json.loads(current['payload']);value.update(handoff_owner=owner_token,handoff_error=str(exc)[:500])
                    c.execute('UPDATE qr_requests SET payload=? WHERE id=?',(json.dumps(value,ensure_ascii=False),identifier))
            raise
        finally:
            # A closed/crashed window is reported; never recreate or reload it.
            context.close()

if __name__=='__main__':
    token=sys.argv[sys.argv.index('--owner-token')+1] if '--owner-token' in sys.argv else ''
    run(sys.argv[1],token,'--background' not in sys.argv)
