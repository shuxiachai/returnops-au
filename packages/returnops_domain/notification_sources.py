"""Exact original intent, T1 reservation and persisted notification transitions."""
from dataclasses import asdict
from datetime import datetime
from sqlalchemy import select, or_
from . import customer_tables as old, lifecycle_tables as life
from .audit import timestamp
from .canonical import digest, decode_document, encode_document
from .lifecycle_events import LifecycleClaim, NotificationObserved, OutcomeAccepted
from .lifecycle_sources import Sources, authority
from .lifecycle_state import current, reject
from .lifecycle_schema import NOTIFICATION, version
from .manual_target import one
from .notification_tables import controls, facts
from .notification_profile import COMPONENT, CHANNEL
from .notification_intent import original_intent, RETURN_PRODUCER, initial_payload
from .return_execution_sources import database_now


def reservation_core(control, claim, now, deadline):
    return dict(profile='notification-reservation/v2', **{name:control[name] for name in
        ('notification_work_id','notification_id','case_id','store_id','owner_id','reservation_id',
         'logical_key','outcome','channel','profile_hash','payload_hash','intent_hash','attempt_count')},
        message_profile=control['profile'], claim_id=claim.claim_id, epoch=claim.epoch,
        case_version=claim.case_version, authority_revision=claim.authority_revision,
        reserved_at=timestamp(now), deadline=timestamp(deadline))


def phase_payload(control, phase, proof_hash):
    return dict(profile='notification-observation/v2', notification_work_id=control['notification_work_id'],
                intent_hash=control['intent_hash'], phase=phase, proof_hash=proof_hash)


