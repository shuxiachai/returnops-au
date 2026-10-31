"""The seven frozen customer routes; trusted composition, bounded input, safe JSON.

register_customer_case_list adds GET /v1/cases outside contract v1 (31 October 2026).
"""
from __future__ import annotations
import json
import asyncio
import re
from decimal import Decimal,InvalidOperation
from fastapi import Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from returnops_domain.audit import identifier
from returnops_domain.customer_service import CustomerFlow
from returnops_domain.errors import FlowError
from returnops_domain.evidence_validation import validate_evidence
from returnops_domain.wire import decode_json_document,normalize_json_numbers,validate
from .customer_authority import CurrentRequestAuthority
from .customer_upload import read_upload

# A query integer must be written as a JSON number literal (RFC 8259): no '_', '+', spaces or
# non-ASCII digits. Integral exponent or fraction forms such as 1e0 and 1.0 stay accepted, as before.
JSON_NUMBER=re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?',re.ASCII)

# Twenty 12,000-codepoint answers can require about 2.9 MiB when
# astral characters use standard ASCII JSON surrogate-pair escapes.
MAX_JSON_BYTES=4*1024*1024

def safe_json(body,status=200,*,correlation):
    return Response(json.dumps(body,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('ascii'),
        status_code=status,media_type='application/json',headers={'X-Correlation-ID':correlation,'Cache-Control':'no-store'})

def one_header(request,name,*,required=False):
    values=request.headers.getlist(name)
    if len(values)>1 or (required and len(values)!=1):
        raise FlowError('UNAUTHENTICATED' if name=='authorization' else 'VALIDATION_ERROR')
    return values[0] if values else None

def _flow(request):
    config=request.app.state.auth_config
    if config is None: raise FlowError('INTERNAL_ERROR')
    auth=one_header(request,'authorization')
    return CustomerFlow(request.app.state.engine,CurrentRequestAuthority(config,auth))

def _query(request,history=False):
    result={}
    for key,value in request.query_params.multi_items():
        if not history or key not in {'kind','cursor','limit','object_id','object_version'} or key in result:
            raise FlowError('VALIDATION_ERROR')
        if key in {'limit','object_version'}:
            failed=False
            try:
                if len(value)>64 or not JSON_NUMBER.fullmatch(value): raise ValueError()
                number=Decimal(value)
                value=normalize_json_numbers(number)
            except (InvalidOperation,ValueError): failed=True
            if failed: raise FlowError('VALIDATION_ERROR') from None
        result[key]=value
    return result

async def _json_body(request):
    content_type=one_header(request,'content-type',required=True)
    if content_type.split(';',1)[0].strip().lower()!='application/json': raise FlowError('VALIDATION_ERROR')
    body=bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk)>MAX_JSON_BYTES: raise FlowError('VALIDATION_ERROR')
        body.extend(chunk)
    return decode_json_document(bytes(body))

def register_customer_routes(app):
    async def dispatch(request,operation,resource_id=None):
        correlation=identifier('corr');failure=None
        try:
            flow=_flow(request)
            # Authenticate before reading any body or running an expensive parser.
            await run_in_threadpool(flow.preflight,operation,resource_id)
            query=_query(request,operation=='listCustomerCaseHistory')
            if operation=='getSession': result=await run_in_threadpool(flow.session)
            elif operation=='getCustomerCase': result=await run_in_threadpool(flow.get_case,resource_id)
            elif operation=='listCustomerCaseHistory': result=await run_in_threadpool(flow.history,resource_id,query)
            elif operation=='getEvidenceContent':
                result=await run_in_threadpool(flow.download,resource_id)
                content,media=result.body
                return Response(content,media_type=media,headers={'X-Correlation-ID':correlation,'Cache-Control':'no-store',
                    'X-Content-Type-Options':'nosniff','Content-Disposition':'attachment'})
            else:
                key=one_header(request,'idempotency-key',required=True);validate('IdempotencyKey',key)
                if operation=='stageEvidence':
                    slots=request.app.state.upload_slots
                    if not slots.acquire(blocking=False): raise FlowError('INTERNAL_ERROR')
                    try:
                        # Bound slow upload lifetime as well as actual bytes. The
                        # permit covers parsing/staging; no unbounded wait queue.
                        async with asyncio.timeout(30): upload=await read_upload(request)
                        material=await run_in_threadpool(validate_evidence,upload.content,upload.filename,upload.media_type,upload.description)
                        result=await run_in_threadpool(flow.stage,material,key,correlation)
                    finally: slots.release()
                else:
                    value=await _json_body(request)
                    if operation=='createCase': result=await run_in_threadpool(flow.create,value,key,correlation)
                    else: result=await run_in_threadpool(flow.clarify,resource_id,value,key,correlation)
                if operation in {'createCase','submitClarification'} and not result.replayed and request.app.state.intake_worker is not None:
                    request.app.state.intake_worker.wake()
            return safe_json(result.body,result.status,correlation=correlation)
        except FlowError as error: failure=(error.status,error.envelope(correlation))
        except Exception: failure=(503,FlowError().envelope(correlation))
        # No original exception chaining/logging or FastAPI validation repr.
        return safe_json(failure[1],failure[0],correlation=correlation)

    @app.get('/v1/session')
    async def session(request:Request): return await dispatch(request,'getSession')
    @app.post('/v1/evidence')
    async def stage(request:Request): return await dispatch(request,'stageEvidence')
    @app.get('/v1/evidence/{evidence_id}/content')
    async def download(evidence_id:str,request:Request): return await dispatch(request,'getEvidenceContent',evidence_id)
    @app.post('/v1/cases')
    async def create(request:Request): return await dispatch(request,'createCase')
    @app.get('/v1/cases/{case_id}')
    async def read(case_id:str,request:Request): return await dispatch(request,'getCustomerCase',case_id)
    @app.get('/v1/cases/{case_id}/history')
    async def history(case_id:str,request:Request): return await dispatch(request,'listCustomerCaseHistory',case_id)
    @app.post('/v1/cases/{case_id}/clarifications')
    async def clarify(case_id:str,request:Request): return await dispatch(request,'submitClarification',case_id)

def register_customer_case_list(app):
    """GET /v1/cases outside contract v1 (31 October 2026): the signed-in customer's own
    cases, newest first. main.py adds it only with password sign-in (`serve --accounts`),
    so without that the frozen route set is unchanged."""
    @app.get('/v1/cases')
    async def own_cases(request:Request):
        correlation=identifier('corr');failure=None
        try:
            flow=_flow(request)
            # Authenticate before looking at the query, as the frozen reads do.
            await run_in_threadpool(flow.preflight,'getSession')
            if request.query_params: raise FlowError('VALIDATION_ERROR')
            result=await run_in_threadpool(flow.list_cases)
            return safe_json(result.body,result.status,correlation=correlation)
        except FlowError as error: failure=(error.status,error.envelope(correlation))
        except Exception: failure=(503,FlowError().envelope(correlation))
        return safe_json(failure[1],failure[0],correlation=correlation)
