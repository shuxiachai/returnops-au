"""The five frozen Founder GET routes (F.05 reads, F.06 analytics); no caller-selected authority or effects."""
from decimal import Decimal, InvalidOperation
from fastapi import Request
from starlette.concurrency import run_in_threadpool
from returnops_domain.audit import identifier
from returnops_domain.errors import FlowError
from returnops_domain.founder_service import FounderQueries
from returnops_domain.wire import normalize_json_numbers
from .customer_authority import CurrentRequestAuthority
from .customer_http import one_header, safe_json


def _query(request, operation):
    allowed = {'cursor', 'limit'}
    if operation == 'listFounderCaseHistory':
        allowed |= {'kind', 'object_id', 'object_version'}
    elif operation == 'getFounderCase':
        allowed = set()
    elif operation == 'getFounderAnalytics':
        allowed = {'created_from', 'created_before', 'status'}
    result = {}
    for key, value in request.query_params.multi_items():
        if key not in allowed or key in result:
            raise FlowError('VALIDATION_ERROR')
        if key in {'limit', 'object_version'}:
            failed = False
            try:
                if len(value) > 64:
                    raise ValueError()
                value = normalize_json_numbers(Decimal(value))
            except (InvalidOperation, ValueError):
                failed = True
            if failed:
                raise FlowError('VALIDATION_ERROR') from None
        result[key] = value
    return result


def register_founder_routes(app):
    async def dispatch(request, operation, case_id=None):
        correlation = identifier('corr')
        try:
            config = request.app.state.auth_config
            if config is None:
                raise FlowError()
            authority = CurrentRequestAuthority(config, one_header(request, 'authorization'))
            # A1.06 showcase: trusted app state only; None unless the flag is on.
            flow = FounderQueries(request.app.state.engine, authority,
                                  facts_provider=getattr(request.app.state, 'coordinator_facts', None))
            result = await run_in_threadpool(flow.read, operation, case_id, lambda: _query(request, operation))
            return safe_json(result.body, result.status, correlation=correlation)
        except FlowError as error:
            failure = error.status, error.envelope(correlation)
        except Exception:
            failure = 503, FlowError().envelope(correlation)
        return safe_json(failure[1], failure[0], correlation=correlation)

    @app.get('/v1/founder/cases')
    async def cases(request: Request):
        return await dispatch(request, 'listFounderCases')

    @app.get('/v1/founder/cases/{case_id}')
    async def detail(case_id: str, request: Request):
        return await dispatch(request, 'getFounderCase', case_id)

    @app.get('/v1/founder/cases/{case_id}/history')
    async def history(case_id: str, request: Request):
        return await dispatch(request, 'listFounderCaseHistory', case_id)

    @app.get('/v1/founder/cases/{case_id}/audit')
    async def audit(case_id: str, request: Request):
        return await dispatch(request, 'listCaseAudit', case_id)

    @app.get('/v1/founder/analytics', operation_id='getFounderAnalytics')
    async def analytics(request: Request):
        return await dispatch(request, 'getFounderAnalytics')
