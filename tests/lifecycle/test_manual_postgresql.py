"""A201 manual-first variants: actual PG entries, receipts and fenced failures."""
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from sqlalchemy import delete, select, update
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_api.main import create_app
from returnops_domain import customer_tables as old, investigation_tables as inv, lifecycle_tables as t
from returnops_domain.audit import identifier
from returnops_domain.canonical import decode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.founder_service import FounderQueries
from returnops_domain.lifecycle_guards import LifecycleGuards
from returnops_domain.manual_denial import COMPONENT, OPERATION
from returnops_domain.registry import TrustedRegistry
from returnops_domain.retention import RetentionService
from manual_helpers import ready, rows, service, snapshot, business, evidence, assert_pending, now

KINDS = ['failure', 'block']


def expire_human(monkeypatch):
    """Advance the real F.03 post-registry session-time check, not resource TTL."""
    from returnops_api.security import authentication
    class ExpiredClock:
        @staticmethod
        def now(tz):
            return now() + timedelta(seconds=1000)
    monkeypatch.setattr(authentication, 'datetime', ExpiredClock)


@pytest.mark.parametrize('source', ['COORDINATOR','ASSESSMENT'])
def test_A201_01_other_real_failure_entries(flow_engine, identities, enabled, request, source):
    from returnops_domain.intake_processor import IntakeProcessor
    from manual_helpers import provision_outcome
    if source == 'COORDINATOR':
        case = identities.flow().create({'original_message':'Original intake failure source'},
            identifier('create'), identifier('corr')).body['case_id']
        def broken(_): raise RuntimeError('private computation fault')
        processor = IntakeProcessor(flow_engine, evaluate=broken, retry_seconds=0)
        assert not processor.run_once() and processor.run_once()
    else:
        from test_proposal_runtime_postgresql import ready as proposal_ready, add_retained_clarifications
        from returnops_domain.proposal_processor import FixedProposalProcessor
        case = proposal_ready(flow_engine, identities)
        add_retained_clarifications(flow_engine, identities, case, 100)
        processor = FixedProposalProcessor(flow_engine)
        assert processor.process(processor.prepare(case)).status == 'FAILED'
    provision_outcome(flow_engine, identities)
    head = rows(flow_engine, old.case_heads)[0]
    body = dict(expected_case_version=head['case_version'], decision='MANUAL_HANDLING', reason='Manual processing.',
                processing_failure_id=head['current_failure_id'])
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body)
    assert_pending(flow_engine, case, body, result)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), real_failure_stage=source)


@pytest.mark.parametrize('acceptance', ['create','clarification'])
@pytest.mark.parametrize('mutation', ['valid','malformed','case','input','version','principal','refs'])
def test_A201_17_intake_accepted_receipt_proof(flow_engine, identities, enabled, request, acceptance, mutation):
    from returnops_domain.intake_processor import IntakeProcessor
    from returnops_domain.investigation_processor import InvestigationProcessor
    from returnops_domain.canonical import encode_document
    from manual_helpers import provision_outcome
    case = identities.flow().create({'original_message':'Original intake acceptance proof'},
        identifier('create'), identifier('corr')).body['case_id']
    if acceptance == 'clarification':
        assert IntakeProcessor(flow_engine).run_once() and InvestigationProcessor(flow_engine).run_once()
        view = identities.flow().get_case(case).body
        group = rows(flow_engine, inv.groups)[0]
        identities.flow().clarify(case, dict(expected_case_version=view['case_version'],
            question_set_id=view['clarification']['question_set_id'], evidence_ids=[],
            answers=[{'question_id':group['reference_question_id'], 'text':'SYN-1001'}]), identifier('clarify'), identifier('corr'))
    def fail(_): raise RuntimeError('synthetic evaluation fault')
    processor = IntakeProcessor(flow_engine, evaluate=fail, retry_seconds=0)
    assert not processor.run_once() and processor.run_once()
    provision_outcome(flow_engine, identities)
    head = rows(flow_engine, old.case_heads)[0]
    work_id = rows(flow_engine, old.intake_sessions)[0]['current_work_id']
    work = next(r for r in rows(flow_engine, old.intake_work) if r['work_id'] == work_id)
    original = next(r for r in rows(flow_engine, old.receipts) if r['acceptance_id'] == work['acceptance_id'])
    if mutation != 'valid':
        with flow_engine.begin() as connection:
            if mutation == 'principal':
                connection.execute(update(old.intake_work).where(old.intake_work.c.work_id == work_id).values(
                    accepted_principal_id=identities.people['customer_b']['principal_id']))
            elif mutation == 'refs':
                connection.execute(update(old.intake_work).where(old.intake_work.c.work_id == work_id).values(source_refs=encode_document([])))
            else:
                value = decode_document(original['body'])
                if mutation == 'malformed': value = {}
                else: value[{'case':'case_id','input':'input_version','version':'case_version'}[mutation]] = (
                    'wrong_case' if mutation == 'case' else 999)
                connection.execute(update(old.receipts).where(old.receipts.c.acceptance_id == work['acceptance_id']).values(body=encode_document(value)))
    body = dict(expected_case_version=head['case_version'], decision='MANUAL_HANDLING', reason='Manual source proof.',
                processing_failure_id=head['current_failure_id'])
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body)
    if mutation == 'valid': assert_pending(flow_engine, case, body, result)
    else: assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), original_acceptance=acceptance)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', ['human_expiry','lease_expiry','human_revoked','grant_revision'])
