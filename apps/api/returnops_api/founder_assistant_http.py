"""Founder AI assistant routes (31 October 2026), outside contract v1.

main.py registers them only with both password sign-in (`serve --accounts`) and the
model showcase, and composes the shared budgeted transport from trusted app state;
nothing in a request selects a model, provider or authority. Each route authenticates
the Founder before it takes one of two call slots, so a stranger cannot spend the key.
"""
from fastapi import Request
from starlette.concurrency import run_in_threadpool
from returnops_domain.audit import identifier
from returnops_domain.errors import FlowError
from returnops_domain.founder_assistant import FounderAssistant
from .customer_authority import CurrentRequestAuthority
from .customer_http import one_header, safe_json


def register_founder_assistant_routes(app):
    async def run(request, operation, method, case_id=None):
        correlation = identifier('corr')
        try:
            config, composition = request.app.state.auth_config, getattr(request.app.state, 'founder_assistant', None)
            if config is None or composition is None:
                raise FlowError()
            assistant = FounderAssistant(request.app.state.engine,
                                         CurrentRequestAuthority(config, one_header(request, 'authorization')), composition)
            await run_in_threadpool(assistant.preflight, operation, case_id)
            if request.query_params:
                raise FlowError('VALIDATION_ERROR')
            slots = request.app.state.assistant_slots
            if not slots.acquire(blocking=False):
                raise FlowError()
            try:
                result = await run_in_threadpool(getattr(assistant, method), *(() if case_id is None else (case_id,)))
            finally:
                slots.release()
            return safe_json(result.body, result.status, correlation=correlation)
        except FlowError as error:
            failure = error.status, error.envelope(correlation)
        except Exception:
            failure = 503, FlowError().envelope(correlation)
        return safe_json(failure[1], failure[0], correlation=correlation)

    @app.post('/v1/founder/cases/{case_id}/assistant/reply')
    async def reply(case_id: str, request: Request):
        return await run(request, 'getFounderCase', 'reply', case_id)

    # C2 Risk Reviewer, advisory (1 November 2026): one case's review, never recorded.
    @app.post('/v1/founder/cases/{case_id}/assistant/risk-review')
    async def risk_review(case_id: str, request: Request):
        return await run(request, 'getFounderCase', 'risk_review', case_id)

    # C3 image evidence observations, advisory (1 November 2026): never recorded.
    @app.post('/v1/founder/cases/{case_id}/assistant/image-observations')
    async def image_observations(case_id: str, request: Request):
        return await run(request, 'getFounderCase', 'image_observations', case_id)

    @app.post('/v1/founder/assistant/triage')
    async def triage(request: Request):
        return await run(request, 'listFounderCases', 'triage')

    @app.post('/v1/founder/assistant/summary')
    async def summary(request: Request):
        return await run(request, 'getFounderAnalytics', 'summary')
