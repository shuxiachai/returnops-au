"""RVP01-05/08: actual retained PASS revision; real PG only in approved CI.

Malformed fixtures mutate persisted rows only after real accepted prerequisites.
They retain database constraints and require a service/Domain denial, not a SQL
constraint exception presented as application validation.
"""
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

from returnops_domain import customer_tables as old, lifecycle_tables as t
from returnops_domain.canonical import digest
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.preview_tables import previews
from returnops_domain.registry import TrustedRegistry
from returnops_domain.revision_denial import COMPONENT, OPERATION
from manual_helpers import business, evidence, rows, snapshot, now
from pass_revision_helpers import (ready, attempt, service, provision, case_rows,
    assert_revised, mutate_authority, mutate_source, mutate_preview)
from test_manual_postgresql import observed, expire_human, UnknownCommit, installed_manual


@pytest.mark.parametrize('outcome', ['PASS', 'PASS_WITH_WARNING'])
@pytest.mark.parametrize('preview_mode', ['none', 'valid', 'expired'])
def test_RVP01_six_actual_pass_revision_paths(flow_engine, identities, enabled, observed, request, outcome, preview_mode):
    case, body, action, at = ready(flow_engine, identities, outcome=outcome, preview_mode=preview_mode)
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at)
    assert_revised(flow_engine, case, body, result, before=before, action=action)
    assert not any(row['purpose'] in {'APPROVAL', 'EXECUTION'} for row in rows(flow_engine, t.authorities))
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), effects=observed)


@pytest.mark.parametrize('preview_mode', ['valid', 'expired'])
def test_RVP01_two_real_expired_replacements_consume_only_tail(flow_engine, identities, enabled, request, preview_mode):
    case, body, action, at = ready(flow_engine, identities, preview_mode=preview_mode, replacements=2)
    chain = sorted(case_rows(flow_engine, previews, case), key=lambda row:row['post_case_version'])
    assert len(chain) == 3 and chain[0]['previous_preview_id'] is None
    for previous, current in zip(chain, chain[1:]):
        assert current['previous_preview_id'] == previous['preview_id']
        assert current['pre_case_version'] == previous['post_case_version']
        assert current['issued_at'] >= previous['expires_at']
    before = snapshot(flow_engine)
    caller = service(flow_engine, identities, clock=lambda:at)
    accepted = caller.accept(case, body, 'chain-revision-key', 'chain_revision')
    assert_revised(flow_engine, case, body, accepted, before=before, action=action)
    after = snapshot(flow_engine)
    replay = caller.accept(case, body, 'chain-revision-key', 'chain_replay')
    recovered = caller.recover(case, body, 'chain-revision-key')
    assert replay.receipt == recovered.receipt == accepted.receipt and snapshot(flow_engine) == after
    remaining = sorted(case_rows(flow_engine, previews, case), key=lambda row:row['post_case_version'])
    assert all(row['consuming_decision_record_id'] is None and row['consumed_at'] is None for row in remaining[:-1])
    assert remaining[-1]['post_case_version'] == body['expected_case_version']
    evidence(request.node.nodeid, before=before, after=after, accepted=asdict(accepted), replay=asdict(replay), recovery=asdict(recovered))


