# Open-source references reviewed for V8

## Beginner guidance

- Worked example: adapted the explicit task completion and review-before-confirmation principles of [check answers](https://design-system.service.gov.uk/patterns/check-answers/) and [confirmation pages](https://design-system.service.gov.uk/patterns/confirmation-pages/). The independently implemented five-step practice uses fictional data, preserves its own progress, and never writes candidate or job state. Printing includes the whole example.

- [GOV.UK task list](https://design-system.service.gov.uk/components/task-list/) and [complete multiple tasks](https://design-system.service.gov.uk/patterns/complete-multiple-tasks/): actionable task names and contextual explanations for a workflow completed over time.
- Inspected the [govuk-frontend task-list template](https://github.com/alphagov/govuk-frontend/blob/main/packages/govuk-frontend/src/govuk/components/task-list/template.njk). Implemented independent native HTML guidance without copying source or adding dependencies.
- Manual, assisted and already-sent routes remain independent. Browser detection does not establish ChatGPT authentication. Guide navigation never starts automation or sends applications.

V8 distinguishes between **licensed code adaptation**, **library dependency**, and **architectural reference**.

## Licensed integration/adaptation

### `speedyapply/JobSpy`

Repository: `https://github.com/speedyapply/JobSpy`

License reviewed: MIT.

Used in V8 as an optional installed dependency (`python-jobspy==1.1.82`) for multi-site discovery. Its normalized output is converted into this project's internal job record and then passes through the same local dedupe/scoring pipeline as every other provider.

### `qpwm06/QuickApply`

Repository: `https://github.com/qpwm06/QuickApply`

License reviewed: MIT.

V8 reviewed/adapted these patterns into the existing FastAPI/SQLite architecture:

- `app/fetcher.py`: run JobSpy in a subprocess, normalize rows and use bounded retry handling;
- `app/job_dedupe.py`: normalize cross-source identity, retain source variants and select a preferred source;
- search profiles: separate market/search campaigns rather than forcing one global query;
- tracker models: separate application state/stage events from discovered-job state;
- scheduler pattern: one coalesced periodic refresh instead of overlapping crawls.

The V8 implementation remains Python/FastAPI/SQLite-specific and adds configurable dedupe scope, safe application queueing and existing ChatGPT/ATS policy boundaries.

### `devdattatalele/auto-apply`

Repository: `https://github.com/devdattatalele/auto-apply`

License reviewed: MIT.

Earlier versions adapted/reimplemented ideas from:

- `lib/scanner.mjs`;
- `lib/fields.mjs`;
- `lib/planner.mjs`;
- `lib/learner.mjs`.

Current corresponding modules include `app/form_scanner.py`, `app/smart_fields.py` and `app/learnings.py`. Account creation, OTP/MFA automation and CAPTCHA bypass are intentionally not imported.

Required MIT notices are reproduced in `THIRD_PARTY_NOTICES.md`.

## Architectural references (no source copied unless separately licensed/noticed)

### `shankswhite/JobApplyAgent`

License reviewed: MIT. The required notice is also included because V8 directly absorbed its conditional-rescan pattern into the deterministic pre-agent pass. Strong patterns observed: snapshot-driven form extraction, layered answer resolution, repeated rescans for conditionally revealed fields, multi-entry form sections, and local reusable-answer cache.

### `browser-use/browser-use`

License reviewed: MIT. Reviewed for the separation between browser harness, agent planning, structured actions and browser execution. V8 continues using its own narrower policy-controlled executor rather than giving a general agent unrestricted browser authority.

### `geckguy/AutoApply`

Patterns: local-first data, review-first application workflow, reusable answers and general-purpose candidate configuration.

### `dyyfk/auto-apply`

Patterns: centralized scouting/queue/dedup, public ATS board feeds, ATS-specific modules. A repository license was not confirmed during review, so implementation patterns were independently re-created rather than copied.

### `tmason10/job-application-automation`

Patterns: visible Playwright browser, manual CAPTCHA/final submission and confirmation detection. A repository license was not confirmed during review, so no source is vendored.

### `Ni-co-la-s/job-application-tracker`

Patterns: multi-source discovery, substantially-identical-job deduplication, application analytics, resume registry and optional PII redaction before cloud LLM use. No repository license was found during review, so V8 uses ideas only and copies no code.

## Resulting V8 principles

1. Structured/public source first, generic search as coverage fallback.
2. Cross-source identity stores one job but retains every useful source URL.
3. Candidate settings and search campaigns are data, not source-code constants.
4. Deterministic form handling runs before agent fallback.
5. Agent actions are validated by local policy and never include final Submit.
6. Queue state, application status and recruiting pipeline stage are separate concepts.
7. Repeated scans and repeated applications are auditable and resumable.
8. Missing facts trigger human review rather than invention.

## Human-review exports

- [Odoo 19 export controller](https://github.com/odoo/odoo/blob/19.0/addons/web/controllers/export.py): reviewed the actual `ExportXlsxWriter` and export-selection implementation. Adapted the filtered-selection, explicit-field and in-memory workbook patterns independently; no Odoo source is copied or vendored.
- [XlsxWriter tables](https://xlsxwriter.readthedocs.io/worksheet.html#worksheet-add-table): used the library for real XLSX files with column filters, frozen headers, wrapped text and editable reviewer feedback.
- [XlsxWriter workbook options](https://xlsxwriter.readthedocs.io/workbook.html#constructor): disabled automatic formulas and URL conversion for untrusted source/review text; job links are explicitly validated and written as hyperlinks.
- Reports are frozen local snapshots, with localized headings, optional review-text translation, retained originals and explicit translation failures. Comments in exported files do not change local approvals or application states.

## Dashboard state semantics

- [BullMQ job implementation](https://github.com/taskforcesh/bullmq/blob/master/src/classes/job.ts) and [idempotent jobs](https://docs.bullmq.io/patterns/idempotent-jobs): reviewed separation of progress, failure reason and completed outcomes. Local manual submission supersedes preparation failure, repeat confirmations are idempotent and late worker writes cannot revert submission. Implemented independently without BullMQ dependencies or copied source.

- [Prefect flow-run implementation](https://github.com/PrefectHQ/prefect/blob/main/src/prefect/flow_runs.py) and [interactive workflows](https://docs.prefect.io/v3/advanced/interactive): reviewed contextual handoff and explicit user-input patterns. Queue presentation now separates current execution, required human action and failure details; no Prefect source is copied.
- [Playwright bring-to-front](https://playwright.dev/python/docs/api/class-page#page-bring-to-front) and [CDP sessions](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-new-cdp-session): identify and activate the existing application tab without navigation or final submission.

- [GitHub Projects: filtering views](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/filtering-projects): independently filter explicit field values. Implemented locally; no GitHub source code is copied.
- [Schema.org: validThrough](https://schema.org/validThrough): interpret a job listing's deadline separately from contract end dates and recruiter responses.
- Recruiter outcomes are confirmed local records with provenance and timestamped history, not inferred from AI recommendations or failed discovery requests.
- [Prefect interactive workflows](https://docs.prefect.io/v3/advanced/interactive): pause automated preparation until explicit human input; implemented independently with the existing SQLite queue.
- [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches): bind confirmation to reviewed content and dismiss stale decisions after changes; no GitHub code is copied.
