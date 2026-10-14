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
## Video study and graphic composition pass — 2026-10-15

The following user-provided Bilibili videos were opened in Edge. Playback frames were sampled, including process and finished-composition frames. This is a visual reference study, **not a claim of complete viewing or a full transcript**. The local Bilibili RAG service was unavailable; Agent Reach was not installed and OpenCLI's browser bridge was disconnected. The browser could nevertheless play the videos after loading.

| Reference | Observations from sampled frames / visible description | Applied to the product |
| --- | --- | --- |
| [机械生命·安卓心](https://www.bilibili.com/video/BV1vkLu68EQe/) — 圆形的石墩 | Monochrome subject, cobalt diagonal shapes, orbital curves, dense texture. Description names ibis Paint X. | An original application-document illustration, with a diagonal colour strip and fine radial structure. |
| [如何学习优秀的视觉设计？](https://www.bilibili.com/video/BV1wiL36GEb8/) — LensTM | Sampled intro, character-design, hazard-stripe and assets/resources segments. Large type overlaps quieter secondary type; strong differences in scale; distinct focal regions. | Layered heading typography and a clear dominant metric rather than four identical visual weights. No claim of extracting all spoken recommendations. |
| [0基础尝试平面构成的一点过程分享](https://www.bilibili.com/video/BV1Gtao6AE45/) — 耶咦是月亮呐- | Sampled construction and finished frames: offset circular frame, thin diagonal guides, monochrome landscape/figure collage and a restrained blue accent. Description names Photoshop. | Asymmetric illustration placement, overlapping line work and a deliberate quiet area reserved for functional text. |
| [一些预制图形的快速生成演示](https://www.bilibili.com/video/BV1Wmp96JEdJ/) — 拉乎 | Sampled grid and radial-shape generation. Description provides rahoo.online and a second part for dot/square-grid updates. | Reusable vector geometry and local, resolution-independent assets. |
| [字体设计/logo设计辅助工具+等高线生成器](https://www.bilibili.com/video/BV1csH96GErh/) — 拉乎 | Sampled click-to-add/remove polygon marks, dot-matrix and contour-generation frames. | Simple geometric brand cuts and a fine contour-like line layer, rather than another full-page grid. |

The live [rahoo.online](https://rahoo.online/) **素材生成** panel was inspected directly. It exposes concentric circles, halftone dots, HUD lines, tick circles, barcodes, waves, repeated lines, dot matrices, polygon grids, contours, common shapes, nested polygons, globe grids, square grids and rays. Circle controls include count/radii/stroke widths/angles/line style/colour, with SVG export and image-save controls.

This revision uses the reusable-vector approach with an **original local SVG**, `static/artwork/application-orbit.svg`, built from circles, ticks, curves, dot/stripe patterns and an application-document motif. No external generator code, video frame, game character, font file or remote runtime was copied into the application. The generator was inspected as a tool reference; the project does not depend on it or require an account.

Composition changes: cobalt/neutral palette with lime reserved for prominent actions, layered display typography, asymmetric header illustration, a dominant first metric, angular cuts, local dot texture, controlled fine lines and quiet data regions. Decoration is hidden from assistive technology, does not intercept input and cannot be mistaken for a real progress gauge. Real chart values, profile ownership and submission semantics remain unchanged. Reduced-motion handling and mobile layouts remain in place.


## Whole-site surface coverage — 2026-10-15

`static/surfaces.css` is loaded after the dashboard, guide, account and personal-task styles, so dynamically opened panels share one palette and control language. `static/surfaces.js` stamps each main view and application dialog, maintains profile-section jump buttons and groups the five account-dialog sections. It moves existing DOM nodes rather than recreating form controls, preserving input values and action handlers. Keyboard jumps focus the destination heading; motion respects the reduced-motion preference. Locale changes update section names.

| Surface | Coverage |
| --- | --- |
| Job discovery | Heading, metric filters, search/source toolbar, cards, matching evidence, AI/human review panels, letters, scan/source diagnostics, empty and failed states |
| Personal profile | Heading, section navigation, identity/contact/education/availability/preferences forms, search campaigns, sources, browser/agent settings, resume library, reusable answers and save/import/export controls |
| Pipeline and queue | Heading, analytics, queue controls, current/next task, takeover and manual-submission controls, queue filters, failed preparation details, per-item actions, tracking board and event history |
| Beginner flow | Heading, readiness, manual/assisted/sent paths, one-action coach, worked example, file upload, practice/more/help disclosures and guide print styles |
| Profiles and accounts dialog | Sticky heading, five section jumps, profile cards/create form, per-site saved accounts, expandable account editor, password states, automation options, Gmail configuration/connection controls |
| Personal tasks dialog | Sticky heading, owner title, pending/completed filters, bulk queue action, task cards, links and queue/status controls |
| Separate pages | Gmail setup guide and callback use `connection.css`; portable HTML review report has embedded matching colours and retains its self-contained print layout |

Native browser confirmation prompts retain browser-managed appearance and their existing confirmation semantics. No sign-in, submission, deletion or background task is triggered by the new visual or section-navigation code.

Browser checks open every main view, both dialogs, an expanded account editor and preparation-error detail, and the separate Gmail guide. Screenshots use labelled example data and are saved under ignored `data/surface-previews/`. Checks cover 320/768/1440px overflow, profile inputs surviving section jumps, keyboard destination focus, dialog labelling, six-language headings and no state-changing API requests from navigation. Queue's untranslated `Tout` option now has a translation in all six catalogs.
