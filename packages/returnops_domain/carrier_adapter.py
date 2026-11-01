"""A3 sandbox carrier adapter behind the core label provider interface.

OF-004; FR-010, UC-04, NFR-004, NFR-007; docs/49-a3-carrier-sandbox.md.

``SandboxCarrierLabel`` is a ``CoreLabelMock`` whose only override is
``_outcome``. Authorisation, the dispatch claim, the fenced ledger insert, the
final checks and the existing UNKNOWN/DENIED replies stay the unchanged core
code, so the same approval and idempotency rules apply whichever adapter is
used. Instead of answering SUCCEEDED locally, ``_outcome`` maps the approved
GENERATE_LABEL command to the carrier sandbox contract and sends it over real
HTTP with ``Idempotency-Key`` set to the control's effect key:

* 201/200 with a verified record -> SUCCEEDED (the fenced insert then writes
  the label ledger, as before);
* 401/403/409/422 on the first attempt -> FAILED (the provider refused, so
  there is no effect; the existing FAILED handling records it);
* a timeout, connection error, 5xx or any other answer -> recovery: look the
  key up (bounded attempts, short backoff), retry the POST once with the SAME
  key when no label is found, then confirm by key once more. Only a verified
  label turns this into SUCCEEDED; anything else raises
  ``CarrierOutcomeUnknown`` so that ``perform()`` returns its existing UNKNOWN
  reply and no ledger row is written.

Timeouts are sized from the dispatch deadline that label_execution.py sets
(at most 30 seconds after the reservation, earlier if the preview expires
first): the carrier call never uses more than 12 seconds and always leaves 5
seconds for the fenced insert and final checks. The client only reaches the
local sandbox on 127.0.0.1; it cannot be pointed at a real carrier. Attempt
records hold phase, method, route template, status, X-Request-Id and elapsed
milliseconds; they never hold the idempotency key, the test key or a body.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPException
import json
import time
from urllib.parse import quote, urlsplit

from .carrier_sandbox import (BY_KEY_ROUTE, CREATE_ROUTE, IDEMPOTENCY_KEY, REFERENCE_FIELDS, TEST_KEY, TOKEN,
                              identifier)
from .core_label_mock import CoreLabelMock
from .customer_uow import CustomerUnitOfWork

# label_execution.py: dispatch_deadline = min(reservation time + 30 s, preview expiry).
DISPATCH_WINDOW_SECONDS = 30.0
# Time always left after the carrier call for the fenced ledger insert and final checks.
DEADLINE_MARGIN_SECONDS = 5.0
# Ceiling for one whole carrier call, including every recovery attempt.
TOTAL_BUDGET_SECONDS = 12.0
REQUEST_TIMEOUT_SECONDS = 2.0
LOOKUP_ATTEMPTS = 3
BACKOFF_SECONDS = (0.05, 0.1, 0.2)
MIN_ATTEMPT_SECONDS = 0.2
MAX_RESPONSE_BYTES = 65536
SUCCESS = frozenset({200, 201})
REJECTED = {401: 'CARRIER_AUTH_REJECTED', 403: 'CARRIER_AUTH_REJECTED',
            409: 'CARRIER_IDEMPOTENCY_CONFLICT', 422: 'CARRIER_INVALID_REQUEST'}


class CarrierOutcomeUnknown(Exception):
    """The carrier result could not be confirmed; perform() turns this into UNKNOWN."""


class CarrierMappingError(ValueError):
    """The core command cannot be mapped to the carrier contract; nothing is sent."""


@dataclass(frozen=True, slots=True)
class CarrierResult:
    """Fields-only outcome of one carrier call; never holds the key or a body."""
    outcome: str
    correlation_id: str | None
    attempts: tuple
    label: dict | None = None
    error: str | None = None
    recovered: bool = False

    def receipt(self) -> dict:
        return dict(outcome=self.outcome, correlation_id=self.correlation_id, recovered=self.recovered,
                    error=self.error, label=None if self.label is None else dict(self.label),
                    attempts=[dict(attempt) for attempt in self.attempts])


@dataclass(frozen=True, slots=True)
class _Reply:
    status: int | None
    error: str | None
    request_id: str | None
    payload: object
    elapsed_ms: int


def label_request(control, command) -> dict:
    """Map the approved GENERATE_LABEL command and its control row to the sandbox body."""
    try:
        parameters = command['parameters']
        if (command['type'] != 'GENERATE_LABEL' or parameters['label_format'] != 'PDF'
                or parameters['chargeable'] is not False or parameters['parcel_id'] != control['parcel_id']):
            raise CarrierMappingError('The command is not a non-chargeable PDF label for this parcel.')
        body = dict(client_reference=command['command_id'], parcel_reference=parameters['parcel_id'],
                    return_reference=control['provider_return_id'], label_format='PDF', service='RETURN',
                    chargeable=False)
    except (KeyError, TypeError):
        raise CarrierMappingError('The command does not have the label contract fields.') from None
    if any(type(body[name]) is not str or TOKEN.fullmatch(body[name]) is None for name in REFERENCE_FIELDS):
        raise CarrierMappingError('A reference does not match the carrier contract.')
    key = control['effect_key']
    if type(key) is not str or IDEMPOTENCY_KEY.fullmatch(key) is None:
        raise CarrierMappingError('The effect key does not match the carrier contract.')
    return body


def dispatch_budget(deadline, *, now=None) -> float:
    """Seconds the carrier call may use before ``deadline`` (0 when too close or unknown)."""
    if not isinstance(deadline, datetime) or deadline.utcoffset() is None:
        return 0.0
    current = datetime.now(timezone.utc) if now is None else now
    return max(0.0, min(TOTAL_BUDGET_SECONDS, (deadline - current).total_seconds() - DEADLINE_MARGIN_SECONDS))


class CarrierLabelClient:
    """HTTP part of the adapter: no database, safe to call from the offline demo."""

    def __init__(self, base_url, *, api_key=TEST_KEY, request_timeout=REQUEST_TIMEOUT_SECONDS,
                 lookup_attempts=LOOKUP_ATTEMPTS, backoff=BACKOFF_SECONDS, budget_seconds=TOTAL_BUDGET_SECONDS,
                 clock=time.monotonic, sleep=time.sleep):
        try:
            parts = urlsplit(base_url)
            port = parts.port
        except (TypeError, ValueError, AttributeError):
            parts = port = None
        if (parts is None or parts.scheme != 'http' or parts.hostname != '127.0.0.1' or port is None
                or parts.path not in ('', '/') or parts.query or parts.fragment or parts.username is not None):
            raise ValueError('The A3 adapter only reaches the local carrier sandbox at http://127.0.0.1:<port>.')
        if type(api_key) is not str or not api_key or not api_key.isascii():
            raise ValueError('Use the sandbox test key.')
        if not 0 < float(request_timeout) <= 10:
            raise ValueError('Use a request timeout between 0 and 10 seconds.')
        if type(lookup_attempts) is not int or not 1 <= lookup_attempts <= 5:
            raise ValueError('Use 1 to 5 lookup attempts.')
        backoff = tuple(float(value) for value in backoff)
        if not backoff or any(not 0 <= value <= 1 for value in backoff):
            raise ValueError('Use short backoff pauses of at most one second.')
        if not 0 < float(budget_seconds) <= DISPATCH_WINDOW_SECONDS - DEADLINE_MARGIN_SECONDS:
            raise ValueError('The carrier budget must fit inside the dispatch window.')
        self._host, self._port = parts.hostname, port
        self._authorization = 'Bearer ' + api_key
        self.request_timeout, self.lookup_attempts = float(request_timeout), lookup_attempts
        self.backoff, self.budget_seconds = backoff, float(budget_seconds)
        self._clock, self._sleep = clock, sleep

    def __repr__(self):
        return (f'CarrierLabelClient(sandbox=http://{self._host}:{self._port}, timeout={self.request_timeout}s, '
                f'lookups={self.lookup_attempts}, budget={self.budget_seconds}s)')

    def create_label(self, idempotency_key, body, *, budget_seconds=None) -> CarrierResult:
        """Create one label idempotently, recovering an uncertain answer by key."""
        if type(idempotency_key) is not str or IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise CarrierMappingError('The idempotency key does not match the carrier contract.')
        payload = json.dumps(body, sort_keys=True, separators=(',', ':')).encode('utf-8')
        budget = self.budget_seconds if budget_seconds is None else max(0.0, min(self.budget_seconds, float(budget_seconds)))
        correlation = identifier('A3C', 6)
        attempts = []

        def finish(outcome, *, label=None, error=None, recovered=False):
            return CarrierResult(outcome, correlation, tuple(attempts), label, error, recovered)

        if budget < MIN_ATTEMPT_SECONDS:
            return finish('FAILED', error='CARRIER_NOT_SENT_DEADLINE')
        stop_at = self._clock() + budget
        lookup_path = '/v1/labels/by-key/' + quote(idempotency_key, safe='')

        def send(phase, method, path, route, data=None):
            remaining = stop_at - self._clock()
            if remaining < MIN_ATTEMPT_SECONDS:
                return None
            reply = self._exchange(method, path, data, idempotency_key, correlation,
                                   min(self.request_timeout, remaining))
            attempts.append(dict(phase=phase, method=method, route=route, status=reply.status, error=reply.error,
                                 request_id=reply.request_id, elapsed_ms=reply.elapsed_ms))
            return reply

        def lookup(phase, tries):
            for index in range(tries):
                pause = self.backoff[min(index, len(self.backoff) - 1)]
                if stop_at - self._clock() < pause + MIN_ATTEMPT_SECONDS:
                    break
                self._sleep(pause)
                reply = send(phase, 'GET', lookup_path, BY_KEY_ROUTE)
                if reply is None:
                    break
                if reply.status == 200:
                    label = self._label(reply, body)
                    return ('FOUND', label) if label is not None else ('MISMATCH', None)
                if reply.status == 404:
                    return 'ABSENT', None
            return 'UNANSWERED', None

        first = send('create', 'POST', CREATE_ROUTE, CREATE_ROUTE, payload)
        if first is None:
            return finish('FAILED', error='CARRIER_NOT_SENT_DEADLINE')
        label = self._label(first, body)
        if label is not None:
            return finish('SUCCEEDED', label=label)
        if first.status in REJECTED:
            return finish('FAILED', error=REJECTED[first.status])
        # Uncertain: the label may or may not exist. Verify by key before anything else.
        state, label = lookup('verify', self.lookup_attempts)
        if state == 'FOUND':
            return finish('SUCCEEDED', label=label, recovered=True)
        if state == 'MISMATCH':
            return finish('UNKNOWN', error='CARRIER_RECORD_MISMATCH')
        # Not found (or not answered): one retry with the SAME key cannot create a second label.
        retry = send('retry', 'POST', CREATE_ROUTE, CREATE_ROUTE, payload)
        label = None if retry is None else self._label(retry, body)
        if label is not None:
            return finish('SUCCEEDED', label=label, recovered=True)
        # After an uncertain first attempt a refusal is not proof of no effect: confirm once more.
        state, label = lookup('confirm', 1)
        if state == 'FOUND':
            return finish('SUCCEEDED', label=label, recovered=True)
        return finish('UNKNOWN', error='CARRIER_OUTCOME_UNKNOWN')

    @staticmethod
    def _label(reply, body):
        """The verified sandbox record for this request, or None."""
        record = reply.payload
        if reply.status not in SUCCESS or type(record) is not dict or record.get('status') != 'CREATED':
            return None
        if any(type(record.get(name)) is not str or TOKEN.fullmatch(record[name]) is None
               for name in ('label_id', 'tracking_number')):
            return None
        if any(record.get(name) != body[name] for name in REFERENCE_FIELDS):
            return None
        created = record.get('created_at')
        return dict(label_id=record['label_id'], tracking_number=record['tracking_number'],
                    created_at=created if type(created) is str and len(created) <= 40 else None)

    def _exchange(self, method, path, data, key, correlation, timeout) -> _Reply:
        started = self._clock()
        headers = {'Authorization': self._authorization, 'Accept': 'application/json',
                   'X-Correlation-Id': correlation, 'Connection': 'close'}
        if data is not None:
            headers.update({'Content-Type': 'application/json', 'Idempotency-Key': key})
        connection = HTTPConnection(self._host, self._port, timeout=timeout)
        status = request_id = payload = error = None
        try:
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status, request_id = response.status, response.getheader('X-Request-Id')
            if len(raw) <= MAX_RESPONSE_BYTES:
                try:
                    payload = json.loads(raw.decode('utf-8'))
                except (UnicodeDecodeError, ValueError):
                    payload = None
        except TimeoutError:
            status, request_id, error = None, None, 'TIMEOUT'
        except (OSError, HTTPException):
            status, request_id, error = None, None, 'CONNECTION'
        finally:
            connection.close()
        if request_id is not None and TOKEN.fullmatch(request_id) is None:
            request_id = 'INVALID'
        elapsed_ms = max(0, int(round((self._clock() - started) * 1000)))
        return _Reply(status, error, request_id, payload, elapsed_ms)


class SandboxCarrierLabel(CoreLabelMock):
    """The core label mock with only ``_outcome`` replaced by the sandbox carrier call."""

    # Set by SandboxLabelFactory. Without a client, _outcome raises: UNKNOWN, never a label.
    client = None
    carrier_result = None

    def _outcome(self, control, command):
        client = self.client
        if not isinstance(client, CarrierLabelClient):
            raise CarrierOutcomeUnknown('No carrier sandbox client is configured.')
        try:
            body = label_request(control, command)
        except CarrierMappingError:
            self.carrier_result = CarrierResult('FAILED', None, (), error='CARRIER_MAPPING_REJECTED')
            return 'FAILED'
        result = client.create_label(control['effect_key'], body,
                                     budget_seconds=dispatch_budget(control['dispatch_deadline']))
        self.carrier_result = result
        if result.outcome in ('SUCCEEDED', 'FAILED'):
            return result.outcome
        raise CarrierOutcomeUnknown('The carrier outcome is still unknown after bounded recovery.')

    @property
    def attempts(self) -> tuple:
        return () if self.carrier_result is None else self.carrier_result.attempts


class SandboxLabelFactory:
    """``mock_factory`` for LabelExecutionService: ``factory(engine)`` returns a SandboxCarrierLabel."""

    def __init__(self, base_url, **client_options):
        self.client = CarrierLabelClient(base_url, **client_options)
        self.adapters = []

    def __call__(self, engine, *, uow_factory=CustomerUnitOfWork):
        adapter = SandboxCarrierLabel(engine, uow_factory=uow_factory)
        adapter.client = self.client
        self.adapters.append(adapter)
        return adapter

    def __repr__(self):
        return f'SandboxLabelFactory({self.client!r}, adapters={len(self.adapters)})'