def test_A201_16_expensive_final_read_rechecks_authority(flow_engine, identities, enabled, request, monkeypatch, kind, mode):
    from returnops_domain import manual_decision
    case, body = ready(flow_engine, identities, kind)
    original_read = manual_decision.read_target
    def slow_read(uow, head, state, request_body, component, **options):
        result = original_read(uow, head, state, request_body, component, **options)
        if options.get('original_state') is not None:
            if mode == 'human_expiry': expire_human(monkeypatch)
            elif mode == 'lease_expiry': caller.clock = lambda: now() + timedelta(seconds=1000)
            else: mutate_authority(uow, identities, case, 'human_revoked' if mode == 'human_revoked' else 'service_revision')
        return result
    monkeypatch.setattr(manual_decision, 'read_target', slow_read)
    caller = service(flow_engine, identities)
    before = snapshot(flow_engine); result = caller.accept(case, body, 'original-manual-key', identifier('corr'))
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result),
             injected_after='final expensive target-source read; prior lifecycle and HUMAN checks already passed')


@pytest.fixture
def observed(monkeypatch):
    """Observable boundary spies plus effect tables, not adapter absence alone."""
    counts = dict(RETURN=0, LABEL=0, notification_send=0, LLM=0, outbound=0, notification_claim=0)
    original = LifecycleGuards.claim
    def claim(self, uow, work_id, *args, **kwargs):
        work = uow.execute(select(t.work.c.purpose).where(t.work.c.work_id == work_id)).scalar_one()
        if work == 'NOTIFICATION':
            counts['notification_claim'] += 1
        return original(self, uow, work_id, *args, **kwargs)
    monkeypatch.setattr(LifecycleGuards, 'claim', claim)
    # Existing Python effects, if invoked, are observable regardless of whether
    # their adapter is currently registered in default composition.
    names = {'create_return':'RETURN', 'generate_label':'LABEL', 'send_notification':'notification_send',
             'complete':'LLM', 'generate_completion':'LLM', 'invoke_model':'LLM'}
    previous = sys.getprofile()
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code.co_name in names:
            counts[names[frame.f_code.co_name]] += 1
    sys.setprofile(profile)
    import socket
    def outbound(*args, **kwargs):
        counts['outbound'] += 1
        raise AssertionError('Manual component must not open an outbound connection')
    monkeypatch.setattr(socket, 'create_connection', outbound)
    try:
        yield counts
        assert counts == dict.fromkeys(counts, 0)
    finally:
        sys.setprofile(previous)


def attempt(engine, identities, case, body, **options):
    return service(engine, identities, **options).accept(case, body, 'original-manual-key', identifier('corr'))


