"""Snapshot stability, live retention and query-bound opaque cursors."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import delete, select, update
from returnops_domain import customer_tables as t, founder_tables as f, investigation_tables as investigation
from returnops_domain.audit import identifier
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.retention import RetentionService
from founder_helpers import accepted, append_statements, business_fingerprints, founder, investigate, rows


def consume(flow, case_id, query):
    records = []
    while True:
        page = flow.read('listFounderCaseHistory', case_id, query).body
        records.extend(page['items'])
        if 'next_cursor' not in page:
            return records
        query = {**query, 'cursor': page['next_cursor']}


def test_126_records_six_windows_stable_append_filter_and_retention(flow_engine, identities):
    original = accepted(identities)
    case_id = original['case_id']
    append_statements(flow_engine, identities, case_id, 125)
    flow = founder(flow_engine, identities)
    view = flow.read('getFounderCase', case_id).body
    window = view['collection_windows']['statements']
    assert window['total_records'] == 126 and window['preview_count'] == 100 and window['truncated']
    assert view['statements'][0]['kind'] == 'ORIGINAL'
    query = {'kind': 'STATEMENT', 'cursor': window['start_cursor']}
    first = flow.read('listFounderCaseHistory', case_id, query).body
    assert [item['recorded_sequence'] for item in first['items']] == list(range(1, 21))
    with ThreadPoolExecutor(max_workers=1) as executor:
        later = executor.submit(append_statements, flow_engine, identities, case_id, 3).result(timeout=10)
    original_id = original['statements'][0]['statement_id']
    assert RetentionService(flow_engine).remove('STATEMENT', original_id)
    records = consume(flow, case_id, query)
    assert len(records) == len({r['record_id'] for r in records}) == 126
    assert [r['recorded_sequence'] for r in records] == list(range(1, 127))
    assert not {r['record_id'] for r in later} & {r['record_id'] for r in records}
    assert records[0]['content_sha256'] == first['items'][0]['content_sha256']
    assert records[0]['actor'] == first['items'][0]['actor']
    assert records[0]['retention_state'] == 'DELETED' and 'content' not in records[0]
    filtered = flow.read('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'object_id': original_id, 'object_version': 1}).body
    assert filtered['items'] == [records[0]]
    assert flow.read('getFounderCase', case_id).body['collection_windows']['statements']['unavailable_count'] == 1
    # All snapshot tables contain typed metadata only, never copied personal bodies.
    assert all(column.type.__class__.__name__ != 'LargeBinary' for table in f.metadata.tables.values() for column in table.columns)


def test_latest_deleted_revision_never_falls_back_to_old_available_body(flow_engine, identities):
    case_id = accepted(identities)['case_id']
    refs = append_statements(flow_engine, identities, case_id, 2, object_id='statement_revised')
    # Explicitly construct the storage boundary where only the latest revision
    # is unavailable; the current preview must not resurrect revision1.
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        uow.execute(delete(t.history_contents).where(t.history_contents.c.record_id == refs[1]['record_id']))
        uow.execute(update(t.history).where(t.history.c.record_id == refs[1]['record_id']).values(retention_state='DELETED', removal_reason='RETENTION_POLICY'))
        uow.commit()
    flow = founder(flow_engine, identities)
    view = flow.read('getFounderCase', case_id).body
    assert all(s['statement_id'] != 'statement_revised' for s in view['statements'])
    versions = flow.read('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'object_id': 'statement_revised'}).body['items']
    assert [r['object_version'] for r in versions] == [1, 2]
    assert 'content' in versions[0] and 'content' not in versions[1]


def test_list_membership_and_summary_stay_frozen_while_cases_progress(flow_engine, identities):
    originals = [accepted(identities, reference='SYN-1001', key='list-case-' + str(index)) for index in range(7)]
    flow = founder(flow_engine, identities)
    first = flow.read('listFounderCases', query={'limit': 2}).body
    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(IntakeProcessor(flow_engine).run_once).result(timeout=10)
        later = executor.submit(accepted, identities, key='list-later-case').result(timeout=10)
    result = first['items'][:]
    page = first
    while 'next_cursor' in page:
        page = flow.read('listFounderCases', query={'limit': 2, 'cursor': page['next_cursor']}).body
        result.extend(page['items'])
    assert [item['case_id'] for item in result] == [item['case_id'] for item in originals]
    assert len(result) == len({r['case_id'] for r in result}) == 7
    assert all(item['status'] == 'SUBMITTED' and item['case_version'] == 1 for item in result)
    current = flow.read('listFounderCases').body['items']
    assert len(current) == 8 and later['case_id'] in {r['case_id'] for r in current}
    assert current[0]['status'] == 'UNDER_INVESTIGATION'


def test_126_audit_events_exact_chain_frozen_while_new_events_append(flow_engine, identities):
    case_id = accepted(identities)['case_id']
    append_statements(flow_engine, identities, case_id, 125)
    flow = founder(flow_engine, identities)
    first = flow.read('listCaseAudit', case_id, {'limit': 17}).body
    append_statements(flow_engine, identities, case_id, 2)
    result = first['items'][:]
    page = first
    while 'next_cursor' in page:
        page = flow.read('listCaseAudit', case_id, {'limit': 17, 'cursor': page['next_cursor']}).body
        result.extend(page['items'])
    assert len(result) == len({e['event_id'] for e in result}) == 126
    assert 'previous_event_hash' not in result[0]
    assert all(item['previous_event_hash'] == previous['event_hash'] for previous, item in zip(result, result[1:]))
    history = {r['record_id']: r for r in consume(flow, case_id, {'kind': 'STATEMENT'})}
    for event in result:
        for ref in event['history_refs']:
            assert all(ref[key] == history[ref['record_id']][key] for key in ('record_id', 'kind', 'object_id', 'object_version'))


def test_cursors_bound_to_purpose_case_kind_filter_limit_principal_and_customer_namespace(flow_engine, identities):
    case_id = accepted(identities)['case_id']
    second = accepted(identities, key='second-case')['case_id']
    append_statements(flow_engine, identities, case_id, 3)
    flow = founder(flow_engine, identities)
    view = flow.read('getFounderCase', case_id).body
    token = view['collection_windows']['statements']['start_cursor']
    before = business_fingerprints(flow_engine)
    invalid = [
        ('listFounderCaseHistory', second, {'kind': 'STATEMENT', 'cursor': token}),
        ('listFounderCaseHistory', case_id, {'kind': 'EVIDENCE', 'cursor': token}),
        ('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'cursor': token, 'limit': 1}),
        ('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'cursor': token, 'object_id': 'statement_absent'}),
        ('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'cursor': token[:-1] + ('A' if token[-1] != 'A' else 'B')}),
        ('listFounderCases', None, {'cursor': token}),
        ('listCaseAudit', case_id, {'cursor': token}),
        ('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'cursor': accepted_cursor(identities, case_id)}),
    ]
    listing = flow.read('listFounderCases', query={'limit': 1}).body['next_cursor']
    audit = flow.read('listCaseAudit', case_id, {'limit': 1}).body['next_cursor']
    invalid += [('listCaseAudit', case_id, {'cursor': listing, 'limit': 1}),
                ('listFounderCases', None, {'cursor': audit, 'limit': 1})]
    for operation, target, query in invalid:
        with pytest.raises(FlowError) as error:
            flow.read(operation, target, query)
        assert error.value.code == 'INVALID_STATE'
    with pytest.raises(FlowError) as error:
        identities.flow().history(case_id, {'kind': 'STATEMENT', 'cursor': token})
    assert error.value.code == 'INVALID_STATE'
    # Change another genuine registry principal to Founder; token doesn't carry role.
    from returnops_domain.registry import TrustedRegistry
    TrustedRegistry(flow_engine).change_principal(identities.people['customer_b']['principal_id'], role='FOUNDER')
    with pytest.raises(FlowError) as error:
        founder(flow_engine, identities, 'customer_b').read('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'cursor': token})
    assert error.value.code == 'INVALID_STATE'
    filtered = flow.read('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'limit': 1}).body
    with pytest.raises(FlowError) as error:
        flow.read('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'limit': 1,
            'cursor': filtered['next_cursor'], 'object_id': 'statement_absent', 'object_version': 1})
    assert error.value.code == 'INVALID_STATE'


def accepted_cursor(identities, case_id):
    return identities.flow().get_case(case_id).body['collection_windows']['statements']['start_cursor']


def test_expired_cursor_and_expiry_during_read_roll_back_metadata(flow_engine, identities):
    case_id = accepted(identities)['case_id']
    now = datetime.now(timezone.utc)
    token = founder(flow_engine, identities, clock=lambda: now, snapshot_ttl=1).read('getFounderCase', case_id).body['collection_windows']['statements']['start_cursor']
    later = founder(flow_engine, identities, clock=lambda: now + timedelta(seconds=2))
    with pytest.raises(FlowError) as error:
        later.read('listFounderCaseHistory', case_id, {'kind': 'STATEMENT', 'cursor': token})
    assert error.value.code == 'INVALID_STATE'
    count = len(rows(flow_engine, f.snapshots))
    clock = iter([now, now + timedelta(seconds=2)])
    with pytest.raises(FlowError) as error:
        founder(flow_engine, identities, clock=lambda: next(clock), snapshot_ttl=1).read('getFounderCase', case_id)
    assert error.value.code == 'INVALID_STATE' and len(rows(flow_engine, f.snapshots)) == count


@pytest.mark.parametrize('reference', ['SYN-1001', 'SYN-CONFLICT'])
def test_retention_removes_projection_keeps_safe_block_without_restoring_lookup_body(flow_engine, identities, enabled, reference):
    original = investigate(flow_engine, identities, reference)
    case_id = original['case_id']
    flow = founder(flow_engine, identities)
    before = flow.read('getFounderCase', case_id).body
    if reference == 'SYN-CONFLICT':
        block_before = flow.read('listFounderCaseHistory', case_id, {'kind': 'ORDER_LOOKUP_BLOCK'}).body['items'][0]
    assert RetentionService(flow_engine).remove('STATEMENT', original['statements'][0]['statement_id'])
    baseline = business_fingerprints(flow_engine)
    after = flow.read('getFounderCase', case_id).body
    assert after['statements'] == [] and after['input_version'] == before['input_version']
    assert 'order_snapshot' not in after and rows(flow_engine, investigation.receipt_contents) == []
    if reference == 'SYN-CONFLICT':
        assert after['order_lookup_block'] == before['order_lookup_block']
        block_after = flow.read('listFounderCaseHistory', case_id, {'kind': 'ORDER_LOOKUP_BLOCK'}).body['items'][0]
        assert block_after == block_before
    assert business_fingerprints(flow_engine) == baseline
