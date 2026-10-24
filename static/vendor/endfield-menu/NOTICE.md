# Endfield menu source and changes

Upstream: https://github.com/ccdr4gon/endfield_menu
Pinned revision: 8d3f3ae592c9573da888599fb4e1b9804f0e2e36
License: GNU GPL v3.0 or later (LICENSE included).

The GPL menu component is retained as a separately served document with source in this directory. Modified files carry SPDX notices. Its DOM event navigation is connected to the host through a bounded postMessage interface. This notice does not change the license of other application files.

Changes: real page navigation; localized labels and candidate summary; existing local Angelina images; no external fonts or requests; explicit open/pause lifecycle; native host navigation on narrow screens; source arrays connected to the host page registry.

Not imported: button-art.js, backdrop-field.js, card-contours.js, which upstream explicitly excludes from its license. Menu illustrations use the application's existing user-provided Angelina assets. No game currencies, UID, level, news or fake latency are displayed.