@pytest.mark.parametrize('kind', KINDS)
def test_A201_01_02_real_manual_sources(flow_engine, identities, enabled, observed, request, kind):
    case, body = ready(flow_engine, identities, kind)
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body)
    assert_pending(flow_engine, case, body, result)
    after = snapshot(flow_engine)
    assert after['lifecycle_authorities'] == before['lifecycle_authorities']
    assert after['order_lookup_receipts'] == before['order_lookup_receipts']
    assert after['order_lookup_contents'] == before['order_lookup_contents']
    assert after['case_heads'][0]['input_version'] == before['case_heads'][0]['input_version']
    audit = [decode_document(r['body']) for r in rows(flow_engine, old.audit)]
    human = next(e for e in audit if e['event_type'] == 'FOUNDER_DECISION_ACCEPTED')
    assert human['actor'] == {'kind':'HUMAN', 'role':'FOUNDER', 'principal_id':identities.people['founder']['principal_id']}
    assert all('payload' not in e and body['reason'] not in str(e) for e in audit)
    reader = FounderQueries(flow_engine, CurrentRequestAuthority(identities.auth_config, 'Bearer ' + identities.tokens['founder']))
    reads_before = snapshot(flow_engine)
    reader.read('getFounderCase', case); reader.read('listFounderCases')
    reader.read('listFounderCaseHistory', case, {'kind':'DECISION'}); reader.read('listCaseAudit', case)
    reads_after = snapshot(flow_engine)
    metadata = {name for name in reads_after if name.startswith('founder_')}
    assert {k:v for k,v in reads_before.items() if k not in metadata} == {k:v for k,v in reads_after.items() if k not in metadata}
    evidence(request.node.nodeid, before=before, after=after, result=asdict(result), effects=observed,
             source='real InvestigationProcessor.finish accepted failure/block', founder_read_metadata=sorted(metadata))


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mutation', ['none','two','wrong_id','actor','scope','input_version','source_version','preview','stale_version'])
def test_A201_13_frozen_request(flow_engine, identities, enabled, request, kind, mutation):
    case, body = ready(flow_engine, identities, kind)
    target = 'processing_failure_id' if kind == 'failure' else 'order_lookup_block_id'
    if mutation == 'none': body.pop(target)
    elif mutation == 'two': body['order_lookup_block_id' if kind == 'failure' else 'processing_failure_id'] = 'other_target'
    elif mutation == 'wrong_id': body[target] = 'wrong_target'
    elif mutation == 'stale_version': body['expected_case_version'] -= 1
    elif mutation == 'preview': body['preview_id'] = 'fake_preview'
    else: body[mutation] = {'principal_id':'fake_founder'} if mutation == 'actor' else 1
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body); after = snapshot(flow_engine)
    assert result.status == 'DENIED' and business(before) == business(after)
    assert result.safe_code in {'VALIDATION_ERROR','INVALID_STATE','STALE_CASE_VERSION'}
    evidence(request.node.nodeid, before=before, after=after, result=asdict(result))


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('decision', ['APPROVE','REJECT','REQUEST_REVISION'])
def test_A201_14_nonmanual_denied(flow_engine, identities, enabled, request, kind, decision):
    case, body = ready(flow_engine, identities, kind); body['decision'] = decision
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', ['missing','customer','revoked','expired','disabled','demoted','wrong_store','foreign_case'])
def test_A201_15_current_human_authority(flow_engine, identities, enabled, request, monkeypatch, kind, mode):
    case, body = ready(flow_engine, identities, kind)
    caller = service(flow_engine, identities, None if mode == 'missing' else 'customer_a' if mode == 'customer' else 'founder')
    registry = TrustedRegistry(flow_engine)
    if mode == 'revoked': registry.revoke_session(identities.sessions['founder']['session_id'])
    elif mode == 'expired': expire_human(monkeypatch)
    elif mode in {'disabled','demoted','wrong_store'}:
        registry.change_principal(identities.people['founder']['principal_id'], **{
            'disabled':{'enabled':False}, 'demoted':{'role':'CUSTOMER'}, 'wrong_store':{'store_id':'other_store'}}[mode])
    elif mode == 'foreign_case':
        with flow_engine.begin() as connection:
            connection.execute(update(old.case_heads).where(old.case_heads.c.case_id == case).values(store_id='other_store'))
    before = snapshot(flow_engine); result = caller.accept(case, body, 'original-manual-key', identifier('corr'))
    assert result.status == 'DENIED' and result.receipt is None and result.audit == 'NOT_RECORDED'
    assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


