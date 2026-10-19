"""Public Founder reads over actual accepted investigation data and strict inputs."""
import pytest
from fastapi.testclient import TestClient
from returnops_api.main import create_app
from returnops_domain import customer_tables as t, investigation_tables as investigation
from returnops_domain.canonical import digest
from returnops_domain.mock_orders import load_builtin_catalogue
from returnops_domain.order_ports import OrderSourceUnavailable
from returnops_domain.wire import validate
from founder_helpers import accepted, business_fingerprints, founder, investigate, rows


class BrokenSource:
    metadata = load_builtin_catalogue().metadata
    def read_matches(self, *args):
        raise OrderSourceUnavailable()


@pytest.mark.parametrize('outcome', ['MATCHED', 'NOT_FOUND', 'CONFLICT', 'AUTHORITY_DENIED', 'PROVIDER_FAILURE'])
def test_four_public_reads_actual_five_outcomes_without_business_writes(flow_engine, identities, enabled, outcome):
    if outcome == 'AUTHORITY_DENIED':
        enabled.grant('synthetic_au_store', 'synthetic_commerce', can_read=False)
    reference = {'MATCHED': 'SYN-1001', 'CONFLICT': 'SYN-CONFLICT'}.get(outcome, 'missing')
    original = investigate(flow_engine, identities, reference, catalogue=BrokenSource() if outcome == 'PROVIDER_FAILURE' else None)
    case_id = original['case_id']
    before = business_fingerprints(flow_engine)
    app = create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False)
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer ' + identities.tokens['founder']}
        urls = [('/v1/founder/cases', 'CaseList'), ('/v1/founder/cases/' + case_id, 'CaseView'),
                ('/v1/founder/cases/' + case_id + '/history?kind=STATEMENT', 'FounderHistoryPage'),
                ('/v1/founder/cases/' + case_id + '/audit', 'AuditPage')]
        bodies = []
        for url, oracle in urls:
            response = client.get(url, headers=headers)
            assert response.status_code == 200, response.text
            validate(oracle, response.json(), internal=True)
            assert response.headers['cache-control'] == 'no-store'
            assert response.headers['x-correlation-id']
            bodies.append(response.json())
        listing, detail, history, audit = bodies
        assert listing['items'][0]['issue_category'] == 'UNCLEAR'
        assert 'current_risk_outcome' not in listing['items'][0]
        assert not {'facts', 'current_proposal', 'current_review', 'action_preview'} & detail.keys()
        assert detail['statements'] == original['statements'] and detail['cited_passages'] == []
        assert history['items'][0]['actor'] == {'kind': 'HUMAN', 'role': 'CUSTOMER', 'principal_id': identities.people['customer_a']['principal_id']}
        for field, window in detail['collection_windows'].items():
            page = client.get('/v1/founder/cases/' + case_id + '/history', headers=headers,
                              params={'kind': window['kind'], 'cursor': window['start_cursor']})
            assert page.status_code == 200
            assert page.json()['snapshot_id'] == window['snapshot_id']
            assert page.json()['snapshot_case_version'] == detail['case_version']
            if field not in {'statements', 'evidence'}:
                assert detail[field] == page.json()['items'] == [] and window['total_records'] == 0
        assert len({w['snapshot_id'] for w in detail['collection_windows'].values()}) == 1
        if outcome == 'MATCHED':
            assert detail['order_snapshot']['snapshot_id'] == 'synthetic_snapshot_1001'
            assert detail['input_version'] == 2 and detail['status'] == 'POLICY_ASSESSMENT'
        elif outcome == 'NOT_FOUND':
            assert detail['status'] == 'AWAITING_INFORMATION' and len(detail['clarification']['questions']) == 2
        elif outcome in {'CONFLICT', 'AUTHORITY_DENIED'}:
            assert detail['order_lookup_block']['status'] == outcome
            page = client.get('/v1/founder/cases/' + case_id + '/history', headers=headers, params={'kind': 'ORDER_LOOKUP_BLOCK'}).json()
            item = page['items'][0]
            assert item['content']['block'] == detail['order_lookup_block']
            assert item['content']['order_lookup']['status'] == outcome
            assert item['content_sha256'] == digest(item['content'], 'history/v1')
            raw_history = next(r for r in rows(flow_engine, t.history) if r['kind'] == 'ORDER_LOOKUP_BLOCK')
            assert item['content_sha256'] != raw_history['content_sha256']
            assert item['actor']['kind'] == 'SERVICE'
        else:
            assert detail['processing_failure']['stage'] == 'ORDER_LOOKUP'
            page = client.get('/v1/founder/cases/' + case_id + '/history', headers=headers, params={'kind': 'PROCESSING_FAILURE'}).json()
            assert page['items'][0]['content'] == detail['processing_failure']
        assert any(event['event_type'] == 'ORDER_INVESTIGATION_ACCEPTED' for event in audit['items'])
    assert business_fingerprints(flow_engine) == before


