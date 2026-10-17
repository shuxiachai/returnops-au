"""Explicit test-only future records. No runtime producer, model or provider ran."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from sqlalchemy import select, update
from returnops_domain import customer_tables as t, founder_tables as f, founder_codec as finite
from returnops_domain.audit import append_event, identifier
from returnops_domain.canonical import digest, encode_document
from returnops_domain.customer_uow import CustomerUnitOfWork

EXAMPLES = {item['name']: item['value'] for item in json.loads(
    (Path(__file__).resolve().parents[2]/'contracts/v1/examples.json').read_text(encoding='utf-8'))['positive']}
KINDS = ('PROPOSAL', 'REVIEW', 'DECISION', 'APPROVAL', 'OPERATION', 'NOTIFICATION')
NAMES = ('history-proposal', 'history-risk-review', 'history-decision', 'history-approval', 'history-operation', 'history-notification')
EVENTS = dict(zip(KINDS, ('PROPOSAL_ACCEPTED','RISK_REVIEW_ACCEPTED','FOUNDER_DECISION_ACCEPTED',
    'FOUNDER_APPROVAL_ISSUED','OPERATION_REVISION_RECORDED','NOTIFICATION_REVISION_RECORDED')))


def material(kind, case_id, *, version=1, proposal_record_id=None):
    fixture = deepcopy(EXAMPLES[NAMES[KINDS.index(kind)]])
    def bind(value):
        if isinstance(value, dict):
            return {key: case_id if key == 'case_id' else 10 if key == 'case_version' else bind(item) for key,item in value.items()}
        if isinstance(value, list):
            return [bind(item) for item in value]
        return value
    fixture = bind(fixture)
    fixture['object_version'] = version
    content = fixture['content']
    if kind == 'PROPOSAL':
        content['packet']['proposal_version'] = version
        content['citation_verification']['proposal_version'] = version
    if kind == 'REVIEW':
        content['proposal_record_id'] = proposal_record_id
        content['review']['proposal_version'] = version
    return fixture


def persist(engine, case_id, fixture, *, mutation=None, event_type=None, actor=None, legacy=False):
    """Bypass production append whitelist only in an isolated synthetic PG test."""
    fixture = deepcopy(fixture)
    if mutation:
        mutation(fixture)
    content_hash = digest(fixture['content'],'history/v1') if legacy else finite.digest(fixture['content'])
    content_bytes = encode_document(fixture['content']) if legacy else finite.encode_document(fixture['content'])
    with CustomerUnitOfWork(engine, write=True) as uow:
        uow.execute(update(t.case_heads).where(t.case_heads.c.case_id == case_id).values(case_version=10))
        head = uow.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
        now = datetime.now(timezone.utc)
        ref = {'record_id':identifier('hist'), 'kind':fixture['kind'], 'object_id':fixture['object_id'], 'object_version':fixture['object_version']}
        uow.execute(t.history.insert().values(**ref, case_id=case_id, case_version=10,
            recorded_sequence=head['history_sequence']+1,recorded_at=now,
            content_sha256=content_hash,retention_state='AVAILABLE',removal_reason=None))
        uow.execute(t.history_contents.insert().values(record_id=ref['record_id'],body=content_bytes))
        if not legacy:
            uow.execute(f.encodings.insert().values(record_id=ref['record_id'],profile=finite.PROFILE,
                source_content_sha256=content_hash,projected_content_sha256=content_hash,receipt_id=None))
        uow.execute(update(t.case_heads).where(t.case_heads.c.case_id == case_id).values(history_sequence=head['history_sequence']+1))
        append_event(uow,case_id,actor=actor or fixture['actor'],event_type=event_type or EVENTS[fixture['kind']],
            correlation_id=identifier('corr'),payload={'synthetic_history_fixture':True},object_ids=[ref['object_id']],history_refs=[ref],now=now)
        uow.commit()
    return ref


def tombstone(engine, record_id):
    with CustomerUnitOfWork(engine, write=True) as uow:
        uow.execute(t.history_contents.delete().where(t.history_contents.c.record_id == record_id))
        uow.execute(update(t.history).where(t.history.c.record_id == record_id).values(retention_state='DELETED',removal_reason='OWNER_REQUEST'))
        uow.commit()