@pytest.mark.parametrize('unfinished', ['PENDING', 'RUNNING', 'PAUSED'])
def test_RVP01_revision_supersedes_each_unfinished_bookkeeping_state(flow_engine, identities, enabled, request, unfinished):
    from returnops_domain.lifecycle_events import OutcomeAccepted
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from returnops_domain.manual_denial import COMPONENT as MANUAL
    from manual_helpers import provision_outcome
    case, body, action, at = ready(flow_engine, identities)
    provision_outcome(flow_engine, identities)
    guard = LifecycleGuards(MANUAL)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        work_id = guard.prepare(uow, case, body['expected_case_version'], OutcomeAccepted, at)
        if unfinished == 'RUNNING':
            assert guard.claim(uow, work_id, at) is not None
        elif unfinished == 'PAUSED':
            # Explicit fixture-only work bookkeeping. The case/proposal/review
            # and the successful revision still use their real accepted paths.
            assert uow.execute(update(t.work).where(t.work.c.work_id == work_id).values(state='PAUSED')).rowcount == 1
        uow.commit()
    prior = next(row for row in rows(flow_engine, t.work) if row['work_id'] == work_id)
    assert prior['state'] == unfinished
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at)
    assert_revised(flow_engine, case, body, result, before=before, action=action)
    after = next(row for row in rows(flow_engine, t.work) if row['work_id'] == work_id)
    assert after['state'] == 'SUPERSEDED' and after['epoch'] == prior['epoch'] + 1
    assert after['claim_id'] is None and after['lease_expires_at'] is None
    assert after['claimed_case_version'] == prior['claimed_case_version']
    assert after['authority_revision'] == prior['authority_revision']
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), original_work=prior, superseded=after)


SOURCES = ['review_event', 'proposal_event', 'review_binding', 'review_claim', 'review_generation',
    'review_projection', 'review_body', 'proposal_body', 'order_raw', 'order_claim', 'order_available',
    'raw_statement', 'evidence_raw', 'order_projection', 'input', 'generation', 'failure', 'block',
    'missing_review', 'review_fingerprint', 'review_ESC', 'review_version']


@pytest.mark.parametrize('mode', SOURCES)
@pytest.mark.parametrize('phase', ['entry', 'final'])
def test_RVP02_full_current_source_is_required(flow_engine, identities, enabled, request, mode, phase):
    # A preview holds an event FK, so the missing-event scenario deliberately
    # uses the equally legal no-preview route rather than catching a SQL error.
    case, body, _, at = ready(flow_engine, identities, preview_mode='none' if mode == 'review_event' else 'valid')
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            mutate_source(uow, mode)
            uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':
                mutate_source(self, mode)
            return super().commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at, uow_factory=Changed)
    assert result.status == 'DENIED' and result.receipt is None
    assert business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=mode, phase=phase)


@pytest.mark.parametrize('mode', ['raw_statement', 'evidence_raw', 'order_projection', 'review_binding', 'missing_review'])
@pytest.mark.parametrize('phase', ['entry', 'final'])
def test_RVP02_domain_proof_survives_bypassed_outer_source_check(flow_engine, identities, enabled, request, monkeypatch, mode, phase):
    from returnops_domain import revision_decision
    from returnops_domain.lifecycle_state import current
    case, body, _, at = ready(flow_engine, identities)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        head = uow.execute(select(old.case_heads).where(old.case_heads.c.case_id == case)).mappings().one()
        seal = revision_decision.read_target(uow, head, current(uow, head), body, COMPONENT)
        preview_seal = revision_decision.read_preview(uow, head, current(uow, head), body['expected_case_version'])
    monkeypatch.setattr(revision_decision, 'read_target', lambda *args, **kwargs:seal)
    original_preview = revision_decision.read_preview
    monkeypatch.setattr(revision_decision, 'read_preview', lambda *args, **kwargs:
        original_preview(*args, **kwargs) if kwargs.get('consumer') is not None else preview_seal)
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            mutate_source(uow, mode)
            uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':
                mutate_source(self, mode)
            return super().commit()
    before = snapshot(flow_engine)
    caller = service(flow_engine, identities, clock=lambda:at, uow_factory=Changed)
    domain_denials = []
    def observe(method_name, original):
        def call(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except FlowError:
                domain_denials.append(method_name)
                raise
        return call
    for method_name in ('prepare', 'claim', 'apply', '_before_commit'):
        monkeypatch.setattr(caller.guard, method_name, observe(method_name, getattr(caller.guard, method_name)))
    result = caller.accept(case, body, 'pass-revision-key', 'lower_domain_revision')
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    assert domain_denials and ('_before_commit' in domain_denials if phase == 'final' else any(
        name in domain_denials for name in ('prepare', 'claim', 'apply')))
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result),
        outer_source_check='both current source and initial preview aliases deliberately bypassed', domain_denials=domain_denials)