def mutate_authority(uow, identities, case, mode):
    if mode in {'human_revoked','human_disabled','human_demoted','human_store','owner'}:
        table = old.sessions if mode == 'human_revoked' else old.case_heads if mode == 'owner' else old.principals
        clause = (table.c.session_id == identities.sessions['founder']['session_id'] if mode == 'human_revoked'
            else table.c.case_id == case if mode == 'owner' else table.c.principal_id == identities.people['founder']['principal_id'])
        values = {'human_revoked':{'revoked':True}, 'human_disabled':{'enabled':False},
            'human_demoted':{'role':'CUSTOMER'}, 'human_store':{'store_id':'other_store'},
            'owner':{'owner_principal_id':identities.people['customer_b']['principal_id']}}[mode]
        uow.execute(update(table).where(clause).values(**values))
    elif mode == 'service_missing':
        uow.execute(delete(t.authorities).where(t.authorities.c.component_id == COMPONENT))
    elif mode in {'service_revoked','service_revision'}:
        uow.execute(update(t.authorities).where(t.authorities.c.component_id == COMPONENT).values(
            **({'enabled':False} if mode == 'service_revoked' else {'revision':2})))
    elif mode in {'claim','lease'}:
        uow.execute(update(t.work).where(t.work.c.component_id == COMPONENT, t.work.c.purpose == 'OUTCOME').values(
            **({'claim_id':'replaced_claim'} if mode == 'claim' else {'authority_revision':2})))


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', ['human_revoked','human_disabled','human_demoted','human_store','owner',
                                  'service_missing','service_revoked','service_revision','claim','lease','human_expired','claim_expired'])
def test_A201_16_before_commit_both_authorities(flow_engine, identities, enabled, request, monkeypatch, kind, mode):
    case, body = ready(flow_engine, identities, kind)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if mode == 'human_expired': expire_human(monkeypatch)
            elif mode == 'claim_expired': caller.guard.clock = lambda: now() + timedelta(seconds=1000)
            else: mutate_authority(self, identities, case, mode)
            return super().commit()
    caller = service(flow_engine, identities, uow_factory=Changed)
    before = snapshot(flow_engine); result = caller.accept(case, body, 'original-manual-key', identifier('corr'))
    after = snapshot(flow_engine)
    assert result.status == 'DENIED' and business(before) == business(after)
    if mode == 'human_expired': assert result.audit == 'NOT_RECORDED'
    evidence(request.node.nodeid, before=before, after=after, result=asdict(result), injection='inside original fenced UoW before commit')


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', ['service_missing','service_revoked'])
def test_A201_16_entry_service_authority(flow_engine, identities, enabled, request, kind, mode):
    case, body = ready(flow_engine, identities, kind)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        mutate_authority(uow, identities, case, mode); uow.commit()
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body)
    assert result.status == 'DENIED' and result.audit == 'NOT_RECORDED' and snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', ['zero','dual','input','generation','receipt_unavailable','receipt_hash','work_binding','source_body','cross_case'])
