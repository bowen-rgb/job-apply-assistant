# V8.4 — structure and dashboard craft

## Product

- Added `DESIGN.md` with the dashboard mode, shape, color, density, motion and state rules used by the UI.
- Added keyboard skip navigation, semantic navigation landmarks and polite live regions for the main status areas.
- Added a visible error state when the local job API cannot be reached.
- Preserved the six-language switcher: 中文、Français、English、Deutsch、Español、Português.

## Code structure

- Added bounded Pydantic contracts for decisions, queue payloads, application statuses and pipeline stages.
- Added `JobRepository` for job/application SQL and `ApplicationService` for reviewer/browser workflow side effects.
- Moved analytics and clear-data mutations behind the repository while preserving the existing API paths.
- Added architecture and contract tests.

## References

The refactor follows FastAPI's modular application guidance and borrows the domain ideas of MIT-licensed JobTrail (applications, stages and history) without copying its incompatible NestJS/React/PostgreSQL implementation. JobSpy remains an optional MIT-licensed provider.
