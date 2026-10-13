"""Synthetic actual approval setup; no production grant provision or DB startup."""
from dataclasses import asdict
from sqlalchemy import select
from returnops_api.private_execution_preparation import compose_private_execution_preparation
from returnops_domain import customer_tables as old, founder_tables as founder, lifecycle_tables as life
from returnops_domain import founder_codec as finite
from returnops_domain.canonical import decode_document, digest
from returnops_domain.execution_preparation_sources import audit_payload
from returnops_domain.execution_preparation_tables import preparations
from returnops_domain.preview_profile import APPROVAL_COMPONENT
from approval_admission_helpers import approved
from manual_helpers import rows, snapshot


def ready(engine, identities, **options):
    arguments, setup = approved(engine, identities, **options)
    return {**arguments, 'correlation_id':'preparation-correlation'}, setup


def service(engine, identities, name='founder', **options):
    return compose_private_execution_preparation(engine, identities.auth_config,
        None if name is None else 'Bearer ' + identities.tokens[name], **options)


def recovered(caller, arguments):
    return caller.recover_preparation(**{key:value for key,value in arguments.items() if key != 'correlation_id'})


def unchanged(engine, caller, arguments, status='DENIED'):
    before = snapshot(engine); result = caller.prepare(**arguments)
    assert result.status == status, asdict(result)
    assert snapshot(engine) == before
    assert result.preparation_id is None and result.operation_id is None
    return result


def assert_delta(engine, before, result, arguments):
    """Verify every physical table, every old row and every unchanged head field."""
    after = snapshot(engine)
    expected = {name:[dict(row) for row in data] for name,data in before.items()}
    added = {}
    for table, key in ((old.history, 'record_id'), (old.history_contents, 'record_id'),
            (founder.encodings, 'record_id'), (old.audit, 'event_id'), (preparations, 'preparation_id')):
        ids = {row[key] for row in before[table.name]}
        new, = [row for row in after[table.name] if row[key] not in ids]
        assert len(after[table.name]) == len(before[table.name]) + 1
        assert [row for row in after[table.name] if row[key] in ids] == before[table.name]
        expected[table.name] = after[table.name]; added[table.name] = new
    case = arguments['case_id']
    old_head, = [r for r in before[old.case_heads.name] if r['case_id'] == case]
    new_head, = [r for r in after[old.case_heads.name] if r['case_id'] == case]
    assert {k:v for k,v in new_head.items() if k not in {'history_sequence','audit_sequence','audit_head'}} == {
        k:v for k,v in old_head.items() if k not in {'history_sequence','audit_sequence','audit_head'}}
    assert new_head['history_sequence'] == old_head['history_sequence']+1
    assert new_head['audit_sequence'] == old_head['audit_sequence']+1
    assert new_head['audit_head'] == added[old.audit.name]['event_hash']
    expected[old.case_heads.name] = [new_head if r['case_id'] == case else r for r in before[old.case_heads.name]]
    assert after == expected
    row, = [r for r in rows(engine, preparations) if r['case_id'] == case]
    assert row['preparation_id'] == result.preparation_id and row['operation_id'] == result.operation_id
    record, = [r for r in rows(engine, old.history) if r['record_id'] == result.first_operation_record_id]
    raw, = [r for r in rows(engine, old.history_contents) if r['record_id'] == record['record_id']]
    body = finite.decode_document(raw['body'])
    assert body['status'] == 'PENDING' and body['attempt_count'] == 1 and record['object_version'] == 1
    assert not {'result','error','provider_operation_id'} & body.keys()
    assert record['content_sha256'] == finite.digest(body)
    audit, = [decode_document(r['body']) for r in rows(engine, old.audit) if r['event_id'] == row['origin_audit_event_id']]
    assert audit['actor'] == {'kind':'SERVICE','component_id':APPROVAL_COMPONENT}
    assert audit['payload_hash'] == digest(audit_payload(row, body, record['content_sha256']), 'audit-payload/v1')
    assert row['binding_hash'] == audit_payload(row, body, record['content_sha256'])['binding_hash']
    work, = [r for r in rows(engine, life.work) if r['work_id'] == arguments['execution_work_id']]
    assert work['state'] == 'PENDING' and work['epoch'] == 0
    assert all(work[name] is None for name in ('claim_id','claimed_case_version','lease_expires_at','authority_revision'))
    assert rows(engine, life.effects) == []
    return after, row, body