@pytest.mark.parametrize('mode', ['body', 'hash', 'audit', 'version', 'generation', 'input', 'chain', 'proposal', 'review', 'consumed'])
@pytest.mark.parametrize('phase', ['entry', 'final'])
def test_RVP03_preview_misbindings_are_denied_by_proof(flow_engine, identities, enabled, request, mode, phase):
    case, body, _, at = ready(flow_engine, identities)
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            mutate_preview(uow, case, mode)
            uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':
                # Domain has cleared the current pointer: restore only a local
                # lookup context, never write an artificial lifecycle state.
                target = self.execute(select(previews).where(previews.c.case_id == case)).mappings().one()
                changes = {'body':dict(body=b'{}'), 'hash':dict(body_hash='0' * 64),
                    'audit':dict(audit_hash='0' * 64), 'version':dict(pre_case_version=target['pre_case_version'] + 5,
                        post_case_version=target['post_case_version'] + 5), 'generation':dict(generation=target['generation'] + 1),
                    'input':dict(input_version=target['input_version'] + 1), 'chain':dict(previous_preview_id=target['preview_id']),
                    'proposal':dict(proposal_record_id=target['review_record_id']), 'review':dict(review_record_id=target['proposal_record_id']),
                    'consumed':dict(consuming_decision_record_id=target['proposal_record_id'], consumed_at=target['issued_at'])}[mode]
                assert self.execute(update(previews).where(previews.c.preview_id == target['preview_id']).values(**changes)).rowcount == 1
            return super().commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at, uow_factory=Changed)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), proof_fault=mode)


@pytest.mark.parametrize('mode', ['equal', 'expired', 'before_issued', 'naive'])
def test_RVP03_expiry_is_allowed_but_invalid_time_is_not(flow_engine, identities, enabled, request, mode):
    case, body, action, at = ready(flow_engine, identities, preview_mode='equal' if mode == 'equal' else 'expired')
    saved, = case_rows(flow_engine, previews, case)
    if mode == 'before_issued':
        at = saved['issued_at'] - timedelta(microseconds=1)
    elif mode == 'naive':
        at = at.replace(tzinfo=None)
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at)
    if mode in {'equal', 'expired'}:
        assert_revised(flow_engine, case, body, result, before=before, action=action)
    else:
        assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), clock=at)


@pytest.mark.parametrize('mode', ['proposal_id', 'proposal_version', 'expected_case_version', 'preview_id', 'scope_fingerprint', 'actor', 'risk_outcome', 'APPROVED', 'missing_review'])
def test_RVP03_request_and_state_are_bounded(flow_engine, identities, enabled, request, mode):
    case, body, _, at = ready(flow_engine, identities)
    if mode in {'proposal_version', 'expected_case_version'}:
        body[mode] += 1
    elif mode in {'proposal_id', 'preview_id', 'scope_fingerprint', 'actor', 'risk_outcome'}:
        body[mode] = 'untrusted_client_field'
    else:
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            if mode == 'APPROVED':
                uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == case).values(status='APPROVED'))
            else:
                uow.execute(update(t.state).where(t.state.c.case_id == case).values(review_record_id=None))
            uow.commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('which', ['old', 'cross_case'])
def test_RVP03_current_preview_cannot_point_to_old_or_foreign_row(flow_engine, identities, enabled, request, which):
    case, body, action, at = ready(flow_engine, identities, replacements=1)
    if which == 'old':
        wrong = min(case_rows(flow_engine, previews, case), key=lambda row:row['post_case_version'])['preview_id']
    else:
        _, _, foreign, _ = ready(flow_engine, identities)
        wrong = foreign['preview_id']
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        assert uow.execute(update(t.state).where(t.state.c.case_id == case).values(preview_id=wrong)).rowcount == 1
        uow.commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), intended_preview=action['preview_id'], injected_preview=wrong)


