"""F.02 health-only API. NFR-006/008; docs/02 infrastructure view.

The fifteen planned /v1 business operations, authentication and Domain Service
are deliberately still unimplemented work packages, pending F.01 acceptance.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .database import build_engine, readiness
from .settings import Settings


def create_app() -> FastAPI:
    settings = Settings.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = build_engine(settings)
        app.state.engine = engine
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="ReturnOps AU environment",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        healthy = readiness(app.state.engine)
        return JSONResponse(
            {"status": "ready" if healthy else "not_ready"},
            status_code=200 if healthy else 503,
        )

    return app
