from .worker_runtime import launch

def launch_apply(job_id: int, *, privacy_confirmed: bool = False, qr_request_id: str = '', civility: str = ''):
    from .browser_control import require_connection
    require_connection()
    args = ['--privacy-confirmed'] if privacy_confirmed else []
    if civility:
        if civility not in {'Monsieur','Madame'}:raise ValueError('Invalid confirmed civility')
        args += ['--civility',civility]
    if qr_request_id:
        import re
        if not re.fullmatch('[0-9a-f]{32}',qr_request_id):raise ValueError('Invalid QR request')
        from .qr_application import ensure_application_window
        ensure_application_window(qr_request_id)
        args += ['--qr-request',qr_request_id]
    return launch('app.apply_worker', job_id, *args)
