"""Private versioned typed codec; preserves Python string codepoints exactly.

Wire JSON is distinct. Strings use UTF-8 surrogatepass, dictionaries sort string
keys, arrays preserve order, booleans and integers have different tags. Floats,
NaN, arbitrary objects, duplicate keys and unbounded nesting are not accepted.
"""
from __future__ import annotations
import hashlib
from .errors import FlowError

_MAGIC = b"ROPS\x01"

def _length(value: int) -> bytes:
    return value.to_bytes(8, "big")

def _encode(value: object, depth: int = 0) -> bytes:
    if depth > 64:
        raise FlowError("VALIDATION_ERROR")
    if value is None: return b"n"
    if type(value) is bool: return b"t" if value else b"f"
    if type(value) is int:
        data = str(value).encode("ascii")
        return b"i" + _length(len(data)) + data
    if type(value) is str:
        data = value.encode("utf-8", "surrogatepass")
        return b"s" + _length(len(data)) + data
    if type(value) is list:
        return b"l" + _length(len(value)) + b"".join(_encode(x, depth + 1) for x in value)
    if type(value) is dict and all(type(k) is str for k in value):
        return b"d" + _length(len(value)) + b"".join(_encode(k, depth + 1) + _encode(value[k], depth + 1) for k in sorted(value))
    raise FlowError("VALIDATION_ERROR")

def canonical_bytes(value: object, domain: str) -> bytes:
    if type(domain) is not str or not domain.isascii() or not 1 <= len(domain) <= 80:
        raise FlowError("INTERNAL_ERROR")
    encoded_domain = domain.encode("ascii")
    return _MAGIC + _length(len(encoded_domain)) + encoded_domain + _encode(value)

def digest(value: object, domain: str) -> str:
    return hashlib.sha256(canonical_bytes(value, domain)).hexdigest()

def encode_document(value: object) -> bytes:
    return canonical_bytes(value, "document/v1")

def decode_document(raw: bytes) -> object:
    data = bytes(raw); offset = 0
    def take(size):
        nonlocal offset
        if size < 0 or offset + size > len(data): raise ValueError
        result = data[offset:offset + size]; offset += size; return result
    def length(): return int.from_bytes(take(8), "big")
    def read(depth=0):
        if depth > 64: raise ValueError
        tag = take(1)
        if tag == b"n": return None
        if tag == b"t": return True
        if tag == b"f": return False
        if tag == b"s": return take(length()).decode("utf-8", "surrogatepass")
        if tag == b"i":
            integer = take(length()).decode("ascii")
            value = int(integer)
            if str(value) != integer: raise ValueError
            return value
        if tag == b"l":
            count = length()
            if count > len(data) - offset: raise ValueError
            return [read(depth + 1) for _ in range(count)]
        if tag == b"d":
            count = length()
            if count > len(data) - offset: raise ValueError
            result = {}; previous = None
            for _ in range(count):
                key = read(depth + 1)
                if type(key) is not str or (previous is not None and key <= previous): raise ValueError
                result[key] = read(depth + 1); previous = key
            return result
        raise ValueError
    failed = False
    try:
        if take(len(_MAGIC)) != _MAGIC or take(length()) != b"document/v1": raise ValueError
        result = read()
        if offset != len(data): raise ValueError
    except (ValueError, UnicodeError, OverflowError, RecursionError):
        failed = True
    if failed: raise FlowError("INTERNAL_ERROR") from None
    return result