def _outcome(uow, head, control, original):
    source = one(uow, old.history, record_id=control['outcome_record_id'])
    event = original['receipt']
    producer = one(uow, life.work, work_id=event['work_id'])
    sources = Sources(uow, head, control['producer_id'])
    _, body = sources.read(source['record_id'], {source['kind']}, current_actor=False)
    binding = one(uow, life.sources, record_id=source['record_id'])
    claim = LifecycleClaim(producer['work_id'], producer['claim_id'], producer['epoch'],
        producer['claimed_case_version'], producer['input_version'], producer['generation'],
        producer['authority_revision'])
    state = current(uow, head, initialize=False)
    if (state is None or not state['available'] or state['generation'] != control['generation']
            or state['input_version'] != control['input_version'] or head['input_version'] != control['input_version']
            or state['notification_work_id'] != control['notification_work_id']
            or state['notification_id'] != control['notification_id']
            or state['outcome_record_id'] != control['outcome_record_id'] or state['outcome'] != control['outcome']
            or producer['component_id'] != control['producer_id'] or producer['purpose'] != 'OUTCOME'
            or producer['state'] != 'DONE' or producer['case_id'] != head['case_id']
            or producer['store_id'] != head['store_id'] or producer['owner_id'] != head['owner_principal_id']
            or producer['input_version'] != control['input_version'] or producer['generation'] != control['generation']):
        reject(uow)
    return_id = label_id = None
    if control['outcome'] == 'RETURN_CREATED':
        from .notification_execution import completed_pair
        pair = completed_pair(uow, head)
        if control['producer_id'] != RETURN_PRODUCER or source['record_id'] != original['initial']['record_id']:
            reject(uow)
        return_id, label_id = pair['return_record_id'], pair['label_record_id']
    elif control['outcome'] == 'REJECTED':
        from .reject_sources import accepted_reject, COMPONENT as producer_id
        if control['producer_id'] != producer_id or accepted_reject(uow, head, source['record_id'], producer_id)['event'] != event:
            reject(uow)
    elif control['outcome'] == 'MANUAL_HANDLED':
        from .manual_denial import COMPONENT as producer_id
        if control['producer_id'] != producer_id or body.get('decision') != 'MANUAL_HANDLING':
            reject(uow)
        if 'proposal_id' in body:
            from .pass_manual_sources import accepted_manual
            if accepted_manual(uow, head, source['record_id'], producer_id)['event'] != event:
                reject(uow)
        else:
            # Replay the genuine pre-outcome target against retained immutable
            # sources. The head's audit highwater stays current for CaseProof.
            from .manual_target import read_target
            original_state = original['manifest']['original_state']
            request = {**body, 'expected_case_version':event['pre_case_version']}
            target = read_target(uow, head, state, request, producer_id,
                                 original_state=original_state, consumer=source['record_id'],
                                 accepted_case_version=event['pre_case_version'])
            if binding['target_record_id'] != target['record']['record_id']:
                reject(uow)
    else:
        reject(uow)
    expected_event = OutcomeAccepted(event['event_id'], claim, source['record_id'],
                                    original['initial']['record_id'], return_id, label_id)
    expected_receipt = dict(event_id=event['event_id'],case_id=head['case_id'],work_id=claim.work_id,
        record_id=source['record_id'],fingerprint=digest({'kind':'OUTCOME',**asdict(expected_event)},'lifecycle-event/v1'),
        event_kind='OUTCOME',source_id=source['record_id'],source_hash=source['content_sha256'],
        source_audit_event_id=sources.proof.origin(source)['event_id'],
        pre_case_version=claim.case_version,pre_input_version=claim.input_version,pre_generation=claim.generation,
        case_version=claim.case_version+1,input_version=claim.input_version,generation=claim.generation,
        status='NOTIFICATION_PENDING',accepted_at=source['recorded_at'])
    from .lifecycle_guards import target
    original_state = original['manifest']['original_state']
    original_head = {**head,'case_version':claim.case_version,'input_version':claim.input_version}
    if (event != expected_receipt or producer['epoch'] < 1 or producer['claim_id'] is None
            or producer['authority_revision'] is None or producer['lease_expires_at'] is not None
            or producer['target_record_id'] is not None
            or producer['target_hash'] != target(original_head,original_state,'OUTCOME')
            or producer['created_at'] > source['recorded_at']
            or source['case_version'] != claim.case_version or source['object_version'] != 1
            or original_state['generation'] != claim.generation or original_state['input_version'] != claim.input_version):
        reject(uow)
    empty = dict(dispatch_source_record_id=None,provider_operation_id=None,
                 artifact_evidence_id=None,artifact_sha256=None,order_projection_id=None)
    expected_binding = dict(record_id=source['record_id'],case_id=head['case_id'],**asdict(claim),
        source_hash=source['content_sha256'],slot='PRIMARY',target_record_id=binding['target_record_id'],**empty)
    note_row = original['initial']
    note_binding = one(uow,life.sources,record_id=note_row['record_id'])
    expected_note_binding = dict(record_id=note_row['record_id'],case_id=head['case_id'],**asdict(claim),
        source_hash=note_row['content_sha256'],slot='PRIMARY' if return_id else 'NOTIFICATION',
        target_record_id=source['record_id'],**empty)
    source_id = pair['label_record_id'] if return_id else source['record_id']
    source_hash = pair['artifact']['result_record']['content_sha256'] if return_id else source['content_sha256']
    note_origin = sources.proof.origin(note_row)
    audits = [item for item in sources.proof.events if item['event_type']=='LIFECYCLE_EVENT_ACCEPTED'
              and item['correlation_id']==event['event_id']]
    payload = dict(event='OUTCOME',work_id=claim.work_id,source_record_id=source['record_id'],generation=claim.generation)
    if (binding != expected_binding or note_binding != expected_note_binding
            or note_row['object_version'] != 1 or note_row['case_version'] != claim.case_version
            or note_row['recorded_at'] != source['recorded_at']
            or note_origin['actor'] != {'kind':'SERVICE','component_id':control['producer_id']}
            or note_origin['payload_hash'] != digest(initial_payload(control['producer_id'],control['outcome'],
                source_id,source_hash),'audit-payload/v1')
            or len(audits)!=1 or audits[0]['actor']!={'kind':'SERVICE','component_id':control['producer_id']}
            or audits[0]['payload_hash']!=digest(payload,'audit-payload/v1')
            or audits[0]['case_version']!=event['case_version']
            or audits[0]['occurred_at']!=timestamp(event['accepted_at'])
            or audits[0]['object_ids']!=[source['object_id'],claim.work_id] or audits[0]['history_refs']!=[]):
        reject(uow)
    return state


