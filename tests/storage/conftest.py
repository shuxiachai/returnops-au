"""Synthetic records and guarded real PostgreSQL fixtures."""

from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from returnops_api.settings import ConfigurationError, require_environment_database
from returnops_domain import InitialCaseRecord, InitialRecordBundle, OriginalStatementRecord, StatementContent


@pytest.fixture
def bundle_factory():
    def build(*, raw_text="  original\ntext\x00🙂 e\u0301 \ud800 \ud83d\ude00  ", reference=" order\x00\udfff "):
        suffix = uuid4().hex
        now = datetime(2026, 9, 26, 1, 2, 3, 456789, tzinfo=timezone.utc)
        case_id, statement_id = "case_" + suffix, "statement_" + suffix
        return InitialRecordBundle(
            InitialCaseRecord(case_id, "customer_test", "store_test", 1, 1, "SUBMITTED", now, now),
            OriginalStatementRecord(statement_id, case_id, "ORIGINAL", 1, 1, 1, now),
            StatementContent(statement_id, raw_text, "UNSPECIFIED", reference),
        )
    return build


@pytest.fixture
def pg_engine():
    secret_url = SecretStr(os.environ.get("DATABASE_URL", ""))
    try:
        require_environment_database(secret_url.get_secret_value())
    except ConfigurationError:
        pytest.fail("Storage tests require an explicitly configured disposable returnops_f02 PostgreSQL database", pytrace=False)
    engine = create_engine(secret_url.get_secret_value(), hide_parameters=True, echo=False, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SHOW server_version_num")).scalar_one()
            assert 170000 <= int(version) < 180000, "Storage acceptance requires PostgreSQL 17"
        yield engine
    finally:
        engine.dispose()
