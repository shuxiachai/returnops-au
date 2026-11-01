"""A3 contract-test carrier sandbox (OF-004; FR-010, UC-04, NFR-004, NFR-007).

This is a small contract-test sandbox that this repository runs itself, on
127.0.0.1 only, for tests and the recovery demonstration. It is not a
carrier's own test environment and it is not reachable from other machines.
Its state lives in memory and disappears when the process stops. Every value
is synthetic: no real shipment, consignment, label or charge exists, and no
carrier is ever contacted. See docs/49-a3-carrier-sandbox.md.

Contract (JSON over HTTP):

  POST /v1/labels                           create one return label, idempotently
  GET  /v1/labels/by-key/{idempotency_key}  the label created for that key, or 404
  GET  /v1/labels/{label_id}                one label, or 404

Every request needs ``Authorization: Bearer <test key>``. TEST_KEY is a fake
test key for this local sandbox only; it is not a credential for any service.
POST also needs an ``Idempotency-Key`` header: the first use answers 201, the
same key with the same body answers 200 with the same record, and the same
key with a different body answers 409. Every response carries an
``X-Request-Id``. Faults are injected only through ``CarrierSandbox.inject``
by the test or demo that owns the sandbox, never by request content.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from secrets import compare_digest, token_hex
import threading
from urllib.parse import unquote

# Fake test key for the local sandbox only; it grants nothing outside this process.
TEST_KEY = 'sandbox-test-key-not-secret'
HOST = '127.0.0.1'
FAULTS = ('error_before_commit', 'timeout_after_commit', 'reject_auth', 'invalid', 'delay_before_commit')
REQUEST_FIELDS = ('client_reference', 'parcel_reference', 'return_reference', 'label_format', 'service', 'chargeable')
REFERENCE_FIELDS = REQUEST_FIELDS[:3]
CREATE_ROUTE = '/v1/labels'
BY_KEY_ROUTE = '/v1/labels/by-key/{idempotency_key}'
BY_ID_ROUTE = '/v1/labels/{label_id}'
MAX_BODY_BYTES = 16384
DEFAULT_FAULT_DELAY = 1.0
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}')
IDEMPOTENCY_KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,254}')
CORRELATION = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}')
_LONG_DIGIT_RUN = re.compile(r'[0-9]{6}')


def identifier(prefix: str, size: int = 5) -> str:
    """Synthetic ID: a letter prefix plus upper-case hex, never six digits in a row.

    Generated IDs may end up in evidence files, and the repository rejects added
    lines with a nine-digit number, so long digit runs are drawn again.
    """
    while True:
        value = prefix + token_hex(size).upper()
        if _LONG_DIGIT_RUN.search(value) is None:
            return value


def body_fingerprint(body: dict) -> str:
    return sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def _unique_pairs(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError('duplicate field')
        result[name] = value
    return result


def parse_label_request(raw: bytes) -> dict | None:
    """Return the request body when it matches the label contract exactly, else None."""
    try:
        body = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, ValueError):
        return None
    if type(body) is not dict or set(body) != set(REQUEST_FIELDS):
        return None
    if any(type(body[name]) is not str or TOKEN.fullmatch(body[name]) is None for name in REFERENCE_FIELDS):
        return None
    if body['label_format'] != 'PDF' or body['service'] != 'RETURN' or body['chargeable'] is not False:
        return None
    return body


class _Label:
    __slots__ = ('label_id', 'tracking_number', 'created_at', 'fingerprint', 'key_digest', 'references')

    def __init__(self, label_id, tracking_number, created_at, fingerprint, key_digest, references):
        self.label_id, self.tracking_number, self.created_at = label_id, tracking_number, created_at
        self.fingerprint, self.key_digest, self.references = fingerprint, key_digest, references

    def public(self) -> dict:
        return dict(label_id=self.label_id, tracking_number=self.tracking_number, status='CREATED',
                    created_at=self.created_at, **self.references)

    def __repr__(self):
        return f'_Label({self.label_id})'


def _key_digest(key: str) -> str:
    return sha256(('carrier-sandbox-key/v1:' + key).encode('utf-8')).hexdigest()


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


class _Handler(BaseHTTPRequestHandler):
    server_version = 'ReturnOpsCarrierSandbox/1'
    sys_version = ''
    timeout = 5

    # Silence the default stderr access log: paths can contain an idempotency key.
    def log_message(self, format, *args):
        return

    def send_response(self, code, message=None):
        super().send_response(code, message)
        if getattr(self, '_request_id', None) is None:
            self._request_id = identifier('SBXR', 6)
        self.send_header('X-Request-Id', self._request_id)

    def _begin(self):
        self._request_id = identifier('SBXR', 6)
        supplied = self.headers.get('X-Correlation-Id')
        self._correlation = supplied if supplied is not None and CORRELATION.fullmatch(supplied) else None

    def _authorized(self) -> bool:
        supplied = self.headers.get('Authorization', '')
        expected = 'Bearer ' + self.server.sandbox._api_key
        return compare_digest(supplied.encode('utf-8', 'replace'), expected.encode('utf-8'))

    def _reply(self, route, status, payload, fault=None):
        data = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        self.server.sandbox._record(self.command, route, status, self._request_id, self._correlation, fault)
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            if self._correlation is not None:
                self.send_header('X-Correlation-Id', self._correlation)
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            pass  # The client already gave up (for example after its own timeout); state is unaffected.

    def _error(self, route, status, code, fault=None):
        self._reply(route, status, {'error': {'code': code}, 'request_id': self._request_id}, fault)

    def _read_body(self) -> bytes | None:
        length = self.headers.get('Content-Length')
        if length is None or not length.isdigit() or int(length) > MAX_BODY_BYTES:
            return None
        try:
            return self.rfile.read(int(length))
        except OSError:
            return None

    def do_POST(self):
        sandbox = self.server.sandbox
        self._begin()
        with sandbox._busy():
            # Read the bounded body first, so an early answer never resets the connection.
            raw = self._read_body()
            if self.path != CREATE_ROUTE:
                return self._error('other', 404, 'not_found')
            if not self._authorized():
                return self._error(CREATE_ROUTE, 401, 'unauthorized')
            fault, delay = sandbox._take_fault()
            if fault == 'reject_auth':
                return self._error(CREATE_ROUTE, 401, 'unauthorized', fault)
            key = self.headers.get('Idempotency-Key')
            if key is None or IDEMPOTENCY_KEY.fullmatch(key) is None:
                return self._error(CREATE_ROUTE, 422, 'idempotency_key_required', fault)
            body = None if raw is None else parse_label_request(raw)
            if body is None or fault == 'invalid':
                return self._error(CREATE_ROUTE, 422, 'invalid_request', fault)
            if fault == 'error_before_commit':
                return self._error(CREATE_ROUTE, 503, 'temporarily_unavailable', fault)
            if fault == 'delay_before_commit':
                sandbox._pause(delay)
            status, label = sandbox._create(key, body)
            if label is None:
                return self._error(CREATE_ROUTE, 409, 'idempotency_key_reused', fault)
            if fault == 'timeout_after_commit':
                sandbox._pause(delay)
            return self._reply(CREATE_ROUTE, status, label.public(), fault)

    def do_GET(self):
        sandbox = self.server.sandbox
        self._begin()
        with sandbox._busy():
            prefix = '/v1/labels/by-key/'
            if self.path.startswith(prefix) and '?' not in self.path:
                route, value = BY_KEY_ROUTE, unquote(self.path[len(prefix):])
            elif self.path.startswith('/v1/labels/') and '?' not in self.path and self.path.count('/') == 3:
                route, value = BY_ID_ROUTE, self.path[len('/v1/labels/'):]
            else:
                return self._error('other', 404, 'not_found')
            if not self._authorized():
                return self._error(route, 401, 'unauthorized')
            label = sandbox._find_by_key(value) if route == BY_KEY_ROUTE else sandbox._find_by_id(value)
            if label is None:
                return self._error(route, 404, 'not_found')
            return self._reply(route, 200, label.public())

    def _unsupported(self):
        self._begin()
        self._error('other', 405, 'method_not_allowed')

    do_PUT = do_PATCH = do_DELETE = _unsupported


class _Busy:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def __enter__(self):
        with self.sandbox._idle:
            self.sandbox._inflight += 1

    def __exit__(self, *exc):
        with self.sandbox._idle:
            self.sandbox._inflight -= 1
            self.sandbox._idle.notify_all()
        return False


class CarrierSandbox:
    """Local contract-test carrier sandbox; synthetic, in memory, 127.0.0.1 only."""

    def __init__(self, *, port: int = 0, api_key: str = TEST_KEY, fault_delay: float = DEFAULT_FAULT_DELAY):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError('Use a TCP port number (0 picks a free one).')
        if type(api_key) is not str or not api_key or not api_key.isascii():
            raise ValueError('Use a non-empty ASCII test key.')
        if not 0 < fault_delay <= 30:
            raise ValueError('Use a fault delay between 0 and 30 seconds.')
        self._port, self._api_key, self._fault_delay = port, api_key, float(fault_delay)
        self._lock = threading.Lock()
        self._idle = threading.Condition()
        self._inflight = 0
        self._stopping = threading.Event()
        self._by_key: dict[str, _Label] = {}
        self._by_id: dict[str, _Label] = {}
        self._labels: list[_Label] = []
        self._log: list[dict] = []
        self._fault = None
        self._server = None
        self._thread = None

    def __repr__(self):
        return f'CarrierSandbox(running={self._server is not None}, labels={len(self._labels)})'

    # Lifecycle -----------------------------------------------------------
    def start(self) -> 'CarrierSandbox':
        if self._server is not None:
            raise RuntimeError('The carrier sandbox is already running.')
        server = _Server((HOST, self._port), _Handler)
        server.sandbox = self
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05},
                                  name='carrier-sandbox', daemon=True)
        self._stopping.clear()
        thread.start()
        self._server, self._thread = server, thread
        return self

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError('The carrier sandbox is not running.')
        return f'http://{HOST}:{self._server.server_address[1]}'

    def close(self) -> None:
        server, thread = self._server, self._thread
        self._server = self._thread = None
        self._stopping.set()
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(5)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()
        return False

    # Fault injection (test or demo only) ----------------------------------
    def inject(self, fault: str, *, times: int | None = 1, delay: float | None = None) -> None:
        """Apply ``fault`` to the next ``times`` authorised POSTs (None: until clear())."""
        if fault not in FAULTS:
            raise ValueError('Unknown sandbox fault.')
        if times is not None and (type(times) is not int or times < 1):
            raise ValueError('Use a positive number of requests, or None.')
        pause = self._fault_delay if delay is None else float(delay)
        if not 0 < pause <= 30:
            raise ValueError('Use a fault delay between 0 and 30 seconds.')
        with self._lock:
            self._fault = [fault, times, pause]

    def clear(self) -> None:
        with self._lock:
            self._fault = None

    # Observation for tests and evidence (never returns keys) ---------------
    def labels_for_key(self, key: str) -> int:
        digest = _key_digest(key)
        with self._lock:
            return sum(1 for label in self._labels if label.key_digest == digest)

    def label_count(self) -> int:
        with self._lock:
            return len(self._labels)

    def requests(self, correlation_id: str | None = None) -> list[dict]:
        with self._lock:
            return [dict(entry) for entry in self._log
                    if correlation_id is None or entry['correlation_id'] == correlation_id]

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """Wait until no request is being handled (for example a delayed late original)."""
        with self._idle:
            return self._idle.wait_for(lambda: self._inflight == 0, timeout)

    # Internal state transitions -------------------------------------------
    def _busy(self):
        return _Busy(self)

    def _pause(self, seconds: float) -> None:
        self._stopping.wait(seconds)

    def _take_fault(self):
        with self._lock:
            if self._fault is None:
                return None, None
            name, remaining, pause = self._fault
            if remaining is not None:
                remaining -= 1
                self._fault = None if remaining == 0 else [name, remaining, pause]
            return name, pause

    def _record(self, method, route, status, request_id, correlation_id, fault):
        with self._lock:
            self._log.append(dict(method=method, route=route, status=status, request_id=request_id,
                                  correlation_id=correlation_id, fault=fault))

    def _create(self, key: str, body: dict):
        fingerprint = body_fingerprint(body)
        with self._lock:
            found = self._by_key.get(key)
            if found is not None:
                return (200, found) if compare_digest(found.fingerprint, fingerprint) else (409, None)
            label_id = identifier('SBXL')
            while label_id in self._by_id:
                label_id = identifier('SBXL')
            label = _Label(label_id, identifier('SBXT'), datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                           fingerprint, _key_digest(key), {name: body[name] for name in REFERENCE_FIELDS})
            self._by_key[key] = label
            self._by_id[label_id] = label
            self._labels.append(label)
            return 201, label

    def _find_by_key(self, key: str):
        with self._lock:
            return self._by_key.get(key)

    def _find_by_id(self, label_id: str):
        with self._lock:
            return self._by_id.get(label_id)
