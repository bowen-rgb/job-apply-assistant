# Dashboard design system

## Product read

This is an **operate** dashboard: a calm local control room for finding, reviewing and tracking job applications. The primary jobs are scanning, filtering, deciding, queueing and moving a candidate through the pipeline. The interface should feel focused and dependable while remaining dense enough for daily use.

## Visual direction

- **Shape:** one coherent language. Cards and settings panels use a 12–16px radius; controls use 8–10px; pills are reserved for status and compact labels.
- **Color:** the dark blue surface is the workspace; aqua is the single action accent; green, amber and red communicate success, attention and blocked states. Decorative gradients stay quiet and never compete with job titles or actions.
- **Typography:** use the system UI stack for fast local rendering and multilingual coverage. Headings are compact with negative tracking; body text stays readable at 13–14px; counts use tabular numerals where available.
- **Density:** compact cards and a horizontal pipeline support an operator scanning many openings. Spacing still increases at the mobile breakpoint so touch targets remain comfortable.
- **Motion:** short hover/focus transitions only. `prefers-reduced-motion` disables movement.

## Interaction rules

- Every request has a visible loading, success, error or empty state.
- Keyboard focus uses a high-contrast outline; controls must remain usable without a pointer.
- The language selector changes interface copy only. Job descriptions, search terms, saved answers and profile data are user data and stay untouched.
- Reviewer and browser actions surface their current state in the page status area. Final Submit is always a manual action.
- Mobile layouts stack controls and keep the pipeline horizontally scrollable rather than shrinking text below a comfortable size.

## Reference implementation

The tokens and dashboard-specific overrides live in `static/style.css` and `static/dashboard.css`. Locale dictionaries live in `static/locales/`; `static/locale.js` applies them without translating user data. New screens should reuse the existing metric, settings-card, status, empty-state and pipeline classes before adding a new visual treatment.
