from .worker_runtime import launch

def launch_apply(job_id: int):
    return launch('app.apply_worker', job_id)
