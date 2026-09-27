# V8 changes

## Discovery

- Added optional `python-jobspy` discovery provider.
- Added per-campaign roles, locations, contracts, sources, JobSpy sites and freshness limits.
- Added background automatic scan interval.
- Added configurable cross-source dedupe scope.
- Added preservation of all source variants for merged jobs.
- Prefetched JobSpy descriptions remain usable when the destination page cannot be fetched.

## Application operations

- Added persistent `application_queue`.
- Added sequential queue worker with `queued / running / waiting_user / done / error` states.
- Added Pipeline dashboard and persistent stage-event history.
- Added `saved / queued / prepared / submitted / screening / interview / offer / rejected / withdrawn` stages.
- Search campaigns can bind a particular CV; campaign-specific CV routing takes precedence over tag routing.

## Dashboard

- Added Pipeline & file navigation view.
- Added JobSpy configuration controls.
- Added search-profile editor.
- Added automatic scan interval and dedupe policy controls.
- Job cards now expose campaign, queue and tracker status.

## Reliability

- JobSpy runs out-of-process with retry/timeout handling.
- Cross-source duplicates keep richer existing body text and alternate source links.
- Queue processing waits for preparation state rather than assuming browser launch means success.
- Existing final-submit, CAPTCHA/MFA, sensitive/legal and account-creation barriers remain unchanged.

## Open-source integration

- Integrated JobSpy as an MIT-licensed dependency.
- Adapted the MIT-licensed QuickApply patterns for JobSpy subprocess isolation/retry, cross-source source variants, search profiles and application tracking concepts.
- Preserved previous MIT attribution for the form-scanning/learning work influenced by `devdattatalele/auto-apply`.
