
## Windows V8.2 dependency fix

If V8.1 stopped with `error: resolution-too-deep`, use V8.2. The installer now installs core, JobSpy, and Scrapling in separate steps and uses `scrapling[fetchers]` rather than the much larger optional `scrapling[all]` dependency graph. See `FIX_V8_2.md`.

# Job Apply Assistant V8.4

## Application documents and queue fixes

### Job-title language

Switching the interface language also displays translated job titles in offer cards and the application pipeline. The original title stays underneath for verification. Common recruitment titles and contract terms use a local glossary; other visible titles are translated on demand through MyMemory and cached locally. Only the public job title is sent to that service. Provider failures keep the original title visible. The source title, candidate profile, matching and application documents are unchanged. Search supports translated titles already available locally.

The French interface now translates review controls and application states. The dashboard uses a restrained warm light palette, compact controls and collapsible matching details.

**Ajouter à la file** adds an offer to the preparation list. **Préparer la suivante** prepares one application and then pauses for the candidate to inspect it; final submission remains manual. **Arrêter** cancels the current preparation cooperatively and retains the remaining queue. Failed and cancelled entries require an explicit retry. Previously prepared offers without a document audit are prepared again; complete preparations wait for review.

Choose an active CV in **Profil & préférences**. A library containing exactly one available CV also works when an imported profile has lost its selection. CV and cover-letter inputs are identified separately, so a letter upload does not receive a CV.

Pre-fill generates a French cover letter for each offer through the existing ChatGPT Web session using the selected CV, job description and profile. The profile checkbox can disable automatic generation. Expand **Lettre de motivation** on an offer to generate, read, refresh or download its PDF before filling a form. CV text and profile information are sent to the configured ChatGPT session for this feature; generated letters remain in local `data/cover_letters/` and are excluded from Git.

Start with `start.bat`, then sign in to ChatGPT in the dedicated Chrome window. The browser must expose the configured local CDP endpoint (default `127.0.0.1:9222`). PDF and DOCX CVs with readable text support generation; scanned PDFs and legacy DOC files need conversion. A generation error stops preparation before opening the application form. Missing document attachment and unanswered required fields produce a human-review state, with document details in the application audit. A generated letter is reused only while the job, profile and CV text are unchanged.

### Controlled application workflow

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

Local data is stored under `data/` and `profile.json`. CV files are placed under `data/resumes/`. Do not commit personal profile/CV/database files to a public repository.

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
