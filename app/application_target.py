"""Minimum facts required before writing a purportedly tailored application letter."""
import json
import re
from .qr_context import usable_company


def qr_context(job):
    value=job.get('application_context_json')
    if not value:return {}
    try:return json.loads(value)
    except (ValueError,TypeError):raise ValueError('Application context unavailable; inspect the page again.')


def requires_letter(job,raw):
    if not raw.get('application',{}).get('generate_cover_letter',True):return False
    context=qr_context(job)
    # A confirmed generic CV pool gets a CV only, never a fictitious vacancy letter.
    return not (context and context.get('kind')=='general')


def letter_target(job):
    context=qr_context(job)
    if job.get('provider_key')=='qr' and not context:
        raise ValueError('Entreprise, poste et missions doivent être identifiés avant de rédiger une lettre ciblée.')
    if context:
        if (context.get('kind')!='vacancy' or not context.get('role_title') or not context.get('tasks')
                or not usable_company(context.get('company',''))):
            raise ValueError('Entreprise, poste et missions doivent être identifiés avant de rédiger une lettre ciblée.')
        return {key:context.get(key) for key in ('kind','company','company_evidence','company_quote','company_source_url','role_title','tasks','final_url')}
    company=str(job.get('company') or '').strip()
    title=str(job.get('title') or '').strip()
    body=str(job.get('body') or job.get('snippet') or '').strip()
    if (not usable_company(company) or not title or len(body)<35
            or re.fullmatch(r'careers?|jobs?|offres? d.emploi|career opportunities.*',title,re.I)):
        raise ValueError('Entreprise, poste et missions doivent être identifiés avant de rédiger une lettre ciblée.')
    return {'kind':'vacancy','company':company,'role_title':title,'tasks':[body[:16000]],'final_url':job.get('url',''),'source':'stored_job'}