def test_A201_17_stale_authoritative_sources(flow_engine, identities, enabled, request, kind, mode):
    case, body = ready(flow_engine, identities, kind)
    if mode == 'generation':
        from returnops_domain.lifecycle_state import current
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            head = uow.execute(select(old.case_heads).where(old.case_heads.c.case_id == case)).mappings().one()
            current(uow, head, initialize=True); uow.commit()
    with flow_engine.begin() as connection:
        if mode == 'zero':
            connection.execute(update(old.case_heads if kind == 'failure' else inv.state).values(
                **({'current_failure_id':None} if kind == 'failure' else {'current_block_id':None})))
        elif mode == 'dual':
            connection.execute(update(inv.state if kind == 'failure' else old.case_heads).values(
                **({'current_block_id':'fake_block'} if kind == 'failure' else {'current_failure_id':'fake_failure'})))
        elif mode == 'input': connection.execute(update(old.case_heads).values(input_version=2))
        elif mode == 'generation': connection.execute(update(t.state).values(generation=t.state.c.generation + 1))
        elif mode == 'receipt_unavailable':
            connection.execute(update(inv.receipts).values(available=False)); connection.execute(delete(inv.receipt_contents))
        elif mode == 'receipt_hash': connection.execute(update(inv.receipts).values(body_hash='f' * 64))
        elif mode == 'work_binding': connection.execute(update(inv.work).values(claim_id='different_claim'))
        elif mode == 'source_body':
            target = next(r for r in rows(flow_engine, old.history) if r['kind'] in {'PROCESSING_FAILURE','ORDER_LOOKUP_BLOCK'})
            connection.execute(update(old.history_contents).where(old.history_contents.c.record_id == target['record_id']).values(body=b'{}'))
        else:
            connection.execute(update(inv.receipts).values(case_id='foreign_case'))
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), negative_fixture=mode)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', ['input','generation','source_body','receipt','claim_binding'])
def test_A201_17_before_commit_source_changes(flow_engine, identities, enabled, request, kind, mode):
    case, body = ready(flow_engine, identities, kind)
    source = next(r for r in rows(flow_engine, old.history) if r['kind'] in {'PROCESSING_FAILURE','ORDER_LOOKUP_BLOCK'})
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if mode == 'input': self.execute(update(old.case_heads).values(input_version=2))
            elif mode == 'generation': self.execute(update(t.state).values(generation=t.state.c.generation + 1))
            elif mode == 'source_body':
                self.execute(update(old.history_contents).where(old.history_contents.c.record_id == source['record_id']).values(body=b'{}'))
            elif mode == 'receipt': self.execute(update(inv.receipts).values(body_hash='f' * 64))
            else: self.execute(update(inv.work).values(claim_id='late_replaced_claim'))
            return super().commit()
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body, uow_factory=Changed)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), precommit_injection=mode)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('state', ['SUBMITTED','POLICY_ASSESSMENT','RISK_REVIEW','AWAITING_APPROVAL','NOTIFICATION_PENDING',
                                  'NOTIFICATION_FAILED','COMPLETED','REJECTED','MANUAL_HANDLED'])
def test_A201_18_new_intent_states(flow_engine, identities, enabled, request, kind, state):
    case, body = ready(flow_engine, identities, kind)
    with flow_engine.begin() as connection: connection.execute(update(old.case_heads).values(status=state))
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body)
    assert result.status == 'DENIED' and result.safe_code == 'INVALID_STATE'
    assert business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), negative_fixture=state)


@pytest.mark.parametrize('kind', KINDS)
def test_A201_22_23_24_30_replay_conflict_newkey_retention(flow_engine, identities, enabled, observed, request, kind):
    case, body = ready(flow_engine, identities, kind); caller = service(flow_engine, identities)
    accepted = caller.accept(case, body, 'original-manual-key', identifier('corr')); assert_pending(flow_engine, case, body, accepted)
    with flow_engine.begin() as connection: connection.execute(update(old.case_heads).values(status='MANUAL_HANDLED', case_version=old.case_heads.c.case_version + 1))
    before = snapshot(flow_engine)
    assert caller.accept(case, body, 'original-manual-key', identifier('corr')).receipt == accepted.receipt
    assert snapshot(flow_engine) == before
    conflicts = []
    for field, value in [('reason','changed'), ('expected_case_version',body['expected_case_version']+2),
                          ('processing_failure_id' if kind == 'failure' else 'order_lookup_block_id','changed_target')]:
        changed = {**body, field:value}; result = caller.accept(case, changed, 'original-manual-key', identifier('corr'))
        assert result.status == 'DENIED' and result.safe_code == 'IDEMPOTENCY_CONFLICT'
        conflicts.append(asdict(result))
    replacement = {**body, 'expected_case_version':body['expected_case_version'] + 2}
    result = caller.accept(case, replacement, 'replacement-key', identifier('corr'))
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    statement = next(r['object_id'] for r in rows(flow_engine, old.history) if r['kind'] == 'STATEMENT')
    RetentionService(flow_engine).remove('STATEMENT', statement)
    retained = snapshot(flow_engine)
    replay = caller.accept(case, body, 'original-manual-key', identifier('corr'))
    assert replay.status == 'DENIED' and replay.safe_code == 'INVALID_STATE'
    assert snapshot(flow_engine) == retained
    assert caller.recover(case, body, 'original-manual-key').receipt is None
    evidence(request.node.nodeid, accepted=asdict(accepted), conflicts=conflicts, replacement=asdict(result),
             before=before, retained=retained, replay=asdict(replay), effects=observed)