@pytest.mark.parametrize('kind', ['STATEMENT', 'EVIDENCE', 'PROPOSAL', 'REVIEW', 'DECISION', 'APPROVAL', 'OPERATION', 'NOTIFICATION', 'PROCESSING_FAILURE', 'ORDER_LOOKUP_BLOCK'])
def test_all_frozen_history_kinds_with_exact_absent_object_filter(flow_engine, identities, kind):
    original = accepted(identities)
    body = founder(flow_engine, identities).read('listFounderCaseHistory', original['case_id'],
        {'kind': kind, 'object_id': 'object_absent', 'object_version': 1}).body
    assert body['items'] == [] and body['object_id'] == 'object_absent' and body['object_version'] == 1
    validate('FounderHistoryPage', body, internal=True)


@pytest.mark.parametrize('suffix', ['?kind=ORDER_LOOKUP', '?kind=ORDER_SNAPSHOT', '?kind=OUTCOME_MESSAGE',
    '?kind=STATEMENT&kind=EVIDENCE', '?kind=STATEMENT&role=FOUNDER', '?kind=STATEMENT&store_id=synthetic_au_store',
    '?kind=STATEMENT&object_version=1', '?kind=STATEMENT&limit=0', '?kind=STATEMENT&limit=101',
    '?kind=STATEMENT&limit=1.5', '?kind=STATEMENT&limit=1e99', '?kind=STATEMENT&cursor=bad%20cursor'])
def test_history_rejects_noncontract_parameters(flow_engine, identities, suffix):
    case_id = accepted(identities)['case_id']
    with TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False)) as client:
        response = client.get('/v1/founder/cases/' + case_id + '/history' + suffix,
                              headers={'Authorization': 'Bearer ' + identities.tokens['founder']})
        assert response.status_code == 422 and response.json()['error']['code'] == 'VALIDATION_ERROR'
        assert response.headers['x-correlation-id'] == response.json()['error']['correlation_id']


def test_list_detail_audit_query_shapes_and_denied_operations(flow_engine, identities):
    case_id = accepted(identities)['case_id']
    with TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False)) as client:
        headers = {'Authorization': 'Bearer ' + identities.tokens['founder']}
        for path in ['/v1/founder/cases?status=SUBMITTED', '/v1/founder/cases?limit=1&limit=2',
                     '/v1/founder/cases/' + case_id + '?cursor=abc', '/v1/founder/cases/' + case_id + '/audit?kind=STATEMENT']:
            assert client.get(path, headers=headers).status_code == 422
        assert client.get('/v1/founder/cases?limit=1e0', headers=headers).status_code == 200
        assert client.post('/v1/founder/cases/' + case_id + '/decisions', headers=headers, json={}).status_code == 404
        assert client.get('/v1/founder/analytics', headers=headers).status_code == 404
