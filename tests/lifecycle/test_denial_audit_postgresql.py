"""Real PG composition proof using an explicitly private, controlled caller.

Future records below are synthetic fixtures. No production denial caller,
proposal producer, Risk PASS, Founder decision, provider or notification runs.
"""
from dataclasses import replace
from datetime import timedelta
import traceback

import pytest
from sqlalchemy import MetaData, delete, select, text, update

from returnops_domain import customer_tables as old, lifecycle_tables as lifecycle
from returnops_domain.audit import identifier, verify_chain
from returnops_domain.canonical import decode_document, digest
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.lifecycle_events import ProposalAccepted
from returnops_domain.lifecycle_guards import LifecycleGuards
from controlled_denial_caller import ControlledCaller, DENIAL_EVENT, Result, TrustedContext
from synthetic_sources import COMPONENT, bind_source, claim, head, material, now, ready, rows, stage


def snapshot(engine):
    """Every physical table, including all six sidecars and original contents."""
    metadata = MetaData()
    with engine.connect() as connection:
        metadata.reflect(bind=connection)
        result = {name: sorted((dict(row) for row in connection.execute(select(table)).mappings()),
                               key=repr) for name, table in metadata.tables.items()}
    assert set(lifecycle.metadata.tables) <= set(result)
    return result


def only_audit_changed(before, after, *, count=1):
    assert set(before) == set(after)
    for name in before:
        if name == old.audit.name:
            assert len(after[name]) == len(before[name]) + count
            assert all(row in after[name] for row in before[name])
        elif name == old.case_heads.name:
            def business(records):
                return [{key: value for key, value in row.items()
                         if key not in {'audit_sequence', 'audit_head'}} for row in records]
            assert business(after[name]) == business(before[name])
        else:
            assert after[name] == before[name], name


def denial_rows(engine):
    return [decode_document(row['body']) for row in rows(engine, old.audit)
            if decode_document(row['body'])['event_type'] == DENIAL_EVENT]


def assert_denial(engine, context, code):
    events = denial_rows(engine)
    assert len(events) == 1
    event = events[0]
    assert event['case_id'] == context.case_id
    assert event['actor'] == {'kind': 'SERVICE', 'component_id': COMPONENT}
    assert event['object_ids'] == event['history_refs'] == []
    assert event['payload_hash'] == digest({'purpose': context.purpose, 'reason': code}, 'audit-payload/v1')
    assert event['correlation_id'].startswith('denial_corr_')
    assert 'payload' not in event and 'reason' not in event
    with CustomerUnitOfWork(engine, write=False) as uow:
        assert verify_chain(uow, context.case_id)


def context_for(engine, case):
    with CustomerUnitOfWork(engine, write=False) as uow:
        current = head(uow, case)
        return TrustedContext(case, current['owner_principal_id'], current['store_id'], 'PROPOSAL')


def staged(uow, identities, case):
    token = claim(uow, case, ProposalAccepted)
    current = head(uow, case)
    body = material('PROPOSAL', current, identities, uow=uow)['content']
    source = stage(uow, current, 'PROPOSAL', body)
    bind_source(uow, source, token)
    return ProposalAccepted(identifier('event'), token, source)


def rejected(identities, case, mode='invalid_state', *, seen=None):
    def operation(uow):
        if seen is not None:
            seen.append(uow)
        event = staged(uow, identities, case)
        guard = LifecycleGuards(COMPONENT)
        if mode == 'invalid_state':
            uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == case).values(status='ESCALATED'))
        elif mode == 'stale_claim':
            event = replace(event, claim=replace(event.claim, epoch=event.claim.epoch + 1))
        elif mode == 'stale_version':
            uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == case).values(
                case_version=event.claim.case_version + 1))
        elif mode == 'before_commit':
            guard.clock = lambda: now() + timedelta(seconds=301)
        guard.apply(uow, event, now())
    return operation


@pytest.mark.parametrize('mode,code', [
    ('invalid_state', 'INVALID_STATE'), ('stale_claim', 'INVALID_STATE'),
    ('stale_version', 'STALE_CASE_VERSION'), ('before_commit', 'INVALID_STATE'),
])
def test_definite_rejection_rolls_back_before_new_authorized_audit(flow_engine, identities, enabled, mode, code):
    case = ready(flow_engine, identities)['case_id']
    context = context_for(flow_engine, case)
    before = snapshot(flow_engine)
    seen, boundaries = [], []

    def new_audit(engine, **kwargs):
        assert len(seen) == 1 and seen[0].finished and seen[0].connection.closed
        assert snapshot(engine) == before
        boundaries.append(True)
        return CustomerUnitOfWork(engine, **kwargs)

    result = ControlledCaller(flow_engine, context, audit_uow=new_audit).run(
        rejected(identities, case, mode, seen=seen))
    assert result == Result('DENIED', code, 'RECORDED')
    assert boundaries == [True]
    after = snapshot(flow_engine)
    only_audit_changed(before, after)
    assert after[old.case_heads.name][0]['audit_sequence'] == before[old.case_heads.name][0]['audit_sequence'] + 1
    assert_denial(flow_engine, context, code)