def _accepted_revision(uow, head, control, sources, row, *, staged=None):
    binding = one(uow, life.sources, record_id=row['record_id'])
    claim = LifecycleClaim(**{name:binding[name] for name in LifecycleClaim.__dataclass_fields__})
    origin = sources.proof.origin(row)
    expected_binding = dict(record_id=row['record_id'],case_id=head['case_id'],**asdict(claim),
        source_hash=row['content_sha256'],target_record_id=control['outcome_record_id'],slot='PRIMARY',
        dispatch_source_record_id=None,provider_operation_id=None,artifact_evidence_id=None,
        artifact_sha256=None,order_projection_id=None)
    if (binding != expected_binding or binding['work_id'] != control['notification_work_id']
            or binding['case_id'] != head['case_id'] or binding['input_version'] != control['input_version']
            or binding['generation'] != control['generation'] or binding['slot'] != 'PRIMARY'
            or binding['source_hash'] != row['content_sha256']
            or binding['target_record_id'] != control['outcome_record_id']
            or origin['actor'] != {'kind':'SERVICE','component_id':COMPONENT}
            or origin['event_type'] != 'NOTIFICATION_REVISION_RECORDED'):
        reject(uow)
    if staged is not None and staged.record_id == row['record_id']:
        if staged.claim != claim:
            reject(uow)
        return claim
    event = one(uow, life.events, record_id=row['record_id'])
    expected = NotificationObserved(event['event_id'], claim, row['record_id'])
    _, body = sources.read(row['record_id'],{'NOTIFICATION'},current_actor=False)
    terminal = {'RETURN_CREATED':'COMPLETED','REJECTED':'REJECTED','MANUAL_HANDLED':'MANUAL_HANDLED'}
    status = (terminal[control['outcome']] if body['status']=='SENT' else
              'NOTIFICATION_FAILED' if body['status']=='FAILED' else 'NOTIFICATION_PENDING')
    expected_receipt = dict(event_id=event['event_id'],case_id=head['case_id'],work_id=claim.work_id,
        record_id=row['record_id'],fingerprint=digest({'kind':'NOTIFICATION',**asdict(expected)},'lifecycle-event/v1'),
        event_kind='NOTIFICATION',source_id=row['record_id'],source_hash=row['content_sha256'],
        source_audit_event_id=origin['event_id'],pre_case_version=row['case_version'],
        pre_input_version=claim.input_version,pre_generation=claim.generation,
        case_version=row['case_version']+1,input_version=claim.input_version,generation=claim.generation,
        status=status,accepted_at=row['recorded_at'])
    if event != expected_receipt:
        reject(uow)
    audits = [entry for entry in sources.proof.events if entry['event_type'] == 'LIFECYCLE_EVENT_ACCEPTED'
              and entry['correlation_id'] == event['event_id']]
    payload = dict(event='NOTIFICATION', work_id=claim.work_id, source_record_id=row['record_id'],
                   generation=claim.generation)
    if (len(audits) != 1 or audits[0]['payload_hash'] != digest(payload, 'audit-payload/v1')
            or audits[0]['actor'] != {'kind':'SERVICE','component_id':COMPONENT}
            or audits[0]['case_version'] != event['case_version']
            or audits[0]['occurred_at'] != timestamp(event['accepted_at'])
            or audits[0]['object_ids'] != [row['object_id'],claim.work_id] or audits[0]['history_refs'] != []):
        reject(uow)
    return claim


