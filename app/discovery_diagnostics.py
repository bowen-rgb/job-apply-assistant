"""Optional event sink shared by discovery adapters; no exceptions are hidden."""
def emit(report, source, method, state, **details):
    if report is not None:
        report(source, method, state, **details)
