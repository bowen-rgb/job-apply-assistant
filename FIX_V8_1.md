# V8.1 Windows bootstrap fix

This patch fixes the Windows setup path that could keep using a different/global Python when `.venv` existed but was incomplete.

- validates `.venv\\Scripts\\python.exe` instead of only the `.venv` folder;
- recreates an incomplete venv automatically;
- uses the venv interpreter for pip and Playwright, so PATH is irrelevant;
- calls Scrapling installer through Python rather than depending on `scrapling.exe` being on PATH;
- installs `scrapling[all]` because V8 uses browser/fetcher plus AI/MCP features;
- quotes Windows paths consistently.
