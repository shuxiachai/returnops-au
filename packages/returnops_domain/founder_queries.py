"""Stable Founder pagination: frozen membership/bounds and live retention."""
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from sqlalchemy import and_, case, func, or_, select
from . import customer_tables as t, founder_tables as f, investigation_tables as investigation
from .audit import identifier, timestamp
from .canonical import decode_document, digest
from .errors import FlowError
from .founder_integrity import CaseProof, lookup_receipt, read_revision as _read_revision
from .storage import original_statement_records
from .wire import validate
from . import founder_codec as finite

WINDOWS = (('STATEMENT', 'statements'), ('EVIDENCE', 'evidence'), ('DECISION', 'decisions'),
           ('APPROVAL', 'approvals'), ('OPERATION', 'operations'), ('NOTIFICATION', 'notifications'))
SUMMARY = ('case_id', 'case_version', 'input_version', 'status')


def read_revision(uow,row,proof):
    if row['kind']=='NOTIFICATION':
        from .notification_projection import verify_founder_note
        verify_founder_note(uow,proof.head,row)
    return _read_revision(uow,row,proof)


def page_query(query):
    if type(query) is not dict or set(query) - {'cursor', 'limit'}:
        raise FlowError('VALIDATION_ERROR')
    result = dict(query)
    if 'cursor' in result:
        validate('Cursor', result['cursor'])
    limit = result.get('limit', 20)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise FlowError('VALIDATION_ERROR')
    result['limit'] = limit
    return result


def snapshot(uow, actor, purpose, now, ttl, head=None, highwater=0):
    result = {'snapshot_id': identifier('fsnap'), 'purpose': purpose,
              'principal_id': actor.principal_id, 'role': actor.role, 'store_id': actor.store_id,
              'case_id': None if head is None else head['case_id'],
              'case_version': None if head is None else head['case_version'],
              'highwater': highwater, 'anchor_hash': None,
              'as_of': now, 'expires_at': now + timedelta(seconds=ttl)}
    if purpose == 'AUDIT':
        result.update(highwater=head['audit_sequence'], anchor_hash=head['audit_head'])
    elif purpose == 'HISTORY':
        result['highwater'] = head['history_sequence']
    uow.execute(f.snapshots.insert().values(**result))
    return result


def cursor(uow, snap, query, last_sequence=0, last_record_id=None):
    token = token_urlsafe(32)
    uow.execute(f.cursors.insert().values(cursor_hash=sha256(token.encode('ascii')).hexdigest(),
        snapshot_id=snap['snapshot_id'], kind=query.get('kind'), page_limit=query.get('limit', 20),
        object_id=query.get('object_id'), object_version=query.get('object_version'),
        last_sequence=last_sequence, last_record_id=last_record_id))
    return token


def resume(uow, actor, purpose, case_id, query, now):
    row = uow.execute(select(f.cursors).where(
        f.cursors.c.cursor_hash == sha256(query['cursor'].encode('ascii')).hexdigest())).mappings().one_or_none()
    if row is None:
        raise FlowError('INVALID_STATE')
    snap = uow.execute(select(f.snapshots).where(f.snapshots.c.snapshot_id == row['snapshot_id'])).mappings().one_or_none()
    if (snap is None or snap['purpose'] != purpose or snap['principal_id'] != actor.principal_id
            or snap['role'] != actor.role or snap['store_id'] != actor.store_id or snap['case_id'] != case_id
            or snap['expires_at'] <= now or row['kind'] != query.get('kind')
            or row['page_limit'] != query.get('limit', 20) or row['object_id'] != query.get('object_id')
            or row['object_version'] != query.get('object_version')):
        raise FlowError('INVALID_STATE')
    return snap, row['last_sequence'], row['last_record_id']


def summary(row):
    result = {name: row[name] for name in SUMMARY}
    result.update(created_at=timestamp(row['created_at']), updated_at=timestamp(row['updated_at']),
                  issue_category='UNCLEAR')
    validate('CaseSummary', result, internal=True)
    return result


def list_cases(uow, actor, query, now, ttl):
    query = page_query(query)
    if 'cursor' in query:
        snap, last, _ = resume(uow, actor, 'LIST', None, query, now)
    else:
        heads = uow.execute(select(t.case_heads).where(t.case_heads.c.store_id == actor.store_id,
            t.case_heads.c.available.is_(True)).order_by(t.case_heads.c.created_at, t.case_heads.c.case_id)).mappings().all()
        snap = snapshot(uow, actor, 'LIST', now, ttl, highwater=len(heads))
        # Whitelisted values only. Bodies/owner identity never enter the snapshot.
        for ordinal, head in enumerate(heads, 1):
            summary(head)
            values = {name: head[name] for name in SUMMARY + ('created_at', 'updated_at')}
            uow.execute(f.members.insert().values(snapshot_id=snap['snapshot_id'], ordinal=ordinal,
                                                  issue_category='UNCLEAR', **values))
        last = 0
    rows = uow.execute(select(f.members).join(t.case_heads, f.members.c.case_id == t.case_heads.c.case_id)
        .where(f.members.c.snapshot_id == snap['snapshot_id'], f.members.c.ordinal > last,
               f.members.c.ordinal <= snap['highwater'], t.case_heads.c.store_id == actor.store_id,
               t.case_heads.c.available.is_(True)).order_by(f.members.c.ordinal).limit(query['limit'] + 1)).mappings().all()
    chosen = rows[:query['limit']]
    result = {'items': [summary(row) for row in chosen]}
    if len(rows) > query['limit']:
        result['next_cursor'] = cursor(uow, snap, query, chosen[-1]['ordinal'])
    validate('CaseList', result, internal=True)
    return result, snap


