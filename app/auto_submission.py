"""Bounded final submission, explicitly enabled by the candidate."""
import re
from .form_engine import generic_confirmation
from .worker_runtime import check_cancelled


def submit_complete_form(page,scope,audit,before_click=lambda:None):
    docs=audit['documents']
    if audit['required_unanswered_count'] or audit['sensitive_or_legal_unanswered_count'] or not docs['resume_attached'] or audit['report'].get('errors'):
        return {'status':'blocked','reason':'Missing answers, documents or form errors.'}
    if docs['letter_generated'] and not(docs['letter_attached'] or docs['letter_text_filled']):
        return {'status':'blocked','reason':'Generated letter was not attached.'}
    # Never retry a click automatically: a timeout might still have sent it.
    success,_=generic_confirmation(page)
    if success:return {'status':'blocked','reason':'Page already contains a confirmation; verify the existing application.'}
    buttons=scope.get_by_role('button',name=re.compile(r'^(submit application|send application|envoyer ma candidature|envoyer la candidature|soumettre ma candidature|postuler|submit|envoyer|bewerbung absenden|enviar candidatura|enviar solicitud|提交申请)$',re.I))
    if buttons.count()!=1 or not buttons.is_visible() or not buttons.is_enabled():
        return {'status':'blocked','reason':'A unique final application button was not identified.'}
    check_cancelled()
    before_click()
    try:buttons.click(timeout=10000)
    except Exception:return {'status':'uncertain','reason':'Send result uncertain. Check the recruiter site before retrying.'}
    for _ in range(20):
        check_cancelled();page.wait_for_timeout(500)
        success,evidence=generic_confirmation(page)
        if success and evidence.startswith('confirmation_text:'):return {'status':'verified','reason':evidence}
        if scope is not page:
            success,evidence=generic_confirmation(scope)
            if success and evidence.startswith('confirmation_text:'):return {'status':'verified','reason':evidence}
    return {'status':'uncertain','reason':'No submission confirmation observed. Check the recruiter site; do not resend blindly.'}
