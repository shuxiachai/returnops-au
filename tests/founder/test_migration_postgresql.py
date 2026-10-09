"""Upgrade real accepted0005 records, including retained safe blocks, without rewrites."""
import pytest
from sqlalchemy import inspect, text
from returnops_domain import founder_tables as f
from returnops_domain import lifecycle_tables as lifecycle
from returnops_domain import preview_tables as preview
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
    after = business_fingerprints(flow_engine)
    added = {**lifecycle.metadata.tables, **preview.metadata.tables}
    assert {name: value for name,value in after.items() if name not in added} == before
    assert set(after)-set(before) == set(added)
    assert all(rows(flow_engine,table)==[] for table in added.values())
    assert len(rows(flow_engine, f.encodings)) == 1
    view = founder(flow_engine, identities).read('getFounderCase', original['case_id']).body
    assert view['order_lookup_block']['status'] == 'CONFLICT'
    assert bool(view['statements']) is (not remove)
    with flow_engine.connect() as connection:
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0009_preview_approval'
    assert business_fingerprints(flow_engine) == after