@pytest.mark.parametrize('phase', ['entry', 'final'])
@pytest.mark.parametrize('mode', ['human_revoked', 'human_disabled', 'human_demoted', 'human_store', 'owner', 'service_missing', 'service_revoked'])
def test_RVP04_fresh_human_and_revision_capability(flow_engine, identities, enabled, request, phase, mode):
    case, body, _, at = ready(flow_engine, identities)
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            mutate_authority(uow, identities, case, mode)
            uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':
                mutate_authority(self, identities, case, mode)
            return super().commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at, uow_factory=Changed)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    if phase == 'entry' and mode != 'owner':
        assert result.audit == 'NOT_RECORDED'
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('mode', ['service_revision', 'claim', 'epoch', 'lease', 'authority', 'generation', 'human_expiry', 'lease_expiry'])
def test_RVP04_original_claim_and_lease_not_replaced(flow_engine, identities, enabled, request, monkeypatch, mode):
    case, body, _, at = ready(flow_engine, identities)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if mode == 'human_expiry':
                expire_human(monkeypatch)
            elif mode == 'lease_expiry':
                caller.clock = caller.guard.clock = lambda:at + timedelta(seconds=1000)
            else:
                mutate_authority(self, identities, case, mode)
            return super().commit()
    caller = service(flow_engine, identities, clock=lambda:at, uow_factory=Changed)
    before = snapshot(flow_engine)
    result = caller.accept(case, body, 'pass-revision-key', 'claim_revision')
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('preview_mode', ['none', 'valid', 'expired'])
def test_RVP04_old_producer_grants_and_approval_are_not_new_revision_authority(flow_engine, identities, enabled, request, preview_mode):
    case, body, action, at = ready(flow_engine, identities, preview_mode=preview_mode)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        uow.execute(update(t.authorities).where(t.authorities.c.purpose.in_(['PROPOSAL', 'REVIEW', 'PREVIEW'])).values(enabled=False, revision=2))
        uow.commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at)
    assert_revised(flow_engine, case, body, result, before=before, action=action)
    assert not any(row['purpose'] == 'APPROVAL' for row in rows(flow_engine, t.authorities))
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


def test_RVP05_replay_conflicts_and_later_actual_generation(flow_engine, identities, enabled, request):
    from returnops_domain.proposal_processor import FixedProposalProcessor
    from pass_review_helpers import build_positive, receiver
    case, body, action, at = ready(flow_engine, identities)
    caller = service(flow_engine, identities, clock=lambda:at)
    accepted = caller.accept(case, body, 'pass-revision-key', 'first_revision')
    assert_revised(flow_engine, case, body, accepted, action=action)
    before = snapshot(flow_engine)
    assert caller.accept(case, body, 'pass-revision-key', 'same_revision').receipt == accepted.receipt
    assert caller.recover(case, body, 'pass-revision-key').receipt == accepted.receipt
    assert snapshot(flow_engine) == before
    conflicts = []
    for field, value in [('reason', 'Changed reason'), ('proposal_id', 'changed_proposal'),
            ('proposal_version', body['proposal_version'] + 1), ('expected_case_version', body['expected_case_version'] + 1)]:
        result = caller.accept(case, {**body, field:value}, 'pass-revision-key', 'conflicting_revision')
        assert result.status == 'DENIED' and result.safe_code == 'IDEMPOTENCY_CONFLICT'
        conflicts.append(asdict(result))
    processor = FixedProposalProcessor(flow_engine, build=build_positive)
    assert processor.process(processor.prepare(case)).status == 'ACCEPTED'
    head, = case_rows(flow_engine, old.case_heads, case)
    assert receiver(flow_engine).accept(case, head['case_version'], 'later-pass-review', 'later_review').status == 'ACCEPTED'
    advanced = snapshot(flow_engine)
    assert caller.accept(case, body, 'pass-revision-key', 'historical_revision').receipt == accepted.receipt
    assert caller.recover(case, body, 'pass-revision-key').receipt == accepted.receipt
    assert snapshot(flow_engine) == advanced
    evidence(request.node.nodeid, before=before, advanced=advanced, accepted=asdict(accepted), conflicts=conflicts)


