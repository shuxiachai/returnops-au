"""Bounded multipart streaming; no temporary-file spool or filename paths."""
import re
import logging
from dataclasses import dataclass,field
from python_multipart.multipart import MultipartParser
from returnops_domain.errors import FlowError
from returnops_domain.evidence_validation import MAX_FILE_BYTES

MAX_BODY_BYTES=MAX_FILE_BYTES+65536
MAX_DESCRIPTION_BYTES=8000
MAX_HEADER_BYTES=16384

@dataclass(frozen=True,repr=False)
class UploadedMaterial:
    content: bytes=field(repr=False)
    filename: str=field(repr=False)
    media_type: str
    description: str|None=field(default=None,repr=False)

def _parameters(raw):
    # Unlike general browser-compatibility parsers, never strip a Windows path
    # from a filename: it is untrusted display metadata, not a filesystem path.
    if len(raw)>MAX_HEADER_BYTES: raise FlowError('VALIDATION_ERROR',status=400)
    text=raw.decode('latin-1'); first,sep,rest=text.partition(';'); params={}
    while sep:
        match=re.match(r'\s*([A-Za-z0-9_-]+)\s*=\s*("(?:[^"\\\r\n]|\\[^\r\n])*"|[^;\s]+)\s*(;|$)',rest)
        if match is None: raise FlowError('VALIDATION_ERROR',status=400)
        key,value,sep=match.groups();key=key.lower()
        if key in params: raise FlowError('VALIDATION_ERROR',status=400)
        if value.startswith('"'): value=re.sub(r'\\(["\\])',r'\1',value[1:-1])
        params[key]=value.encode('latin-1');rest=rest[match.end():]
    return first.strip().lower(),params

class _Collector:
    def __init__(self):
        self.parts={};self.name=None;self.data=None;self.headers={};self.header_name=bytearray();self.header_value=bytearray()
        self.complete=False;self.filename=None;self.media=None;self.header_bytes=0
    def part_begin(self):
        if len(self.parts)>=2: raise FlowError('VALIDATION_ERROR',status=400)
        self.headers={};self.name=None;self.data=bytearray();self.header_bytes=0
    def header_field(self,data,start,end):
        self.header_bytes+=end-start
        if self.header_bytes>MAX_HEADER_BYTES: raise FlowError('VALIDATION_ERROR',status=400)
        self.header_name.extend(data[start:end])
    def header_value_part(self,data,start,end):
        self.header_bytes+=end-start
        if self.header_bytes>MAX_HEADER_BYTES: raise FlowError('VALIDATION_ERROR',status=400)
        self.header_value.extend(data[start:end])
    def header_end(self):
        name=bytes(self.header_name).lower(); value=bytes(self.header_value)
        if name not in {b'content-disposition',b'content-type'} or name in self.headers: raise FlowError('VALIDATION_ERROR',status=400)
        self.headers[name]=value;self.header_name.clear();self.header_value.clear()
    def headers_finished(self):
        disposition,params=_parameters(self.headers.get(b'content-disposition',b''))
        if disposition!='form-data' or params.get('name') not in {b'file',b'description'}: raise FlowError('VALIDATION_ERROR',status=400)
        self.name=params['name'].decode('ascii')
        if self.name in self.parts: raise FlowError('VALIDATION_ERROR',status=400)
        if self.name=='file':
            if set(params)!={'name','filename'}: raise FlowError('VALIDATION_ERROR',status=400)
            self.filename=params['filename'].decode('utf-8','surrogatepass')
            media,options=_parameters(self.headers.get(b'content-type',b''))
            if options: raise FlowError('UNSUPPORTED_MEDIA_TYPE')
            self.media=media
        elif set(params)!={'name'}: raise FlowError('VALIDATION_ERROR',status=400)
    def part_data(self,data,start,end):
        if self.name is None: raise FlowError('VALIDATION_ERROR',status=400)
        cap=MAX_FILE_BYTES if self.name=='file' else MAX_DESCRIPTION_BYTES
        if len(self.data)+end-start>cap:
            raise FlowError('REQUEST_TOO_LARGE' if self.name=='file' else 'VALIDATION_ERROR')
        self.data.extend(data[start:end])
    def part_end(self):
        if self.name is None: raise FlowError('VALIDATION_ERROR',status=400)
        self.parts[self.name]=bytes(self.data);self.data=None
    def end(self): self.complete=True

async def read_upload(request):
    collector=_Collector();failed=False
    try:
        raw=request.headers.get('content-type','').encode('latin-1')
        kind,params=_parameters(raw);boundary=params.get('boundary',b'')
        if kind!='multipart/form-data' or set(params)!={'boundary'} or not 1<=len(boundary)<=70 or any(c<33 or c>126 for c in boundary):
            raise FlowError('VALIDATION_ERROR',status=400)
        callbacks={'on_part_begin':collector.part_begin,'on_header_field':collector.header_field,
            'on_header_value':collector.header_value_part,'on_header_end':collector.header_end,
            'on_headers_finished':collector.headers_finished,'on_part_data':collector.part_data,
            'on_part_end':collector.part_end,'on_end':collector.end}
        parser=MultipartParser(boundary,callbacks,max_size=MAX_BODY_BYTES,max_header_count=2,max_header_size=MAX_HEADER_BYTES)
        # The third-party state machine logs raw malformed header/boundary
        # bytes. Silence only this parser instance, never application logging.
        parser.logger=logging.Logger("returnops-private-multipart",level=logging.CRITICAL+1)
        parser.logger.addHandler(logging.NullHandler());parser.logger.propagate=False
        total=0
        async for chunk in request.stream():
            total+=len(chunk)
            if total>MAX_BODY_BYTES: raise FlowError('REQUEST_TOO_LARGE')
            parser.write(chunk)
        parser.finalize()
        if not collector.complete or 'file' not in collector.parts: raise FlowError('VALIDATION_ERROR',status=400)
        description=None if 'description' not in collector.parts else collector.parts['description'].decode('utf-8','surrogatepass')
        return UploadedMaterial(collector.parts['file'],collector.filename,collector.media,description)
    except FlowError: raise
    except Exception: failed=True
    if failed: raise FlowError('VALIDATION_ERROR',status=400) from None
