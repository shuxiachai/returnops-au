"""Exact allowed operation/audit deltas constructed from the original seal."""
from copy import deepcopy
from sqlalchemy import update
from . import customer_tables as old, founder_tables as founder, founder_codec as finite
from .audit import append_event
from .canonical import encode_document
from .label_execution_sources import COMPONENT


def append_operation(uow, head, record_id, body, revision, payload, correlation, now):
    finite.validate('OperationAttempt', body)
    ref = dict(record_id=record_id, kind='OPERATION', object_id=body['operation_id'], object_version=revision)
    record = dict(**ref, case_id=head['case_id'], case_version=head['case_version'],
        recorded_sequence=head['history_sequence'] + 1, recorded_at=now, content_sha256=finite.digest(body),
        retention_state='AVAILABLE', removal_reason=None)
    content = dict(record_id=record_id, body=finite.encode_document(body))
    encoding = dict(record_id=record_id, profile=finite.PROFILE, source_content_sha256=record['content_sha256'],
        projected_content_sha256=record['content_sha256'], receipt_id=None)
    for table,row in ((old.history,record),(old.history_contents,content),(founder.encodings,encoding)):
        uow.execute(table.insert().values(**row))
    uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == head['case_id']).values(
        history_sequence=head['history_sequence'] + 1))
    event = append_event(uow, head['case_id'], actor={'kind':'SERVICE','component_id':COMPONENT},
        event_type='OPERATION_REVISION_RECORDED', correlation_id=correlation, payload=payload,
        object_ids=[body['operation_id']], history_refs=[ref], now=now)
    audit = audit_row(head, event)
    post = {**head, 'history_sequence':head['history_sequence'] + 1,
            'audit_sequence':head['audit_sequence'] + 1, 'audit_head':event['event_hash']}
    return record, event, post, [(old.history,record),(old.history_contents,content),(founder.encodings,encoding),(old.audit,audit)]


def audit_row(head, event):
    return dict(event_id=event['event_id'], case_id=head['case_id'], sequence=head['audit_sequence'] + 1,
                event_hash=event['event_hash'], body=encode_document(event))


def expected_delta(before, additions, replacements, post_head):
    result = deepcopy(before)
    for table,row in additions:
        keys = [str(column.name) for column in table.primary_key.columns]
        if set(row) != {str(column.name) for column in table.columns} or any(
                all(saved[k] == row[k] for k in keys) for saved in result[table.name]):
            raise ValueError('Unexpected inserted identity or column set')
        result[table.name].append(deepcopy(row))
        result[table.name].sort(key=lambda saved:tuple(saved[k] for k in keys))
    for table,prior,row in replacements:
        keys = [str(column.name) for column in table.primary_key.columns]
        matches = [i for i,saved in enumerate(result[table.name]) if all(saved[k] == prior[k] for k in keys)]
        if len(matches) != 1 or result[table.name][matches[0]] != prior or set(row) != set(prior):
            raise ValueError('Unexpected replacement identity or original row')
        result[table.name][matches[0]] = deepcopy(row)
    original, = result[old.case_heads.name]
    allowed = {'case_version','updated_at','history_sequence','audit_sequence','audit_head'}
    if any(original[k] != post_head[k] for k in original if k not in allowed):
        raise ValueError('Unexpected business pointer change')
    result[old.case_heads.name] = [deepcopy(post_head)]
    return result
