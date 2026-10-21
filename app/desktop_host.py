"""Desktop-owned backend: one process, graceful stop, bounded worker cleanup.

Windows job ownership ensures even a forced host termination reaps its workers.
Chrome is deliberately outside this job: closing the desk must not destroy login.
"""
import ctypes
import json
import os
import sys
import threading
from ctypes import wintypes


def own_process_tree():
    if os.name != 'nt':
        return None

    class Basic(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD),
                    ('SchedulingClass', wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('ReadOperationCount', 'WriteOperationCount',
                    'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class Extended(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', Basic), ('IoInfo', IO),
                    ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    handle = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    # Only Chrome is explicitly launched with BREAKAWAY; workers remain in the job.
    limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x800
    if not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    # Non-inheritable handle retained until this host exits. Never close it early.
    return handle


def main():
    job_handle = own_process_tree()
    import uvicorn
    from .main import app
    instance = os.environ['JAA_DESKTOP_INSTANCE']

    @app.get('/api/desktop/ready', include_in_schema=False)
    def desktop_ready():
        # Startup probe must not depend on external sites or Chrome health checks.
        return {'ready': True, 'pid': os.getpid()}

    @app.middleware('http')
    async def desktop_instance(request, call_next):
        response = await call_next(request)
        response.headers['X-JAA-Desktop-Instance'] = instance
        return response

    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1',
        port=int(os.environ.get('JAA_DESKTOP_PORT', '18765')), log_level='warning',
        access_log=False, timeout_graceful_shutdown=4))

    def control():
        for line in sys.stdin:
            if line.strip() == 'shutdown':
                break
        server.should_exit = True  # EOF also means the desktop owner disappeared.

    threading.Thread(target=control, daemon=True, name='desktop-control').start()
    print(json.dumps({'event': 'starting', 'pid': os.getpid()}), flush=True)
    server.run()
    from .worker_runtime import terminate_all
    terminate_all(timeout=3)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