@pytest.mark.parametrize('field', ['reason', 'proposal_id', 'proposal_version', 'expected_case_version'])
def test_RVP05_matching_forged_fingerprint_cannot_rebind_original_decision(flow_engine, identities, enabled, request, field):
    case, body, action, at = ready(flow_engine, identities)
    caller = service(flow_engine, identities, clock=lambda:at)
    accepted = caller.accept(case, body, 'pass-revision-key', 'revision')
    assert_revised(flow_engine, case, body, accepted, action=action)
    altered = {**body, field:body[field] + 1 if isinstance(body[field], int)
        else 'Changed original value' if field == 'reason' else 'changed_original_value'}
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        assert uow.execute(update(old.acceptances).where(old.acceptances.c.operation == OPERATION,
            old.acceptances.c.target == case).values(fingerprint=digest(altered, 'founder-revision-request/v1'))).rowcount == 1
        uow.commit()
    before = snapshot(flow_engine)
    replay = caller.accept(case, altered, 'pass-revision-key', 'forged_replay')
    recovered = caller.recover(case, altered, 'pass-revision-key')
    assert replay.status == 'DENIED' and recovered.status == 'UNKNOWN'
    assert business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), replay=asdict(replay), recovery=asdict(recovered), forged_request_field=field)


@pytest.mark.parametrize('mode', ['target_hash', 'event_generation', 'event_fingerprint', 'binding_target', 'claim', 'request_key', 'receipt_version', 'receipt_time', 'receipt_decision', 'acceptance_time'])
def test_RVP05_replay_requires_original_fact_receipt_and_history(flow_engine, identities, enabled, request, mode):
    from returnops_domain.canonical import decode_document, encode_document
    case, body, action, at = ready(flow_engine, identities)
    caller = service(flow_engine, identities, clock=lambda:at)
    accepted = caller.accept(case, body, 'pass-revision-key', 'revision')
    assert_revised(flow_engine, case, body, accepted, action=action)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        work = uow.execute(select(t.work).where(t.work.c.component_id == COMPONENT)).mappings().one()
        fact = uow.execute(select(old.acceptances).where(old.acceptances.c.operation == OPERATION)).mappings().one()
        if mode in {'target_hash', 'claim'}:
            uow.execute(update(t.work).where(t.work.c.work_id == work['work_id']).values(**(
                {'target_hash':'0' * 64} if mode == 'target_hash' else {'claim_id':'replaced_claim'})))
        elif mode.startswith('event_'):
            uow.execute(update(t.events).where(t.events.c.event_kind == 'REVISION').values(**(
                {'generation':99} if mode == 'event_generation' else {'fingerprint':'0' * 64})))
        elif mode == 'binding_target':
            uow.execute(update(t.sources).where(t.sources.c.work_id == work['work_id']).values(target_record_id=None))
        elif mode == 'request_key':
            uow.execute(update(old.acceptances).where(old.acceptances.c.acceptance_id == fact['acceptance_id']).values(request_key='changed-original-key'))
        elif mode == 'acceptance_time':
            uow.execute(update(old.acceptances).where(old.acceptances.c.acceptance_id == fact['acceptance_id']).values(accepted_at=fact['accepted_at'] + timedelta(seconds=1)))
        else:
            row = uow.execute(select(old.receipts).where(old.receipts.c.acceptance_id == fact['acceptance_id'])).mappings().one()
            receipt = decode_document(row['body'])
            if mode == 'receipt_version':
                receipt['case_version'] += 1
            elif mode == 'receipt_time':
                from returnops_domain.audit import timestamp
                receipt['accepted_at'] = timestamp(fact['accepted_at'] + timedelta(seconds=1))
            else:
                receipt['decision_id'] = 'different_decision'
            uow.execute(update(old.receipts).where(old.receipts.c.acceptance_id == fact['acceptance_id']).values(body=encode_document(receipt)))
        uow.commit()
    before = snapshot(flow_engine)
    replay = caller.accept(case, body, 'pass-revision-key', 'broken_replay')
    recovered = caller.recover(case, body, 'pass-revision-key')
    assert replay.status == 'DENIED' and recovered.status == 'UNKNOWN'
    assert business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), replay=asdict(replay), recovery=asdict(recovered))


