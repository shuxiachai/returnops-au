"""Explicit, default-unregistered adapter for the frozen Founder decision POST."""
from dataclasses import dataclass
from typing import Callable

from fastapi import Request
from starlette.concurrency import run_in_threadpool

from returnops_domain.audit import identifier
from returnops_domain.errors import FlowError
from returnops_domain.wire import validate
from .customer_http import _json_body, one_header, safe_json


PATH = '/v1/founder/cases/{case_id}/decisions'
OPERATION = 'recordFounderDecision'
_CODES = frozenset({'UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND',
    'STALE_CASE_VERSION', 'IDEMPOTENCY_CONFLICT', 'INVALID_STATE',
    'VALIDATION_ERROR', 'INTERNAL_ERROR'})
_AUDITS = frozenset({'RECORDED', 'NOT_RECORDED', 'UNKNOWN', 'NOT_ATTEMPTED'})


@dataclass(frozen=True, repr=False)
class FounderDecisionRequestPorts:
    """Trusted request composition; no port or authority comes from HTTP fields."""
    preflight: Callable[[str], None]
    approve: object
    reject: object
    revision: object
    manual: object


def _safe_error(error):
    code = getattr(error, 'code', None)
    return FlowError(code if type(code) is str and code in _CODES else 'INTERNAL_ERROR')


def _receipt(result, case_id, decision):
    # UNKNOWN never reads a receipt, audit detail or recovery method.
    status = result.status
    if type(status) is not str or status not in {'ACCEPTED', 'DENIED'}:
        raise FlowError()
    if status == 'DENIED':
        if (result.receipt is not None or type(result.audit) is not str or
                result.audit not in _AUDITS):
            raise FlowError()
        code = result.safe_code
        if type(code) is not str or code not in _CODES:
            raise FlowError()
        raise FlowError(code)
    try:
        if (result.safe_code is not None or type(result.audit) is not str or
                result.audit != 'NOT_ATTEMPTED'):
            raise ValueError()
        body = validate('DecisionReceipt', result.receipt, internal=True)
        if body['case_id'] != case_id or body['decision'] != decision:
            raise ValueError()
    except Exception:
        raise FlowError() from None
    # A replay may have a historical case_version. Do not invent expected+1.
    return body


def register_founder_decision_candidate(app, request_ports_factory):
    """Register one opt-in route; leave default app composition unchanged."""
    if not callable(request_ports_factory):
        raise ValueError('A trusted request ports factory is required.')
    for route in app.routes:
        if ((getattr(route, 'operation_id', None) or getattr(route, 'unique_id', None)) == OPERATION or
                getattr(route, 'path', None) == PATH and
                'POST' in (getattr(route, 'methods', None) or set())):
            raise ValueError('Founder decision route is already registered.')

    async def record_decision(case_id: str, request: Request):
        correlation = identifier('corr')
        try:
            authorization = one_header(request, 'authorization')
            ports = request_ports_factory(authorization)
            await run_in_threadpool(ports.preflight, case_id)
            if request.query_params:
                raise FlowError('VALIDATION_ERROR')
            key = one_header(request, 'idempotency-key', required=True)
            validate('IdempotencyKey', key)
            value = validate('FounderDecisionRequest', await _json_body(request))
            # The schema's minLength counts spaces; a blank rationale is no rationale (customer
            # text has the same rule in wire.py). 30 October 2026 review.
            if not value['reason'].strip():
                raise FlowError('VALIDATION_ERROR')
            service = {'APPROVE': ports.approve, 'REJECT': ports.reject,
                       'REQUEST_REVISION': ports.revision,
                       'MANUAL_HANDLING': ports.manual}[value['decision']]
            result = await run_in_threadpool(service.accept, case_id, value, key, correlation)
            return safe_json(_receipt(result, case_id, value['decision']), 202, correlation=correlation)
        except FlowError as error:
            failure = _safe_error(error)
        except Exception:
            failure = FlowError()
        return safe_json(failure.envelope(correlation), failure.status, correlation=correlation)

    app.add_api_route(PATH, record_decision, methods=['POST'], operation_id=OPERATION)
