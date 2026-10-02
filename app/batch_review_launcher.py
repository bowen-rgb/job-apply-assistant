from .worker_runtime import launch

def launch_batch_review(mode: str = 'strong'):
    return launch('app.batch_review_worker', mode)
