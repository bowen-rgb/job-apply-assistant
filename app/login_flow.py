"""Deterministic login only on the configured HTTPS origin; no AI sees secrets."""
import re
from urllib.parse import urljoin
from .site_accounts import account_for,origin
from .worker_runtime import check_cancelled


def dismiss_optional_popups(page):
    for frame in page.frames:
        for label in [r'^Tout refuser$',r'^Reject all$',r'^Continuer sans accepter$',r'^Reject optional cookies$']:
            button=frame.get_by_role('button',name=re.compile(label,re.I))
            try:
                if button.count()==1 and button.is_visible():button.click(timeout=2000)
            except Exception:pass
        # Close only named dialog close controls, never arbitrary confirmation.
        for dialog in frame.get_by_role('dialog').all():
            if dialog.locator('input,textarea,select').count():continue
            close=dialog.get_by_role('button',name=re.compile(r'^(close|fermer|鍏抽棴|schlie脽en|cerrar|fechar)$',re.I))
            try:
                if close.count()==1 and close.is_visible():close.click(timeout=2000)
            except Exception:pass


def login_if_needed(page):
    for frame in page.frames:
        if frame.locator('input[autocomplete="one-time-code"]:visible').count():
            return {'status':'handoff','reason':'Verification code or MFA required. Complete it on the open page.'}
        passwords=frame.locator('input[type=password]:visible')
        if not passwords.count():continue
        if passwords.count()!=1:return {'status':'handoff','reason':'Account creation or password-change form requires your review.'}
        account=account_for(frame.url)
        if not account:return {'status':'handoff','reason':'Login required: configure this site account or sign in on the open page.'}
        form=passwords.locator('xpath=ancestor::form[1]')
        if form.count()!=1:return {'status':'handoff','reason':'Login form could not be identified.'}
        destination=urljoin(frame.url,form.get_attribute('action') or frame.url)
        if origin(destination)!=account['origin']:return {'status':'handoff','reason':'Login destination differs from the configured origin.'}
        users=form.locator('input[type=email]:visible, input[autocomplete=username]:visible, input[name=username]:visible, input[name=email]:visible')
        if users.count()!=1:return {'status':'handoff','reason':'Login username field is ambiguous.'}
        submit=form.get_by_role('button',name=re.compile(r'^(sign in|log in|login|se connecter|connexion|鐧诲綍|anmelden|iniciar sesi贸n|entrar)$',re.I))
        if submit.count()!=1:return {'status':'handoff','reason':'Login button could not be identified.'}
        check_cancelled()
        try:
            users.fill(account['username']);passwords.fill(account['password']);submit.click(timeout=5000)
        except Exception:
            return {'status':'handoff','reason':'Login could not finish. Check the open page before retrying.'}
        for _ in range(16):
            check_cancelled();page.wait_for_timeout(500)
            try:
                if frame.locator('input[autocomplete="one-time-code"]:visible').count():
                    return {'status':'handoff','reason':'Verification code or MFA required. Complete it on the open page.'}
                if not frame.locator('input[type=password]:visible').count():return {'status':'logged_in','reason':'Login form completed; application flow will be checked next.'}
            except Exception:break
        return {'status':'handoff','reason':'Login was not completed. Check password, verification code or MFA; password reset is not automatic.'}
    return {'status':'not_needed','reason':''}
