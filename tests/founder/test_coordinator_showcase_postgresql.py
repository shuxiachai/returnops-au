"""A1.06 showcase on real PG17 with a stubbed model: actual cases, Founder reads, no writes.

docs/44; FR-002, NFR-003/007/008/009, BR-008/BR-012. The worker reads in
read-only units of work, calls the stub with no connection held, re-checks the
digest and stores facts in process only. Business tables (everything except the
Founder snapshot/cursor tables written by every Founder read) are unchanged, the
audit chain and CaseProof stay valid, and the feature-off view keeps the
test_queries_postgresql "no facts" behaviour.
"""
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from returnops_api.main import create_app
from returnops_domain import customer_tables as t
from returnops_domain.audit import identifier, verify_chain
from returnops_domain.coordinator_showcase import (CoordinatorAnnotationStore, CoordinatorShowcaseWorker,
    PROMPT_VERSION, ShowcaseSettings, project_facts)
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.founder_integrity import CaseProof
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.model_transport import ModelReply, ModelTransportError
from returnops_domain.retention import RetentionService
from returnops_domain.wire import validate
from founder_helpers import accepted, business_fingerprints

FACTS = {'issue_category': 'FAULTY_OR_QUALITY_ISSUE', 'customer_requested_outcome': 'UNSPECIFIED',
         'possible_basis': 'UNDETERMINED', 'assessment_status': 'MISSING_INFORMATION', 'line_items': [],
         'summary': 'The customer reports a problem with the item and asks what can be done.'}


class StubTransport:
    def __init__(self, content=None, error=None):
        self.calls, self.error = [], error
        self.content = json.dumps(FACTS) if content is None else content

    def __call__(self, invocation):
        self.calls.append(invocation)
        if self.error is not None:
            raise ModelTransportError(self.error)
        return ModelReply(self.content, 200, 40)


def worker(engine, transport, store, **settings):
    return CoordinatorShowcaseWorker(engine, transport, store,
                                     settings=ShowcaseSettings('campus_proxy', 'stub-model', **settings))


def founder_read(engine, identities, case_id, store=None):
    app = create_app(engine=engine, auth_config=identities.auth_config, enable_processor=False,
                     enable_fixed_proposal=False, enable_founder_decisions=False, enable_model_showcase=False)
    headers = {'Authorization': 'Bearer ' + identities.tokens['founder']}
    with TestClient(app) as client:
        assert app.state.coordinator_facts is None
        if store is not None:
            # The same trusted composition main.py installs when the flag is on.
            app.state.coordinator_facts = lambda uow, head: project_facts(uow, head, store)
        detail = client.get('/v1/founder/cases/' + case_id, headers=headers)
        audit = client.get('/v1/founder/cases/' + case_id + '/audit', headers=headers, params={'limit': 100})
    assert detail.status_code == 200, detail.text
    assert audit.status_code == 200, audit.text
    validate('CaseView', detail.json(), internal=True)
    validate('AuditPage', audit.json(), internal=True)
    assert all(item['actor']['kind'] != 'MODEL' for item in audit.json()['items'])
    return detail.json()


def assert_integrity(engine, case_id):
    with CustomerUnitOfWork(engine, write=False) as uow:
        head = uow.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
        CaseProof(uow, head)
        assert verify_chain(uow, case_id)
        uow.commit()


def test_recorded_facts_survive_the_order_match_and_nothing_is_written(flow_engine, identities, enabled):
    body = accepted(identities, 'SYN-1001')
    case_id = body['case_id']
    assert IntakeProcessor(flow_engine).run_once()
    store, transport = CoordinatorAnnotationStore(), StubTransport()
    before = business_fingerprints(flow_engine)
    result, = worker(flow_engine, transport, store).run_once()
    assert business_fingerprints(flow_engine) == before
    assert (result.case_id, result.outcome, result.attempts, result.statement_count) == (case_id, 'RECORDED', 1, 1)
    call, = transport.calls
    assert call.prompt_version == PROMPT_VERSION and call.model_id == 'stub-model'
    assert json.loads(call.input_json) == {'statements': [{'kind': 'ORIGINAL', 'text': '  synthetic original    '}],
                                           'original_requested_outcome': 'UNSPECIFIED', 'has_order_reference': True}
    assert 'SYN-1001' not in call.input_json and 'synthetic original' not in call.system_prompt
    # ORDER_MATCHED advances input_version without a new statement: same digest.
    assert InvestigationProcessor(flow_engine, retry_seconds=0).run_once()
    before = business_fingerprints(flow_engine)
    detail = founder_read(flow_engine, identities, case_id, store)
    assert detail['input_version'] == 2 and detail['status'] == 'POLICY_ASSESSMENT'
    assert detail['facts'] == FACTS
    plain = founder_read(flow_engine, identities, case_id)
    assert 'facts' not in plain and set(detail) - set(plain) == {'facts'}
    assert worker(flow_engine, transport, store).run_once() == [] and len(transport.calls) == 1
    assert business_fingerprints(flow_engine) == before
    assert_integrity(flow_engine, case_id)