class UnknownCommit(CustomerUnitOfWork):
    actual_commit = True
    def commit(self):
        for check in self._commit_checks: check()
        if self.actual_commit: self.transaction.commit()
        else: self.transaction.rollback()
        self.finished = True
        raise AcceptanceOutcomeUnknown()


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('committed', [True, False])
@pytest.mark.parametrize('revoked', [False, True])
def test_A201_27_28_acceptance_unknown(flow_engine, identities, enabled, request, kind, committed, revoked):
    case, body = ready(flow_engine, identities, kind)
    class Unknown(UnknownCommit): actual_commit = committed
    caller = service(flow_engine, identities, uow_factory=Unknown)
    before = snapshot(flow_engine)
    result = caller.accept(case, body, 'original-manual-key', identifier('corr'))
    assert result.status == 'UNKNOWN' and result.audit == 'NOT_ATTEMPTED'
    actual = snapshot(flow_engine)  # Independent DB connection after original UoW has closed.
    facts = [r for r in rows(flow_engine, old.acceptances) if r['operation'] == OPERATION]
    assert len(facts) == int(committed)
    if not committed: assert actual == before
    if revoked: TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    recovery_before = snapshot(flow_engine)
    recovered = caller.recover(case, body, 'original-manual-key')
    assert snapshot(flow_engine) == recovery_before
    assert recovered.audit == 'NOT_ATTEMPTED'
    if committed and not revoked:
        assert recovered.status == 'ACCEPTED'; assert_pending(flow_engine, case, body, recovered)
    else: assert recovered.status == 'UNKNOWN' and recovered.receipt is None
    retry = None
    if not committed and not revoked:
        # Actual rollback is independently known from the injected transaction
        # completion plus full-table equality, not inferred from absent fact.
        retry = attempt(flow_engine, identities, case, body)
        assert_pending(flow_engine, case, body, retry)
    evidence(request.node.nodeid, before=before, actual=actual, result=asdict(result),
             recovered=asdict(recovered), retry=None if retry is None else asdict(retry),
             proof='transaction.commit completed' if committed else 'transaction.rollback completed; every table unchanged')


@pytest.mark.parametrize('kind', KINDS)
def test_A201_28_absence_is_unresolved(flow_engine, identities, enabled, request, kind):
    case, body = ready(flow_engine, identities, kind); before = snapshot(flow_engine)
    result = service(flow_engine, identities).recover(case, body, 'never-observed-key')
    assert result.status == 'UNKNOWN' and result.audit == 'NOT_ATTEMPTED' and snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), rollback_proof=False)


@pytest.mark.parametrize('kind', KINDS)
def test_A201_29_every_write_rolls_back(flow_engine, identities, enabled, observed, request, kind):
    case, body = ready(flow_engine, identities, kind)
    trace = []
    class Probe(CustomerUnitOfWork):
        def execute(self, statement, parameters=None):
            if not getattr(statement, 'is_select', False) and getattr(statement, 'table', None) is not None:
                trace.append(str(statement.table.name) + ':' + ('insert' if statement.is_insert else 'update' if statement.is_update else 'delete'))
            return super().execute(statement, parameters)
        def commit(self):
            for check in self._commit_checks: check()
            self.poison(); raise FlowError('INVALID_STATE')
    before = snapshot(flow_engine)
    probe = attempt(flow_engine, identities, case, body, uow_factory=Probe)
    assert probe.status == 'DENIED' and len(trace) >= 20
    assert business(snapshot(flow_engine)) == business(before)
    results = []
    for point in range(1, len(trace) + 1):
        class Fault(CustomerUnitOfWork):
            writes = 0
            def execute(self, statement, parameters=None):
                if not getattr(statement, 'is_select', False) and getattr(statement, 'table', None) is not None:
                    self.writes += 1
                    if self.writes == point:
                        self.poison(); raise RuntimeError('RAW-SENSITIVE-SQL-DO-NOT-EXPOSE')
                return super().execute(statement, parameters)
        original = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body, uow_factory=Fault)
        after = snapshot(flow_engine)
        assert result.status == 'DENIED' and business(original) == business(after)
        assert 'RAW-SENSITIVE' not in str(asdict(result))
        results.append(dict(point=point, write=trace[point - 1], result=asdict(result), before=original, after=after))
    evidence(request.node.nodeid, trace=trace, probe=asdict(probe), faults=results, effects=observed)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', ['recorded','revoked','audit_committed_unknown','audit_rolledback_unknown'])
