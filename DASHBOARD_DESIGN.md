# Dashboard and personal tasks

The sidebar **Dashboard / 工作台** opens the overview. The beginner guide remains available. The profile dropdown controls every API request and data snapshot.

- First level: visible jobs, pending human confirmation, active queue records, recorded submissions. These use the same `matchFilter` predicates as the job cards, rather than another interpretation of job status. All saved jobs is shown separately.
- Next step: missing CV, personal tasks, application queue and beginner guidance. No action starts a scan or sends an application implicitly.
- Charts: daily first-save counts (7/30 days), source counts excluding skipped jobs, and queue counts. Source bars and metrics open corresponding job filters. Queue bars open the queue with per-record explanations and takeover controls. Queue errors are preparation errors, never recruiter rejections.
- Overview requests a fresh owner-scoped snapshot every 6 seconds while visible. Background tabs pause polling. Manual refresh is available. Failed requests preserve the last successful snapshot with a disconnected label. Before the first success, counts are unknown, not zero. Requests time out after 10 seconds and never overlap.
- Daily discovery uses first_seen_at, falling back to discovered_at. SQLite timestamps are interpreted as UTC; day boundaries use the viewer's local timezone. Unknown timestamps are excluded. This is not an application or response trend.
- Every chart has a readable data table. Values remain visible without hover. Buttons work with the keyboard, focus and expanded tables survive refresh, and animations respect reduced-motion preferences. Six interface languages and 320px/mobile/desktop layouts are covered by browser tests.

Personal tasks: pending vacancies expose **Add to queue**, with a bulk button for pending vacancies only. Import reuses the exact job URL and existing queue row. Contact leads and materials cannot enter the application queue. Already submitted/closed jobs are blocked. Import does not invent a successful review, start a worker or submit. Existing failed/cancelled queue entries remain visible for explicit recovery rather than silently resetting attempts.

The visual design uses an original industrial composition: dark navigation, off-white grid surfaces, square panels, small indices, restrained lime highlights and clear text hierarchy. No game assets are copied. Reference is stylistic, not an imported game UI.

Design references consulted 2026-10-15:
- IBM Carbon visualization overview: https://www.carbondesignsystem.com/building-blocks/data-visualization/overview
- USWDS visualization guidance (simple familiar charts, clear text, equivalent tabular data): https://designsystem.digital.gov/components/data-visualizations/
- Official Arknights: Endfield visual reference: https://endfield.gryphline.com/en-us

Validation: browser coverage for snapshot changes, disconnected-state retention, chart periods, source navigation, all six languages, responsive overflow and no JavaScript errors; backend coverage for task ownership, queue idempotency, sent-job protection and contact/material exclusion.