@pytest.mark.parametrize('committed', [True, False])
@pytest.mark.parametrize('revoked', [True, False])
def test_RVP05_unknown_has_no_automatic_retry_or_denial(flow_engine, identities, enabled, request, committed, revoked):
    case, body, _, at = ready(flow_engine, identities)
    class Unknown(UnknownCommit):
        actual_commit = committed
    caller = service(flow_engine, identities, clock=lambda:at, uow_factory=Unknown)
    before = snapshot(flow_engine)
    result = caller.accept(case, body, 'pass-revision-key', 'unknown_revision')
    assert result.status == 'UNKNOWN' and result.audit == 'NOT_ATTEMPTED'
    actual = snapshot(flow_engine)
    assert len([row for row in rows(flow_engine, old.acceptances) if row['operation'] == OPERATION]) == int(committed)
    if not committed:
        assert actual == before
    if revoked:
        TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    recovery_before = snapshot(flow_engine)
    recovered = caller.recover(case, body, 'pass-revision-key')
    assert recovered.status == ('ACCEPTED' if committed and not revoked else 'UNKNOWN')
    assert recovered.audit == 'NOT_ATTEMPTED' and snapshot(flow_engine) == recovery_before
    evidence(request.node.nodeid, before=before, actual=actual, result=asdict(result), recovery=asdict(recovered), completion='actual commit' if committed else 'actual rollback')


@pytest.mark.parametrize('preview_mode', ['none', 'valid'])
def test_RVP05_each_business_write_and_final_check_roll_back(flow_engine, identities, enabled, observed, request, preview_mode):
    case, body, _, at = ready(flow_engine, identities, preview_mode=preview_mode)
    trace = []
    class Probe(CustomerUnitOfWork):
        def execute(self, statement, parameters=None):
            if not getattr(statement, 'is_select', False) and getattr(statement, 'table', None) is not None:
                trace.append(statement.table.name + (' INSERT' if statement.is_insert else ' UPDATE' if statement.is_update else ' DELETE'))
            return super().execute(statement, parameters)
        def commit(self):
            for check in self._commit_checks:
                check()
            self.poison()
            raise FlowError('INVALID_STATE')
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at, uow_factory=Probe)
    assert result.status == 'DENIED' and len(trace) >= 15 and business(snapshot(flow_engine)) == business(before)
    if preview_mode == 'valid':
        assert previews.name + ' UPDATE' in trace
    outcomes = []
    for point in range(1, len(trace) + 1):
        class Fault(CustomerUnitOfWork):
            writes = 0
            def execute(self, statement, parameters=None):
                if not getattr(statement, 'is_select', False) and getattr(statement, 'table', None) is not None:
                    self.writes += 1
                    if self.writes == point:
                        self.poison()
                        raise RuntimeError('RAW_SENSITIVE_TEST_FAULT')
                return super().execute(statement, parameters)
        before = snapshot(flow_engine)
        denied = attempt(flow_engine, identities, case, body, at, uow_factory=Fault)
        after = snapshot(flow_engine)
        assert denied.status == 'DENIED' and business(after) == business(before)
        assert 'RAW_SENSITIVE' not in str(asdict(denied))
        outcomes.append(dict(point=point, write=trace[point - 1], result=asdict(denied)))
    evidence(request.node.nodeid, trace=trace, outcomes=outcomes, after=snapshot(flow_engine), effects=observed)