def test_A201_32_fresh_denial_transactions(flow_engine, identities, enabled, request, kind, mode):
    case, body = ready(flow_engine, identities, kind)
    class Original(CustomerUnitOfWork):
        exited = False
        def __exit__(self, *args):
            result = super().__exit__(*args); type(self).exited = True
            if mode == 'revoked': TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
            return result
    class Audit(UnknownCommit if 'unknown' in mode else CustomerUnitOfWork):
        actual_commit = mode == 'audit_committed_unknown'
        enters = 0
        def __enter__(self):
            assert Original.exited
            type(self).enters += 1
            return super().__enter__()
    body['expected_case_version'] -= 1
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, uow_factory=Original, audit_uow=Audit)
    after = snapshot(flow_engine)
    assert result.status == 'DENIED' and Audit.enters == 1
    assert result.audit == ('RECORDED' if mode == 'recorded' else 'NOT_RECORDED' if mode == 'revoked' else 'UNKNOWN')
    delta = len(after['customer_audit_events']) - len(before['customer_audit_events'])
    assert delta == int(mode in {'recorded','audit_committed_unknown'})
    if mode != 'revoked': assert business(after) == business(before)
    for row in rows(flow_engine, old.audit):
        event = decode_document(row['body'])
        if event['event_type'] == 'FOUNDER_MANUAL_DENIED':
            from returnops_domain.canonical import digest
            assert event['payload_hash'] == digest({'purpose':'OUTCOME', 'reason':'STALE_CASE_VERSION'}, 'audit-payload/v1')
            assert 'payload' not in event
            assert event['history_refs'] == [] and event['object_ids'] == []
    evidence(request.node.nodeid, before=before, after=after, result=asdict(result), audit_enters=Audit.enters)


@pytest.mark.parametrize('kind', KINDS)
def test_A201_25_independent_processes(flow_engine, identities, enabled, request, kind, tmp_path):
    case, body = ready(flow_engine, identities, kind)
    # Synthetic test auth exists only in this task-owned ephemeral fixture file.
    config = identities.auth_config
    config_path = tmp_path / 'synthetic-process.json'
    config_path.write_text(json.dumps(dict(case=case, request=body, schema=flow_engine._customer_test_schema,
        issuer=config.issuer, audience=config.audience, signing_key=config.signing_key.hex(),
        token=identities.tokens['founder'])), encoding='utf-8')
    probe = Path(__file__).with_name('manual_process_probe.py')
    processes = [subprocess.Popen([sys.executable, '-B', str(probe), str(config_path)], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=os.environ.copy()) for _ in range(2)]
    outputs = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=45)
        assert process.returncode == 0 and stderr == b''
        outputs.append(json.loads(stdout))
    # Each caller may re-send its key after the retryable 503 transient (#103); the attempt records
    # are compared separately and every other field must be identical.
    diagnostics = json.dumps([{name: output.get(name) for name in ('status', 'safe_code', 'audit', 'attempts')}
                              for output in outputs], sort_keys=True)
    for output in outputs:
        assert 1 <= len(output['attempts']) <= 3 and output['attempts'][-1]['status'] == output['status'], diagnostics
        for earlier in output['attempts'][:-1]:
            assert (earlier['status'], earlier['safe_code']) == ('DENIED', 'INTERNAL_ERROR'), diagnostics
    final = [{name: value for name, value in output.items() if name != 'attempts'} for output in outputs]
    assert final[0] == final[1] and final[0]['status'] == 'ACCEPTED', diagnostics
    assert not any(outputs[0]['effects'].values()), diagnostics
    assert len([r for r in rows(flow_engine, old.acceptances) if r['operation'] == OPERATION]) == 1
    assert len([r for r in rows(flow_engine, old.history) if r['kind'] == 'DECISION']) == 1
    assert len([r for r in rows(flow_engine, t.work) if r['purpose'] == 'NOTIFICATION']) == 1
    evidence(request.node.nodeid, outputs=outputs, after=snapshot(flow_engine), independent_process_count=2)