def validate_control(uow, head, control, *, staged=None):
    original = original_intent(uow, head, control)
    state = _outcome(uow, head, control, original)
    sources = Sources(uow, head, COMPONENT)
    revisions = [row for row in sources.proof.revisions.values()
                 if row['kind'] == 'NOTIFICATION' and row['object_id'] == control['notification_id']]
    if not revisions or revisions[0]['record_id'] != control['initial_notification_record_id']:
        reject(uow)
    from .notification_mock import verify_fact
    aliases = [facts.c.notification_work_id == control['notification_work_id'],
        facts.c.notification_id == control['notification_id'], facts.c.logical_key == control['logical_key'],
        facts.c.intent_hash == control['intent_hash']]
    if control['reservation_id'] is not None:
        aliases.append(facts.c.reservation_id == control['reservation_id'])
    saved = [dict(row) for row in uow.execute(select(facts).where(
        or_(*aliases)).order_by(facts.c.attempt_count,facts.c.fact_id)).mappings()]
    for fact in saved:
        verify_fact(uow, control, fact)
    fact_by_attempt = {fact['attempt_count']:fact for fact in saved}
    if len(fact_by_attempt) != len(saved):
        reject(uow)
    retries = [] if control['retry_authorization'] is None else decode_document(control['retry_authorization'])
    if not isinstance(retries, list):
        reject(uow)
    previous = original['note']
    reservation_count = 0
    previous_phase = 'INITIAL'
    last_fact = (None,None,None)
    last_retry = (None,None)
    last_reservation = (None,None)
    for number,row in enumerate(revisions[1:], 2):
        _, body = sources.read(row['record_id'], {'NOTIFICATION'}, current_actor=False)
        claim = _accepted_revision(uow, head, control, sources, row, staged=staged)
        if (row['object_version'] != number or body['notification_id'] != previous['notification_id']
                or body['outcome'] != previous['outcome'] or body['case_id'] != head['case_id']
                or body['case_version'] != row['case_version']
                or body['message'] != previous['message'] or body['next_steps'] != previous['next_steps']
                or body['updated_at'] != timestamp(row['recorded_at']) or previous['status'] == 'SENT'):
            reject(uow)
        if body['status'] == 'PENDING' and body['attempt_count'] == previous['attempt_count'] + 1:
            reservation_count += 1
            if previous['status'] != 'PENDING':
                reject(uow)
            if ((body['attempt_count']==1 and previous_phase!='INITIAL')
                    or (body['attempt_count']>1 and previous_phase!='RETRY')):
                reject(uow)
            fact = fact_by_attempt.get(body['attempt_count'])
            raw = (control['reservation_core'] if body['attempt_count'] == control['attempt_count']
                   else None if fact is None else fact['reservation_core'])
            if raw is None:
                reject(uow)
            core = decode_document(raw)
            if (core['attempt_count'] != body['attempt_count'] or core['claim_id'] != claim.claim_id
                    or core['epoch'] != claim.epoch or core['case_version'] != claim.case_version
                    or core['authority_revision'] != claim.authority_revision
                    or core['reserved_at'] != body['updated_at'] or claim.case_version != row['case_version']):
                reject(uow)
            expected_payload = phase_payload(control, 'RESERVE', digest(core, 'notification-reservation/v2'))
            previous_phase = 'RESERVE'
            last_reservation = (row['record_id'], staged.event_id if staged is not None
                and staged.record_id==row['record_id'] else one(uow,life.events,record_id=row['record_id'])['event_id'])
        elif body['status'] in {'SENT','FAILED'} and body['attempt_count'] == previous['attempt_count']:
            fact = fact_by_attempt.get(body['attempt_count'])
            if previous['status'] != 'PENDING' or previous_phase!='RESERVE' or fact is None:
                reject(uow)
            expected_status = 'SENT' if fact['status'] == 'SENT' else 'FAILED'
            if body['status'] != expected_status or row['recorded_at'] < fact['accepted_at']:
                reject(uow)
            if body['status'] == 'SENT' and body.get('sent_at') != timestamp(fact['accepted_at']):
                reject(uow)
            expected_payload = phase_payload(control, 'FACT', fact['fact_hash'])
            previous_phase = 'FACT'
            last_fact = (fact['fact_id'],row['record_id'],staged.event_id if staged is not None
                and staged.record_id==row['record_id'] else one(uow,life.events,record_id=row['record_id'])['event_id'])
        elif body['status'] == 'PENDING' and previous['status'] == 'FAILED' and body['attempt_count'] == previous['attempt_count']:
            fact = fact_by_attempt.get(body['attempt_count'])
            entries = [entry for entry in retries if entry['record_id'] == row['record_id']]
            if fact is None or fact['status'] != 'NO_EFFECT_FAILED' or len(entries) != 1 or previous_phase!='FACT':
                reject(uow)
            entry = entries[0]
            if (entry['fact_id'] != fact['fact_id'] or entry['fact_hash'] != fact['fact_hash']
                    or entry['expected_case_version'] != row['case_version']
                    or entry['authorized_at'] != body['updated_at']):
                reject(uow)
            human = [audit for audit in sources.proof.events if audit['event_id'] == entry['audit_id']]
            authorization = {name:value for name,value in entry.items() if name != 'audit_id'}
            if (len(human) != 1 or human[0]['actor'] != {'kind':'HUMAN','role':'FOUNDER','principal_id':entry['principal_id']}
                    or human[0]['event_type'] != 'NOTIFICATION_RETRY_AUTHORIZED'
                    or human[0]['payload_hash'] != digest(authorization, 'audit-payload/v1')
                    or human[0]['occurred_at'] != entry['authorized_at']):
                reject(uow)
            expected_payload = phase_payload(control, 'RETRY', digest(entry, 'notification-retry/v2'))
            previous_phase = 'RETRY'
            last_retry = (row['record_id'],entry['event_id'])
        else:
            reject(uow)
        if sources.proof.origin(row)['payload_hash'] != digest(expected_payload, 'audit-payload/v1'):
            reject(uow)
        previous = body
    if (previous['attempt_count'] != control['attempt_count']
            or state['notification_record_id'] != (revisions[-2]['record_id'] if staged is not None else revisions[-1]['record_id'])
            or control['attempt_count'] != reservation_count
            or (control['accepted_fact_id'],control['accepted_record_id'],control['accepted_event_id']) != last_fact
            or (control['reservation_record_id'],control['reservation_event_id']) != last_reservation
            or (control['retry_record_id'],control['retry_event_id']) != last_retry
            or len(retries) != sum(1 for row in revisions if row['record_id'] in {entry['record_id'] for entry in retries})):
        reject(uow)
    allowed = ({'READY'} if not control['attempt_count'] else
               {'SENT'} if previous['status'] == 'SENT' else
               {'NO_EFFECT_FAILED'} if previous['status'] == 'FAILED' else
               {'READY'} if retries and revisions[-1]['record_id'] == control['retry_record_id']
               else {'RESERVED','UNKNOWN'})
    if control['state'] not in allowed:
        reject(uow)
    return dict(original=original, state=state, sources=sources, revisions=revisions, note=previous, facts=saved)


