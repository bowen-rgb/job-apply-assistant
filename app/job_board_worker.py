"""Native, isolated job-board dispatch over the vendored MIT scraper primitives.

No upstream CLI, MCP server, scrape_jobs facade, pandas or DataFrame boundary.
One site's structured errors cannot silently become an empty successful scan.
"""
import importlib
import json
import sys

SITES = {'indeed':'Indeed','linkedin':'LinkedIn','glassdoor':'Glassdoor',
         'google':'Google','hellowork':'HelloWork','zip_recruiter':'ZipRecruiter',
         'bayt':'Bayt','naukri':'Naukri','bdjobs':'BDJobs'}


def collect(payload, factory=None):
    from .vendor.jobspy.model import ScraperInput
    rows = []
    for site in payload['sites']:
        if site not in SITES:
            raise ValueError('Unsupported job board: '+site)
        module = 'ziprecruiter' if site == 'zip_recruiter' else site
        scraper = (factory(site) if factory else
                   getattr(importlib.import_module('app.vendor.jobspy.'+module), SITES[site])())
        request = ScraperInput.model_validate({
            'site_name':[site], 'search_term':payload['search_term'],
            'google_search_term':payload.get('google_search_term'), 'location':payload['location'],
            'results_wanted':payload['results_wanted'], 'hours_old':payload.get('hours_old') or None,
            'country_indeed':payload.get('country_indeed') or 'worldwide',
            'fetch_description':bool(payload.get('linkedin_fetch_description')),
            **({'job_type':payload['job_type']} if payload.get('job_type') else {})})
        jobs = scraper.scrape(request)
        if scraper.error and not jobs:
            raise RuntimeError(f'{site}: {scraper.error}')
        for job in jobs:
            row = job.model_dump(mode='json')
            row['site'] = site
            rows.append(row)
    return rows


if __name__ == '__main__':
    json.dump(collect(json.loads(sys.argv[1])), sys.stdout, ensure_ascii=False, default=str)
