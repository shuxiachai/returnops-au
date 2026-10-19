"""Real schema-isolated PG17 and private test identities, shared with investigation."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from returnops_api.settings import require_environment_database

spec = importlib.util.spec_from_file_location('founder_investigation_fixture', Path(__file__).parents[1] / 'investigation/conftest.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
identities = shared.identities
enabled = shared.enabled


@pytest.fixture
def flow_engine(request):
    raw = os.environ.get('DATABASE_URL', '')
    require_environment_database(raw)
    schema = 'customer_test_' + uuid4().hex
    control = create_engine(raw, hide_parameters=True, echo=False)
    with control.begin() as connection:
        assert 170000 <= int(connection.execute(text('SHOW server_version_num')).scalar_one()) < 180000
        assert connection.execute(text('SELECT count(*) FROM pg_namespace WHERE nspname=:name'), {'name': schema}).scalar_one() == 0
        connection.execute(text('CREATE SCHEMA ' + schema))
    engine = create_engine(raw, hide_parameters=True, echo=False, pool_size=8, max_overflow=4,
        connect_args={'connect_timeout': 3, 'options': '-c search_path=' + schema + ' -c statement_timeout=10000'})
    engine._customer_test_schema = schema
    try:
        migrate(engine, getattr(request, 'param', 'head'))
        yield engine
    finally:
        engine.dispose()
        with control.begin() as connection:
            connection.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        control.dispose()


def migrate(engine, revision='head'):
    config = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, revision)
