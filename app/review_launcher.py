from .worker_runtime import launch

def launch_review(job_id: int, snapshot_path: str | None = None):
    return launch('app.review_worker', job_id, *([str(snapshot_path)] if snapshot_path else []))
