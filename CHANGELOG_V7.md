# V7 changes

- Added a bounded ChatGPT Web planning/execution loop for complex application forms.
- Added stable live-form IDs and privacy-reduced form snapshots.
- Added local hard policy for Submit, account/login, CAPTCHA/MFA, sensitive/protected and legal/work-authorization fields.
- Added SQLite field/dropdown learning with success/failure weighting.
- Added public Greenhouse, Ashby and Lever board discovery for explicitly configured company boards.
- Added arbitrary custom recruitment domains to the dashboard (`Name | domain.com`).
- Removed the hard-coded French search-engine locale; locale is now optional/configurable.
- Generalized query wording to include job/careers/emploi terminology.
- Preserves search-engine evidence when a job page is login-protected or scraper-blocked (`fetch_mode=search-snippet`).
- LinkedIn job URLs are no longer discarded at discovery time; inaccessible pages stay marked unverified until opened in the signed-in browser.
- Added agent controls, board/source settings, agent trace links and learning stats to the local dashboard.
- Added shared ChatGPT Web lock/bridge for reviewer and form planner workers.
- Hardened the deterministic entry-button logic so it does not treat final-submit wording as an Apply-page navigation button.
- Unified sensitive/legal detection between deterministic and agentic filling.
- Added `doctor.py` / `doctor.bat`.
- Added third-party MIT attribution for adapted/reimplemented `devdattatalele/auto-apply` patterns.
- Expanded automated tests from V6 to 19 core/API/agent tests.
