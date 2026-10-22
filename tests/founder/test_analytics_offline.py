"""F.06 analytics without a database: route, query, counting and invariants.

Offline: placeholder engine, scripted unit of work and authority. The real
authorization matrix and SQL run in test_analytics_postgresql.py. OF-006,
FR-011/012, NFR-005/008; docs/43.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import pytest
from sqlalchemy.dialects import postgresql
from starlette.requests import Request
from returnops_api.founder_http import _query
from returnops_api.main import create_app
from returnops_api.security.authentication import AuthConfig
from returnops_domain import founder_codec as finite
from returnops_domain.analytics_queries import (OUTCOMES, STATUSES, check_snapshot, cohort_statement,
    current_outcome, latency_block, parse_query, percentile_ms)
from returnops_domain.canonical import digest, encode_document
from returnops_domain.errors import FlowError
from returnops_domain.founder_service import FounderQueries
from returnops_domain.ports import Actor
from future_history_fixtures import material

EXAMPLES = {item['name']: item['value'] for item in json.loads(
    (Path(__file__).resolve().parents[2] / 'contracts/v1/examples.json').read_text(encoding='utf-8'))['positive']}
NOW = datetime(2026, 9, 7, 2, 0, tzinfo=timezone.utc)


def code(call, *args):
    with pytest.raises(FlowError) as raised:
        call(*args)
    return raised.value.code


def test_default_composition_registers_exactly_one_analytics_get():
    config = AuthConfig('analytics-tests', 'analytics-api', secrets.token_bytes(48), leeway_seconds=0)
    app = create_app(engine=object(), auth_config=config, enable_processor=False, enable_fixed_proposal=False,
                     enable_founder_decisions=False)
    route, = [r for r in app.routes if getattr(r, 'path', '') == '/v1/founder/analytics']
    assert route.methods == {'GET'} and route.operation_id == 'getFounderAnalytics'
    assert sum(1 for r in app.routes if getattr(r, 'path', '').startswith('/v1/founder/')) == 5


def request(query):
    return Request({'type': 'http', 'method': 'GET', 'path': '/v1/founder/analytics', 'headers': [],
                    'query_string': query.encode('ascii')})


def test_http_query_whitelist_for_analytics():
    assert _query(request(''), 'getFounderAnalytics') == {}
    assert _query(request('status=SUBMITTED&created_from=2026-09-06T00:00:00Z'), 'getFounderAnalytics') == {
        'status': 'SUBMITTED', 'created_from': '2026-09-06T00:00:00Z'}
    for query in ['status=SUBMITTED&status=ESCALATED', 'created_from=2026-09-06T00:00:00Z&created_from=2026-09-06T00:00:00Z',
                  'limit=1', 'cursor=abc', 'kind=STATEMENT', 'store_id=synthetic_au_store', 'Status=SUBMITTED']:
        assert code(_query, request(query), 'getFounderAnalytics') == 'VALIDATION_ERROR', query


def test_valid_queries_are_echoed_exactly():
    assert parse_query({}) == ({}, None, None)
    window = EXAMPLES['analytics-query-window']
    filters, start, before = parse_query(dict(window))
    assert filters == window and start < before and start.utcoffset().total_seconds() == 0
    assert parse_query({'created_before': '2026-09-07T00:00:00.123456Z', 'status': 'ESCALATED'})[0] == {
        'created_before': '2026-09-07T00:00:00.123456Z', 'status': 'ESCALATED'}


@pytest.mark.parametrize('query', [
    {'created_from': '2026-09-07T00:00:00Z', 'created_before': '2026-09-06T00:00:00Z'},  # reversed
    {'created_from': '2026-09-06T00:00:00Z', 'created_before': '2026-09-06T00:00:00Z'},  # empty
    {'status': 'UNKNOWN'}, {'status': 'submitted'}, {'status': 'SUBMITTED,ESCALATED'}, {'status': ''},
    {'status': ['SUBMITTED']}, {'created_from': '2026-09-06T00:00:00'},  # naive
    {'created_from': '2026-09-06T00:00:00+00:00'}, {'created_from': '2026-09-06T10:00:00+10:00'},
    {'created_from': '2026-09-06T00:00:00z'}, {'created_from': '2026-09-06t00:00:00Z'},
    {'created_from': '2026-09-06 00:00:00Z'}, {'created_from': '2026-09-06'}, {'created_from': ''},
    {'created_from': '2026-09-06T23:59:60Z'}, {'created_from': '2026-02-30T00:00:00Z'},
    {'created_from': '2026-09-06T00:00:00.1234567Z'}, {'created_from': '\uff12026-09-06T00:00:00Z'},
    {'created_from': 1757116800}, {'limit': 1}, {'store_id': 'synthetic_au_store'}])
def test_invalid_queries_are_422(query):
    assert code(parse_query, query) == 'VALIDATION_ERROR'
    assert code(parse_query, None) == 'VALIDATION_ERROR'


def test_percentile_is_linear_type7_in_integer_ms():
    assert percentile_ms([1200], 50) == percentile_ms([1200], 95) == 1200
    assert percentile_ms([2000, 1000], 50) == 1500 and percentile_ms([1000, 2000], 95) == 1950
    assert percentile_ms([1, 2], 50) == 2 and percentile_ms([1, 4], 50) == 2  # exact .5 rounds half-even
    assert percentile_ms([0, 1, 2, 3], 95) == 3 and percentile_ms(list(range(101)), 95) == 95
    for samples, percent in [([], 50), ([1], 101), ([1], 50.0)]:
        assert code(percentile_ms, samples, percent) == 'INTERNAL_ERROR'


def test_latency_block_tiers_and_rejections():
    assert latency_block(3) == {'metric_version': 'proposal-latency-v1', 'sample_count': 0,
                                'failed_count': 0, 'unmeasured_count': 3}
    assert latency_block(3, [1200], 1) == {'metric_version': 'proposal-latency-v1', 'sample_count': 1,
        'failed_count': 1, 'unmeasured_count': 1, 'p50_ms': 1200, 'p95_ms': 1200}
    for args in [(1, [1], 1), (1, [-1]), (1, [True]), (1, [1.5]), (1, (), -1), (True,)]:
        assert code(latency_block, *args) == 'INTERNAL_ERROR'


def canonical(snapshot):
    snapshot = deepcopy(snapshot)
    snapshot['cases_by_status'].sort(key=lambda item: STATUSES.index(item['status']))
    snapshot['current_risk_counts'].sort(key=lambda item: OUTCOMES.index(item['outcome']))
    return snapshot


def test_contract_examples_pass_and_every_broken_invariant_is_503():
    assert check_snapshot(EXAMPLES['analytics-empty']) == EXAMPLES['analytics-empty']
    base = canonical(EXAMPLES['analytics-windowed'])  # this module emits enum order
    assert check_snapshot(base) == base
    def status_sum(s): s['cases_by_status'][0]['count'] += 1
    def risk_sum(s): s['cases_without_current_review'] -= 1
    def latency_sum(s): s['proposal_latency']['unmeasured_count'] += 1
    def order(s): s['proposal_latency']['p50_ms'] = 1300
    def empty_percentile(s): s['proposal_latency'].update(sample_count=0, unmeasured_count=2)
    def missing_percentile(s): del s['proposal_latency']['p95_ms']
    def duplicate(s): s['cases_by_status'] = [{'status': 'COMPLETED', 'count': 2}, {'status': 'COMPLETED', 'count': 1}]
    def unordered(s): s['cases_by_status'].reverse()
    def zero(s): s['current_risk_counts'].append({'outcome': 'ESCALATE', 'count': 0})
    def extra(s): s['proposal_latency']['mean_ms'] = 1200
    for mutation in [status_sum, risk_sum, latency_sum, order, empty_percentile, missing_percentile,
                     duplicate, unordered, zero, extra]:
        changed = deepcopy(base)
        mutation(changed)
        assert code(check_snapshot, changed) == 'INTERNAL_ERROR', mutation.__name__


def review_row(*, legacy=False, mutate=None, **changes):
    content = material('REVIEW', 'case_analytics', proposal_record_id='hist_proposal_current')['content']
    content['review']['case_id'] = 'case_analytics'
    if mutate:
        mutate(content)
    body = encode_document(content) if legacy else finite.encode_document(content)
    row = {'case_id': 'case_analytics', 'status': 'AWAITING_APPROVAL', 'input_version': 1,
           'state_case_id': 'case_analytics', 'state_input_version': 1, 'proposal_version': 1,
           'proposal_record_id': 'hist_proposal_current', 'state_available': True, 'review_accepted': True,
           'review_object_id': content['review']['review_id'],
           'review_sha256': digest(content, 'history/v1') if legacy else finite.digest(content),
           'review_body': body, 'review_profile': None if legacy else finite.PROFILE,
           'proposal_object_id': content['review']['proposal_id'], 'proposal_object_version': 1, 'proposal_failed': False}
    row.update(changes)
    return row


def test_current_review_requires_current_identity_and_intact_body():
    assert current_outcome(review_row()) == 'PASS'
    assert current_outcome(review_row(legacy=True)) == 'PASS'
    assert current_outcome(review_row(legacy=True, review_profile=finite.LEGACY_PROFILE)) == 'PASS'
    assert current_outcome(review_row(mutate=lambda c: c['review'].update(outcome='ESCALATE'))) == 'ESCALATE'
    stale = [review_row(input_version=2, state_input_version=2),  # review of input 1 after a new input
             review_row(state_input_version=2), review_row(proposal_version=2, proposal_object_version=2),
             review_row(proposal_object_version=2), review_row(proposal_object_id='proposal_other'),
             review_row(proposal_record_id='hist_proposal_old'), review_row(review_object_id='review_other'),
             review_row(review_sha256='0' * 64), review_row(review_body=b'ROPS\x02broken'),
             review_row(review_profile='historical-order-block/v1'), review_row(legacy=True, review_profile=finite.PROFILE),
             review_row(review_body=None), review_row(state_available=False), review_row(state_case_id=None),
             review_row(mutate=lambda c: c['review'].update(outcome='UNKNOWN')),
             review_row(mutate=lambda c: c['review'].update(input_version=True)),
             review_row(mutate=lambda c: c['review'].update(case_id='case_other')),
             review_row(review_accepted=False)]  # REVIEW history row without an accepted REVIEW/REVIEW_PASS receipt
    assert [current_outcome(row) for row in stale] == [None] * len(stale)


def test_cohort_is_one_statement_with_two_correlated_receipt_checks():
    statement = cohort_statement('synthetic_au_store', None, NOW, 'ESCALATED')
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert statement.is_select and sql.count('SELECT') == 3 and sql.count('EXISTS (SELECT') == 2
    assert sql.count('LEFT OUTER JOIN') == 5 and sql.count('FROM lifecycle_event_receipts') == 2
    assert 'lifecycle_event_receipts.input_version = case_heads.input_version' in sql
    assert 'lifecycle_event_receipts.record_id = case_lifecycle_state.review_record_id' in sql
    assert {'PROPOSAL_FAILED', 'REVIEW', 'REVIEW_PASS'} <= {value for value in compiled.params.values() if type(value) is str} | {
        item for value in compiled.params.values() if type(value) in (list, tuple) for item in value}
    for name in ('case_heads', 'case_lifecycle_state', 'customer_history_revisions',
                 'customer_history_contents', 'founder_history_encodings'):
        assert name in sql
    assert 'case_heads.available IS true' in sql and 'case_heads.created_at <' in sql


class FakeResult:
    def __init__(self, rows): self.rows = rows
    def mappings(self): return self
    def all(self): return self.rows


class Harness:
    """Scripted read-only UoW and current authority; records every call."""
    def __init__(self, rows=(), role='FOUNDER'):
        self.rows, self.calls = list(rows), []
        self.actor = Actor('synthetic_principal', role, 'synthetic_au_store', 'session_1')
        harness = self
        class UoW:
            def __init__(self, engine, *, write):
                harness.calls.append(('open', write))
                self.connection = 'connection'
            def __enter__(self): return self
            def __exit__(self, *args): harness.calls.append('close'); return False
            def execute(self, statement, parameters=None):
                assert statement.is_select
                harness.calls.append('select')
                return FakeResult(harness.rows)
            def commit(self): harness.calls.append('commit')
        self.queries = FounderQueries(object(), self.authority, clock=lambda: NOW, uow_factory=UoW)

    def authority(self, connection, operation, case_id=None):
        assert connection == 'connection'
        self.calls.append((operation, case_id))
        return self.actor

    def query(self, value):
        def supply():
            self.calls.append('query')
            return value
        return supply


def head(case_id, status, **changes):
    row = review_row(case_id=case_id, status=status, state_case_id=None, review_body=None)
    row.update(changes)
    return row


def test_service_reads_read_only_reauthorizes_and_counts_tier0():
    rows = [head('case_a', 'ESCALATED', proposal_failed=True), head('case_b', 'SUBMITTED'), review_row(),
            head('case_c', 'ESCALATED')]
    harness = Harness(rows)
    result = harness.queries.read('getFounderAnalytics', None, harness.query({}))
    assert result.status == 200
    assert harness.calls == [('open', False), ('getSession', None), ('getFounderAnalytics', None), 'query', 'select',
                             ('getSession', None), ('getFounderAnalytics', None), 'commit', 'close']
    assert result.body == {'as_of': '2026-09-07T02:00:00.000000Z', 'filters': {}, 'case_count': 4,
        'cases_by_status': [{'status': 'SUBMITTED', 'count': 1}, {'status': 'AWAITING_APPROVAL', 'count': 1},
                            {'status': 'ESCALATED', 'count': 2}],
        'current_risk_counts': [{'outcome': 'PASS', 'count': 1}], 'cases_without_current_review': 3,
        'proposal_latency': {'metric_version': 'proposal-latency-v1', 'sample_count': 0, 'failed_count': 1,
                             'unmeasured_count': 3}}


def test_service_denials_precede_query_and_bad_rows_are_503():
    customer = Harness(role='CUSTOMER')
    assert code(customer.queries.read, 'getFounderAnalytics', None, customer.query({})) == 'FORBIDDEN'
    assert 'query' not in customer.calls and 'select' not in customer.calls and 'commit' not in customer.calls
    for query in [{'status': 'NOPE'}, {'created_from': '2026-09-06T00:00:00'}]:
        harness = Harness()
        assert code(harness.queries.read, 'getFounderAnalytics', None, harness.query(query)) == 'VALIDATION_ERROR'
        assert 'select' not in harness.calls and 'commit' not in harness.calls
    harness = Harness()
    assert code(harness.queries.read, 'getFounderAnalytics', 'case_a', harness.query({})) == 'FORBIDDEN'
    assert harness.calls == []
    for rows, query in [([head('case_a', 'SUBMITTED'), head('case_a', 'SUBMITTED')], {}),
                        ([head('case_a', 'NOT_A_STATUS')], {}), ([head('case_a', 'SUBMITTED')], {'status': 'ESCALATED'}),
                        ([head('case_a', 'SUBMITTED', proposal_failed=None)], {})]:
        harness = Harness(rows)
        assert code(harness.queries.read, 'getFounderAnalytics', None, harness.query(query)) == 'INTERNAL_ERROR'
        assert 'commit' not in harness.calls