def validate_reservation(uow, reservation_id, *, sending):
    if type(sending) is not bool or version(uow.connection) != NOTIFICATION:
        reject(uow)
    control = one(uow, controls, reservation_id=reservation_id)
    head = one(uow, old.case_heads, case_id=control['case_id'])
    grant = authority(uow, head, COMPONENT, 'NOTIFICATION', lock_rows=uow.write)
    seal = validate_control(uow, head, control)
    core = decode_document(control['reservation_core'])
    claim = LifecycleClaim(control['notification_work_id'], control['reservation_claim_id'],
        control['reservation_epoch'], control['reservation_case_version'], control['input_version'],
        control['generation'], control['reservation_authority_revision'])
    expected = reservation_core(control, claim, control['reservation_at'], control['reservation_deadline'])
    if (core != expected or encode_document(core) != bytes(control['reservation_core'])
            or digest(core, 'notification-reservation/v2') != control['reservation_hash']
            or control['reservation_record_id'] not in {row['record_id'] for row in seal['revisions']}):
        reject(uow)
    if sending:
        work = seal['original']['work']
        if (control['state'] != 'RESERVED' or seal['note']['status'] != 'PENDING'
                or work['state'] != 'PENDING' or work['claim_id'] != claim.claim_id or work['epoch'] != claim.epoch
                or work['claimed_case_version'] != claim.case_version or work['lease_expires_at'] is not None
                or grant['revision'] != claim.authority_revision or work['authority_revision'] != claim.authority_revision
                or head['case_version'] != claim.case_version + 1
                or not control['reservation_at'] <= database_now(uow) < control['reservation_deadline']):
            reject(uow)
    return dict(control=control, reservation=core, head=head)


