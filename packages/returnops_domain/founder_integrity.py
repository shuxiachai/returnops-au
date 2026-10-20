"""Verified F.05 projections of immutable customer/investigation provenance.

Read metadata never stores personal bodies. Public block content is the complete
frozen HistoricalOrderLookupBlock; its digest differs from the legacy bare-block
digest. Both are verified, and the source row is never rewritten.
"""
from sqlalchemy import select
from . import customer_tables as t, investigation_tables as investigation, founder_tables as f
from .audit import timestamp
from .canonical import decode_document, digest
from .errors import FlowError
from .wire import validate
from . import founder_history_types as future
from . import founder_codec as finite

BLOCK_PROFILE = 'historical-order-block/v1'
ORIGINS = {
    **future.ORIGINS,
    'OUTCOME_MESSAGE': {'NOTIFICATION_CUSTOMER_MESSAGE_RECORDED'},
    'STATEMENT': {'CUSTOMER_CASE_ACCEPTED', 'CUSTOMER_CLARIFICATION_ACCEPTED', 'INITIAL_RECORD_IMPORTED'},
    'EVIDENCE': {'CUSTOMER_CASE_ACCEPTED', 'CUSTOMER_CLARIFICATION_ACCEPTED'},
    'PROCESSING_FAILURE': {'CUSTOMER_INTAKE_FAILED', 'ORDER_INVESTIGATION_ACCEPTED', 'FIXED_PROPOSAL_FAILED'},
    'ORDER_LOOKUP_BLOCK': {'ORDER_INVESTIGATION_ACCEPTED'},
}
IDENTITIES = {'STATEMENT': 'statement_id', 'EVIDENCE': 'evidence_id',
              'PROCESSING_FAILURE': 'failure_id', 'ORDER_LOOKUP_BLOCK': 'block_id'}


class CaseProof:
    """Verify the stored event chain and exact revision references once per read.

    This detects inconsistency against the retained chain/head, not an attacker
    who can rewrite the whole database. Original payloads are not reconstructed.
    """
    def __init__(self, uow, head):
        self.head = head
        from .generated_evidence import namespace_active
        generated_active=namespace_active(uow)
        self.revisions = {row['record_id']: row for row in uow.execute(
            select(t.history).where(t.history.c.case_id == head['case_id'])
            .order_by(t.history.c.recorded_sequence)).mappings()}
        if [r['recorded_sequence'] for r in self.revisions.values()] != list(range(1, head['history_sequence'] + 1)):
            raise FlowError()
        self.events = []
        self.origins = {}
        previous = None
        records = uow.execute(select(t.audit).where(t.audit.c.case_id == head['case_id'])
                              .order_by(t.audit.c.sequence)).mappings()
        for sequence, row in enumerate(records, 1):
            event = decode_document(row['body'])
            validate('AuditEvent', event, internal=True)
            unsigned = {key: value for key, value in event.items() if key != 'event_hash'}
            if (row['sequence'] != sequence or row['event_id'] != event['event_id']
                    or event['case_id'] != head['case_id'] or event['case_version'] > head['case_version']
                    or event.get('previous_event_hash') != previous or row['event_hash'] != event['event_hash']
                    or digest({'sequence': sequence, 'event': unsigned}, 'audit/v1') != event['event_hash']):
                raise FlowError()
            seen = set()
            for ref in event.get('history_refs', []):
                revision = self.revisions.get(ref['record_id'])
                if (revision is None or ref['record_id'] in seen
                        or any(ref[key] != revision[key] for key in ('kind', 'object_id', 'object_version'))
                        or revision['case_version'] > event['case_version']):
                    raise FlowError()
                seen.add(ref['record_id'])
                generated_candidate = (generated_active and revision['kind'] == 'EVIDENCE' and event['event_type'] == 'GENERATED_LABEL_EVIDENCE_BOUND')
                if event['event_type'] in ORIGINS.get(revision['kind'], set()) or generated_candidate:
                    if (event['case_version'] != revision['case_version']
                            or event['occurred_at'] != timestamp(revision['recorded_at'])
                            or revision['object_id'] not in event['object_ids']
                            or ref['record_id'] in self.origins):
                        raise FlowError()
                    self.origins[ref['record_id']] = event
            self.events.append(event)
            previous = event['event_hash']
        if head['audit_sequence'] != len(self.events) or head['audit_head'] != previous:
            raise FlowError()
        # A new SERVICE origin is recognized only through the full low-level
        # generated certificate, never through an event-name allowlist.
        from .generated_evidence import is_generated_id
        candidates = [(r,self.origins.get(r['record_id'])) for r in self.revisions.values()
            if generated_active and r['kind']=='EVIDENCE' and (is_generated_id(r['object_id']) or
                self.origins.get(r['record_id'],{}).get('event_type')=='GENERATED_LABEL_EVIDENCE_BOUND')]
        for record,event in candidates:
            from .generated_evidence import validate_generated_origin
            if event is None: raise FlowError()
            validate_generated_origin(uow,self,record,event)
        if generated_active and any(e['event_type']=='GENERATED_LABEL_EVIDENCE_BOUND' and
                (len(e['history_refs'])!=1 or e['history_refs'][0]['record_id'] not in {r['record_id'] for r,_ in candidates})
                for e in self.events): raise FlowError()
        if generated_active:
            from .label_artifact_tables import artifacts
            from .label_execution_tables import artifact_work
            work_ids=select(artifact_work.c.work_id).where(artifact_work.c.case_id==head['case_id'])
            stored=set(uow.execute(select(artifacts.c.evidence_record_id).where(artifacts.c.work_id.in_(work_ids))).scalars())
            if stored!={r['record_id'] for r,_ in candidates}:raise FlowError()

    def origin(self, row):
        event = self.origins.get(row['record_id'])
        if event is None:
            raise FlowError()
        return event


