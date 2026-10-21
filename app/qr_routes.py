from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel, Field
from . import qr_application as qr

router=APIRouter(prefix='/api/qr')

class Selection(BaseModel):
    url:str=Field(max_length=4000)
    source_name:str=Field(default="",max_length=180)

class Dispatch(BaseModel):
    resume_id:str=Field(max_length=80)
    company:str=Field(default='',max_length=200)
    resume_explicit:bool=True

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
def analyze(identifier:str):
    try:return qr.analyze_request(identifier)
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