def test_clarification_retires_the_old_entry_and_records_a_new_digest(flow_engine, identities):
    flow = identities.flow()
    case_id = flow.create({'original_message': 'My mug arrived cracked. Email jo@example.com please.'},
                          'showcase-create', identifier('corr')).body['case_id']
    assert IntakeProcessor(flow_engine).run_once()
    store, transport = CoordinatorAnnotationStore(), StubTransport()
    first, = worker(flow_engine, transport, store).run_once()
    assert first.outcome == 'RECORDED' and first.redaction_counts == {'email': 1, 'phone': 0, 'order_reference': 0}
    assert 'jo@example.com' not in transport.calls[0].input_json
    assert founder_read(flow_engine, identities, case_id, store)['facts'] == FACTS
    view = flow.get_case(case_id).body
    request = {'expected_case_version': view['case_version'], 'question_set_id': view['clarification']['question_set_id'],
               'answers': [{'question_id': view['clarification']['questions'][0]['question_id'],
                            'text': 'It was a gift; the order was SYN-2002.'}], 'evidence_ids': []}
    flow.clarify(case_id, request, 'showcase-answer', identifier('corr'))
    assert 'facts' not in founder_read(flow_engine, identities, case_id, store)
    assert store.state(first.input_digest) is None
    assert worker(flow_engine, transport, store).run_once() == []
    assert IntakeProcessor(flow_engine).run_once()
    second, = worker(flow_engine, transport, store).run_once()
    assert second.outcome == 'RECORDED' and second.input_digest != first.input_digest and second.statement_count == 2
    assert second.redaction_counts == {'email': 1, 'phone': 0, 'order_reference': 1}
    assert [s['kind'] for s in json.loads(transport.calls[1].input_json)['statements']] == ['ORIGINAL', 'CLARIFICATION']
    assert founder_read(flow_engine, identities, case_id, store)['facts'] == FACTS
    assert_integrity(flow_engine, case_id)


def test_retention_removal_stops_projection_and_evicts(flow_engine, identities):
    body = accepted(identities)
    case_id = body['case_id']
    assert IntakeProcessor(flow_engine).run_once()
    store = CoordinatorAnnotationStore()
    result, = worker(flow_engine, StubTransport(), store).run_once()
    assert result.outcome == 'RECORDED' and founder_read(flow_engine, identities, case_id, store)['facts'] == FACTS
    assert RetentionService(flow_engine).remove('STATEMENT', body['statements'][0]['statement_id'])
    assert 'facts' not in founder_read(flow_engine, identities, case_id, store)
    assert store.state(result.input_digest) is None and len(store) == 0
    assert worker(flow_engine, StubTransport(), store).run_once() == []
    assert_integrity(flow_engine, case_id)


def test_rejected_and_failed_replies_project_nothing_and_write_nothing(flow_engine, identities):
    body = accepted(identities)
    case_id = body['case_id']
    assert IntakeProcessor(flow_engine).run_once()
    before = business_fingerprints(flow_engine)
    store = CoordinatorAnnotationStore()
    supported = StubTransport(json.dumps({**FACTS, 'assessment_status': 'SUPPORTED'}))
    result, = worker(flow_engine, supported, store).run_once()
    assert (result.outcome, result.failure_code) == ('REJECTED', 'SUPPORTED')
    assert 'facts' not in founder_read(flow_engine, identities, case_id, store)
    other = CoordinatorAnnotationStore()
    failing = StubTransport(error='HTTP_5XX')
    result, = worker(flow_engine, failing, other, retry_delays=(0, 0)).run_once()
    assert (result.outcome, result.failure_code, result.attempts, len(failing.calls)) == ('FAILED', 'HTTP_5XX', 3, 3)
    assert 'facts' not in founder_read(flow_engine, identities, case_id, other)
    assert business_fingerprints(flow_engine) == before
    assert_integrity(flow_engine, case_id)


def test_feature_off_keeps_the_existing_view(flow_engine, identities):
    body = accepted(identities)
    case_id = body['case_id']
    assert IntakeProcessor(flow_engine).run_once()
    plain = founder_read(flow_engine, identities, case_id)
    empty = founder_read(flow_engine, identities, case_id, CoordinatorAnnotationStore())
    assert 'facts' not in plain and set(plain) == set(empty)
    assert plain['statements'] == empty['statements'] == body['statements']