def history_page(uow, actor, head, query, now, ttl):
    query = validate('FounderHistoryQuery', query)
    query.setdefault('limit', 20)
    if 'cursor' in query:
        snap, last, last_id = resume(uow, actor, 'HISTORY', head['case_id'], query, now)
    else:
        snap = snapshot(uow, actor, 'HISTORY', now, ttl, head)
        last, last_id = 0, None
    proof = CaseProof(uow, head)
    conditions = [t.history.c.case_id == head['case_id'], t.history.c.kind == query['kind'],
        t.history.c.recorded_sequence <= snap['highwater'], t.history.c.case_version <= snap['case_version'],
        or_(t.history.c.recorded_sequence > last,
            and_(t.history.c.recorded_sequence == last, t.history.c.record_id > (last_id or '')))]
    for name in ('object_id', 'object_version'):
        if name in query:
            conditions.append(t.history.c[name] == query[name])
    rows = uow.execute(select(t.history).where(*conditions)
        .order_by(t.history.c.recorded_sequence, t.history.c.record_id).limit(query['limit'] + 1)).mappings().all()
    chosen = rows[:query['limit']]
    result = {'case_id': head['case_id'], 'kind': query['kind'], 'snapshot_id': snap['snapshot_id'],
              'snapshot_case_version': snap['case_version'], 'as_of': timestamp(snap['as_of']),
              'items': [read_revision(uow, row, proof) for row in chosen]}
    for name in ('object_id', 'object_version'):
        if name in query:
            result[name] = query[name]
    if len(rows) > query['limit']:
        result['next_cursor'] = cursor(uow, snap, query, chosen[-1]['recorded_sequence'], chosen[-1]['record_id'])
    finite.validate('FounderHistoryPage', result)
    return result, snap


def audit_page(uow, actor, head, query, now, ttl):
    query = page_query(query)
    proof = CaseProof(uow, head)
    if 'cursor' in query:
        snap, last, _ = resume(uow, actor, 'AUDIT', head['case_id'], query, now)
    else:
        snap = snapshot(uow, actor, 'AUDIT', now, ttl, head)
        last = 0
    upper = snap['highwater']
    if (upper > len(proof.events) or last > upper
            or (None if upper == 0 else proof.events[upper - 1]['event_hash']) != snap['anchor_hash']):
        raise FlowError()
    chosen = proof.events[last:min(last + query['limit'], upper)]
    result = {'items': chosen}
    if last + len(chosen) < upper:
        result['next_cursor'] = cursor(uow, snap, query, last + len(chosen))
    validate('AuditPage', result, internal=True)
    return result, snap


def _window(uow, head, snap, proof, kind):
    scope = and_(t.history.c.case_id == head['case_id'], t.history.c.kind == kind,
                 t.history.c.recorded_sequence <= snap['highwater'], t.history.c.case_version <= snap['case_version'])
    total, unavailable = uow.execute(select(func.count(), func.coalesce(func.sum(
        case((t.history.c.retention_state != 'AVAILABLE', 1), else_=0)), 0)).where(scope)).one()
    ranked = select(t.history, func.row_number().over(partition_by=t.history.c.object_id,
        order_by=(t.history.c.object_version.desc(), t.history.c.recorded_sequence.desc())).label('position')).where(scope).subquery()
    chosen = list(uow.execute(select(ranked).where(ranked.c.position == 1, ranked.c.retention_state == 'AVAILABLE')
        .order_by(ranked.c.recorded_sequence.desc(), ranked.c.record_id.desc()).limit(100)).mappings())
    if kind == 'STATEMENT':
        original_id = uow.execute(select(original_statement_records.c.statement_id).where(
            original_statement_records.c.case_id == head['case_id'])).scalar_one_or_none()
        if original_id is not None and not any(row['object_id'] == original_id for row in chosen):
            original = uow.execute(select(ranked).where(ranked.c.position == 1,
                ranked.c.object_id == original_id, ranked.c.retention_state == 'AVAILABLE')).mappings().one_or_none()
            if original is not None:
                chosen = chosen[:99] + [original]
    chosen.sort(key=lambda row: (row['recorded_sequence'], row['record_id']))
    bodies = [read_revision(uow, row, proof)['content'] for row in chosen]
    window = {'kind': kind, 'snapshot_id': snap['snapshot_id'], 'snapshot_case_version': snap['case_version'],
              'total_records': total, 'preview_count': len(chosen), 'unavailable_count': unavailable,
              'truncated': total > len(chosen), 'start_cursor': cursor(uow, snap, {'kind': kind, 'limit': 20})}
    return bodies, window