def test_catching_guard_rejection_cannot_commit_original_poisoned_transaction(flow_engine, identities, enabled):
    case = ready(flow_engine, identities)['case_id']
    before = snapshot(flow_engine)
    context = context_for(flow_engine, case)
    attempts = []

    def operation(uow):
        try:
            rejected(identities, case)(uow)
        except FlowError as error:
            assert error.code == 'INVALID_STATE' and uow.failed
        with pytest.raises(FlowError) as caught:
            uow.commit()
        assert caught.value.code == 'INTERNAL_ERROR'
        attempts.append('poison prevented commit')
        raise FlowError('INVALID_STATE')

    assert ControlledCaller(flow_engine, context).run(operation) == Result('DENIED', 'INVALID_STATE', 'RECORDED')
    assert attempts == ['poison prevented commit']
    only_audit_changed(before, snapshot(flow_engine))
    assert_denial(flow_engine, context, 'INVALID_STATE')


def change_authority(connection, context, mode):
    if mode in {'revoke', 'missing_grant', 'revision'}:
        statement = delete(lifecycle.authorities) if mode == 'missing_grant' else update(lifecycle.authorities).values(
            **({'revision': 2} if mode == 'revision' else {'enabled': False}))
        connection.execute(statement.where(lifecycle.authorities.c.store_id == context.store_id,
            lifecycle.authorities.c.component_id == COMPONENT, lifecycle.authorities.c.purpose == context.purpose))
    elif mode in {'owner_disabled', 'owner_role', 'owner_store'}:
        values = {'owner_disabled': {'enabled': False}, 'owner_role': {'role': 'FOUNDER'},
                  'owner_store': {'store_id': 'synthetic_other_store'}}[mode]
        connection.execute(update(old.principals).where(old.principals.c.principal_id == context.owner_id).values(**values))
    elif mode == 'lifecycle_unavailable':
        connection.execute(update(lifecycle.state).where(lifecycle.state.c.case_id == context.case_id).values(available=False))
    else:
        values = {'owner': {'owner_principal_id': 'synthetic_customer_b'},
                  'store': {'store_id': 'synthetic_other_store'}, 'unavailable': {'available': False}}[mode]
        connection.execute(update(old.case_heads).where(old.case_heads.c.case_id == context.case_id).values(**values))


@pytest.mark.parametrize('mode', ['revoke', 'missing_grant', 'owner', 'store', 'unavailable',
                                  'owner_disabled', 'owner_role', 'owner_store', 'lifecycle_unavailable'])
def test_between_transactions_current_scope_loss_writes_no_audit(flow_engine, identities, enabled, mode):
    case = ready(flow_engine, identities)['case_id']
    context = context_for(flow_engine, case)
    original = snapshot(flow_engine)
    after_change = []

    def new_audit(engine, **kwargs):
        assert snapshot(engine) == original
        with engine.begin() as connection:
            change_authority(connection, context, mode)
        after_change.append(snapshot(engine))
        return CustomerUnitOfWork(engine, **kwargs)

    result = ControlledCaller(flow_engine, context, audit_uow=new_audit).run(rejected(identities, case))
    assert result == Result('DENIED', 'INVALID_STATE', 'NOT_RECORDED')
    assert len(after_change) == 1 and snapshot(flow_engine) == after_change[0]
    assert denial_rows(flow_engine) == []


@pytest.mark.parametrize('mode', ['revoke', 'revision', 'owner', 'store', 'unavailable', 'owner_disabled',
                                  'lifecycle_unavailable', 'sql_write_failure', 'commit_check_failure'])
def test_audit_transaction_rechecks_and_rolls_back_every_staged_change(flow_engine, identities, enabled, mode):
    case = ready(flow_engine, identities)['case_id']
    context = context_for(flow_engine, case)
    before = snapshot(flow_engine)
    attempts = []

    class AuditFault(CustomerUnitOfWork):
        def commit(self):
            attempts.append('audit commit attempted once')
            if mode == 'sql_write_failure':
                self.execute(text('SELECT 1 / 0 AS private_sql_marker'))
            elif mode == 'commit_check_failure':
                def broken():
                    raise RuntimeError('private_commit_callback_marker')
                self.before_commit(broken)
            else:
                change_authority(self.connection, context, mode)
            super().commit()

    result = ControlledCaller(flow_engine, context, audit_uow=AuditFault).run(rejected(identities, case))
    assert result == Result('DENIED', 'INVALID_STATE', 'NOT_RECORDED')
    assert attempts == ['audit commit attempted once']
    assert snapshot(flow_engine) == before and denial_rows(flow_engine) == []


