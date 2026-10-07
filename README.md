
## First-time users / Première utilisation / 第一次使用

Open **Premiers pas / Start here / 从这里开始** in the sidebar and select your language. Choose manual application, assisted preparation, or recording an application already sent. Each page has contextual help. Print the in-app guide or save it as PDF, or read the [French / Chinese user guide](USER_GUIDE.md).

New users now start in **Simple mode → Guide me**, with one real action at a time: CV → choose one job → apply on the recruiter’s site → explicitly confirm submission → finish. **Show all tools** restores the full dashboard. No ChatGPT connection is needed for the simple manual path.

## Windows V8.2 dependency fix

If V8.1 stopped with `error: resolution-too-deep`, use V8.2. The installer now installs core, JobSpy, and Scrapling in separate steps and uses `scrapling[fetchers]` rather than the much larger optional `scrapling[all]` dependency graph. See `FIX_V8_2.md`.

# Job Apply Assistant V8.4

## Application documents and queue fixes

### Matching and source diagnostics

Weekends and night shifts marked **Yes / Flexible** mean those shifts are possible in addition to daytime and weekdays. They do not restrict discovery to those schedules, and the AI review prompt now states that meaning explicitly. Preferred keywords rank candidates locally; source searches no longer require every preferred phrase or exclude vacancies merely because a site menu mentions CDI. Role matching handles common French feminine/masculine forms. Structured job descriptions take precedence over page navigation and related vacancies; local strong matches indicate relevance while missing dates still require checking before applying. Confirmed contract/end-date conflicts remain excluded.

Existing local matches are recalculated when the server starts. **Recalculate matches** updates scores from stored records without fetching or changing saved/skipped jobs, application history or review verdicts. Legacy Plany page chrome and recommendation dates are removed during recalculation. A scan in progress must finish before using the button.

Expand **Source diagnostics** under the scan progress to see attempted searches, raw results before deduplication and errors for each campaign/source/method. A successful search with zero results differs from a blocked request, missing dependency or query omitted by the configured budget. Diagnostics persist for the last completed scan. Search sources run before the potentially long JobSpy sweep; JobSpy failures are isolated and reported per site. City One's current public detail URLs and Bing destination redirects are recognized. Search results that point to France Travail, HelloWork or Indeed public listing pages are followed to bounded sets of detail links; those listing pages are never stored as individual vacancies. Connections and result counts can still change with site availability and verification challenges; the [JobSpy upstream documentation](https://github.com/speedyapply/JobSpy) describes its board-specific limitations.

### Job-title language

Switching the interface language also displays translated job titles in offer cards and the application pipeline. The original title stays underneath for verification. Common recruitment titles and contract terms use a local glossary; other visible titles are translated on demand through MyMemory and cached locally. Only the public job title is sent to that service. Provider failures keep the original title visible. The source title, candidate profile, matching and application documents are unchanged. Search supports translated titles already available locally.

The French interface now translates review controls and application states. The dashboard uses a restrained warm light palette, compact controls and collapsible matching details.

### Share human-review results

On the jobs page, expand **Export for human review**. Choose either all jobs awaiting your confirmation (both recommended and uncertain AI verdicts) or the currently displayed jobs after filtering/searching. Choose standalone **HTML** for reading, printing and sharing, or **Excel (.xlsx)** for filtering and entering feedback. Then select Chinese, French, English, German, Spanish or Portuguese and generate/download the file. The recipient does not need this app or access to its local server.

Reports include original job links, AI conclusions, reasons, risks, questions to verify, available job facts and original review text. Excel adds reviewer-feedback dropdowns and editable comment columns. The export freezes the selected records when generation starts; later local changes do not silently alter the report. An exported opinion does not approve a job, submit an application or update the local database. Record final confirmations in the app.

Report headings use the selected language locally. With **Translate review text via ChatGPT** enabled, non-French exports translate titles and review text through the configured, signed-in ChatGPT browser session; original text stays available. These requests include the selected review text, not the full CV or candidate profile. Translation runs in the background with progress and cancellation, and successful translations are cached locally. Disabled, unavailable or incomplete translation keeps the original text with an explicit warning. French exports retain the original French reviews. Excel marks cells exceeding its text limit; use HTML to read those texts in full.

