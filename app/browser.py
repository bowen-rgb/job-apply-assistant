from .worker_runtime import launch

def launch_apply(job_id: int, *, privacy_confirmed: bool = False):
    return launch('app.apply_worker', job_id, *(['--privacy-confirmed'] if privacy_confirmed else []))
