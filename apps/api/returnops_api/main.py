"""Health diagnostics and the seven frozen customer operations."""
from contextlib import asynccontextmanager
from threading import BoundedSemaphore
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from returnops_domain.intake_processor import IntakeProcessor,IntakeWorker
from .database import build_engine,readiness
from .settings import Settings
from .customer_config import load_private_auth_config
from .customer_http import register_customer_routes

def create_app(*,engine=None,auth_config=None,enable_processor=True):
    # Keyword injection is trusted Python composition for tests, never HTTP input.
    configured=auth_config if auth_config is not None else load_private_auth_config()
    settings=Settings.from_environment() if engine is None else None
    @asynccontextmanager
    async def lifespan(app):
        actual=engine if engine is not None else build_engine(settings)
        app.state.engine=actual;app.state.auth_config=configured;app.state.intake_worker=None
        app.state.upload_slots=BoundedSemaphore(2)
        try:
            if configured is not None and enable_processor:
                app.state.intake_worker=IntakeWorker(IntakeProcessor(actual))
                app.state.intake_worker.start()
            yield
        finally:
            if app.state.intake_worker is not None: app.state.intake_worker.stop()
            if engine is None: actual.dispose()
    app=FastAPI(title='ReturnOps AU',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    @app.get('/health/live')
    def live(): return {'status':'alive'}
    @app.get('/health/ready')
    def ready():
        healthy=readiness(app.state.engine)
        return JSONResponse({'status':'ready' if healthy else 'not_ready'},status_code=200 if healthy else 503)
    register_customer_routes(app)
    return app