def apply_observation(uow, head, state, row, body, work, event, now):
    """Called by the Domain guard itself, including direct event submissions."""
    if version(uow.connection) != NOTIFICATION or work['component_id'] != COMPONENT:
        reject(uow)
    control = one(uow, controls, notification_work_id=work['work_id'])
    seal = validate_control(uow, head, control, staged=event)
    if row['record_id'] != seal['revisions'][-1]['record_id'] or row['case_version'] != head['case_version']:
        reject(uow)
    if row['record_id'] == control['reservation_record_id']:
        core = decode_document(control['reservation_core'])
        if (control['state'] != 'RESERVED' or control['reservation_event_id'] != event.event_id
                or core != reservation_core(control,event.claim,control['reservation_at'],control['reservation_deadline'])
                or control['reservation_hash'] != digest(core,'notification-reservation/v2')
                or encode_document(core) != bytes(control['reservation_core'])
                or control['reservation_at'] != now or control['reservation_deadline'] > work['lease_expires_at']
                or not now < control['reservation_deadline'] or body['status'] != 'PENDING'
                or any(fact['attempt_count'] == control['attempt_count'] for fact in seal['facts'])):
            reject(uow)
    elif row['record_id'] == control['accepted_record_id']:
        fact = one(uow, facts, fact_id=control['accepted_fact_id'])
        from .notification_mock import verify_fact
        verify_fact(uow,control,fact)
        if (control['accepted_event_id'] != event.event_id or fact['attempt_count'] != control['attempt_count']
                or fact['notification_work_id'] != control['notification_work_id']
                or body['status'] != ('SENT' if fact['status'] == 'SENT' else 'FAILED')):
            reject(uow)
    elif row['record_id'] == control['retry_record_id']:
        entries = decode_document(control['retry_authorization'])
        entry = next((item for item in entries if item['record_id'] == row['record_id']), None)
        if entry is None or control['retry_event_id'] != event.event_id or body['status'] != 'PENDING':
            reject(uow)
        check_retry_authority(uow, head, entry, now)
    else:
        reject(uow)
    if body['status'] == 'SENT':
        return {'RETURN_CREATED':'COMPLETED','REJECTED':'REJECTED','MANUAL_HANDLED':'MANUAL_HANDLED'}[control['outcome']]
    return 'NOTIFICATION_FAILED' if body['status'] == 'FAILED' else 'NOTIFICATION_PENDING'


def check_retry_authority(uow, head, entry, now):
    person = one(uow, old.principals, principal_id=entry['principal_id'])
    session = one(uow, old.sessions, session_id=entry['session_id'])
    if (person['role'] != 'FOUNDER' or not person['enabled'] or person['store_id'] != head['store_id']
            or session['principal_id'] != person['principal_id'] or session['revoked']
            or [session[name] for name in ('issued_at','not_before','expires_at')] != entry['session_bounds']
            or not session['issued_at'] <= session['not_before'] <= now.timestamp() < session['expires_at']):
        reject(uow, 'UNAUTHENTICATED')
