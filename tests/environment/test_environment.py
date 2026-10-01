"""F.02 environment checks, not case/approval/provider acceptance.

Trace: NFR-003/006/007/008; docs/02 architecture and docs/10 environment plan.
The real-PostgreSQL tests require an explicitly injected DATABASE_URL. They do
not skip when configuration is absent and never edit the public version table.
Failure cases below use isolated doubles, not mutations of the shared database.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

from returnops_api import database, main
from returnops_api.settings import ConfigurationError, Settings, require_environment_database


EXPECTED_REVISION = "0006_founder_reads"
EXPECTED_TABLES = ['accepted_order_contents', 'accepted_order_projections', 'alembic_version', 'case_heads', 'case_investigation_state', 'case_records', 'customer_acceptances', 'customer_audit_events', 'customer_clarification_sets', 'customer_evidence', 'customer_evidence_contents', 'customer_history_contents', 'customer_history_cursors', 'customer_history_revisions', 'customer_history_snapshots', 'customer_intake_sessions', 'customer_intake_work', 'customer_principals', 'customer_processing_failures', 'customer_receipt_refs', 'customer_receipts', 'customer_scope_audit_events', 'customer_scope_audit_heads', 'customer_sessions', 'discarded_order_invocations', 'founder_history_encodings', 'founder_list_members', 'founder_read_cursors', 'founder_read_snapshots', 'investigation_clarification_inputs', 'investigation_inputs', 'investigation_policy_events', 'investigation_provider_grants', 'investigation_question_groups', 'investigation_services', 'investigation_work', 'order_lookup_blocks', 'order_lookup_contents', 'order_lookup_receipts', 'original_statement_contents', 'original_statement_records']
SECRET = "environment-test-secret-do-not-log"
STUB_URL = f"postgresql+psycopg://environment_user:{SECRET}@stub.invalid/environment"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class ScalarValues:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def all(self) -> list[Any]:
        return list(self.values)

    def __iter__(self) -> Iterator[Any]:
        return iter(self.values)


class QueryResult:
    """Minimal SQLAlchemy result protocol for the two read-only health queries."""

    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def scalar(self) -> Any:
        return self.values[0] if self.values else None

    def scalar_one(self) -> Any:
        assert len(self.values) == 1
        return self.values[0]

    def scalars(self) -> ScalarValues:
        return ScalarValues(self.values)

    def all(self) -> list[tuple[Any]]:
        return [(value,) for value in self.values]

    def fetchall(self) -> list[tuple[Any]]:
        return self.all()

    def __iter__(self) -> Iterator[tuple[Any]]:
        return iter(self.all())


class DiagnosticConnection:
    def __init__(self, engine: DiagnosticEngine) -> None:
        self.engine = engine

    def __enter__(self) -> DiagnosticConnection:
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    def execute(self, statement: Any, *args: Any, **kwargs: Any) -> QueryResult:
        sql = " ".join(str(statement).upper().split())
        self.engine.statements.append(sql)
        # A readiness request must not migrate, stamp or write application data.
        assert sql.startswith("SELECT "), f"Non-read-only health query: {sql}"
        if "ALEMBIC_VERSION" in sql:
            if self.engine.failure == "revision":
                raise SQLAlchemyError(f"Version query failed: {STUB_URL}")
            return QueryResult(list(self.engine.revisions))
        assert sql == "SELECT 1", f"Unexpected health query: {sql}"
        if self.engine.failure == "probe":
            raise SQLAlchemyError(f"Probe query failed: {STUB_URL}")
        return QueryResult([1])


class DiagnosticEngine:
    """No network or real database; each test owns its query observations."""

    def __init__(
        self,
        revisions: tuple[str, ...] = (EXPECTED_REVISION,),
        failure: str | None = None,
    ) -> None:
        self.revisions = revisions
        self.failure = failure
        self.statements: list[str] = []
        self.disposed = False

    def connect(self) -> DiagnosticConnection:
        if self.failure == "connect":
            raise SQLAlchemyError(f"Connection failed: {STUB_URL}")
        return DiagnosticConnection(self)

    def dispose(self) -> None:
        self.disposed = True


def application_with_engine(
    monkeypatch: pytest.MonkeyPatch, engine: DiagnosticEngine
) -> Any:
    monkeypatch.setenv("DATABASE_URL", STUB_URL)
    monkeypatch.setattr(main, "build_engine", lambda settings: engine)
    return main.create_app()


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        f"not-a-database-url-{SECRET}",
        f"sqlite:///{SECRET}",
        f"postgresql://environment_user:{SECRET}@stub.invalid/environment",
        f"postgresql+psycopg://environment_user:{SECRET}@/environment",
        f"postgresql+psycopg://environment_user:{SECRET}@stub.invalid",
        f"postgresql+psycopg://environment_user:{SECRET}@stub.invalid/",
        f"postgresql+psycopg://environment_user:{SECRET}@stub.invalid:bad/environment",
    ],
    ids=[
        "missing", "empty", "malformed", "sqlite", "wrong-driver",
        "no-host", "no-db", "empty-db", "invalid-port",
    ],
)
def test_invalid_configuration_is_explicit_and_masks_url(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, url: str | None
) -> None:
    if url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(ConfigurationError) as caught:
        main.create_app()
    assert str(caught.value), "Configuration failure needs an actionable safe message"
    for output in (str(caught.value), repr(caught.value), caplog.text):
        assert SECRET not in output
        assert "environment_user" not in output
        assert "stub.invalid" not in output
        if url:
            assert url not in output


def test_valid_settings_do_not_disclose_url_in_normal_representations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", STUB_URL)
    settings = Settings.from_environment()
    for output in (str(settings), repr(settings), settings.model_dump_json()):
        assert SECRET not in output
        assert STUB_URL not in output


def test_liveness_survives_database_outage_and_engine_is_disposed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = DiagnosticEngine(failure="connect")
    app = application_with_engine(monkeypatch, engine)
    with TestClient(app) as client:
        assert app.state.engine is engine
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}
        assert not engine.disposed
    assert engine.disposed


def test_readiness_accepts_only_the_expected_single_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert database.EXPECTED_SCHEMA_REVISION == EXPECTED_REVISION
    engine = DiagnosticEngine()
    app = application_with_engine(monkeypatch, engine)
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
    assert "SELECT 1" in engine.statements
    assert any("ALEMBIC_VERSION" in sql for sql in engine.statements)
    assert engine.disposed


@pytest.mark.parametrize(
    "revisions",
    [(), ("0001_environment",), ("9999_unexpected",), (EXPECTED_REVISION, "0000_other")],
    ids=["unversioned", "old", "unexpected", "multiple-heads"],
)
def test_readiness_rejects_invalid_revision_sets(
    monkeypatch: pytest.MonkeyPatch, revisions: tuple[str, ...]
) -> None:
    engine = DiagnosticEngine(revisions=revisions)
    app = application_with_engine(monkeypatch, engine)
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}
    assert engine.disposed


@pytest.mark.parametrize("failure", ["connect", "probe", "revision"])
def test_database_failures_return_503_without_disclosing_configuration(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure: str,
) -> None:
    engine = DiagnosticEngine(failure=failure)
    app = application_with_engine(monkeypatch, engine)
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}
        assert client.get("/health/live").json() == {"status": "alive"}
    for output in (response.text, caplog.text):
        assert SECRET not in output
        assert STUB_URL not in output
    assert engine.disposed


def test_environment_app_has_only_frozen_customer_and_founder_reads_and_no_identity_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = application_with_engine(monkeypatch, DiagnosticEngine())
    assert {route.path for route in app.routes} == {"/health/live", "/health/ready", "/v1/session", "/v1/evidence",
        "/v1/evidence/{evidence_id}/content", "/v1/cases", "/v1/cases/{case_id}",
        "/v1/cases/{case_id}/history", "/v1/cases/{case_id}/clarifications",
        "/v1/founder/cases", "/v1/founder/cases/{case_id}",
        "/v1/founder/cases/{case_id}/history", "/v1/founder/cases/{case_id}/audit"}
    with TestClient(app) as client:
        for path in ("/docs", "/redoc", "/openapi.json", "/v1/login", "/v1/founder/analytics"):
            assert client.get(path).status_code == 404
        assert client.get("/v1/session").status_code == 503  # no configured key/default identity
        assert client.get("/v1/founder/cases").status_code == 503


@pytest.fixture
def real_database_url() -> SecretStr:
    value = os.environ.get("DATABASE_URL")
    if not value:
        pytest.fail("Real PostgreSQL checks require an explicitly injected DATABASE_URL")
    if "?" in value or "#" in value:
        pytest.fail(
            "Environment DATABASE_URL must not contain query parameters or fragments",
            pytrace=False,
        )
    try:
        parsed = make_url(value)
    except Exception:
        pytest.fail("DATABASE_URL must be a valid PostgreSQL psycopg URL", pytrace=False)
    if parsed.drivername != "postgresql+psycopg" or not parsed.host or not parsed.database:
        pytest.fail("DATABASE_URL requires PostgreSQL psycopg, host and database", pytrace=False)
    try:
        require_environment_database(value)
    except ConfigurationError:
        pytest.fail(
            "Environment integration checks require a dedicated returnops_f02 or "
            "returnops_f02_* database; refusing to use another database",
            pytrace=False,
        )
    # pytest can display fixture arguments in failure reports. Preserve the
    # secret wrapper so the configured DSN is not printed in those reports.
    return SecretStr(value)


def test_expected_revision_matches_the_only_migration_head() -> None:
    scripts = ScriptDirectory.from_config(Config(str(REPOSITORY_ROOT / "alembic.ini")))
    assert scripts.get_heads() == [database.EXPECTED_SCHEMA_REVISION]


@pytest.mark.parametrize("target", [
    "unrelated", "returnops_f02?dbname=unrelated", "returnops_f02#fragment",
    "returnops_f02_UPPER", "returnops_f02_" + "x" * 64,
])
def test_direct_alembic_rejects_wrong_database_before_connection(target: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = (
        f"postgresql+psycopg://unused:{SECRET}@127.0.0.1:1/{target}"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
        cwd=REPOSITORY_ROOT, env=environment, capture_output=True, text=True,
        timeout=10, check=False,
    )
    assert result.returncode != 0
    assert "F.02 migration requires a dedicated" in result.stderr
    assert SECRET not in result.stdout + result.stderr


@pytest.fixture
def real_engine(real_database_url: SecretStr) -> Iterator[Engine]:
    engine = create_engine(
        real_database_url.get_secret_value(),
        connect_args={"connect_timeout": 3},
        hide_parameters=True,
        echo=False,
    )
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.database
def test_real_postgresql_is_connected_and_at_the_environment_revision(
    real_engine: Engine,
) -> None:
    assert database.readiness(real_engine), "Configured PostgreSQL is not at the expected revision"
    with real_engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
        revisions = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalars().all()
    assert revisions == [EXPECTED_REVISION]


@pytest.mark.database
def test_real_application_readiness(real_database_url: SecretStr) -> None:
    # The fixture validates that this is an explicitly configured real database.
    app = main.create_app()
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        response = client.get("/health/ready")
        assert response.status_code == 200, "Real application database readiness failed"
        assert response.json() == {"status": "ready"}


@pytest.mark.database
def test_repeat_upgrade_head_preserves_the_exact_initial_record_schema(
    real_database_url: SecretStr, real_engine: Engine,
) -> None:
    # The URL fixture enforces the dedicated database name before Alembic runs.
    # Initial empty-database migration is a separate startup check. Here both
    # invocations deliberately repeat upgrade on that already-initialised DB.
    assert sorted(inspect(real_engine).get_table_names(schema="public")) == EXPECTED_TABLES, "Refusing migration checks against an unexpected schema"
    assert database.readiness(real_engine), "Migrate the dedicated environment DB first"
    configuration = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    for _ in range(2):
        command.upgrade(configuration, "head")
        assert database.readiness(real_engine)
        assert sorted(inspect(real_engine).get_table_names(schema="public")) == EXPECTED_TABLES


@pytest.mark.database
def test_temporary_table_transaction_rolls_back_without_public_writes(
    real_engine: Engine,
) -> None:
    # real_engine depends on the dedicated-name URL guard. TEMP lives only in
    # this session; even its creation is rolled back, including assertion errors.
    with real_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(
                "CREATE TEMP TABLE returnops_f02_txn_probe (value INTEGER) ON COMMIT DROP"
            ))
            connection.execute(text("INSERT INTO returnops_f02_txn_probe VALUES (1)"))
            assert connection.execute(
                text("SELECT value FROM returnops_f02_txn_probe")
            ).scalar_one() == 1
        finally:
            transaction.rollback()
        assert connection.execute(text(
            "SELECT to_regclass('pg_temp.returnops_f02_txn_probe') IS NULL"
        )).scalar_one() is True
