# Repository homepage design

The README is a product introduction and a route into the documentation. It should answer what the application does, what a new user needs, and where to go next before showing implementation history.

## References reviewed

The following official repository introductions were reviewed on 2026-10-16. They inform the information hierarchy; no source artwork or introduction text was copied.

- [Reactive Resume](https://github.com/reactive-resume/reactive-resume): a concise product description, capabilities grouped by user activity, followed by setup and documentation.
- [AppFlowy](https://github.com/AppFlowy-IO/AppFlowy): a recognizable product introduction with direct installation and documentation routes.
- [Supabase](https://github.com/supabase/supabase): a short project identity, capability overview and clear documentation entry points.

## Decisions for this project

- Keep English and Chinese as separate, equivalent introductions, with a language switch near the title.
- Lead with an original vector cover, one description and four navigation links. Use only a few factual badges; do not imply an existing CI pipeline or an unverified project license.
- Group capabilities by what a candidate does: discover, prepare, review and follow up.
- Put Windows installation before technical details. Keep manual setup and the long screenshot behind GitHub-supported disclosure controls.
- Preserve the original accumulated README in an explicitly labeled archive. Existing guide filenames remain stable.
- State data transfers and automation boundaries accurately. Local storage is distinct from offline operation; optional automatic sending is distinct from the default manual path.

## Assets and provenance

- `assets/hero.svg` is an original, self-contained illustration. Its paper, cobalt, green and lime palette follows the application's existing visual language. It uses system fonts, has accessible title/description elements and contains no external assets or scripts.
- `assets/dashboard-en.png` and `assets/dashboard-zh.png` are full-page captures of the running application in its compact layout, using an empty local workspace. They show real zero counts and setup prompts, with no fabricated application history or personal documents.
- Third-party presentation patterns are references, not implementation dependencies or endorsements.

## Keeping it tidy

Put release-by-release changes in the changelog or a focused guide. Update the homepage when the primary product description, supported setup or feature boundaries change. Keep both language versions aligned and check local links whenever documents move.
