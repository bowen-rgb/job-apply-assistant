"""Console-free dashboard backend with local-file stop control and owned workers."""
import os
from pathlib import Path
import threading
import time

from .process_ownership import own_process_tree


def main():
    ownership = own_process_tree()
    import uvicorn
    from .main import app
    from .worker_runtime import terminate_all
    control = Path(os.environ['JAA_DASHBOARD_CONTROL'])
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=int(os.environ.get('JAA_DASHBOARD_PORT','8765')),
                                         access_log=False, log_level='warning', timeout_graceful_shutdown=4))
    def watch():
        while not server.should_exit:
            if control.exists():
                server.should_exit = True
                return
            time.sleep(.25)
    threading.Thread(target=watch, daemon=True, name='dashboard-stop').start()
    try:
        server.run()
    finally:
        terminate_all(timeout=4)
        control.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
