"""Health diagnostics and the frozen customer/Founder read operations."""
from contextlib import asynccontextmanager
from threading import BoundedSemaphore
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from returnops_domain.intake_processor import IntakeProcessor,IntakeWorker
from returnops_domain.investigation_processor import InvestigationProcessor
from .database import build_engine,readiness
from .settings import Settings
from .customer_config import load_private_auth_config
from .customer_http import register_customer_routes
from .founder_http import register_founder_routes

def create_app(*,engine=None,auth_config=None,enable_processor=True,enable_fixed_proposal=None,
               enable_founder_decisions=None,enable_model_showcase=None):
    # Keyword injection is trusted Python composition for tests, never HTTP input.
    configured=auth_config if auth_config is not None else load_private_auth_config()
    if enable_fixed_proposal is None:
        flag = os.environ.get('RETURNOPS_FIXED_PROPOSAL_DEMO','0')
        if flag not in {'0','1'}:
            raise ValueError('The synthetic fixed-proposal flag must be 0 or 1.')
        enable_fixed_proposal = flag == '1'
    if type(enable_fixed_proposal) is not bool:
        raise ValueError('The synthetic fixed-proposal flag must be boolean.')
    if enable_founder_decisions is None:
        flag = os.environ.get('RETURNOPS_FOUNDER_DECISIONS','0')
        if flag not in {'0','1'}:
            raise ValueError('The Founder decision route flag must be 0 or 1.')
        enable_founder_decisions = flag == '1'
    if type(enable_founder_decisions) is not bool:
        raise ValueError('The Founder decision route flag must be boolean.')
    if enable_model_showcase is None:
        flag = os.environ.get('RETURNOPS_MODEL_SHOWCASE','0')
        if flag not in {'0','1'}:
            raise ValueError('The model showcase flag must be 0 or 1.')
        enable_model_showcase = flag == '1'
    if type(enable_model_showcase) is not bool:
        raise ValueError('The model showcase flag must be boolean.')
    model_settings=None
    if enable_model_showcase:
        # A1.06 advisory showcase (docs/44): missing model settings fail startup.
        from .model_settings import ModelSettings
        model_settings=ModelSettings.from_environment()
    settings=Settings.from_environment() if engine is None else None
    @asynccontextmanager
    async def lifespan(app):
        actual=engine if engine is not None else build_engine(settings)
        app.state.engine=actual;app.state.auth_config=configured;app.state.intake_worker=None;app.state.investigation_worker=None
        app.state.proposal_worker=None
        app.state.coordinator_showcase=None;app.state.coordinator_facts=None
        app.state.upload_slots=BoundedSemaphore(2)
        try:
            if configured is not None and enable_processor:
                app.state.intake_worker=IntakeWorker(IntakeProcessor(actual))
                app.state.intake_worker.start()
                app.state.investigation_worker=IntakeWorker(InvestigationProcessor(actual))
                app.state.investigation_worker.start()
                if enable_fixed_proposal:
                    from returnops_domain.proposal_processor import FixedProposalProcessor
                    app.state.proposal_worker=IntakeWorker(FixedProposalProcessor(actual))
                    app.state.proposal_worker.start()
            if model_settings is not None:
                from returnops_domain.coordinator_showcase import (CoordinatorAnnotationStore,
                    CoordinatorShowcaseWorker, project_facts)
                store=CoordinatorAnnotationStore()
                app.state.coordinator_showcase=CoordinatorShowcaseWorker(actual,model_settings.transport(),store,
                    settings=model_settings.worker_settings())
                app.state.coordinator_facts=lambda uow,head:project_facts(uow,head,store)
                if configured is not None and enable_processor:
                    app.state.coordinator_showcase.start()
            yield
        finally:
            try:
                if app.state.proposal_worker is not None: app.state.proposal_worker.stop()
                if app.state.investigation_worker is not None: app.state.investigation_worker.stop()
                if app.state.intake_worker is not None: app.state.intake_worker.stop()
            finally:
                # Stopped last in its own try: stop() never waits for a model call.
                try:
                    if app.state.coordinator_showcase is not None: app.state.coordinator_showcase.stop()
                except Exception:
                    pass
            if engine is None: actual.dispose()
    app=FastAPI(title='ReturnOps AU',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    @app.get('/health/live')
    def live(): return {'status':'alive'}
    @app.get('/health/ready')
    def ready():
        healthy=readiness(app.state.engine)
        return JSONResponse({'status':'ready' if healthy else 'not_ready'},status_code=200 if healthy else 503)
    register_customer_routes(app)
    register_founder_routes(app)
    if enable_founder_decisions:
        # A2.07: the frozen decision POST, composed from trusted app state at
        # request time exactly like the Founder reads; HTTP fields confer nothing.
        from returnops_domain.errors import FlowError
        from .founder_decision_http import register_founder_decision_candidate
        from .private_founder_decision_http import compose_private_founder_decision_http
        def founder_decision_ports(authorization):
            if app.state.auth_config is None:
                raise FlowError()
            return compose_private_founder_decision_http(app.state.engine, app.state.auth_config)(authorization)
        register_founder_decision_candidate(app, founder_decision_ports)
    return app
