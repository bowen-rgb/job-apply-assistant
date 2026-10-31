# Review actions and connection recovery

The Dashboard review flow lives in these modules:

| Responsibility | Files |
| --- | --- |
| Browser response detection, bounded waiting and retry | `app/chatgpt_bridge.py` |
| Batch selection, saved progress and preparation queue admission | `app/match_review.py` |
| Questions, user-confirmed facts and action counts | `app/review_gaps.py` |
| Exclusive workflow stage totals | `app/review_inventory.py` |
| HTTP endpoints | `app/main.py` |
| Dashboard action buttons and clarification dialog | `static/match-automation.js`, `static/review-gaps.js` |

## Separate action counts

`GET /api/matches/gaps` and `GET /api/matches/automation` expose `actions`:

- `personal_input`: jobs with unanswered blocking candidate questions.
- `public_research`: jobs with blocking questions about public posting details.
- `rereview`: jobs whose personal questions have been answered, or whose evaluation/legacy response needs another review.

Each action contains unique `job_ids` and a `count`. Mixed questions may put a job in more than one action. These action counts are not the mutually exclusive workflow inventory totals. Queued, submitted, inactive and currently processing jobs cannot be selected for another action.

The `research` and `rereview` POST modes target their corresponding sets, and do not expand into initial reviews. `strong` skips unresolved personal/public-only gaps, while retaining initial reviews and error recovery. Legacy `clarify` remains available for already-open older Dashboard tabs.

Candidate-only blockers do not trigger an identical second model call. Candidate facts still come from explicitly saved answers; public research cannot supply personal claims or consent.

## Live linkage and cumulative totals

The automation status endpoint reads stage inventory, action targets and the complete clarification dialog data in one SQLite read transaction. The Dashboard applies this shared snapshot to the counters and any open dialog every two seconds. Changed snapshots also refresh the job list and an already-open application queue; slow detail requests are coalesced separately so they cannot block subsequent counter updates. Saving a candidate answer requests the next shared snapshot immediately, while preserving other unsaved answer drafts.

`inventory.cumulative.reviewed` counts unique jobs with a completed review in the current candidate workspace, including jobs later rescored out of the strong-match selection. It comes from review evidence in the database, not the latest batch progress file. Re-reviewing a job, changing batch modes or restarting the backend does not reset or double-count it. Clicking the cumulative counter selects those same job IDs.

Batch progress is separately labeled as the current batch, with its remaining count including the job currently being reviewed. Action buttons count outstanding questions, not batch tasks remaining. Strong-match stage counts retain their explicitly labeled scope; the full queue button shows all queue records, including other match levels. Successful automatic review is verified against the existing authorization token and admitted to the preparation queue by the batch worker; incomplete reviews are not treated as approvals.

If a host exits after approval but before queue admission, its orphaned running state is treated as interrupted on resume. Saved targets are retained, allowing an unchanged, authorized approval to complete its queue handoff without another model request.

## Response recovery

The original fixed response timeout could expire while ChatGPT was still generating. Visible generation or changed response text now extends the idle deadline, up to three configured response windows per attempt. Waiting remains cooperative with Stop. A response timeout or visible response-loading error permits one retry in a fresh worker-owned chat tab. No recruiter tab or shared browser context is reloaded or closed. If the retry fails, the batch pauses with saved progress and diagnostic evidence.

This bounds local recovery; it does not guarantee ChatGPT network availability, login validity or a usable model response.

## Verification

Run with the project's virtual environment:

```powershell
.venv\Scripts\python.exe -X utf8 -m unittest tests.test_review_reliability tests.test_match_review tests.test_review_gaps tests.test_chatgpt_bridge tests.test_match_automation_ui -v
```

The regressions use isolated databases and mocked browser responses. Dashboard click checks verify separate counts and request modes without reviewing or submitting real applications.