def lookup_receipt(uow, receipt_id, case_id, input_version, status, origin):
    receipt = uow.execute(select(investigation.receipts).where(
        investigation.receipts.c.receipt_id == receipt_id)).mappings().one_or_none()
    if (receipt is None or receipt['case_id'] != case_id or receipt['input_version'] != input_version
            or receipt['status'] != status):
        raise FlowError()
    work = uow.execute(select(investigation.work).where(
        investigation.work.c.work_id == receipt['work_id'])).mappings().one_or_none()
    head = uow.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
    # These public projections use final MATCHED/CONFLICT/AUTHORITY_DENIED
    # receipts only. An earlier failure attempt is not a substitute source.
    if (work is None or work['case_id'] != case_id or work['input_version'] != input_version
            or work['owner_id'] != head['owner_principal_id'] or work['store_id'] != head['store_id']
            or work['state'] != 'DONE' or work['invocation_id'] != receipt_id
            or work['claim_id'] != receipt['claim_id'] or work['epoch'] != receipt['epoch']
            or work['claimed_case_version'] is None or origin['case_version'] != work['claimed_case_version'] + 1
            or work['completed_at'] != receipt['recorded_at']
            or origin['occurred_at'] != timestamp(receipt['recorded_at'])
            or origin['event_type'] != 'ORDER_INVESTIGATION_ACCEPTED' or receipt_id not in origin['object_ids']):
        raise FlowError()
    raw = uow.execute(select(investigation.receipt_contents.c.body).where(
        investigation.receipt_contents.c.receipt_id == receipt_id)).scalar_one_or_none()
    if not receipt['available']:
        if raw is not None:
            raise FlowError()
        return None
    if raw is None:
        raise FlowError()
    body = decode_document(raw)
    if (digest(body, 'order-receipt/v1') != receipt['body_hash']
            or body['request']['case_id'] != case_id or body['request']['input_version'] != input_version
            or body['service_signature'] != work['service_signature'] or body['grant_signature'] != work['grant_signature']):
        raise FlowError()
    result = validate('OrderLookupResult', body['result'], internal=True)
    if result['case_id'] != case_id or result['input_version'] != input_version or result['status'] != status:
        raise FlowError()
    return result


def block_content(uow, row, content, origin):
    validate('OrderLookupBlock', content, internal=True)
    block = uow.execute(select(investigation.blocks).where(
        investigation.blocks.c.block_id == row['object_id'])).mappings().one_or_none()
    if (block is None or block['case_id'] != row['case_id']
            or block['input_version'] != content['input_version']
            or decode_document(block['body']) != content or block['receipt_id'] not in origin['object_ids']):
        raise FlowError()
    result = {key: content[key] for key in ('case_id', 'input_version', 'status', 'message')}
    accepted = lookup_receipt(uow, block['receipt_id'], row['case_id'], content['input_version'], content['status'], origin)
    if accepted is not None and accepted != result:
        raise FlowError()
    wrapper = {'block': content, 'order_lookup': result}
    validate('HistoricalOrderLookupBlock', wrapper, internal=True)
    values = {'record_id': row['record_id'], 'profile': BLOCK_PROFILE,
              'source_content_sha256': row['content_sha256'],
              'projected_content_sha256': digest(wrapper, 'history/v1'), 'receipt_id': block['receipt_id']}
    stored = uow.execute(select(f.encodings).where(f.encodings.c.record_id == row['record_id'])).mappings().one_or_none()
    if stored is None:
        # GET may register this hash-only encoding metadata under its exclusive fence.
        uow.execute(f.encodings.insert().values(**values))
    elif any(stored[key] != value for key, value in values.items()):
        raise FlowError()
    return wrapper, values['projected_content_sha256']


