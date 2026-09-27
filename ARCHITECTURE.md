# Architecture

Job Apply Assistant is a local-first FastAPI application. The browser dashboard talks to a localhost API; discovery, scoring, review, application preparation and tracking stay in the local workspace. The final application submission remains a human action.

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

Browser workers may discover, review and pre-fill. They stop at CAPTCHA/MFA, account creation, sensitive or legal questions and final Submit. Audit files and agent traces are stored locally and are served only after path validation under the local data directory.
