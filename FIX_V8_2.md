# V8.2 Windows dependency resolver fix

V8.1 installed `scrapling[all]` in the same pip transaction as the rest of the application. The `all` extra also pulls optional MCP/shell dependencies that the runtime does not need, and on some Windows/Python 3.12 setups pip 26 can end with `resolution-too-deep` while backtracking through Click and related packages.

V8.2 changes setup as follows:

1. installs a small, pinned core dependency set first;
2. installs JobSpy in its own transaction;
3. installs only `scrapling[fetchers]==0.4.15` instead of `scrapling[all]`;
4. pins Click 8.3.0 so pip does not backtrack through Click 7.x;
5. installs Playwright Chromium after dependency resolution;
6. treats Scrapling's extra browser-component installer as optional, because JobSpy + HTTP fetching + Chrome/CDP remain usable if that optional step fails.

No profile or application data format changed between V8.1 and V8.2.
