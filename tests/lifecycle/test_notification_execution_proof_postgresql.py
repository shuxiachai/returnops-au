"""AC03 subset: real completed chain, current eligibility and hostile proof rows.

Cloud-only PostgreSQL tests. Corruption is explicit adversarial fixture data,
never an accepted business action or evidence of a real provider operation.
"""
from dataclasses import asdict

import pytest
from sqlalchemy import delete, select, update

from label_artifact_helpers import (
    complete, evidence, pdf_call_counts, ready, rows, service, snapshot,
)
from returnops_domain import customer_tables as old, lifecycle_tables as life
from returnops_domain.canonical import digest
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.label_artifact_tables import contents
from returnops_domain.label_execution_tables import controls as labels
from returnops_domain.notification_execution import completed_pair
from returnops_domain.retention import RetentionService
from returnops_domain.return_execution_sources import ledger_payload
from returnops_domain.return_execution_tables import controls as returns, ledger


def _completed(engine, identities):
    args, _ = ready(engine, identities)
    result = complete(service(engine, identities), args)
    assert result.status == 'COMMITTED', asdict(result)
    return args, result


def _read_pair(engine, case_id):
    # The actual UoW acquires the production shared fence. No actor, original
    # Founder key, dispatch adapter or new approval is passed to the reader.
    with CustomerUnitOfWork(engine, write=False) as uow:
        head = dict(uow.execute(select(old.case_heads).where(
            old.case_heads.c.case_id == case_id)).mappings().one())
        pair = completed_pair(uow, head)
        uow.commit()
    return pair


def _reject_without_writes(engine, case_id):
    before = snapshot(engine)
    with pdf_call_counts() as calls:
        with pytest.raises(FlowError) as denied:
            _read_pair(engine, case_id)
    assert denied.value.code == 'INVALID_STATE'
    assert snapshot(engine) == before
    assert all(calls[name] == 0 for name in (
        'render', 'text_line', 'assembly', 'expected_pdf',
        'artifact_retrieval', 'return_provider', 'label_provider',
    ))
    return calls


def test_notification_proof_reads_actual_complete_chain_without_dispatch(
        flow_engine, identities, enabled, request):
    args, result = _completed(flow_engine, identities)
    before = snapshot(flow_engine)
    with pdf_call_counts() as calls:
        pair = _read_pair(flow_engine, args['case_id'])
    assert pair['evidence_id'] == result.label_evidence_id
    assert pair['return_record_id'] == rows(flow_engine, returns)[0]['result_record_id']
    assert pair['label_record_id'] == pair['artifact']['result_record']['record_id']
    assert pair['artifact']['content'] is not None
    assert pair['acceptance']['acceptance_id'] == pair['returned']['approval_acceptance_id']
    assert calls['validation'] > 0
    assert all(calls[name] == 0 for name in (
        'render', 'text_line', 'assembly', 'expected_pdf',
        'artifact_retrieval', 'return_provider', 'label_provider',
    ))
    assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, evidence_id=pair['evidence_id'],
             return_record_id=pair['return_record_id'],
             label_record_id=pair['label_record_id'], actual_code_calls=calls)


@pytest.mark.parametrize('fault', [
    'new_generation', 'approval_pointer', 'competing_manual',
    'wrong_return_key_hash', 'wrong_return_store', 'missing_return_fact',
    'missing_label_effect', 'extra_lifecycle_effect', 'unknown_effect',
    'pdf_bytes', 'missing_pdf_bytes',
])
def test_notification_proof_rejects_incomplete_or_noncurrent_chain(
        flow_engine, identities, enabled, request, fault):
    args, result = _completed(flow_engine, identities)
    assert _read_pair(flow_engine, args['case_id'])['evidence_id'] == result.label_evidence_id
    with flow_engine.begin() as connection:
        state = connection.execute(select(life.state)).mappings().one()
        label = connection.execute(select(labels)).mappings().one()
        if fault == 'new_generation':
            connection.execute(update(life.state).values(generation=state['generation'] + 1))
        elif fault == 'approval_pointer':
            connection.execute(update(life.state).values(approval_record_id=state['proposal_record_id']))
        elif fault == 'competing_manual':
            connection.execute(update(life.state).values(outcome='MANUAL_HANDLED'))
        elif fault == 'wrong_return_key_hash':
            original = connection.execute(select(returns.c.original_key_hash)).scalar_one()
            wrong = '0' * 64 if original != '0' * 64 else '1' * 64
            connection.execute(update(returns).values(original_key_hash=wrong))
        elif fault == 'wrong_return_store':
            connection.execute(update(returns).values(store_id='unrelated-store'))
        elif fault == 'missing_return_fact':
            connection.execute(delete(ledger))
        elif fault == 'missing_label_effect':
            connection.execute(delete(life.effects).where(
                life.effects.c.operation_id == label['operation_id']))
        elif fault == 'extra_lifecycle_effect':
            original = dict(connection.execute(select(life.effects).limit(1)).mappings().one())
            original['operation_id'] = 'unexpected-notification-operation'
            connection.execute(life.effects.insert().values(**original))
        elif fault == 'unknown_effect':
            connection.execute(update(life.effects).where(
                life.effects.c.operation_id == label['operation_id']).values(status='UNKNOWN'))
        elif fault == 'pdf_bytes':
            raw = bytes(connection.execute(select(contents.c.body)).scalar_one())
            connection.execute(update(contents).values(body=raw + b'\nforged-notification-proof'))
        else:
            connection.execute(delete(contents))
    calls = _reject_without_writes(flow_engine, args['case_id'])
    evidence(request.node.nodeid, fault=fault, actual_code_calls=calls)


