"""Re-evaluate stored jobs without scraping or changing user/application actions."""
import json
import re
from collections import Counter

from .db import connect
from .extractor import extract_date_range
from .scoring import evaluate
from .search_profiles import expand_runtime_profile


def clean_stored_job(job):
    cleaned = dict(job)
    body = cleaned.get('body') or ''
    # Repair legacy Plany records containing a complete navigation/recommendation page.
    if cleaned.get('provider_key') == 'plany' and 'Métier :' in body:
        body = body[body.index('Métier :'):]
        body = re.split(r'Ces offres pourraient aussi|Mes jobs, mon rythme', body, maxsplit=1)[0]
        cleaned['body'] = body.strip()
        start, end = extract_date_range(body)
        cleaned['start_date'] = start
        cleaned['end_date'] = end
        match = re.search(r'Type de contrat\s*:\s*([^\n]+)', body)
        if match:
            cleaned['employment_type'] = match.group(1).strip()
    return cleaned


def rescore_jobs(profile):
    campaigns = expand_runtime_profile(profile)
    by_id = {c['search_profile_id']: c for c in campaigns}
    counts = Counter()
    with connect() as c:
        rows = c.execute('SELECT * FROM jobs').fetchall()
        for row in rows:
            job = clean_stored_job(dict(row))
            campaign = by_id.get(job['search_profile_id'], profile)
            score, decision, reason, flags = evaluate(job, campaign)
            if 'unverified_' in (job.get('reason') or ''):
                reason += '; unverified_stored_result'
            c.execute('''UPDATE jobs SET score=?,decision=?,reason=?,body=?,employment_type=?,start_date=?,end_date=?,
                         availability_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                      (score, decision, reason, job['body'], job['employment_type'], job['start_date'], job['end_date'],
                       'expired' if decision == 'expired' else 'unknown', job['id']))
            counts[decision] += 1
    return {'updated': len(rows), 'decisions': dict(counts)}
