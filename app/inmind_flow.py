"""Visible Inmind CV-import preparation; no final registration click here."""
import re
import json
from pathlib import Path
from urllib.parse import urlsplit
from .worker_runtime import check_cancelled


def prepare_registration(page, profile, report, job=None, resume_path=None):
    if urlsplit(page.url).hostname!='cv.inmind.fr':
        report['errors'].append('Inmind preparation stopped: unexpected origin')
        return report
    if job and urlsplit(page.url).path.rstrip('/')!=urlsplit(job['url']).path.rstrip('/'):
        report['errors'].append('Inmind preparation stopped: recipient path changed')
        return report
    if page.locator('#upload_applicant_resume_upload').count() and not page.locator('#firstname').count():
        if not profile.get('invocation_privacy_confirmed'):
            report['errors'].append('Inmind: confirm this employer’s CV-use terms before continuing')
            return report
        terms=page.locator('.content__section--required').filter(has_text=re.compile(r'conditions générales|terms',re.I))
        if terms.count()!=1:
            report['errors'].append('Inmind: employer terms control is missing or ambiguous')
            return report
        if not terms.locator('.form__group__radio-bttn--is-checked').count():
            check_cancelled();terms.locator('.form__group__radio-bttn').click(timeout=3000)
        report['actions'].append({'field':'privacy','strategy':'explicit_this_invocation','text':terms.inner_text()[:1000]})
        proceed=page.get_by_role('button',name=re.compile(r'^VALIDER(?:\s+check)?$',re.I))
        if proceed.count()!=1 or not proceed.is_enabled():
            report['errors'].append('Inmind CV import cannot advance; inspect the existing page')
            return report
        check_cancelled();proceed.click(timeout=10000)
        page.locator('#firstname').wait_for(state='visible',timeout=45000)
        session=page.context.new_cdp_session(page)
        try:report['inmind_import_target']=session.send('Target.getTargetInfo')['targetInfo']['targetId']
        finally:session.detach()
    if page.locator('#firstname').count() and 'resume' not in report['filled'] and job and resume_path:
        # Only carry an upload from the exact retained tab and matching sealed CV.
        from .application_safety import file_hash
        try:
            previous=json.loads(Path(job.get('fill_audit_path') or '').read_text(encoding='utf-8'))
            matching=any(d.get('role')=='resume' and d.get('sha256')==file_hash(resume_path) for d in previous['materials']['documents'])
            if previous['report'].get('inmind_import_target')==job.get('application_tab_id') and matching and previous['documents']['resume_attached']:
                report['filled'].append('resume')
                report['inmind_import_target']=job['application_tab_id']
                report['actions'].append({'field':'resume','strategy':'retained_tab_verified_upload','audit':job['fill_audit_path']})
        except (OSError,ValueError,KeyError):pass
    # Imported CV text can misparse names: use the candidate's confirmed identity.
    for selector,key in [('#firstname','first_name'),('#lastname','last_name'),('#email','email'),('#phone','phone')]:
        field=page.locator(selector)
        if field.count()==1 and field.is_visible() and profile.get(key):
            field.fill(profile[key])
            report['filled'].append(key)
    civility=profile.get('invocation_civility')
    if civility and page.locator('#firstname').count():
        label=page.get_by_text('M.' if civility=='Monsieur' else 'Mme',exact=True)
        choice=label.locator('xpath=..')
        if choice.count()==1:
            if not choice.locator('.is_checked').count():choice.click(timeout=3000)
            report['filled'].append('civility')
    report['filled']=list(dict.fromkeys(report['filled']))
    return report