@pytest.mark.parametrize('mode', ['recorded', 'revoked', 'audit_committed_unknown', 'audit_rolledback_unknown'])
def test_RVP05_denial_reauthorizes_after_original_transaction_closes(flow_engine, identities, enabled, request, mode):
    case, body, _, at = ready(flow_engine, identities)
    class Original(CustomerUnitOfWork):
        exited = False
        def __exit__(self, *args):
            result = super().__exit__(*args)
            type(self).exited = True
            if mode == 'revoked':
                TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
            return result
    class Audit(UnknownCommit if 'unknown' in mode else CustomerUnitOfWork):
        actual_commit = mode == 'audit_committed_unknown'
        enters = 0
        def __enter__(self):
            assert Original.exited
            type(self).enters += 1
            return super().__enter__()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, {**body, 'expected_case_version':body['expected_case_version'] - 1}, at,
        uow_factory=Original, audit_uow=Audit)
    after = snapshot(flow_engine)
    assert result.status == 'DENIED' and Audit.enters == 1
    assert result.audit == ('RECORDED' if mode == 'recorded' else 'NOT_RECORDED' if mode == 'revoked' else 'UNKNOWN')
    assert len(after[old.audit.name]) - len(before[old.audit.name]) == int(mode in {'recorded', 'audit_committed_unknown'})
    if mode != 'revoked':
        assert business(after) == business(before)
    evidence(request.node.nodeid, before=before, after=after, result=asdict(result), audit_enters=Audit.enters)


@pytest.mark.parametrize('outcome', ['PASS', 'PASS_WITH_WARNING'])
def test_RVP08_installed_private_call_has_exact_modules_and_no_effects(flow_engine, identities, enabled, request, tmp_path, installed_manual, outcome):
    case, body, action, at = ready(flow_engine, identities, outcome=outcome)
    config = identities.auth_config
    source = dict(case=case, request=body, schema=flow_engine._customer_test_schema, issuer=config.issuer,
        audience=config.audience, signing_key=config.signing_key.hex(), token=identities.tokens['founder'], at=at.isoformat())
    path = tmp_path / 'synthetic-pass-revision-installed.json'
    path.write_text(json.dumps(source), encoding='utf-8')
    root = Path(__file__).resolve().parents[2]
    modules = ['revision_decision.py', 'revision_sources.py', 'pass_revision_sources.py', 'revision_denial.py',
        'lifecycle_guards.py', 'preview_sources.py', 'pass_review_sources.py', 'lifecycle_proposal.py']
    hashes = {}
    for name in modules:
        checkout = root / 'packages/returnops_domain' / name
        installed = installed_manual / 'returnops_domain' / name
        assert checkout.read_bytes() == installed.read_bytes()
        hashes[name] = sha256(installed.read_bytes()).hexdigest()
    assert (root / 'apps/api/returnops_api/private_revision.py').read_bytes() == (installed_manual / 'returnops_api/private_revision.py').read_bytes()
    assert not (installed_manual / 'tests').exists() and not (installed_manual / 'pass_revision_helpers.py').exists()
    before = snapshot(flow_engine)
    child = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).with_name('pass_revision_process_probe.py')),
        str(path), str(installed_manual)], cwd=tmp_path, env=os.environ.copy(), capture_output=True, timeout=60)
    assert child.returncode == 0 and child.stderr == b'', (child.returncode, child.stderr.decode(errors='replace'))
    output = json.loads(child.stdout)
    assert output['status'] == 'ACCEPTED' and output['revision_claims'] == 1
    assert not any(output['effects'].values())
    from returnops_domain.revision_decision import RevisionResult
    assert_revised(flow_engine, case, body, RevisionResult(output['status'], output['receipt']), before=before, action=action)
    assert output['module_hashes'] == hashes
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), output=output, installed_hashes=hashes, isolated_python=True, cwd=str(tmp_path))


def test_RVP08_default_composition_does_not_create_revision_grant_or_public_route(flow_engine, identities, enabled, request):
    from returnops_api.main import create_app
    case, body, _, at = ready(flow_engine, identities, grant=False)
    before = snapshot(flow_engine)
    app = create_app(engine=flow_engine, auth_config=identities.auth_config)
    assert not any('POST' in getattr(route, 'methods', set()) and ('decision' in route.path or 'revision' in route.path) for route in app.routes)
    result = attempt(flow_engine, identities, case, body, at)
    assert result.status == 'DENIED' and result.audit == 'NOT_RECORDED' and snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))
