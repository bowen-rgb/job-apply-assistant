"""Windows-user encrypted local secrets. Passwords never enter profile exports."""
import ctypes
import json
import sys
from ctypes import wintypes
from filelock import FileLock
from .workspaces import data_dir


class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(value, decrypt=False):
    if sys.platform!='win32':raise RuntimeError('Credential storage requires Windows DPAPI')
    raw=ctypes.create_string_buffer(value)
    source=Blob(len(value),ctypes.cast(raw,ctypes.POINTER(ctypes.c_ubyte)))
    output=Blob()
    api=ctypes.WinDLL('crypt32',use_last_error=True)
    method=api.CryptUnprotectData if decrypt else api.CryptProtectData
    method.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    method.restype=wintypes.BOOL
    if not method(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):
        raise RuntimeError('Local credential encryption unavailable')
    try:return ctypes.string_at(output.data,output.size)
    finally:
        free=ctypes.WinDLL('kernel32').LocalFree
        free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p
        free(output.data)


def read():
    path=data_dir()/'secrets.dpapi'
    if not path.exists():return {}
    return json.loads(_crypt(path.read_bytes(),True))


def update(callback):
    folder=data_dir();folder.mkdir(parents=True,exist_ok=True)
    with FileLock(str(folder/'secrets.lock')):
        data=read();result=callback(data)
        encrypted=_crypt(json.dumps(data,ensure_ascii=False).encode('utf-8'))
        path=folder/'secrets.dpapi';tmp=path.with_suffix('.tmp');tmp.write_bytes(encrypted);tmp.replace(path)
        return result
