"""Corrupt bodies, references, actors and lookup bindings fail closed."""
import pytest
from sqlalchemy import select, update
from returnops_domain import customer_tables as t, founder_tables as f, investigation_tables as investigation
from returnops_domain.canonical import decode_document, digest, encode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.intake_processor import IntakeProcessor
from founder_helpers import accepted, founder, investigate, rows


@pytest.mark.parametrize('corruption', ['body', 'chain', 'exact_ref', 'missing_actor_origin', 'conflicting_actor_origin'])
def test_history_and_audit_inconsistency_is_not_silently_projected(flow_engine, identities, corruption):
    case_id = accepted(identities)['case_id']
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        event_row = uow.execute(select(t.audit).where(t.audit.c.case_id == case_id)).mappings().one()
        event = decode_document(event_row['body'])
        if corruption == 'body':
            revision = uow.execute(select(t.history)).mappings().one()
            content = decode_document(uow.execute(select(t.history_contents.c.body)).scalar_one())
            content['raw_text'] = 'tampered fixture content'
            uow.execute(update(t.history_contents).where(t.history_contents.c.record_id == revision['record_id']).values(body=encode_document(content)))
        elif corruption == 'chain':
            uow.execute(update(t.audit).where(t.audit.c.event_id == event_row['event_id']).values(event_hash='0' * 64))
        else:
            if corruption == 'exact_ref':
                event['history_refs'][0]['object_version'] = 2
            elif corruption == 'missing_actor_origin':
                event['event_type'] = 'UNRELATED_SAFE_EVENT'
            else:
                event['history_refs'].append(dict(event['history_refs'][0]))
            unsigned = {k: v for k, v in event.items() if k != 'event_hash'}
            event['event_hash'] = digest({'sequence': 1, 'event': unsigned}, 'audit/v1')
            uow.execute(update(t.audit).where(t.audit.c.event_id == event_row['event_id']).values(body=encode_document(event), event_hash=event['event_hash']))
            uow.execute(update(t.case_heads).where(t.case_heads.c.case_id == case_id).values(audit_head=event['event_hash']))
        uow.commit()
    with pytest.raises(FlowError) as error:
        founder(flow_engine, identities).read('listFounderCaseHistory', case_id, {'kind': 'STATEMENT'})
    assert error.value.code == 'INTERNAL_ERROR'
    assert rows(flow_engine, f.snapshots) == []
    if corruption not in {'body', 'missing_actor_origin'}:
        with pytest.raises(FlowError) as error:
            founder(flow_engine, identities).read('listCaseAudit', case_id)
        assert error.value.code == 'INTERNAL_ERROR'


@pytest.mark.parametrize('corruption', ['receipt_hash', 'source_hash', 'encoding_hash', 'block_binding'])
def test_block_wrapper_cannot_hide_a_mismatched_private_source(flow_engine, identities, enabled, corruption):
    case_id = investigate(flow_engine, identities, 'SYN-CONFLICT')['case_id']
    flow = founder(flow_engine, identities)
    flow.read('listFounderCaseHistory', case_id, {'kind': 'ORDER_LOOKUP_BLOCK'})
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        if corruption == 'receipt_hash':
            uow.execute(update(investigation.receipts).values(body_hash='0' * 64))
        elif corruption == 'source_hash':
            uow.execute(update(t.history).where(t.history.c.kind == 'ORDER_LOOKUP_BLOCK').values(content_sha256='0' * 64))
        elif corruption == 'encoding_hash':
            uow.execute(update(f.encodings).values(projected_content_sha256='0' * 64))
        else:
            uow.execute(update(investigation.blocks).values(input_version=2))
        uow.commit()
    with pytest.raises(FlowError) as error:
        flow.read('listFounderCaseHistory', case_id, {'kind': 'ORDER_LOOKUP_BLOCK'})
    assert error.value.code == 'INTERNAL_ERROR'


def test_projection_body_hash_and_safe_current_target_binding_are_verified(flow_engine, identities, enabled):
    case_id = investigate(flow_engine, identities)['case_id']
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        uow.execute(update(investigation.projections).values(snapshot_hash='0' * 64))
        uow.commit()
    with pytest.raises(FlowError) as error:
        founder(flow_engine, identities).read('getFounderCase', case_id)
    assert error.value.code == 'INTERNAL_ERROR'

@pytest.mark.parametrize('reference', ['SYN-1001', 'SYN-CONFLICT'])
def test_receipt_cannot_borrow_another_real_cases_work(flow_engine, identities, enabled, reference):
    first = investigate(flow_engine, identities, reference, key='first-source-case')['case_id']
    second = accepted(identities, reference, key='second-source-case')['case_id']
    assert IntakeProcessor(flow_engine).run_once()
    foreign_work = next(row for row in rows(flow_engine, investigation.work) if row['case_id'] == second)
    assert foreign_work['state'] == 'PENDING'
    assert not any(row['work_id'] == foreign_work['work_id'] for row in rows(flow_engine, investigation.receipts))
    # A second DONE receipt at the same epoch would violate the existing UNIQUE
    # constraint before reaching the reader. This real queued foreign work has
    # no receipt, so only work_id changes and the original valid epoch remains.
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        uow.execute(update(investigation.receipts).where(investigation.receipts.c.case_id == first).values(work_id=foreign_work['work_id']))
        uow.commit()
    with pytest.raises(FlowError) as error:
        founder(flow_engine, identities).read('getFounderCase', first)
    assert error.value.code == 'INTERNAL_ERROR'


@pytest.mark.parametrize('reference', ['SYN-1001', 'SYN-CONFLICT'])
def test_receipt_cannot_borrow_another_claim_epoch(flow_engine, identities, enabled, reference):
    case_id = investigate(flow_engine, identities, reference)['case_id']
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        receipt = uow.execute(select(investigation.receipts).where(
            investigation.receipts.c.case_id == case_id)).mappings().one()
        uow.execute(update(investigation.receipts).where(
            investigation.receipts.c.receipt_id == receipt['receipt_id']).values(epoch=receipt['epoch'] + 1))
        uow.commit()
    with pytest.raises(FlowError) as error:
        founder(flow_engine, identities).read('getFounderCase', case_id)
    assert error.value.code == 'INTERNAL_ERROR'
