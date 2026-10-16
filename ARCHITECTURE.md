# Architecture

Job Apply Assistant is a local-first FastAPI application. The browser dashboard talks to a localhost API; discovery, scoring, review, application preparation and tracking stay in the local workspace. Final submission is manual by default. Opt-in automatic sending requires approved material versions and a complete supported form.

## Boundaries

```text
static dashboard
      ↓ validated HTTP contracts
API handlers (app/main.py)
      ↓ workflow decisions
application services (app/services/)
      ↓ SQL and transaction boundaries
repositories (app/repositories/)
      ↓
SQLite + local files + isolated browser workers
```

- `app/contracts.py` is the vocabulary shared by the API and UI: decision values, application statuses, pipeline stages and bounded request payloads.
- `app/services/` coordinates work that has side effects, such as queueing a reviewer or launching the browser pre-fill worker.
- `app/repositories/` owns SQL, ordering, mutations and transaction boundaries. This keeps SQL out of route handlers and gives the workflow a small seam for tests.
- Existing providers, ATS adapters, browser workers and ChatGPT Web integration remain isolated behind their existing modules. This preserves the local safety boundary and avoids coupling the dashboard to a vendor API.

The compatibility shell in `app/main.py` still contains the small, read-only system/profile routes. Job and application workflow routes now use the repository/service boundary. The next safe extraction point is one router per product area (`profile`, `jobs`, `pipeline`, `system`) once the API surface settles.

## Design choices from mature projects

- FastAPI's official “bigger applications” pattern recommends grouping endpoints with `APIRouter`; the current repository/service extraction is the first step toward that split: [FastAPI — Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/).
- [JobTrail](https://github.com/kaylaehman/jobtrail) is an MIT-licensed self-hosted tracker with explicit jobs, applications, rounds and status history. Its NestJS/React/PostgreSQL stack does not fit this local Python tool, so only the domain ideas were adopted: a separate application history, pipeline stages and event records.
- [JobSpy](https://github.com/speedyapply/JobSpy) is an MIT-licensed provider already integrated as an optional discovery source. Its scraper code is not copied into the application core.

No source repository was forked into this project because the closest mature tracker used a different runtime and deployment model. Reusing its concepts keeps the project maintainable and preserves its existing Windows/local-first workflow.

## Safety boundary

Browser workers may discover, review and pre-fill. They stop at CAPTCHA/MFA, account creation and unanswered sensitive or legal questions. The assisted navigation agent cannot click final Submit. The separate bounded sender can do so only with explicit opt-in, human-approved document versions and complete form checks.

`app/application_safety.py` owns material snapshots, approvals and submission evidence. Before filling, the worker copies the actual document bytes into candidate-owned `material_versions/`. Its approval token binds these hashes, inline letter text, listing/review context and the saved profile. Both approval and the final click recheck the current files and context. Combined PDFs use a verified content cache so an unchanged preparation preserves the reviewed bytes.

The final-click hook commits a unique per-job `submission_attempts` record before clicking. Any attempt, including an interrupted one, blocks automatic redispatch independently of the dashboard status. A post-click confirmation must contain observed success text; a URL hint alone is insufficient. Its receipt stores that text, URL, time, attempt and material token, with a hash anchored in SQLite. Only this receipt path can write `submitted_verified`; generic status endpoints and the worker status helper reject it. Missing or altered receipts cause the UI to show evidence requiring verification, including historical records created before this mechanism existed. These are local integrity checks, not a cryptographic attestation by the recruiter.

Additive SQLite migrations preserve existing jobs. All snapshots, approvals, attempts and receipts follow the active candidate's data directory/database. Material downloads resolve only sealed, hash-checked versions; the browser cannot request arbitrary file paths. Audit files and agent traces are also served only after path validation under the local data directory.
