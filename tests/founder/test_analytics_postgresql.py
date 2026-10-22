"""F.06 analytics over real PG17 rows: cohort, current review, isolation, no writes.

Statuses, created_at and lifecycle references are set directly on accepted
synthetic cases; PROPOSAL/REVIEW records use the existing test-only history
fixtures. The latency test uses the real intake, investigation and fixed
proposal producers. Counts are hand computed and reconciled with the contracts'
fixture oracle. OF-006, FR-011/012, NFR-005/008; docs/43.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text, update
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_api.main import create_app
from returnops_domain import customer_tables as t, lifecycle_tables as lifecycle
from returnops_domain.audit import identifier, timestamp
from returnops_domain.customer_service import CustomerFlow
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.proposal_policy import FixedProposalPolicy
from returnops_domain.proposal_processor import FixedProposalProcessor
from returnops_domain.registry import TrustedRegistry
from returnops_domain.wire import validate
from founder_helpers import accepted, append_statements, investigate, rows
from future_history_fixtures import material, persist, tombstone

sys.path.append(str(Path(__file__).resolve().parents[1] / 'contracts'))
from test_contract_v1_rc2 import assert_analytics_fixture  # noqa: E402  fixture oracle, not a query

EXAMPLES = {item['name']: item['value'] for item in json.loads(
    (Path(__file__).resolve().parents[2] / 'contracts/v1/examples.json').read_text(encoding='utf-8'))['positive']}
PATH = '/v1/founder/analytics'
UNMEASURED = ('UNMEASURED', None)


def z(value):
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def everything(engine):
    """Every table, Founder metadata included: analytics must write nothing."""
    with engine.connect() as connection:
        return {name: sha256(repr(sorted((tuple(row) for row in connection.execute(text('SELECT * FROM "' + name + '"'))),
                key=repr)).encode('utf-8', 'surrogatepass')).hexdigest() for name in sorted(inspect(connection).get_table_names())}


def shape(engine, case_id, created_at, status, *, input_version=1, available=True):
    with CustomerUnitOfWork(engine, write=True) as uow:
        uow.execute(update(t.case_heads).where(t.case_heads.c.case_id == case_id).values(
            created_at=created_at, status=status, input_version=input_version, available=available))
        uow.commit()


def point(engine, case_id, *, input_version=1, proposal=None, version=0, review=None):
    values = dict(case_id=case_id, input_version=input_version, generation=1, proposal_version=version,
        proposal_record_id=proposal, review_record_id=review, preview_id=None, approval_record_id=None,
        outcome_record_id=None, outcome=None, notification_id=None, notification_record_id=None,
        notification_hash=None, notification_work_id=None, return_record_id=None, label_record_id=None, available=True)
    with CustomerUnitOfWork(engine, write=True) as uow:
        uow.execute(lifecycle.state.insert().values(**values))
        uow.commit()


def receipt(engine, case_id, record_id, kind, *, input_version=1):
    """Accepted lifecycle receipt row only (test-only); no guard or producer runs."""
    now = datetime.now(timezone.utc)
    with CustomerUnitOfWork(engine, write=True) as uow:
        head = uow.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
        work_id = identifier('work')
        uow.execute(lifecycle.work.insert().values(work_id=work_id, case_id=case_id, component_id='analytics_fixture',
            store_id=head['store_id'], owner_id=head['owner_principal_id'], purpose='PROPOSAL' if kind == 'PROPOSAL_FAILED' else 'REVIEW',
            input_version=input_version, generation=1, target_hash=sha256(record_id.encode('ascii')).hexdigest(),
            target_record_id=None, state='DONE', claim_id=None, epoch=0, claimed_case_version=None,
            authority_revision=None, idempotency_key=None, lease_expires_at=None, created_at=now))
        uow.execute(lifecycle.events.insert().values(event_id=identifier('event'), case_id=case_id, work_id=work_id,
            record_id=record_id, fingerprint='0' * 64, event_kind=kind, source_id=record_id, case_version=10,
            source_hash='0' * 64, source_audit_event_id=identifier('audit'), pre_case_version=10,
            pre_input_version=input_version, pre_generation=1, input_version=input_version, generation=1,
            status=head['status'], accepted_at=now))
        uow.commit()


def reviewed(engine, case_id, outcome, *, version=1, legacy=False, accept=True):
    proposal = persist(engine, case_id, material('PROPOSAL', case_id, version=version))
    review = persist(engine, case_id, material('REVIEW', case_id, version=version, proposal_record_id=proposal['record_id']),
                     mutation=lambda fixture: fixture['content']['review'].update(outcome=outcome), legacy=legacy)
    if accept:  # the two accepted-review event kinds written by lifecycle_guards
        receipt(engine, case_id, review['record_id'], 'REVIEW_PASS' if outcome.startswith('PASS') else 'REVIEW')
    return proposal, review


def review_fact(outcome, *, version=1, input_version=1):
    return {'proposal_id': 'proposal-demo-001', 'proposal_version': version, 'input_version': input_version,
            'outcome': outcome, 'reviewed_at': '2026-09-07T02:00:00Z'}


def other_store(engine, identities):
    """A second store through the trusted registry; its case must never leak."""
    now, config = int(time.time()), identities.auth_config
    people = [dict(principal_id='synthetic_other_' + role.lower(), store_id='synthetic_other_store', role=role, enabled=True)
              for role in ('CUSTOMER', 'FOUNDER')]
    sessions = [dict(session_id=identifier('session'), principal_id=p['principal_id'], issued_at=now - 1,
                     not_before=now - 1, expires_at=now + 899, revoked=False) for p in people]
    TrustedRegistry(engine).provision(people, sessions)
    tokens = {p['role']: 'Bearer ' + jwt.encode(dict(iss=config.issuer, aud=config.audience, sub=s['principal_id'],
        jti=s['session_id'], iat=s['issued_at'], nbf=s['not_before'], exp=s['expires_at']), config.signing_key, algorithm='HS256')
        for p, s in zip(people, sessions)}
    case_id = CustomerFlow(engine, CurrentRequestAuthority(config, tokens['CUSTOMER'])).create(
        {'original_message': 'other store synthetic request'}, 'analytics-other-store', identifier('corr')).body['case_id']
    return case_id, tokens['FOUNDER']


def get(client, token, **params):
    response = client.get(PATH, headers={'Authorization': token}, params=params)
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-correlation-id']
    body = response.json()
    validate('AnalyticsSnapshot', body, internal=True)
    counts = body['proposal_latency']
    assert sum(item['count'] for item in body['cases_by_status']) == body['case_count']
    assert sum(item['count'] for item in body['current_risk_counts']) + body['cases_without_current_review'] == body['case_count']
    assert counts['sample_count'] + counts['failed_count'] + counts['unmeasured_count'] == body['case_count']
    return body


def buckets(body, field='cases_by_status', key='status'):
    return [(item[key], item['count']) for item in body[field]]


def test_hand_computed_cohort_current_review_isolation_and_no_writes(flow_engine, identities):
    base = (datetime.now(timezone.utc) - timedelta(days=10)).replace(microsecond=0)
    at = lambda hours: base + timedelta(hours=hours)
    facts = []

    def case(name, created_at, status, *, reviews=(), proposal_version=None, input_version=1, available=True,
             latency=UNMEASURED):
        case_id = accepted(identities, key='analytics-' + name)['case_id']
        shape(flow_engine, case_id, created_at, status, input_version=input_version, available=available)
        if available:
            row = {'case_id': case_id, 'created_at': timestamp(created_at), 'input_version': input_version,
                   'statuses': [(timestamp(created_at), status)], 'reviews': list(reviews), 'latency': latency}
            if proposal_version is not None:
                row.update(proposal_id='proposal-demo-001', proposal_version=proposal_version)
            facts.append(row)
        return case_id

    c = case('pass', at(1), 'AWAITING_APPROVAL', reviews=[review_fact('PASS')], proposal_version=1)
    proposal, review = reviewed(flow_engine, c, 'PASS')
    point(flow_engine, c, proposal=proposal['record_id'], version=1, review=review['record_id'])
    c = case('escalate', at(2), 'ESCALATED', reviews=[review_fact('ESCALATE')], proposal_version=1)
    proposal, review = reviewed(flow_engine, c, 'ESCALATE')
    point(flow_engine, c, proposal=proposal['record_id'], version=1, review=review['record_id'])
    # Retried proposal: two proposal/review versions, counted once at the current one.
    c = case('retry', at(3), 'AWAITING_APPROVAL', proposal_version=2,
             reviews=[review_fact('PASS'), review_fact('PASS_WITH_WARNING', version=2)])
    reviewed(flow_engine, c, 'PASS')
    proposal, review = reviewed(flow_engine, c, 'PASS_WITH_WARNING', version=2)
    point(flow_engine, c, proposal=proposal['record_id'], version=2, review=review['record_id'])
    # A review of input 1 still referenced after input 2 is not current.
    c = case('stale', at(4), 'POLICY_ASSESSMENT', input_version=2, proposal_version=1, reviews=[review_fact('PASS')])
    proposal, review = reviewed(flow_engine, c, 'PASS')
    point(flow_engine, c, input_version=2, proposal=proposal['record_id'], version=1, review=review['record_id'])
    c = case('awaiting_review', at(5), 'RISK_REVIEW', proposal_version=1)
    proposal = persist(flow_engine, c, material('PROPOSAL', c))
    point(flow_engine, c, proposal=proposal['record_id'], version=1)
    c = case('deleted_review', at(6), 'REJECTED', proposal_version=1)
    proposal, review = reviewed(flow_engine, c, 'PASS')
    point(flow_engine, c, proposal=proposal['record_id'], version=1, review=review['record_id'])
    tombstone(flow_engine, review['record_id'])
    case('plain', at(7), 'SUBMITTED')
    c = case('legacy', at(8), 'COMPLETED', reviews=[review_fact('PASS')], proposal_version=1)
    proposal, review = reviewed(flow_engine, c, 'PASS', legacy=True)
    point(flow_engine, c, proposal=proposal['record_id'], version=1, review=review['record_id'])
    # A proposal-step failure for the current input is failed; one for an older
    # input is not, and a REVIEW row without an accepted receipt is not current.
    c = case('proposal_failed', at(11), 'ESCALATED', latency=('FAILED', None))
    receipt(flow_engine, c, persist(flow_engine, c, material('PROPOSAL', c))['record_id'], 'PROPOSAL_FAILED')
    c = case('old_failure', at(12), 'POLICY_ASSESSMENT', input_version=2)
    receipt(flow_engine, c, persist(flow_engine, c, material('PROPOSAL', c))['record_id'], 'PROPOSAL_FAILED')
    c = case('unaccepted', at(13), 'APPROVED', proposal_version=1)
    proposal, review = reviewed(flow_engine, c, 'PASS', accept=False)
    point(flow_engine, c, proposal=proposal['record_id'], version=1, review=review['record_id'])
    case('before_window', base - timedelta(seconds=1), 'SUBMITTED')
    case('upper_bound', base + timedelta(days=1), 'SUBMITTED')
    case('unavailable', at(9), 'SUBMITTED', available=False)
    foreign, foreign_founder = other_store(flow_engine, identities)
    shape(flow_engine, foreign, at(10), 'ESCALATED')

    founder = 'Bearer ' + identities.tokens['founder']
    window = {'created_from': z(base), 'created_before': z(base + timedelta(days=1))}
    before = everything(flow_engine)
    with TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False)) as client:
        body = get(client, founder, **window)
        assert body['filters'] == window and body['case_count'] == 11
        assert buckets(body) == [('SUBMITTED', 1), ('POLICY_ASSESSMENT', 2), ('RISK_REVIEW', 1), ('AWAITING_APPROVAL', 2),
            ('APPROVED', 1), ('ESCALATED', 2), ('COMPLETED', 1), ('REJECTED', 1)]
        assert buckets(body, 'current_risk_counts', 'outcome') == [('PASS', 2), ('PASS_WITH_WARNING', 1), ('ESCALATE', 1)]
        assert body['cases_without_current_review'] == 7
        assert body['proposal_latency'] == {'metric_version': 'proposal-latency-v1', 'sample_count': 0,
                                            'failed_count': 1, 'unmeasured_count': 10}
        assert_analytics_fixture(body, facts)
        selected = get(client, founder, status='AWAITING_APPROVAL', **window)
        assert selected['filters'] == {**window, 'status': 'AWAITING_APPROVAL'} and selected['case_count'] == 2
        assert buckets(selected, 'current_risk_counts', 'outcome') == [('PASS', 1), ('PASS_WITH_WARNING', 1)]
        assert_analytics_fixture(selected, facts)
        everything_visible = get(client, founder)
        assert everything_visible['filters'] == {} and everything_visible['case_count'] == 13
        assert_analytics_fixture(everything_visible, facts)
        other = get(client, foreign_founder)
        assert other['case_count'] == 1 and buckets(other) == [('ESCALATED', 1)]
        assert other['cases_without_current_review'] == 1
    assert everything(flow_engine) == before


def test_empty_cohort_and_future_bound_is_clamped_to_as_of(flow_engine, identities):
    founder = 'Bearer ' + identities.tokens['founder']
    empty = {key: value for key, value in EXAMPLES['analytics-empty'].items() if key != 'as_of'}
    with TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False)) as client:
        body = get(client, founder)
        assert {key: value for key, value in body.items() if key != 'as_of'} == empty
        current = accepted(identities, key='analytics-current')['case_id']
        future = accepted(identities, key='analytics-future')['case_id']
        shape(flow_engine, future, datetime.now(timezone.utc) + timedelta(hours=1), 'SUBMITTED')
        far = {'created_before': '2999-01-01T00:00:00Z'}
        clamped = get(client, founder, **far)
        as_of = datetime.fromisoformat(clamped['as_of'][:-1] + '+00:00')
        created = {row['case_id']: row['created_at'] for row in rows(flow_engine, t.case_heads)}
        assert created[current] < as_of < created[future]
        assert clamped['filters'] == far and clamped['case_count'] == 1 and buckets(clamped) == [('SUBMITTED', 1)]
        late = {'created_from': z(datetime.now(timezone.utc) + timedelta(minutes=30)), 'created_before': '2999-01-01T00:00:00Z'}
        nothing = get(client, founder, **late)
        assert nothing['filters'] == late and {key: value for key, value in nothing.items()
                                               if key not in {'as_of', 'filters'}} == {k: v for k, v in empty.items() if k != 'filters'}


def test_http_authorization_and_query_matrix(flow_engine, identities):
    accepted(identities, key='analytics-matrix')
    before = everything(flow_engine)
    with TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False)) as client:
        founder = {'Authorization': 'Bearer ' + identities.tokens['founder']}
        customer = {'Authorization': 'Bearer ' + identities.tokens['customer_a']}
        for headers, params, status, error in [
                ({}, {}, 401, 'UNAUTHENTICATED'), (customer, {}, 403, 'FORBIDDEN'),
                (customer, {'status': 'NOPE'}, 403, 'FORBIDDEN'), (founder, {'status': 'NOPE'}, 422, 'VALIDATION_ERROR'),
                (founder, {'status': 'SUBMITTED,ESCALATED'}, 422, 'VALIDATION_ERROR'),
                (founder, {'created_from': '2026-09-06T00:00:00'}, 422, 'VALIDATION_ERROR'),
                (founder, {'created_from': '2026-09-07T00:00:00Z', 'created_before': '2026-09-06T00:00:00Z'}, 422, 'VALIDATION_ERROR'),
                (founder, {'created_from': '2026-09-06T00:00:00Z', 'created_before': '2026-09-06T00:00:00Z'}, 422, 'VALIDATION_ERROR'),
                (founder, {'limit': '1'}, 422, 'VALIDATION_ERROR')]:
            response = client.get(PATH, headers=headers, params=params)
            assert response.status_code == status and response.json()['error']['code'] == error, (params, response.text)
            assert response.headers['x-correlation-id'] == response.json()['error']['correlation_id']
            assert response.headers['cache-control'] == 'no-store'
        duplicate = client.get(PATH + '?status=SUBMITTED&status=SUBMITTED', headers=founder)
        assert duplicate.status_code == 422
        doubled = client.get(PATH, headers=[('Authorization', founder['Authorization'])] * 2)
        assert doubled.status_code == 401
        assert get(client, founder['Authorization'])['case_count'] == 1
    assert everything(flow_engine) == before


def test_real_producers_tier0_latency_counts_only_proposal_failures(flow_engine, identities, enabled):
    from test_queries_postgresql import BrokenSource
    proposed = investigate(flow_engine, identities, 'SYN-1001', key='analytics-proposed')['case_id']
    FixedProposalPolicy(flow_engine).grant('synthetic_au_store', synthetic_demo=True, enabled=True)
    assert FixedProposalProcessor(flow_engine).run_once()
    # Capacity boundary as in the lifecycle runtime test: the original plus 100
    # clarifications exceed the fixed proposer, which records PROPOSAL_FAILED.
    capacity = investigate(flow_engine, identities, 'SYN-1001', key='analytics-capacity')['case_id']
    append_statements(flow_engine, identities, capacity, 100)
    worker = FixedProposalProcessor(flow_engine)
    assert worker.process(worker.prepare(capacity)).status == 'FAILED'
    failed = investigate(flow_engine, identities, 'missing', key='analytics-failed', catalogue=BrokenSource())['case_id']
    blocked = investigate(flow_engine, identities, 'SYN-CONFLICT', key='analytics-blocked')['case_id']
    heads = {row['case_id']: row for row in rows(flow_engine, t.case_heads)}
    # Why Tier 0: the proposal's current input (2, created by the order match)
    # has no intake work row; intake DONE exists only for input 1.
    receipts = [row for row in rows(flow_engine, lifecycle.events) if row['case_id'] == proposed]
    assert [(row['event_kind'], row['input_version']) for row in receipts] == [('PROPOSAL', 2)]
    assert heads[proposed]['input_version'] == 2 and heads[proposed]['status'] == 'RISK_REVIEW'
    assert {row['input_version'] for row in rows(flow_engine, t.intake_work) if row['case_id'] == proposed} == {1}
    assert [(row['event_kind'], row['input_version']) for row in rows(flow_engine, lifecycle.events)
            if row['case_id'] == capacity] == [('PROPOSAL_FAILED', 2)] and heads[capacity]['input_version'] == 2
    # An order-lookup failure happens before the complete input: no receipt, unmeasured.
    failures = [row for row in rows(flow_engine, t.processing_failures) if row['case_id'] == failed]
    assert len(failures) == 1 and failures[0]['input_version'] == heads[failed]['input_version']
    assert not any(row['case_id'] == failed for row in rows(flow_engine, lifecycle.events))
    assert heads[failed]['status'] == heads[blocked]['status'] == heads[capacity]['status'] == 'ESCALATED'
    with TestClient(create_app(engine=flow_engine, auth_config=identities.auth_config, enable_processor=False)) as client:
        body = get(client, 'Bearer ' + identities.tokens['founder'])
    assert body['case_count'] == 4 and buckets(body) == [('RISK_REVIEW', 1), ('ESCALATED', 3)]
    assert body['current_risk_counts'] == [] and body['cases_without_current_review'] == 4
    assert body['proposal_latency'] == {'metric_version': 'proposal-latency-v1', 'sample_count': 0,
                                        'failed_count': 1, 'unmeasured_count': 3}
    assert_analytics_fixture(body, [{'case_id': case_id, 'created_at': timestamp(heads[case_id]['created_at']),
        'input_version': heads[case_id]['input_version'], 'statuses': [(timestamp(heads[case_id]['created_at']), heads[case_id]['status'])],
        'reviews': [], 'latency': ('FAILED', None) if case_id == capacity else UNMEASURED}
        for case_id in (proposed, capacity, failed, blocked)])
