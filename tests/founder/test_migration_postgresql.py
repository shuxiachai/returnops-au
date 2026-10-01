"""Upgrade real accepted0005 records, including retained safe blocks, without rewrites."""
import pytest
from sqlalchemy import inspect, text
from returnops_domain import founder_tables as f
from returnops_domain.retention import RetentionService
from conftest import migrate
from founder_helpers import business_fingerprints, founder, investigate, rows


@pytest.mark.parametrize('flow_engine', ['0005_order_investigation'], indirect=True)
@pytest.mark.parametrize('remove', [False, True])
def test_real_0005_upgrade_and_repeat_preserve_all_existing_business_bytes(flow_engine, identities, enabled, remove):
    original = investigate(flow_engine, identities, 'SYN-CONFLICT')
    if remove:
        RetentionService(flow_engine).remove('STATEMENT', original['statements'][0]['statement_id'])
    before = business_fingerprints(flow_engine)
    assert not set(f.metadata.tables) & set(inspect(flow_engine).get_table_names())
    migrate(flow_engine)
    migrate(flow_engine)
    assert business_fingerprints(flow_engine) == before
    assert len(rows(flow_engine, f.encodings)) == 1
    view = founder(flow_engine, identities).read('getFounderCase', original['case_id']).body
    assert view['order_lookup_block']['status'] == 'CONFLICT'
    assert bool(view['statements']) is (not remove)
    with flow_engine.connect() as connection:
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0006_founder_reads'
    assert business_fingerprints(flow_engine) == before