def _current_target(uow, proof, head, kind, object_id, persisted):
    matches = [row for row in proof.revisions.values() if row['kind'] == kind and row['object_id'] == object_id]
    if not matches:
        raise FlowError()
    row = max(matches, key=lambda r: (r['object_version'], r['recorded_sequence']))
    record = read_revision(uow, row, proof)
    if 'content' not in record:
        raise FlowError()
    body = record['content']['block'] if kind == 'ORDER_LOOKUP_BLOCK' else record['content']
    if body['case_id'] != head['case_id'] or body['input_version'] != head['input_version'] or body != persisted:
        raise FlowError()
    return body


def _order(uow, proof, head, projection_id):
    row = uow.execute(select(investigation.projections).where(
        investigation.projections.c.projection_id == projection_id)).mappings().one_or_none()
    if (row is None or row['case_id'] != head['case_id'] or not row['available']
            or row['input_version'] > head['input_version'] or row['input_version'] != row['source_input_version'] + 1):
        raise FlowError()
    raw = uow.execute(select(investigation.projection_contents.c.body).where(
        investigation.projection_contents.c.projection_id == projection_id)).scalar_one_or_none()
    if raw is None:
        raise FlowError()
    body = validate('OrderSnapshot', decode_document(raw), internal=True)
    if (body['snapshot_id'] != row['snapshot_id'] or body['snapshot_version'] != row['snapshot_version']
            or digest(body, 'accepted-order/v1') != row['snapshot_hash']):
        raise FlowError()
    origins = [event for event in proof.events if event['event_type'] == 'ORDER_INVESTIGATION_ACCEPTED'
               and row['receipt_id'] in event['object_ids'] and projection_id in event['object_ids']]
    if len(origins) != 1 or origins[0]['occurred_at'] != timestamp(row['accepted_at']):
        raise FlowError()
    accepted = lookup_receipt(uow, row['receipt_id'], head['case_id'], row['source_input_version'], 'MATCHED', origins[0])
    if accepted is None or accepted['snapshot'] != body:
        raise FlowError()
    return body


def case_view(uow, actor, head, now, ttl):
    proof = CaseProof(uow, head)
    snap = snapshot(uow, actor, 'HISTORY', now, ttl, head)
    result = {name: head[name] for name in SUMMARY}
    result.update(created_at=timestamp(head['created_at']), updated_at=timestamp(head['updated_at']),
                  cited_passages=[], collection_windows={})
    for kind, field in WINDOWS:
        result[field], result['collection_windows'][field] = _window(uow, head, snap, proof, kind)
    if head['current_question_set_id'] is not None:
        questions = uow.execute(select(t.questions).where(t.questions.c.question_set_id == head['current_question_set_id'],
            t.questions.c.case_id == head['case_id'])).mappings().one_or_none()
        if questions is None or questions['input_version'] != head['input_version']:
            raise FlowError()
        result['clarification'] = {'question_set_id': questions['question_set_id'], 'input_version': questions['input_version'],
                                   'questions': decode_document(questions['questions'])}
    if head['current_failure_id'] is not None:
        failure = uow.execute(select(t.processing_failures).where(
            t.processing_failures.c.failure_id == head['current_failure_id'])).mappings().one_or_none()
        if failure is None or failure['case_id'] != head['case_id'] or failure['input_version'] != head['input_version']:
            raise FlowError()
        result['processing_failure'] = _current_target(uow, proof, head, 'PROCESSING_FAILURE',
            failure['failure_id'], decode_document(failure['body']))
    state = uow.execute(select(investigation.state).where(investigation.state.c.case_id == head['case_id'])).mappings().one_or_none()
    if state is not None and state['current_block_id'] is not None:
        block = uow.execute(select(investigation.blocks).where(
            investigation.blocks.c.block_id == state['current_block_id'])).mappings().one_or_none()
        if block is None:
            raise FlowError()
        result['order_lookup_block'] = _current_target(uow, proof, head, 'ORDER_LOOKUP_BLOCK',
            state['current_block_id'], decode_document(block['body']))
    if state is not None and state['current_projection_id'] is not None:
        result['order_snapshot'] = _order(uow, proof, head, state['current_projection_id'])
    from .lifecycle_projection import project
    project(uow,head,result)
    finite.validate('CaseView', result)
    return result, snap
