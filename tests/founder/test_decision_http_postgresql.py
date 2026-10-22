"""A2.07: the public Founder decision POST over actual PostgreSQL state.

HTTP -> founder_decision_http -> private composition -> the existing approve,
reject, revision and manual Domain services. Cases are prepared with the
existing lifecycle test helpers (retained PASS review, server-owned preview,
accepted ESCALATE, investigation failure and order-lookup block). The boundary
must accept exactly once per original key, deny stale or wrong-scope requests
before any business effect, and never let client fields confer authority.
docs/08 A2.07; FR-009/FR-010/FR-012; NFR-002/NFR-004/NFR-006.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from returnops_api.main import create_app
from returnops_domain import customer_tables as old
from returnops_domain.canonical import decode_document
from returnops_domain.scope_audit import events as scope_events, heads as scope_heads
from returnops_domain.wire import validate

# The decision prerequisites are the lifecycle component helpers; this module
# shares their fixtures (founder/conftest is what lifecycle/conftest re-exports).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lifecycle'))
import approve_helpers, reject_helpers, revision_helpers, manual_helpers  # noqa: E402
from manual_helpers import rows, snapshot  # noqa: E402
from pass_revision_helpers import business_snapshot  # noqa: E402

def _accepted(receipt):
    # The lifecycle assertion helpers read the service result, receipt included;
    # over HTTP that receipt is the validated 202 body.
    return SimpleNamespace(status='ACCEPTED', safe_code=None, audit='NOT_ATTEMPTED', receipt=receipt)


def _client(flow_engine, identities, **options):
    return TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False,
                                 enable_fixed_proposal=False, enable_founder_decisions=True, **options))


def _headers(identities, name='founder', key='decision-http-key-1'):
    value = {}
    if key is not None:
        value['Idempotency-Key'] = key
    if name is not None:
        value['Authorization'] = 'Bearer ' + identities.tokens[name]
    return value


def _post(client, identities, case, body, **options):
    return client.post('/v1/founder/cases/' + case + '/decisions', json=body, headers=_headers(identities, **options))


def _prepare(flow_engine, identities, kind):
    if kind == 'approve':
        case, _, body = approve_helpers.ready(flow_engine, identities)
    elif kind == 'reject':
        case, body = reject_helpers.ready(flow_engine, identities)
    elif kind == 'revision':
        case, body = revision_helpers.ready(flow_engine, identities)
    else:
        case, body = manual_helpers.ready(flow_engine, identities, kind.removeprefix('manual_'))
    return case, body


def _assert_effect(flow_engine, kind, case, body, receipt):
    result = _accepted(receipt)
    if kind == 'approve':
        approve_helpers.assert_approved_without_effects(flow_engine, case, body, result)
    elif kind == 'reject':
        reject_helpers.assert_rejected(flow_engine, case, body, result)
    elif kind == 'revision':
        revision_helpers.assert_revised(flow_engine, case, body, result)
    else:
        manual_helpers.assert_pending(flow_engine, case, body, result)


def _denial_audits(flow_engine, case):
    # Audit rows carry the typed event inside the canonical body, as the
    # existing denial tests read them (test_founder_reject_postgresql.py).
    events = [decode_document(r['body']) for r in rows(flow_engine, old.audit) if r['case_id'] == case]
    return [e for e in events if e['event_type'] == 'FOUNDER_APPROVE_DENIED']


def _assert_error(response, status, code):
    assert response.status_code == status, response.text
    error = response.json()['error']
    assert error['code'] == code and error['details'] == []
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-correlation-id'] == error['correlation_id']


@pytest.mark.parametrize('kind', ['approve', 'reject', 'revision', 'manual_failure', 'manual_block'])
def test_DH01_each_decision_is_accepted_exactly_once_over_http(flow_engine, identities, enabled, kind):
    case, body = _prepare(flow_engine, identities, kind)
    with _client(flow_engine, identities) as client:
        first = _post(client, identities, case, body)
        assert first.status_code == 202, first.text
        receipt = validate('DecisionReceipt', first.json(), internal=True)
        assert receipt['case_id'] == case and receipt['decision'] == body['decision']
        assert receipt['processing_status'] == 'ACCEPTED' and ('approval_id' in receipt) is (kind == 'approve')
        assert first.headers['cache-control'] == 'no-store' and first.headers['x-correlation-id']
        _assert_effect(flow_engine, kind, case, body, receipt)
        after = business_snapshot(snapshot(flow_engine))
        # Same original key and content: the retained receipt, no second effect.
        replay = _post(client, identities, case, body)
        assert replay.status_code == 202 and replay.json() == first.json()
        # Same key, different content: conflict, still no second effect.
        conflict = _post(client, identities, case, {**body, 'reason': body['reason'] + ' (changed)'})
        _assert_error(conflict, 409, 'IDEMPOTENCY_CONFLICT')
        assert business_snapshot(snapshot(flow_engine)) == after
        assert len([r for r in rows(flow_engine, old.history) if r['case_id'] == case and r['kind'] == 'DECISION']) == 1


def test_DH02_stale_version_and_wrong_approval_scope_deny_before_any_effect(flow_engine, identities, enabled):
    case, body = _prepare(flow_engine, identities, 'approve')
    before = business_snapshot(snapshot(flow_engine))
    with _client(flow_engine, identities) as client:
        stale = _post(client, identities, case, {**body, 'expected_case_version': body['expected_case_version'] + 1},
                      key='decision-http-stale')
        _assert_error(stale, 409, 'STALE_CASE_VERSION')
        assert business_snapshot(snapshot(flow_engine)) == before
        forged_scope = _post(client, identities, case, {**body, 'scope_fingerprint': '0' * 64}, key='decision-http-scope')
        _assert_error(forged_scope, 409, 'INVALID_STATE')
        assert business_snapshot(snapshot(flow_engine)) == before
        other_preview = _post(client, identities, case, {**body, 'preview_id': 'preview_not_retained'},
                              key='decision-http-preview')
        _assert_error(other_preview, 409, 'INVALID_STATE')
        assert business_snapshot(snapshot(flow_engine)) == before
        # Each business denial leaves its own fresh-authority denial audit.
        assert len(_denial_audits(flow_engine, case)) == 3
        # The exact retained scope is still approvable afterwards.
        accepted = _post(client, identities, case, body, key='decision-http-exact')
        assert accepted.status_code == 202, accepted.text
        approve_helpers.assert_approved_without_effects(flow_engine, case, body, _accepted(accepted.json()))


@pytest.mark.parametrize('fault', ['forged_approval_field', 'forged_actor_field', 'customer_token', 'no_token',
                                   'missing_key', 'query_parameter', 'other_decision_with_preview'])
def test_DH03_client_fields_roles_and_transport_cannot_confer_authority(flow_engine, identities, enabled, fault):
    case, body = _prepare(flow_engine, identities, 'approve')
    before = business_snapshot(snapshot(flow_engine))
    with _client(flow_engine, identities) as client:
        url = '/v1/founder/cases/' + case + '/decisions'
        if fault == 'forged_approval_field':
            response = _post(client, identities, case, {**body, 'approval_id': 'approval_forged'})
            _assert_error(response, 422, 'VALIDATION_ERROR')
        elif fault == 'forged_actor_field':
            response = _post(client, identities, case, {**body, 'principal_id': identities.people['founder']['principal_id']})
            _assert_error(response, 422, 'VALIDATION_ERROR')
        elif fault == 'customer_token':
            _assert_error(_post(client, identities, case, body, name='customer_a'), 403, 'FORBIDDEN')
        elif fault == 'no_token':
            _assert_error(_post(client, identities, case, body, name=None), 401, 'UNAUTHENTICATED')
        elif fault == 'missing_key':
            _assert_error(_post(client, identities, case, body, key=None), 422, 'VALIDATION_ERROR')
        elif fault == 'query_parameter':
            response = client.post(url + '?force=1', json=body, headers=_headers(identities))
            _assert_error(response, 422, 'VALIDATION_ERROR')
        else:
            reject_body = {**body, 'decision': 'REJECT'}  # preview fields are APPROVE-only by schema
            _assert_error(_post(client, identities, case, reject_body), 422, 'VALIDATION_ERROR')
        assert business_snapshot(snapshot(flow_engine)) == before
        assert not [r for r in rows(flow_engine, old.history) if r['case_id'] == case and r['kind'] in {'DECISION', 'APPROVAL'}]
        # Schema, transport and identity refusals happen before any Domain service:
        # no denial audit is recorded (NOT_RECORDED), nothing is written at all.
        assert _denial_audits(flow_engine, case) == []


def test_DH04_concurrent_duplicate_approvals_produce_one_approval(flow_engine, identities, enabled):
    case, body = _prepare(flow_engine, identities, 'approve')
    with _client(flow_engine, identities) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: _post(client, identities, case, body, key='decision-http-double'), range(2)))
    # Write units of work serialize on the exclusive fence: the second caller finds
    # the retained fact and replays the identical receipt (docs/09 section 7.3 #6).
    # Only a 5 s lock timeout may surface, and then as retryable INTERNAL_ERROR 503;
    # any 409 here would be a contract violation, not an acceptable outcome.
    statuses = sorted(r.status_code for r in responses)
    assert statuses[0] == 202 and all(s in {202, 503} for s in statuses), [r.text for r in responses]
    accepted = [r.json() for r in responses if r.status_code == 202]
    assert all(item == accepted[0] for item in accepted)
    for response in responses:
        if response.status_code == 503:
            _assert_error(response, 503, 'INTERNAL_ERROR')
            assert 'original request key' in response.json()['error']['message']
    approve_helpers.assert_approved_without_effects(flow_engine, case, body, _accepted(accepted[0]))
    assert len([r for r in rows(flow_engine, old.history) if r['case_id'] == case and r['kind'] == 'DECISION']) == 1
    assert len([r for r in rows(flow_engine, old.history) if r['case_id'] == case and r['kind'] == 'APPROVAL']) == 1


def test_DH05_accepted_decision_is_visible_through_the_founder_reads(flow_engine, identities, enabled):
    case, body = _prepare(flow_engine, identities, 'reject')
    with _client(flow_engine, identities) as client:
        receipt = _post(client, identities, case, body).json()
        reads = {'Authorization': 'Bearer ' + identities.tokens['founder']}
        detail = client.get('/v1/founder/cases/' + case, headers=reads)
        assert detail.status_code == 200 and detail.json()['status'] == 'NOTIFICATION_PENDING'
        assert detail.json()['case_version'] == receipt['case_version'] == body['expected_case_version'] + 1
        history = client.get('/v1/founder/cases/' + case + '/history', headers=reads, params={'kind': 'DECISION'})
        assert history.status_code == 200 and history.json()['items']
        assert receipt['decision_id'] in history.text
        audit = client.get('/v1/founder/cases/' + case + '/audit', headers=reads)
        assert audit.status_code == 200 and audit.json()['items']


def test_DH07_authority_lost_after_preflight_is_denied_by_the_service(flow_engine, identities, enabled, monkeypatch):
    """The read-only preflight passes; the session is revoked before the Domain
    service runs; the service's own fresh authorization must refuse with no effect."""
    from returnops_domain.approve_decision import FounderApproveService
    from returnops_domain.registry import TrustedRegistry
    case, body = _prepare(flow_engine, identities, 'approve')
    before = business_snapshot(snapshot(flow_engine))
    original = FounderApproveService.accept
    revoked = []
    def accept_after_revocation(self, *args, **kwargs):
        if not revoked:
            TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
            revoked.append(True)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(FounderApproveService, 'accept', accept_after_revocation)
    with _client(flow_engine, identities) as client:
        response = _post(client, identities, case, body, key='decision-http-revoked')
    _assert_error(response, 401, 'UNAUTHENTICATED')
    assert revoked == [True]
    # The revocation itself rewrites the founder's session row and the scope audit
    # chain; everything else, other sessions included, must be exactly as before.
    founder_session = identities.sessions['founder']['session_id']
    def comparable(value):
        value = {k: v for k, v in value.items() if k not in {scope_events.name, scope_heads.name}}
        value[old.sessions.name] = [r for r in value[old.sessions.name] if r['session_id'] != founder_session]
        return value
    assert comparable(business_snapshot(snapshot(flow_engine))) == comparable(before)
    session = next(r for r in rows(flow_engine, old.sessions) if r['session_id'] == founder_session)
    assert session['revoked'] is True
    # Fresh authority fails inside record_denial too: NOT_RECORDED, no audit row.
    assert _denial_audits(flow_engine, case) == []
    assert not [r for r in rows(flow_engine, old.history) if r['case_id'] == case and r['kind'] in {'DECISION', 'APPROVAL'}]


def test_DH06_default_composition_has_no_decision_route_on_postgresql(flow_engine, identities, enabled):
    case, body = _prepare(flow_engine, identities, 'reject')
    before = business_snapshot(snapshot(flow_engine))
    with TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False,
                               enable_fixed_proposal=False, enable_founder_decisions=False)) as client:
        response = _post(client, identities, case, body)
    assert response.status_code == 404
    assert business_snapshot(snapshot(flow_engine)) == before
