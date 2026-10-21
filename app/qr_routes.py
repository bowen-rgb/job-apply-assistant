from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from fastapi.responses import FileResponse
from . import qr_application as qr

router=APIRouter(prefix='/api/qr')

class Selection(BaseModel):
    url:str=Field(max_length=4000)
    source_name:str=Field(default="",max_length=180)

class Analysis(BaseModel):
    language:Literal["zh","fr","en","de","es","pt"]="zh"

class Dispatch(BaseModel):
    resume_id:str=Field(max_length=80)
    company:str=Field(default='',max_length=200)
    resume_explicit:bool=True

@router.post('/{identifier}/image')
def save_image(identifier:str,image:UploadFile=File(...)):
    try:return qr.save_image(identifier,image.file.read(qr.MAX_IMAGE+1))
    except KeyError:raise HTTPException(404,'qr_not_found')
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.get('/{identifier}/image')
def get_image(identifier:str):
    try:
        qr.get_request(identifier)
        path=qr.image_path(identifier)
        if not path.is_file():raise KeyError(identifier)
        return FileResponse(path,media_type='image/png',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    except KeyError:raise HTTPException(404,'qr_not_found')

@router.post('/decode')
def decode(image:UploadFile=File(...)):
    try:return {'codes':qr.decode_image(image.file.read(qr.MAX_IMAGE+1))}
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.post('/inspect')
def inspect(payload:Selection):
    try:return qr.create_request(payload.url,payload.source_name)
    except ValueError as exc:raise HTTPException(400,str(exc))
    except (OSError,TimeoutError):raise HTTPException(422,'qr_page_unavailable')

@router.get('')
def listing():
    return qr.list_requests()

@router.delete('/{identifier}')
def remove(identifier:str):
    try:return qr.remove_request(identifier)
    except KeyError:raise HTTPException(404,'qr_not_found')
    except ValueError as exc:raise HTTPException(409,str(exc))

@router.get('/{identifier}')
def status(identifier:str):
    try:return qr.request_status(identifier)
    except KeyError:raise HTTPException(404,'qr_not_found')

@router.post('/{identifier}/analyze')
def analyze(identifier:str,payload:Analysis|None=None):
    try:return qr.analyze_request(identifier,payload.language if payload else "zh")
    except KeyError:raise HTTPException(404,'qr_not_found')
    except ValueError as exc:raise HTTPException(409,str(exc))

@router.post('/{identifier}/start')
def start(identifier:str,payload:Dispatch):
    try:return qr.start_request(identifier,payload.resume_id,payload.company)
    except KeyError:raise HTTPException(404,'qr_not_found')
    except ValueError as exc:raise HTTPException(409,str(exc))
    except (OSError,TimeoutError):raise HTTPException(422,'qr_page_unavailable')

@router.post('/{identifier}/resume')
def resume(identifier:str):
    try:return qr.resume_request(identifier)
    except KeyError:raise HTTPException(404,'qr_not_found')
    except ValueError as exc:raise HTTPException(409,str(exc))
    except (OSError,TimeoutError):raise HTTPException(422,'qr_page_unavailable')


@router.post('/{identifier}/selection')
def selection(identifier:str,payload:Dispatch):
    try:return qr.save_selection(identifier,payload.resume_id,payload.company,payload.resume_explicit)
    except KeyError:raise HTTPException(404,'qr_not_found')
    except ValueError as exc:raise HTTPException(409,str(exc))


@router.post('/{identifier}/target')
def target(identifier:str,payload:Selection):
    try:return qr.set_target(identifier,payload.url)
    except KeyError:raise HTTPException(404,'qr_not_found')
    except ValueError as exc:raise HTTPException(409,str(exc))
    except (OSError,TimeoutError):raise HTTPException(422,'qr_page_unavailable')


@router.post('/{identifier}/crawl')
def crawl(identifier:str,payload:Analysis|None=None):
    try:return qr.crawl_request(identifier,payload.language if payload else "zh")
    except KeyError:raise HTTPException(404,'qr_not_found')
    except ValueError as exc:raise HTTPException(409,str(exc))


@router.post('/{identifier}/crawl-stop')
def crawl_stop(identifier:str):
    try:return qr.stop_crawl(identifier)
    except KeyError:raise HTTPException(404,'qr_not_found')