@pytest.mark.parametrize('kind', KINDS)
def test_A201_34_private_composition_default_unregistered(flow_engine, identities, enabled, observed, request, kind):
    case, body = ready(flow_engine, identities, kind, grant=False)
    app = create_app(engine=flow_engine, auth_config=identities.auth_config)
    assert not any('POST' in getattr(r, 'methods', set()) and 'decision' in r.path for r in app.routes)
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body)
    assert result.status == 'DENIED' and result.audit == 'NOT_RECORDED' and snapshot(flow_engine) == before
    from manual_helpers import provision_outcome
    provision_outcome(flow_engine, identities)
    grants = rows(flow_engine, t.authorities)
    result = attempt(flow_engine, identities, case, body)
    assert_pending(flow_engine, case, body, result)
    assert rows(flow_engine, t.authorities) == grants
    assert not any(r['purpose'] == 'NOTIFICATION' for r in grants)
    evidence(request.node.nodeid, result=asdict(result), after=snapshot(flow_engine), effects=observed,
             default_route_paths=[r.path for r in app.routes], source_module=sys.modules['returnops_api.private_manual'].__file__)


@pytest.fixture(scope='module')
def installed_manual(tmp_path_factory):
    """Use an exact prebuilt target, or build offline in this fixture's own dir."""
    import shutil
    root = Path(__file__).resolve().parents[2]
    path = os.environ.get('MANUAL_INSTALLED_DIR')
    if path:
        installed = Path(path)
    else:
        build = tmp_path_factory.mktemp('manual-install')
        source = build / 'source'; source.mkdir()
        shutil.copy2(root / 'pyproject.toml', source / 'pyproject.toml')
        for directory in ['packages','apps/api']:
            shutil.copytree(root / directory, source / directory, ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info'))
        environment = {**os.environ, 'PIP_NO_INDEX':'1', 'PIP_DISABLE_PIP_VERSION_CHECK':'1'}
        result = subprocess.run([sys.executable,'-B','-m','pip','wheel','--no-deps','--no-build-isolation',
            '--wheel-dir',str(build / 'wheels'),str(source)], env=environment, cwd=build, capture_output=True)
        assert result.returncode == 0
        wheel, = list((build / 'wheels').glob('*.whl'))
        installed = build / 'installed'
        result = subprocess.run([sys.executable,'-B','-m','pip','install','--no-deps','--target',str(installed),str(wheel)],
            env=environment, cwd=build, capture_output=True)
        assert result.returncode == 0
    for name in ['manual_decision.py','manual_target.py','manual_denial.py']:
        assert (root / 'packages/returnops_domain' / name).read_bytes() == (installed / 'returnops_domain' / name).read_bytes()
    assert (root / 'apps/api/returnops_api/private_manual.py').read_bytes() == (installed / 'returnops_api/private_manual.py').read_bytes()
    return installed


@pytest.mark.parametrize('kind', KINDS)
def test_A201_34_installed_real_private_call(flow_engine, identities, enabled, request, kind, tmp_path, installed_manual):
    case, body = ready(flow_engine, identities, kind)
    config = identities.auth_config
    path = tmp_path / 'synthetic-installed-call.json'
    path.write_text(json.dumps(dict(case=case, request=body, schema=flow_engine._customer_test_schema,
        issuer=config.issuer, audience=config.audience, signing_key=config.signing_key.hex(),
        token=identities.tokens['founder'])), encoding='utf-8')
    before = snapshot(flow_engine)
    result = subprocess.run([sys.executable,'-I','-B',str(Path(__file__).with_name('manual_process_probe.py')),
        str(path),str(installed_manual)], cwd=tmp_path, env=os.environ.copy(), capture_output=True, timeout=30)
    assert result.returncode == 0 and result.stderr == b''
    accepted = json.loads(result.stdout)
    assert accepted['status'] == 'ACCEPTED' and accepted['receipt']['case_version'] == body['expected_case_version'] + 1
    assert not any(accepted['effects'].values())
    after = snapshot(flow_engine)
    assert after['lifecycle_authorities'] == before['lifecycle_authorities']
    assert rows(flow_engine, old.case_heads)[0]['status'] == 'NOTIFICATION_PENDING'
    assert not rows(flow_engine, t.effects)
    evidence(request.node.nodeid, before=before, after=after, result=accepted, installed_path=str(installed_manual),
             isolated_python=True, caller_working_directory=str(tmp_path))