def _insert_extra_return_fact(engine, link):
    with engine.begin() as connection:
        original = dict(connection.execute(select(ledger)).mappings().one())
        extra = dict(original, effect_key='unexpected-notification-effect',
                     operation_id='unexpected-notification-operation',
                     provider_operation_id='unexpected-notification-provider-operation',
                     provider_return_id='unexpected-notification-provider-return')
        if link in {'dispatch_binding_hash', 'unrelated'}:
            extra['dispatch_record_id'] = 'unexpected-notification-dispatch'
        if link in {'dispatch_record_id', 'unrelated'}:
            extra['dispatch_binding_hash'] = (
                '0' * 64 if original['dispatch_binding_hash'] != '0' * 64 else '1' * 64)
        # This is a self-consistent extra independent ledger row, rather than
        # an invalid hash on the original fact. The extra identity must not be
        # hidden by lookup of only the known original effect key.
        extra['fact_hash'] = digest(ledger_payload(extra), 'core-return-fact/v1')
        if link != 'unrelated':
            assert extra[link] == original[link]
        else:
            assert all(extra[name] != original[name] for name in (
                'effect_key', 'operation_id', 'dispatch_record_id', 'dispatch_binding_hash'))
        connection.execute(ledger.insert().values(**extra))
        assert len(connection.execute(select(ledger)).mappings().all()) == 2


@pytest.mark.parametrize('link', ['dispatch_record_id', 'dispatch_binding_hash'])
def test_notification_proof_rejects_extra_independent_return_fact(
        flow_engine, identities, enabled, request, link):
    args, _ = _completed(flow_engine, identities)
    _read_pair(flow_engine, args['case_id'])
    _insert_extra_return_fact(flow_engine, link)
    calls = _reject_without_writes(flow_engine, args['case_id'])
    evidence(request.node.nodeid, extra_fact_link=link, actual_code_calls=calls)


def test_notification_proof_limits_fact_inventory_to_original_identity(
        flow_engine, identities, enabled, request):
    args, result = _completed(flow_engine, identities)
    _insert_extra_return_fact(flow_engine, 'unrelated')
    before = snapshot(flow_engine)
    with pdf_call_counts() as calls:
        pair = _read_pair(flow_engine, args['case_id'])
    assert pair['evidence_id'] == result.label_evidence_id
    assert snapshot(flow_engine) == before
    assert all(calls[name] == 0 for name in (
        'render', 'text_line', 'assembly', 'expected_pdf',
        'artifact_retrieval', 'return_provider', 'label_provider',
    ))
    evidence(request.node.nodeid, unrelated_fixture_fact=True, actual_code_calls=calls)


def test_notification_proof_does_not_reconstruct_retained_pdf(
        flow_engine, identities, enabled, request):
    args, result = _completed(flow_engine, identities)
    _read_pair(flow_engine, args['case_id'])
    assert RetentionService(flow_engine).remove('EVIDENCE', result.label_evidence_id)
    assert not rows(flow_engine, contents)
    calls = _reject_without_writes(flow_engine, args['case_id'])
    assert not rows(flow_engine, contents)
    evidence(request.node.nodeid, unavailable_evidence=result.label_evidence_id,
             actual_code_calls=calls)
