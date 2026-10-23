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


LOGIN_PATH = re.compile(r'/(?:login|signin|sign-in|sign_in|connexion(?:-inscription)?|authenticate|auth)(?:/|$|[.#])',re.I)
LOGIN_BUTTON = re.compile(r'^(sign in|log in|login|se connecter|connexion|登录|anmelden|iniciar sesi[oó]n|entrar|continue|continuer|next|suivant|weiter)$',re.I)
USER_FIELDS = 'input[type=email]:visible,input[autocomplete=username]:visible,input[name=username]:visible,input[name=email]:visible,input[name=login]:visible'


def _handoff(reason):
    return {'status':'handoff','reason':reason}


def _verification(frame):
    if frame.locator('input[autocomplete="one-time-code"]:visible,input[name=otp]:visible,input[name=verificationCode]:visible').count():
        return 'Verification code or MFA required. Complete it on the open page.'
    if frame.locator('iframe[title*="captcha" i]:visible,iframe[title*="challenge" i]:visible').count():
        return 'Human verification required. Complete it on the open page.'
    try:
        text=frame.locator('body').inner_text(timeout=1500)
        if len(text)<2000 and re.search(r'verify you are human|checking your browser|正在验证|验证设备',text,re.I):
            return 'Human verification required. Complete it on the open page.'
    except Exception:pass
    return ''


def _authenticated_surface(frame):
    try:
        return bool(re.search(r'my applications|mes candidatures|tableau de bord',frame.locator('body').inner_text(timeout=1500),re.I)) or any(
            item.is_visible() for item in frame.get_by_text(re.compile(r'^(déconnexion|se déconnecter|sign out|log out)$',re.I)).all())
    except Exception:return False


def resume_application_after_login(page, job_url):
    """Return from an account landing page, leaving any open application intact."""
    from urllib.parse import urlparse
    if page.url==job_url or page.locator('input[type=file]').count():return
    parsed=urlparse(job_url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:return
    path=urlparse(page.url).path
    landing=LOGIN_PATH.search(path) or re.search(r'/(?:dashboard|account|my-account|espacepersonnel|mon-espace)(?:/|$)',path,re.I)
    if landing and _authenticated_surface(page):
        page.goto(job_url,wait_until='domcontentloaded',timeout=30000)


def login_if_needed(page, on_progress=None):
    """Bounded automatic login inside the application tab, never a separate desk.

    Reused sessions take the no-form path. Secrets stay on their configured exact
    origin. Email-first transitions are allowed only in an identified login form;
    a password is sent at most once per invocation, with no silent retry loop.
    """
    from urllib.parse import urlparse
    sent=set();email_origin='';attempted=False
    for step in range(3):
        selected=None
        for frame in page.frames:
            problem=_verification(frame)
            if problem:return _handoff(problem)
            passwords=frame.locator('input[type=password]:visible')
            users=frame.locator(USER_FIELDS)
            login_path=bool(LOGIN_PATH.search(urlparse(frame.url).path))
            if not passwords.count() and not (login_path and users.count()):continue
            selected=(frame,passwords,users,login_path);break
        if selected is None:
            if any(LOGIN_PATH.search(urlparse(f.url).path) for f in page.frames) and not _authenticated_surface(page):
                return _handoff('Login page is not ready or uses an unsupported sign-in method. Complete it on the open page.')
            return {'status':'logged_in' if attempted else 'not_needed','reason':'Login completed; checking the application next.' if attempted else ''}
        frame,passwords,users,login_path=selected
        if passwords.count()>1 or frame.locator('input[autocomplete="new-password"]:visible').count():
            return _handoff('Account creation or password-change form requires your review.')
        field=passwords if passwords.count() else users
        if field.count()!=1:return _handoff('Login field is ambiguous. Check the open page.')
        form=field.locator('xpath=ancestor::form[1]')
        if form.count()!=1:return _handoff('Login form could not be identified.')
        if form.locator('input[type=file]').count():
            return {'status':'not_needed','reason':''} if not passwords.count() else _handoff('Mixed application and login form requires your review.')
        account=account_for(frame.url)
        if not account:return _handoff('Login required: save this website account and enable automatic login, or sign in on the open page.')
        try:
            current_origin=origin(frame.url)
            destination=urljoin(frame.url,form.get_attribute('action') or frame.url)
            safe=origin(destination)==current_origin==account['origin']
        except ValueError:safe=False
        if not safe:return _handoff('Login destination differs from the configured origin.')
        stage='password' if passwords.count() else 'email'
        if (current_origin,stage) in sent:return _handoff('Login was not accepted. Check credentials on the open page; no automatic retry or reset was attempted.')
        submit=form.get_by_role('button',name=LOGIN_BUTTON)
        if submit.count()!=1:return _handoff('Login button could not be identified unambiguously.')
        form_users=form.locator(USER_FIELDS)
        if passwords.count() and not form_users.count() and email_origin!=current_origin:
            # A remembered account must identify the same saved username before
            # we send its password. Do not guess from a different browser account.
            if account['username'].casefold() not in frame.locator('body').inner_text().casefold():
                return _handoff('Confirm the remembered account before automatic password entry.')
        if form_users.count()>1:return _handoff('Login username field is ambiguous.')
        check_cancelled()
        if on_progress:on_progress('Signing in with the locally saved website account.')
        sent.add((current_origin,stage));attempted=True
        try:
            if form_users.count():form_users.fill(account['username'])
            if passwords.count():passwords.fill(account['password'])
            else:email_origin=current_origin
            submit.click(timeout=5000)
        except Exception:return _handoff('Login could not finish. Check the open page before retrying.')
        # Wait for a real state change, not merely a disappearing password input.
        transitioned=False
        for _ in range(16):
            check_cancelled();page.wait_for_timeout(500)
            for current in page.frames:
                problem=_verification(current)
                if problem:return _handoff(problem)
            try:
                if form.locator('[role=alert]:visible').count():
                    return _handoff('The website reported a login error. Check credentials; automatic retry is paused.')
                next_password=any(f.locator('input[type=password]:visible').count() for f in page.frames)
                if stage=='email' and next_password:transitioned=True;break
                has_fields=any(f.locator('input[type=password]:visible').count() or
                               (LOGIN_PATH.search(urlparse(f.url).path) and f.locator(USER_FIELDS).count()) for f in page.frames)
                login_url=any(LOGIN_PATH.search(urlparse(f.url).path) for f in page.frames)
                if not has_fields and (not login_url or _authenticated_surface(page)):
                    return {'status':'logged_in','reason':'Login completed; checking the application next.'}
            except Exception:
                # A navigation can detach the old form. Inspect fresh frames on
                # the next tick; it is not evidence of a successful sign-in.
                continue
        if transitioned:continue
        return _handoff('Login was not completed. Check credentials or verification on the open page; no automatic retry or reset was attempted.')
    return _handoff('Login needs additional steps. Complete them on the open page.')
