from .worker_runtime import launch

def launch_apply(job_id: int, *, privacy_confirmed: bool = False, qr_request_id: str = ''):
    from .browser_control import require_connection
    require_connection()
    args = ['--privacy-confirmed'] if privacy_confirmed else []
    if qr_request_id:
        import re
        if not re.fullmatch('[0-9a-f]{32}',qr_request_id):raise ValueError('Invalid QR request')
        args += ['--qr-request',qr_request_id]
    return launch('app.apply_worker', job_id, *args)