@pytest.mark.parametrize('actually_committed', [False, True])
def test_original_commit_unknown_is_never_a_denial_or_automatic_retry(flow_engine, identities, enabled, actually_committed):
    case = ready(flow_engine, identities)['case_id']
    context = context_for(flow_engine, case)
    before = snapshot(flow_engine)
    calls, saved, audit_calls = [], [], []

    class UnknownOriginal(CustomerUnitOfWork):
        def commit(self):
            if actually_committed:
                super().commit()
            raise AcceptanceOutcomeUnknown()

    def operation(uow):
        calls.append('original once')
        event = staged(uow, identities, case)
        receipt = LifecycleGuards(COMPONENT).apply(uow, event, now())
        saved.append((event, receipt))

    def forbidden_audit(*args, **kwargs):
        audit_calls.append(True)
        raise AssertionError('unknown original was misclassified')

    result = ControlledCaller(flow_engine, context, operation_uow=UnknownOriginal,
                              audit_uow=forbidden_audit).run(operation)
    assert result == Result('UNKNOWN', None, 'NOT_ATTEMPTED')
    assert calls == ['original once'] and audit_calls == [] and denial_rows(flow_engine) == []
    if actually_committed:
        observed = snapshot(flow_engine)
        assert len(observed[lifecycle.events.name]) == 1
        accepted = observed[lifecycle.events.name][0]
        original_event, original_receipt = saved[0]
        assert accepted['event_id'] == original_event.event_id
        assert accepted['record_id'] == original_event.record_id
        assert accepted['work_id'] == original_event.claim.work_id
        assert accepted['case_id'] == case
        for field in ('event_id', 'record_id', 'work_id', 'case_id', 'fingerprint', 'source_hash'):
            assert accepted[field] == original_receipt[field]
        # Explicit existing receipt recovery with the original event identity;
        # no producer is invoked and no new source/event identity is invented.
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            assert LifecycleGuards(COMPONENT).apply(uow, saved[0][0], now()) == saved[0][1]
            uow.commit()
        assert snapshot(flow_engine) == observed and calls == ['original once']
    else:
        assert snapshot(flow_engine) == before
        assert rows(flow_engine, lifecycle.events) == []


@pytest.mark.parametrize('actually_committed', [False, True])
def test_audit_commit_unknown_reports_unknown_without_retry(flow_engine, identities, enabled, actually_committed):
    case = ready(flow_engine, identities)['case_id']
    context = context_for(flow_engine, case)
    before = snapshot(flow_engine)
    attempts = []

    class UnknownAudit(CustomerUnitOfWork):
        def commit(self):
            attempts.append('audit once')
            if actually_committed:
                super().commit()
            raise AcceptanceOutcomeUnknown()

    result = ControlledCaller(flow_engine, context, audit_uow=UnknownAudit).run(rejected(identities, case))
    assert result == Result('DENIED', 'INVALID_STATE', 'UNKNOWN')
    assert attempts == ['audit once']
    if actually_committed:
        only_audit_changed(before, snapshot(flow_engine))
        assert_denial(flow_engine, context, 'INVALID_STATE')
    else:
        assert snapshot(flow_engine) == before and denial_rows(flow_engine) == []


@pytest.mark.parametrize('change', [dict(purpose='AUDIT'), dict(purpose='private_sensitive_purpose'),
                                   dict(component_id='fake_service'), dict(case_id='sensitive invalid id')])
def test_invalid_trusted_configuration_never_runs_operation_or_audit(flow_engine, identities, enabled, change):
    case = ready(flow_engine, identities)['case_id']
    context = replace(context_for(flow_engine, case), **change)
    before = snapshot(flow_engine)
    calls = []

    def forbidden_operation(uow):
        calls.append(True)
        raise AssertionError('invalid context reached operation')

    assert ControlledCaller(flow_engine, context).run(forbidden_operation) == Result('DENIED', 'VALIDATION_ERROR', 'NOT_RECORDED')
    assert calls == [] and snapshot(flow_engine) == before


