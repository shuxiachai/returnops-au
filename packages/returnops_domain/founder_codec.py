"""Opt-in finite-number history profile; the existing v1 codec is unchanged.

ROPS02 uses the original typed string/list/map encoding and a binary64 tag only
for finite nonintegral floats. Integral floats normalize to integers; integers
are never converted to floats. New future-history bodies and hashes use distinct
document/finite-v2 and history/finite-v2 domains.
"""
import hashlib
import math
import struct
from copy import deepcopy
from .errors import FlowError
from .wire import _validator

MAGIC = b'ROPS\x02'
BODY_DOMAIN = 'document/finite-v2'
HISTORY_DOMAIN = 'history/finite-v2'
PROFILE = 'founder-finite/v2'
LEGACY_PROFILE = 'founder-finite/v2-from-v1'
_SCHEMAS = {'HistoricalProposalBundle','HistoricalRiskReview','FounderDecisionRecord',
            'ApprovalRecord','OperationAttempt','NotificationRecord','FounderHistoryRecord',
            'FounderHistoryPage','CaseView'}


def _length(value):
    return value.to_bytes(8,'big')


def _encode(value, depth=0):
    if depth > 64:
        raise FlowError()
    if value is None: return b'n'
    if type(value) is bool: return b't' if value else b'f'
    if type(value) is float:
        if not math.isfinite(value): raise FlowError()
        if value.is_integer(): value=int(value)
        else: return b'r'+struct.pack('>d',value)
    if type(value) is int:
        data=str(value).encode('ascii')
        return b'i'+_length(len(data))+data
    if type(value) is str:
        data=value.encode('utf-8','surrogatepass')
        return b's'+_length(len(data))+data
    if type(value) is list:
        return b'l'+_length(len(value))+b''.join(_encode(item,depth+1) for item in value)
    if type(value) is dict and all(type(key) is str for key in value):
        return b'd'+_length(len(value))+b''.join(_encode(key,depth+1)+_encode(value[key],depth+1) for key in sorted(value))
    raise FlowError()


def canonical_bytes(value, domain):
    if domain not in {BODY_DOMAIN,HISTORY_DOMAIN}:
        raise FlowError()
    encoded=domain.encode('ascii')
    return MAGIC+_length(len(encoded))+encoded+_encode(value)


def digest(value):
    return hashlib.sha256(canonical_bytes(value,HISTORY_DOMAIN)).hexdigest()


def encode_document(value):
    return canonical_bytes(value,BODY_DOMAIN)


def decode_document(raw):
    data=bytes(raw)
    offset=0
    def take(size):
        nonlocal offset
        if size < 0 or offset+size > len(data): raise ValueError()
        result=data[offset:offset+size]
        offset+=size
        return result
    def length(): return int.from_bytes(take(8),'big')
    def read(depth=0):
        if depth > 64: raise ValueError()
        tag=take(1)
        if tag == b'n': return None
        if tag == b't': return True
        if tag == b'f': return False
        if tag == b'r':
            value=struct.unpack('>d',take(8))[0]
            if not math.isfinite(value) or value.is_integer(): raise ValueError()
            return value
        if tag == b's': return take(length()).decode('utf-8','surrogatepass')
        if tag == b'i':
            encoded=take(length()).decode('ascii')
            value=int(encoded)
            if str(value) != encoded: raise ValueError()
            return value
        if tag == b'l':
            count=length()
            if count > len(data)-offset: raise ValueError()
            return [read(depth+1) for _ in range(count)]
        if tag == b'd':
            count=length()
            if count > len(data)-offset: raise ValueError()
            result={}
            previous=None
            for _ in range(count):
                key=read(depth+1)
                if type(key) is not str or (previous is not None and key <= previous): raise ValueError()
                result[key]=read(depth+1)
                previous=key
            return result
        raise ValueError()
    failed=False
    try:
        if take(len(MAGIC)) != MAGIC or take(length()) != BODY_DOMAIN.encode('ascii'): raise ValueError()
        result=read()
        if offset != len(data) or encode_document(result) != data: raise ValueError()
    except (ValueError,UnicodeError,OverflowError,RecursionError,struct.error):
        failed=True
    if failed: raise FlowError() from None
    return result


def validate(name,value):
    """Only internal Founder output/body schemas opt into the finite profile."""
    if name not in _SCHEMAS: raise FlowError()
    canonical_bytes(value,BODY_DOMAIN)
    if next(_validator(name).iter_errors(value),None) is not None: raise FlowError()
    return deepcopy(value)
