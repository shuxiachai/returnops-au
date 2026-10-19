# F.02 / NFR-003/006/007. Official multi-platform manifest verified 2026-09-07.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS package-build

WORKDIR /build
COPY requirements-dev.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-dev.lock
COPY apps/api/ ./apps/api/
COPY packages/returnops_domain/ ./packages/returnops_domain/
RUN python -m pip wheel --no-deps --no-build-isolation --wheel-dir /wheels .

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock \
    && useradd --create-home --uid 10001 appuser

COPY --from=package-build /wheels/ /wheels/
RUN python -m pip install --no-cache-dir --no-deps /wheels/*.whl
COPY alembic.ini ./
COPY alembic/ ./alembic/
USER 10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "returnops_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