def test_raw_dto_fake_actor_cause_sql_and_traceback_never_enter_audit_or_logs(flow_engine, identities, enabled, caplog, capsys):
    case = ready(flow_engine, identities)['case_id']
    context = context_for(flow_engine, case)
    before = snapshot(flow_engine)
    marker = 'sensitive_raw_dto_marker'
    rejected_dto = {'actor': {'kind': 'HUMAN', 'role': 'FOUNDER', 'principal_id': marker},
                    'purpose': 'AUDIT', 'raw_text': marker, 'sql': 'SELECT ' + marker}
    traces = []

    def operation(uow):
        event = staged(uow, identities, case)
        guard = LifecycleGuards(COMPONENT)
        def broken(*args):
            try:
                raise ValueError(repr(rejected_dto))
            except ValueError as cause:
                raise RuntimeError(marker) from cause
        guard._proposal = broken
        try:
            guard.apply(uow, event, now())
        except FlowError as error:
            traces.append(''.join(traceback.format_exception(error)))
            assert error.__cause__ is None and error.__context__ is None
            raise

    result = ControlledCaller(flow_engine, context).run(operation)
    assert result == Result('DENIED', 'INVALID_STATE', 'RECORDED')
    only_audit_changed(before, snapshot(flow_engine))
    assert_denial(flow_engine, context, 'INVALID_STATE')
    output = capsys.readouterr()
    visible = repr(result) + repr(denial_rows(flow_engine)) + ''.join(traces) + caplog.text + output.out + output.err
    assert marker not in visible and repr(rejected_dto) not in visible


def test_absent_case_has_no_audit_and_initializes_no_sidecar(flow_engine, identities):
    context = TrustedContext('synthetic_missing_case', identities.people['customer_a']['principal_id'],
                             identities.people['customer_a']['store_id'], 'PROPOSAL')
    before = snapshot(flow_engine)
    def operation(uow):
        LifecycleGuards(COMPONENT).prepare(uow, context.case_id, 1, ProposalAccepted, now())
    assert ControlledCaller(flow_engine, context).run(operation) == Result('DENIED', 'NOT_FOUND', 'NOT_RECORDED')
    assert snapshot(flow_engine) == before


def test_denial_audit_does_not_initialize_absent_lifecycle_state(flow_engine, identities, enabled):
    case = ready(flow_engine, identities)['case_id']
    context = context_for(flow_engine, case)
    # Explicit legacy-like fixture: no lifecycle work/source/event references.
    with flow_engine.begin() as connection:
        connection.execute(delete(lifecycle.state).where(lifecycle.state.c.case_id == case))
    before = snapshot(flow_engine)
    assert before[lifecycle.state.name] == []
    result = ControlledCaller(flow_engine, context).run(rejected(identities, case))
    assert result == Result('DENIED', 'INVALID_STATE', 'RECORDED')
    only_audit_changed(before, snapshot(flow_engine))
    assert rows(flow_engine, lifecycle.state) == []
    assert_denial(flow_engine, context, 'INVALID_STATE')


def test_real_superseded_claim_does_not_block_current_authority_denial_audit(flow_engine, identities, enabled):
    case = ready(flow_engine, identities)['case_id']
    context = context_for(flow_engine, case)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        stale = claim(uow, case, ProposalAccepted)
        uow.commit()
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        replacement = LifecycleGuards(COMPONENT).claim(uow, stale.work_id, now() + timedelta(seconds=61))
        assert replacement.epoch == stale.epoch + 1
        uow.commit()
    before = snapshot(flow_engine)

    def operation(uow):
        current = head(uow, case)
        source = stage(uow, current, 'PROPOSAL', material('PROPOSAL', current, identities, uow=uow)['content'])
        bind_source(uow, source, stale)
        LifecycleGuards(COMPONENT).apply(uow, ProposalAccepted(identifier('event'), stale, source), now())

    assert ControlledCaller(flow_engine, context).run(operation) == Result('DENIED', 'INVALID_STATE', 'RECORDED')
    only_audit_changed(before, snapshot(flow_engine))
    assert rows(flow_engine, lifecycle.work)[0]['claim_id'] == replacement.claim_id
    assert_denial(flow_engine, context, 'INVALID_STATE')


def test_new_transaction_uses_current_enabled_grant_revision(flow_engine, identities, enabled):
    case = ready(flow_engine, identities)['case_id']
    context = context_for(flow_engine, case)
    before = snapshot(flow_engine)
    current_baseline = []

    def new_audit(engine, **kwargs):
        assert snapshot(engine) == before
        with engine.begin() as connection:
            change_authority(connection, context, 'revision')
        current_baseline.append(snapshot(engine))
        return CustomerUnitOfWork(engine, **kwargs)

    assert ControlledCaller(flow_engine, context, audit_uow=new_audit).run(rejected(identities, case)) == Result(
        'DENIED', 'INVALID_STATE', 'RECORDED')
    assert len(current_baseline) == 1
    only_audit_changed(current_baseline[0], snapshot(flow_engine))
    assert_denial(flow_engine, context, 'INVALID_STATE')
