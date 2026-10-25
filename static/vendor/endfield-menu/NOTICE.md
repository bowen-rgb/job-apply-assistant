# Endfield menu source and changes

Upstream: https://github.com/ccdr4gon/endfield_menu
Pinned revision: 8d3f3ae592c9573da888599fb4e1b9804f0e2e36
License: GNU GPL v3.0 or later (LICENSE included).

The GPL menu component is retained as a separately served document with source in this directory. Modified files carry SPDX notices. Its DOM event navigation is connected to the host through a bounded postMessage interface. This notice does not change the license of other application files.

Changes: real page navigation; localized labels and candidate summary; existing local Angelina images; no external fonts or automatic external requests; explicit open/pause lifecycle; native host navigation on narrow screens; source arrays connected to the host page registry. Local clock and music playback are included. Only an explicit location request loads the OpenStreetMap embed; Google Maps is an optional outbound link. Music and coordinates are not uploaded to the application backend.

Not imported: button-art.js, backdrop-field.js, card-contours.js, which upstream explicitly excludes from its license. Menu illustrations use the application's existing user-provided Angelina assets. No game currencies, UID, level, news or fake latency are displayed.

2026-10-25 visual revision restores the upstream charcoal/yellow/orange palette and fits translated SVG labels to measured glyph bounds. Official Endfield background imagery is referenced from the host's artwork/endfield directory; it has its own source/rights notice there and is not licensed under this component's GPL.
