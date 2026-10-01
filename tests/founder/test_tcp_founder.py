"""Actual TCP across independent API processes, using persisted Founder cursors."""
import base64
import importlib.util
import json
from pathlib import Path
import sys
import httpx
from returnops_api.demo import _require_private_output_runtime
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from founder_helpers import accepted, append_statements, business_fingerprints, investigate

# Reuse the established process harness without importing another test suite's
# unqualified test helper. The process itself imports this candidate via PYTHONPATH.
spec = importlib.util.spec_from_file_location('founder_tcp_harness', Path(__file__).with_name('tcp_support.py'))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


def test_tcp_four_routes_restart_snapshot_retention_and_five_outcomes(flow_engine, identities, enabled, tmp_path):
    from test_queries_postgresql import BrokenSource
    from returnops_domain.retention import RetentionService
    _require_private_output_runtime()
    examples = []
    for reference in ['SYN-1001', 'missing', 'SYN-CONFLICT']:
        examples.append(investigate(flow_engine, identities, reference, key='tcp-' + reference))
    enabled.grant('synthetic_au_store', 'synthetic_commerce', can_read=False)
    examples.append(investigate(flow_engine, identities, key='tcp-denied'))
    enabled.grant('synthetic_au_store', 'synthetic_commerce', can_read=True)
    examples.append(investigate(flow_engine, identities, key='tcp-failure', catalogue=BrokenSource()))
    case_id = examples[0]['case_id']
    append_statements(flow_engine, identities, case_id, 101)
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    auth = private / 'auth.json'
    auth.write_text(json.dumps({'issuer': identities.auth_config.issuer, 'audience': identities.auth_config.audience,
        'signing_key_base64': base64.b64encode(identities.auth_config.signing_key).decode('ascii')}), encoding='utf-8')
    headers = {'Authorization': 'Bearer ' + identities.tokens['founder']}
    baseline = business_fingerprints(flow_engine)
    logs = [tmp_path / ('founder-api-' + str(i) + '.log') for i in range(2)]
    with harness.api_process(flow_engine, auth, logs[0]) as (url, first_pid):
        with httpx.Client(base_url=url, headers=headers, timeout=10) as client:
            listing = client.get('/v1/founder/cases')
            assert listing.status_code == 200 and len(listing.json()['items']) == 5
            for index, original in enumerate(examples):
                response = client.get('/v1/founder/cases/' + original['case_id'])
                assert response.status_code == 200
                detail = response.json()
                assert detail['status'] == ['POLICY_ASSESSMENT', 'AWAITING_INFORMATION', 'ESCALATED', 'ESCALATED', 'ESCALATED'][index]
                assert client.get('/v1/founder/cases/' + original['case_id'] + '/audit').status_code == 200
            first = client.get('/v1/founder/cases/' + case_id + '/history', params={'kind': 'STATEMENT'}).json()
            assert len(first['items']) == 20 and 'next_cursor' in first
    assert business_fingerprints(flow_engine) == baseline
    RetentionService(flow_engine).remove('STATEMENT', examples[0]['statements'][0]['statement_id'])
    baseline = business_fingerprints(flow_engine)
    with harness.api_process(flow_engine, auth, logs[1]) as (url, second_pid):
        assert first_pid != second_pid
        with httpx.Client(base_url=url, headers=headers, timeout=10) as client:
            records = first['items'][:]
            cursor = first['next_cursor']
            while True:
                response = client.get('/v1/founder/cases/' + case_id + '/history', params={'kind': 'STATEMENT', 'cursor': cursor})
                assert response.status_code == 200
                page = response.json()
                assert page['snapshot_id'] == first['snapshot_id']
                records.extend(page['items'])
                if 'next_cursor' not in page:
                    break
                cursor = page['next_cursor']
            assert len(records) == len({record['record_id'] for record in records}) == 102
            detail = client.get('/v1/founder/cases/' + case_id).json()
            assert 'order_snapshot' not in detail
            tombstone = client.get('/v1/founder/cases/' + case_id + '/history', params={'kind': 'STATEMENT',
                'object_id': examples[0]['statements'][0]['statement_id']}).json()['items'][0]
            assert tombstone['retention_state'] == 'DELETED' and 'content' not in tombstone
            assert client.get('/v1/founder/cases', headers={'Authorization': 'Bearer ' + identities.tokens['customer_a']}).status_code == 403
            assert client.get('/v1/founder/cases/' + case_id + '/history', params={'kind': 'STATEMENT', 'cursor': cursor, 'limit': 1}).status_code == 409
    assert business_fingerprints(flow_engine) == baseline
    raw = b''.join(path.read_bytes() for path in logs)
    for token in identities.tokens.values():
        assert token.encode() not in raw
    assert base64.b64encode(identities.auth_config.signing_key) not in raw
    assert b'synthetic original' not in raw
