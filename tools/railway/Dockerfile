# Railway image for the Week 13 demonstration (docs/46 section 9, docs/15 PD-03):
# the web build, the demo API and Caddy in one service; PostgreSQL is a separate
# Railway service. R.05.b; NFR-003/009. Base images pinned by digest on 30 October 2026.
FROM node:24-bookworm-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c AS web-build

WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/index.html apps/web/vite.config.ts apps/web/tsconfig.json apps/web/tsconfig.node.json apps/web/postcss.config.js apps/web/tailwind.config.js ./
COPY apps/web/public/ ./public/
COPY apps/web/src/ ./src/
# VITE_API_BASE_URL stays unset: the browser calls /v1 on the same origin, which Caddy proxies.
# Only the bundle: `npm run build` also type-checks the tests, which import contracts/ from the
# repository root; the CI web job runs that type check.
RUN npx --no-install vite build

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS package-build

WORKDIR /build
COPY requirements-dev.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-dev.lock
COPY apps/api/ ./apps/api/
COPY packages/returnops_domain/ ./packages/returnops_domain/
RUN python -m pip wheel --no-deps --no-build-isolation --wheel-dir /wheels .

FROM caddy:2-alpine@sha256:eb4d35b7452d1ab6171fbdbe8d9275b2301dad6dad92115d91e19fb9b24d510f AS caddy

FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -m 700 /app/private \
    && chown 10001 /app/private

COPY --from=package-build /wheels/ /wheels/
RUN python -m pip install --no-cache-dir --no-deps /wheels/*.whl
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
COPY --from=web-build /web/dist/ ./web/
COPY tools/railway/Caddyfile tools/railway/start.py ./
USER 10001
EXPOSE 8080
CMD ["python", "/app/start.py"]
