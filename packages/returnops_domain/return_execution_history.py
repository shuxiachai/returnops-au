"""Only Domain writes operation history/audit and its accepted effect index."""
from sqlalchemy import update
from . import customer_tables as old, founder_tables as founder, lifecycle_tables as life, founder_codec as finite
from .audit import append_event
from .canonical import digest
from .return_execution_sources import COMPONENT


def append_operation(uow, head, record_id, body, object_version, payload, correlation, now):
    finite.validate('OperationAttempt', body)
    ref = dict(record_id=record_id, kind='OPERATION', object_id=body['operation_id'], object_version=object_version)
    source_hash = finite.digest(body)
    record = dict(**ref, case_id=head['case_id'], case_version=head['case_version'], recorded_sequence=head['history_sequence'] + 1,
        recorded_at=now, content_sha256=source_hash, retention_state='AVAILABLE', removal_reason=None)
    uow.execute(old.history.insert().values(**record))
    uow.execute(old.history_contents.insert().values(record_id=record_id, body=finite.encode_document(body)))
    uow.execute(founder.encodings.insert().values(record_id=record_id, profile=finite.PROFILE,
        source_content_sha256=source_hash, projected_content_sha256=source_hash, receipt_id=None))
    uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == head['case_id']).values(history_sequence=head['history_sequence'] + 1))
    event = append_event(uow, head['case_id'], actor={'kind': 'SERVICE', 'component_id': COMPONENT},
        event_type='OPERATION_REVISION_RECORDED', correlation_id=correlation, payload=payload,
        object_ids=[body['operation_id']], history_refs=[ref], now=now)
    return record, event


def effect_values(control, body, record):
    identity = digest({name: body[name] for name in ('operation_id', 'case_id', 'command_id', 'approval_id',
        'proposal_id', 'proposal_version', 'input_version', 'provider_id', 'operation_fingerprint', 'idempotency_key')}, 'lifecycle-effect/v1')
    return dict(operation_id=control['operation_id'], case_id=control['case_id'], record_id=record['record_id'], object_version=3,
        approval_record_id=control['approval_record_id'], command_id=control['command_id'], input_version=control['input_version'],
        generation=control['generation'], operation_type='CREATE_RETURN', status=body['status'], identity_hash=identity,
        artifact_evidence_id=None, artifact_sha256=None, dispatch_source_record_id=control['dispatch_record_id'])