Private snapshots/files stay under `data/review_exports/`, and translations under `data/review_translation_cache/`; both are excluded from Git. File generation uses [Odoo's filtered, explicit-column export pattern](https://github.com/odoo/odoo/blob/19.0/addons/web/controllers/export.py), independently implemented with [XlsxWriter tables](https://xlsxwriter.readthedocs.io/worksheet.html#worksheet-add-table). HTML contains its own styles and has no scripts or local-server dependency.

**Ajouter à la file** adds an offer to the preparation list. **Préparer la suivante** prepares one application and then pauses for the candidate to inspect it; final submission remains manual. **Arrêter** cancels the current preparation cooperatively and retains the remaining queue. Failed and cancelled entries require an explicit retry. Previously prepared offers without a document audit are prepared again; complete preparations wait for review.

Choose an active CV in **Profil & préférences**. A library containing exactly one available CV also works when an imported profile has lost its selection. CV and cover-letter inputs are identified separately, so a letter upload does not receive a CV.

Pre-fill generates a French cover letter for each offer through the existing ChatGPT Web session using the selected CV, job description and profile. The profile checkbox can disable automatic generation. Expand **Lettre de motivation** on an offer to generate, read, refresh or download its PDF before filling a form. CV text and profile information are sent to the configured ChatGPT session for this feature; generated letters remain in local `data/cover_letters/` and are excluded from Git.

Start with `start.bat`, then sign in to ChatGPT in the dedicated Chrome window. The browser must expose the configured local CDP endpoint (default `127.0.0.1:9222`). PDF and DOCX CVs with readable text support generation; scanned PDFs and legacy DOC files need conversion. A generation error stops preparation before opening the application form. Missing document attachment and unanswered required fields produce a human-review state, with document details in the application audit. A generated letter is reused only while the job, profile and CV text are unchanged.

### Controlled application workflow

The queue now highlights the current job with its ID, company, actual preparation step and step-start time: browser connection, letter generation, opening the vacancy, finding its form, filling/attaching documents, checking fields and handoff. It also shows the next application requiring attention after preparation pauses. Filter queue entries by running, awaiting your intervention, failed, queued, completed or cancelled; counts remain visible independently of the selected filter. Pipeline cards show preparation failures with actionable explanations and expandable original error details. **Preparation failed** is an automation outcome, not a recruiter rejection.

**I already submitted this application** is available in failed/cancelled/queued entries, the next-action panel and pipeline cards, as well as prepared handoffs. It records your manual submission even if automation failed or you closed the browser tab, completes the queue entry and removes the job from pending intervention. Historical failures remain in the expanded preparation history. A late automation completion/error cannot overwrite a confirmed submission. Repeated confirmations preserve later recruiter stages and repair an inconsistent queue entry. **Clear completed** removes only completed queue entries; failed/cancelled jobs require explicit removal.

**Open or resume application** focuses the original tab when available. If it has been closed, it opens the public vacancy URL in the dedicated browser and explicitly reports that old unsent entries were not restored. It does not repeat filling or submit anything. **Open job in my browser** remains available if the dedicated browser is unavailable. Already-submitted/closed applications cannot be reopened through this preparation action. If already sent, use confirmation instead of sending again.

Existing-tab activation uses its recorded browser target (or an unambiguous exact URL for older preparations), preserving unsent form values. If automation is running, use **Stop before taking over**, wait for it to end, then open/resume the application. Stopping retains the tab in the dedicated browser. Inspect documents and answers, complete any missing site steps, submit manually on the site, then use **I already submitted this application**. **Requeue for preparation** only requeues an explicit retry; a preparation button starts it.

This handoff presentation applies [Prefect's contextual human-input workflow](https://docs.prefect.io/v3/advanced/interactive), informed by its [flow-run implementation](https://github.com/PrefectHQ/prefect/blob/main/src/prefect/flow_runs.py). Existing-tab activation uses [Playwright's `bring_to_front`](https://playwright.dev/python/docs/api/class-page#page-bring-to-front), preserving the prepared page. Preparation steps reflect observed worker stages rather than a simulated percentage.

The queue now separates **needs input on the recruitment site** from **prefilled, awaiting manual submission**. Each handoff shows CV/letter attachment checks, the number and labels of missing required fields when available, and an application-form link. Keep the prepared tab in the dedicated browser: opening the link in a new tab may not retain unsent form values. After submitting successfully on the recruitment site, use **I sent it on the site** to finish the local queue entry. This button only records your confirmation. Missing or unreadable audit files show an unknown state and require checking the site or preparing again.

**Add strong matches** adds eligible jobs without duplicating entries or retrying failures. **Prepare the next** retains the one-application workflow. **Prepare the batch** processes the jobs queued at the start, sequentially, retaining each successful form for manual submission. Missing input, failure or cancellation pauses the batch. New jobs added while a batch runs wait for the next start. **Retry / prepare again** explicitly requeues an entry; then choose a preparation button. Submitted and withdrawn jobs cannot be requeued or retried. Recording a submission also completes its queue entry.

This local implementation applies [Prefect's interactive workflow handoff](https://docs.prefect.io/v3/advanced/interactive) and [BullMQ's idempotent job pattern](https://docs.bullmq.io/patterns/idempotent-jobs): preparation and human submission have separate states, and retries are explicit. It does not add those systems as dependencies.

Use **Rédiger la lettre** to generate and preview the French letter and download its PDF. It uses the selected CV and the actual job/company information. The ChatGPT letter conversation remains open for inspection. **Pré-remplir** reuses a matching letter, or generates it first; it then fills contact fields and attaches CV/letter to separately identified upload controls. Hidden dropzone inputs are matched with their own nearby text. The final submit control is never clicked.

**Évaluer le poste** is a separate, optional job-fit review. Pre-fill no longer launches a review or AI navigation automatically. Advanced form navigation remains available only when `application.assisted_form_navigation` is explicitly enabled. **Passer** immediately hides the job from ordinary views and removes its pending preparation; **Ignorées → Restaurer** brings it back.

Queue entries are claimed once per explicit start, cancellation cannot be overwritten by a late completion, and failures do not advance to another application. Managed workers use UTF-8 log files, deduplicate active launches and check cancellation while waiting for ChatGPT and between application stages. Stop is cooperative: an in-flight browser navigation can take up to its bounded timeout before returning. Prepared tabs stay open for manual inspection; there is no indefinitely running submission observer. Use **Marquer envoyée** after submitting manually.

These semantics adapt the cancellation and pause patterns documented by [BullMQ](https://docs.bullmq.io/guide/workers/cancelling-jobs) and its [worker pause guide](https://docs.bullmq.io/guide/workers/pausing-queues) to the existing local Python/SQLite app. [Reactive Resume](https://github.com/reactive-resume/reactive-resume) was reviewed as a mature local/self-hosted document product; it does not replace the application's browser workflow.

Regression tests cover a GBK console, separate hidden CV/letter dropzones in a real headless browser, generation failure before form opening, single-step queues and cancellation racing with completion. Install Playwright Chromium with `python -m playwright install chromium` before running browser fixture tests.

Local-first job discovery, review, tracking and semi-automatic application assistant.

V8.2 is designed as a reusable personal automation tool rather than a script tied to one person, country or profession. Identity, availability, job targets, search campaigns, CVs, sources, reviewer policy and browser automation are editable from the local dashboard.

## V8.3 dashboard and language settings

The dashboard now has a compact job overview, clickable status metrics, clearer empty states, a horizontally scrolling application pipeline and a layout that works on smaller screens. Choose the interface language from the selector at the top of the sidebar: Chinese, French, English, German, Spanish or Portuguese. The choice is saved in this browser and applies immediately to the dashboard, including job cards and pipeline controls. Job descriptions, search terms, saved answers and other user data are never translated or changed by the switch.

The interface catalogs live in `static/locales/`. French is the fallback language if a translation key is missing. The translations were generated as a starting point and key job-search terms were reviewed manually; contributions improving phrasing are welcome.

## V8.4 structure and interface polish

V8.4 keeps the local-first workflow while introducing a clearer application boundary: validated request contracts live in `app/contracts.py`, SQL and transactions live in `app/repositories/`, and browser/reviewer side effects are coordinated in `app/services/`. The dashboard adds keyboard skip navigation, explicit live status and error states, a calmer system font stack, and a documented visual language in `DESIGN.md`. See `ARCHITECTURE.md` for the boundary map and the mature-project patterns used as references.

The repository excludes local profiles, résumés, browser sessions, job databases and audit files. Copy `profile.example.json` to `profile.json` or use the Windows launcher to create a local profile before use.

To run the tests on Windows, use `run_tests.bat`; it installs the small test dependency set before running the suite.

## V8.2 highlights

### Multi-source discovery with JobSpy

V8.2 adds an optional first-class `python-jobspy` provider. A search campaign can query selected sites such as Indeed, Google Jobs, LinkedIn or Glassdoor and feed those results into the same extraction, scoring and deduplication pipeline used by search engines, custom domains and public ATS boards.

The JobSpy call runs in a subprocess with bounded retries, so one scraper failure does not crash the local FastAPI server.

### Search campaigns

Instead of one global search definition, create multiple independent profiles from the dashboard. Each campaign can define:

- roles;
- locations;
- contract types;
- selected built-in sources;
- JobSpy sites;
- freshness/result limits;
- country for Indeed/Glassdoor;
- an optional dedicated CV.

Candidate identity, safety rules and browser settings stay global.

### Cross-source deduplication

The same opening may appear through a company ATS, a job board, JobSpy and a search engine. V8.2 adds a normalized job identity and keeps all known `source_variants` while storing one primary job record.

The dedupe scope is configurable:

- `title_company_location` — safer default;
- `title_company` — more aggressive cross-location merging.

### Application queue

Jobs can be added to a local queue and prepared sequentially. The worker launches the existing ATS/agent pre-fill pipeline, waits until a job becomes `prefilled`, `needs_human`, submitted or errors, then advances to the next queued job.

**Final submission remains manual.** Queue automation does not bypass CAPTCHA/MFA, create accounts, make legal declarations or click final Submit.

### Pipeline tracker

The dashboard now has a Pipeline view with stages:

`Saved → Queued → Prepared → Submitted → Screening → Interview → Offer`

and terminal stages `Rejected` / `Withdrawn`. Stage changes are stored as events; notes and follow-up dates are supported by the API.

### Automatic scanning

An optional local scheduler can rescan at a configurable minute interval. `0` disables scheduling. The scheduler respects the same scan lock, so overlapping scans are not started.

## Existing V7 capabilities retained

- local FastAPI dashboard;
- personal profile editor;
- multiple local CVs with tags and automatic CV routing;
- reusable non-sensitive answers;
- Scrapling static/dynamic fetching;
- Bing / DuckDuckGo discovery and arbitrary custom `site:` sources;
- public Greenhouse, Ashby and Lever board discovery;
- ATS detection and deterministic adapters;
- safe ChatGPT Web reviewer through an existing Chrome/CDP session;
- bounded agent fallback for difficult forms;
- stable DOM field IDs, custom dropdown handling and local field learnings;
- application fill audit and agent trace;
- automatic confirmation-page detection after a **manual** Submit;
- localhost-only API hardening.

## Windows quick start

Run:

```bat
run_windows.bat
```

It creates `.venv`, installs Python dependencies and Playwright Chromium, prepares Scrapling, starts a reusable debug Chrome profile, starts the local server and opens:

```text
http://127.0.0.1:8765
```

After the first install, use:

```bat
start.bat
```

Run diagnostics with:

```bat
doctor.bat
```

## Dashboard workflow

1. Open **Profil & préférences**.
2. Enter candidate identity and availability.
3. Upload one or more CVs; optionally add tags.
4. Define global targets and/or several **Profils de recherche**.
5. Select discovery sources and optional JobSpy sites.
6. Log into ChatGPT and any required job sites in the debug Chrome profile.
7. Scan the web.
8. Keep / skip jobs and run ChatGPT review where useful.
9. Add chosen jobs to **File** or pre-fill one directly.
10. Use **Pipeline & file** to prepare jobs sequentially and track outcomes.
11. Review each prepared form and submit manually.

## Search-source architecture

```text
Public ATS boards ─┐
Direct source pages├─→ normalize → dedupe/source variants → score → Inbox
JobSpy boards ─────┤
Search engines ────┤
Custom domains ────┘

Inbox → human choice / ChatGPT review → application queue
      → deterministic ATS adapter → safe agent fallback → manual Submit
      → confirmation detection → Pipeline tracker
```

## ChatGPT Web reviewer

The web reviewer is controlled through the configured Chrome/CDP session. This is browser automation over the ChatGPT web UI, not a stable OpenAI API contract, so `app/chatgpt_bridge.py` remains isolated from the rest of the system.

For difficult application forms the model returns a constrained action plan. Local policy validates every action before execution. It cannot request arbitrary JavaScript execution or final submission.

## Safety / candidate agency boundaries

The automation deliberately stops or hands off when it encounters:

- CAPTCHA or MFA;
- account creation / password setup;
- citizenship, visa or work-authorization declarations;
- health/disability and protected-personal questions;
- criminal-history questions;
- legal attestations or signatures;
- ambiguous required facts;
- the final application submission action.

## Data storage

The pre-fill action generates a job-specific letter through the connected ChatGPT
session, saves its response as a local PDF, and uploads it alongside the selected
CV. Embedded application dialogs are scanned as well as the main page. Cegid
OneClick sites expose only a CV import: the application then uploads a combined
PDF containing the original CV followed by the letter, without changing either
source file. The worker stops before final submission. A site-specific privacy
charter pauses the workflow until the user explicitly accepts for that application.

Local data is stored under `data/` and `profile.json`. CV files are placed under `data/resumes/`. Do not commit personal profile/CV/database files to a public repository.

## Dashboard states and recruiter evidence

Dashboard filters use explicit field/value comparisons, following the
[GitHub Projects filtering pattern](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/filtering-projects).
Local matching (`decision=reject`) means incompatible candidate criteria. AI
`SKIP` means a recommendation to skip. Neither is a recruiter rejection.
Expired listings use their deadline (`JobPosting.validThrough`) or an explicit
closure notice, independently of matching. A failed fetch or missing deadline
leaves availability unknown; a matching score never certifies that a listing
is still open. Expiration evidence is a snapshot: open the original listing or
scan again to check its current state.

Record recruiter responses from an email, the application portal or a phone
call using the pipeline stage selector, or “Record recruiter rejection” on a
submitted card. The application must first be confirmed submitted. A response
requires a source and a note containing the message date and confirmed result.
The dashboard stores the source, note and recording timestamp and exposes the
stage history. Old manually set stages without a source are shown as requiring
confirmation. This app does not read a mailbox or ATS account automatically.

Counters follow the same filters as cards, including text/source restrictions.
Ignoring a listing hides it from matching views but preserves submitted and
recruiter-outcome history. Saving toggles on/off. Submitted, withdrawn, rejected,
expired or ignored records cannot be prepared again; queue retries are explicit.
Pipeline “queued” and “prepared” stages require an actual queue item or completed
prefill rather than creating a fictional worker result. Manually confirming
submission in either view updates the same application state. Actions report
server failures instead of displaying a success message.

## Human confirmation after AI review

Both `APPLY` (green) and `HUMAN_REVIEW` (orange) appear in the human-confirmation
inbox until you explicitly allow preparation or decline it. The AI verdict is
preserved separately from the human decision. Confirmed and declined jobs have
their own views, and confirmation can be undone. Submitted, expired, withdrawn
and ignored jobs do not inflate the pending-confirmation counter.

“Queue confirmed jobs” selects only your confirmed, eligible jobs, including
orange recommendations you have checked. Individual preparation, enqueue,
retry, the batch worker and the application worker all enforce confirmation
for completed green/orange AI reviews. A legacy queue pauses when it reaches an
unconfirmed job. Final submission remains manual on the recruiter's website;
confirmation permits preparation only.

Confirmation is bound to the reviewed recommendation and listing content.
Rerunning AI review or changing job details invalidates an older approval, while
an unchanged scan timestamp does not. A stale browser confirmation returns a
conflict instead of approving unseen changes. Decisions are timestamped in the
tracking history. This independently implements the human-input pause pattern
from [Prefect](https://docs.prefect.io/v3/advanced/interactive) and the stale-review
principle from [GitHub](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches), without adding either as a dependency.

## Tests

```bat
run_tests.bat
```

or:

```bash
python -m unittest discover -s tests -v
```

V8.2 currently covers profile generalization, dates, ATS routing, safety barriers, public board configuration, cross-source identity, search campaigns, queue/pipeline API and analytics.

## Open-source lineage

The project intentionally learns from mature open-source job-search/application projects. Code is only adapted where an explicit compatible license was verified; architectural ideas from repositories without a confirmed license are reimplemented independently. See:

- `OPEN_SOURCE_REFERENCES.md`
- `THIRD_PARTY_NOTICES.md`
- `CHANGELOG_V8.md`