def read_revision(uow, row, proof):
    origin = proof.origin(row)
    result = {name: row[name] for name in ('record_id', 'case_id', 'kind', 'object_id', 'object_version',
                                          'case_version', 'recorded_sequence', 'content_sha256', 'retention_state')}
    result.update(recorded_at=timestamp(row['recorded_at']), actor=origin['actor'])
    raw = uow.execute(select(t.history_contents.c.body).where(t.history_contents.c.record_id == row['record_id'])).scalar_one_or_none()
    if row['retention_state'] == 'AVAILABLE':
        if raw is None:
            raise FlowError()
        if row['kind'] in future.SCHEMAS:
            content, encoding = _future_source(uow, row, raw)
            future.verify_content(row, content, origin, proof, lambda source: read_revision(uow, source, proof))
            projected = finite.digest(content)
            if encoding is None:
                uow.execute(f.encodings.insert().values(record_id=row['record_id'],profile=finite.LEGACY_PROFILE,
                    source_content_sha256=row['content_sha256'],projected_content_sha256=projected,receipt_id=None))
            elif encoding['projected_content_sha256'] != projected:
                raise FlowError()
            result['content_sha256'] = projected
        else:
            content = decode_document(raw)
            if digest(content, 'history/v1') != row['content_sha256']:
                raise FlowError()
            if row['kind'] != 'ORDER_LOOKUP_BLOCK' and uow.execute(select(f.encodings.c.record_id).where(
                    f.encodings.c.record_id == row['record_id'])).scalar_one_or_none() is not None:
                raise FlowError()
            schema = {'STATEMENT': 'CustomerStatement', 'EVIDENCE': 'EvidenceAttachment',
                      'PROCESSING_FAILURE': 'ProcessingFailure', 'ORDER_LOOKUP_BLOCK': 'OrderLookupBlock'}.get(row['kind'])
            if schema is None:
                raise FlowError()
            validate(schema, content, internal=True)
            if content[IDENTITIES[row['kind']]] != row['object_id']:
                raise FlowError()
            if row['kind'] != 'STATEMENT' and content['case_id'] != row['case_id']:
                raise FlowError()
        if row['kind'] == 'ORDER_LOOKUP_BLOCK':
            content, result['content_sha256'] = block_content(uow, row, content, origin)
        result['content'] = content
    else:
        if raw is not None:
            raise FlowError()
        result['removal_reason'] = row['removal_reason']
        if row['kind'] in future.SCHEMAS:
            encoding = _future_encoding(uow, row)
            if encoding is None:
                raise FlowError()
            result['content_sha256'] = encoding['projected_content_sha256']
        elif row['kind'] == 'ORDER_LOOKUP_BLOCK':
            encoding = uow.execute(select(f.encodings).where(f.encodings.c.record_id == row['record_id'])).mappings().one_or_none()
            if (encoding is None or encoding['profile'] != BLOCK_PROFILE
                    or encoding['source_content_sha256'] != row['content_sha256']
                    or encoding['receipt_id'] not in origin['object_ids']):
                raise FlowError()
            result['content_sha256'] = encoding['projected_content_sha256']
        elif uow.execute(select(f.encodings.c.record_id).where(
                f.encodings.c.record_id == row['record_id'])).scalar_one_or_none() is not None:
            raise FlowError()
    finite.validate('FounderHistoryRecord', result)
    return result


def _future_encoding(uow, row):
    encoding = uow.execute(select(f.encodings).where(f.encodings.c.record_id == row['record_id'])).mappings().one_or_none()
    if encoding is not None and (encoding['profile'] not in {finite.PROFILE,finite.LEGACY_PROFILE}
            or encoding['receipt_id'] is not None or encoding['source_content_sha256'] != row['content_sha256']
            or (encoding['profile'] == finite.PROFILE and encoding['source_content_sha256'] != encoding['projected_content_sha256'])):
        raise FlowError()
    return encoding


def _future_source(uow, row, raw):
    encoding = _future_encoding(uow, row)
    if encoding is not None and encoding['profile'] == finite.PROFILE:
        content = finite.decode_document(raw)
        actual = finite.digest(content)
    else:
        # Absence authorizes only the legacy v1 decode/verify/backfill path.
        # Never inspect a v2 header and silently authorize missing metadata.
        content = decode_document(raw)
        actual = digest(content, 'history/v1')
    if actual != row['content_sha256']:
        raise FlowError()
    return content, encoding


def register_existing_block_encodings(connection):
    """0006 backfill of hash-only metadata; valid accepted0005 rows are preserved."""
    case_ids = connection.execute(select(t.history.c.case_id).where(
        t.history.c.kind.in_(['ORDER_LOOKUP_BLOCK', *future.SCHEMAS])).distinct()).scalars().all()
    for case_id in case_ids:
        head = connection.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
        proof = CaseProof(connection, head)
        for row in proof.revisions.values():
            if row['kind'] == 'ORDER_LOOKUP_BLOCK' or row['kind'] in future.SCHEMAS:
                read_revision(connection, row, proof)
