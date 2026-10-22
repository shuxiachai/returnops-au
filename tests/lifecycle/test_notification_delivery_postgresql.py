"""Cloud-only actual three-outcome delivery, query recovery and no-effect retry."""
from dataclasses import asdict
import json
import pytest
from sqlalchemy import select, update
from returnops_domain import customer_tables as old, lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown
from returnops_domain.notification_mock import CoreMockNotification
from returnops_domain.notification_tables import controls, facts
from returnops_domain.notification_profile import COMPONENT
from returnops_domain.wire import validate
from notification_helpers import ready, service, rows, snapshot, evidence, pdf_call_counts, _diagnostic_uow


class NoEffect(CoreMockNotification):
    def _outcome(self):
        return 'NO_EFFECT_FAILED'


class LostReply(CoreMockNotification):
    def deliver(self,reservation_id):
        found=super().deliver(reservation_id)
        assert found is not None
        raise AcceptanceOutcomeUnknown()


class NoSend(CoreMockNotification):
    def deliver(self,reservation_id):
        return None


def _validate_audit_events(audits):
    """Validate the complete retained collection without imposing a page limit."""
    for event in audits:
        validate('AuditEvent', event, internal=True)


def _emit_send_diagnostics(capsys, kind, domain, mock):
    """Emit bounded safe observer fields directly, never a pytest object repr."""
    kinds = {'return', 'reject', 'manual_pass', 'manual_escalated',
             'manual_failure', 'manual_block', 'manual_intake', 'manual_assessment'}
    types = {'FlowError', 'AcceptanceOutcomeUnknown', 'OperationalError', 'InterfaceError',
             'DBAPIError', 'StatementError', 'DataError', 'IntegrityError', 'ProgrammingError',
             'ValueError', 'TypeError', 'KeyError', 'IndexError', 'AssertionError', 'RuntimeError'}
    codes = {'UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND', 'VALIDATION_ERROR',
             'STALE_CASE_VERSION', 'IDEMPOTENCY_CONFLICT', 'INVALID_STATE',
             'REQUEST_TOO_LARGE', 'UNSUPPORTED_MEDIA_TYPE', 'INTERNAL_ERROR'}
    alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'

    def count(value):
        return value if type(value) is int and 0 <= value <= 1000000 else None

    def name(value, *, module=False):
        allowed = alphabet + ('.' if module else '<>')
        limit = 160 if module else 64
        if (type(value) is str and 0 < len(value) <= limit
                and all(character in allowed for character in value)
                and (not module or value.startswith('returnops_domain.'))):
            return value
        return 'UNAVAILABLE'

    safe_kind = kind if type(kind) is str and kind in kinds else 'OTHER'
    with capsys.disabled():
        for scope, observed in (('domain', domain), ('mock', mock)):
            observed = observed if type(observed) is dict else {}
            events = observed.get('events', [])
            events = events if type(events) is list else []
            base = dict(format=1, kind=safe_kind, scope=scope)
            records = [dict(**base, part='container', events=min(len(events), 8),
                            events_omitted=count(max(0, len(events)-8)),
                            dropped=count(observed.get('dropped')))]
            for index, entry in enumerate(events[:8]):
                entry = entry if type(entry) is dict else {}
                frames = entry.get('frames', [])
                frames = frames if type(frames) is list else []
                stage, error_type, code = (entry.get(key) for key in ('stage', 'type', 'safe_code'))
                records.append(dict(**base, part='event', event_index=index,
                    stage=stage if type(stage) is str and stage in {'poison', 'exit'} else 'OTHER',
                    type=error_type if type(error_type) is str and error_type in types else 'OTHER_EXCEPTION',
                    safe_code=code if type(code) is str and code in codes else None,
                    frames=min(len(frames), 12), frames_omitted=count(max(0, len(frames)-12)),
                    frames_truncated=entry.get('frames_truncated') if type(entry.get('frames_truncated')) is bool else None))
                for frame_index, frame in enumerate(frames[:12]):
                    frame = frame if type(frame) is dict else {}
                    records.append(dict(**base, part='frame', event_index=index, frame_index=frame_index,
                        module=name(frame.get('module'), module=True), function=name(frame.get('function')),
                        line=count(frame.get('line'))))
            for record in records:
                line = 'RETURNOPS_NOTIFICATION_SEND_DIAGNOSTIC ' + json.dumps(
                    record, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
                assert len(line) <= 1024
                print(line, flush=True)


@pytest.mark.parametrize('kind',['return','reject','manual_pass','manual_escalated',
                                'manual_failure','manual_block','manual_intake','manual_assessment'])
def test_actual_producers_send_one_independent_fact_and_terminal_outcome(
        flow_engine,identities,enabled,request,kind,capsys):
    setup=ready(flow_engine,identities,kind)
    before=snapshot(flow_engine)
    domain_observed={'events':[],'dropped':0}
    mock_observed={'events':[],'dropped':0}
    with pdf_call_counts() as calls:
        delivered=service(flow_engine,identities,uow_factory=_diagnostic_uow(domain_observed),
            mock=CoreMockNotification(flow_engine,uow_factory=_diagnostic_uow(mock_observed))).send(setup['work_id'])
    if delivered.status != 'SENT':
        _emit_send_diagnostics(capsys, kind, domain_observed, mock_observed)
    assert delivered.status=='SENT',{'result':asdict(delivered),
        'domain_diagnostics':domain_observed,'mock_diagnostics':mock_observed}
    saved=rows(flow_engine,facts)
    assert len(saved)==1 and saved[0]['status']=='SENT'
    control=rows(flow_engine,controls)[0]
    assert saved[0]['fact_id']==control['accepted_fact_id']
    assert saved[0]['notification_work_id']==setup['work_id']
    assert control['notification_id']==setup['control']['notification_id']
    assert control['logical_key']==setup['control']['logical_key']
    assert control['attempt_count']==saved[0]['attempt_count']==1
    head=rows(flow_engine,old.case_heads)[0]
    assert head['status']==('COMPLETED' if kind=='return' else 'REJECTED' if kind=='reject' else 'MANUAL_HANDLED')
    from returnops_domain.canonical import decode_document, digest
    from returnops_domain.notification_customer_origin import EVENT, customer_payload, history_ref
    messages=[row for row in rows(flow_engine,old.history) if row['kind']=='OUTCOME_MESSAGE']
    assert len(messages)==1
    audits=[decode_document(row['body']) for row in rows(flow_engine,old.audit)]
    customer_audits=[event for event in audits if event['event_type']==EVENT]
    assert len(customer_audits)==1
    accepted=next(row for row in rows(flow_engine,old.history) if row['record_id']==control['accepted_record_id'])
    assert customer_audits[0]['history_refs']==[history_ref(accepted)]
    assert accepted['kind']=='NOTIFICATION'
    assert customer_audits[0]['payload_hash']==digest(customer_payload(control,saved[0],messages[0]),'audit-payload/v1')
    _validate_audit_events(audits)
    if kind=='manual_assessment':
        assert len(audits)>100
    assert all(calls[name]==0 for name in ('render','text_line','assembly','expected_pdf',
                                          'return_provider','label_provider','artifact_retrieval'))
    after=snapshot(flow_engine)
    for name in ('lifecycle_effect_refs','core_mock_return_ledger','core_mock_label_ledger',
                 'generated_label_artifact_contents','generated_label_artifacts'):
        assert after[name]==before[name]
    for _ in range(2):
        assert service(flow_engine,identities).reconcile(setup['work_id']).status=='SENT'
        assert service(flow_engine,identities).send(setup['work_id']).status=='SENT'
    assert snapshot(flow_engine)==after
    evidence(request.node.nodeid,kind=kind,result=asdict(delivered),before=before,after=after,
             independent_fact=saved[0]['fact_id'],actual_calls=calls)


def test_unknown_missing_fact_queries_only_and_never_authorizes_retry(flow_engine,identities,enabled,request):
    setup=ready(flow_engine,identities)
    initial=service(flow_engine,identities,mock=NoSend(flow_engine)).send(setup['work_id'])
    assert initial.status=='UNKNOWN'
    assert rows(flow_engine,facts)==[]
    before=snapshot(flow_engine)
    class ForbiddenSend(CoreMockNotification):
        def deliver(self,*args):
            pytest.fail('UNKNOWN recovery invoked sender')
    caller=service(flow_engine,identities,mock=ForbiddenSend(flow_engine))
    assert caller.send(setup['work_id']).status=='UNKNOWN'
    assert caller.reconcile(setup['work_id']).status=='UNKNOWN'
    version=rows(flow_engine,old.case_heads)[0]['case_version']
    assert caller.retry(setup['work_id'],version).status=='UNKNOWN'
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,result=asdict(initial),before=before,after=snapshot(flow_engine))


def test_lost_t2_reply_restores_t3_from_original_fact_without_another_send(flow_engine,identities,enabled,request):
    setup=ready(flow_engine,identities)
    unknown=service(flow_engine,identities,mock=LostReply(flow_engine)).send(setup['work_id'])
    assert unknown.status=='UNKNOWN'
    original_fact=rows(flow_engine,facts)
    assert len(original_fact)==1 and original_fact[0]['status']=='SENT'
    class QueryOnly(CoreMockNotification):
        def deliver(self,*args):pytest.fail('Recovery attempted another send')
    recovered=service(flow_engine,identities,mock=QueryOnly(flow_engine)).reconcile(setup['work_id'])
    assert recovered.status=='SENT',asdict(recovered)
    assert rows(flow_engine,facts)==original_fact
    after=snapshot(flow_engine)
    assert service(flow_engine,identities).reconcile(setup['work_id']).status=='SENT'
    assert snapshot(flow_engine)==after
    evidence(request.node.nodeid,unknown=asdict(unknown),recovered=asdict(recovered),fact=original_fact)


@pytest.mark.parametrize('caller',['founder','customer_a','customer_b',None])
def test_retry_needs_current_founder_and_preserves_original_delivery_identity(
        flow_engine,identities,enabled,request,caller):
    setup=ready(flow_engine,identities)
    failed=service(flow_engine,identities,mock=NoEffect(flow_engine)).send(setup['work_id'])
    assert failed.status=='NO_EFFECT_FAILED',asdict(failed)
    before=snapshot(flow_engine)
    head=rows(flow_engine,old.case_heads)[0]
    retried=service(flow_engine,identities,caller).retry(setup['work_id'],head['case_version'])
    if caller!='founder':
        assert retried.status=='UNKNOWN' and snapshot(flow_engine)==before
    else:
        assert retried.status=='READY'
        assert service(flow_engine,identities).send(setup['work_id']).status=='SENT'
        control=rows(flow_engine,controls)[0]
        assert control['notification_work_id']==setup['work_id']
        assert control['notification_id']==setup['control']['notification_id']
        assert control['logical_key']==setup['control']['logical_key']
        assert control['attempt_count']==2
        saved=sorted(rows(flow_engine,facts),key=lambda row:row['attempt_count'])
        assert [row['status'] for row in saved]==['NO_EFFECT_FAILED','SENT']
        assert len({row['reservation_id'] for row in saved})==2
        assert len({row['logical_key'] for row in saved})==1
        assert rows(flow_engine,life.effects)==[]
    evidence(request.node.nodeid,caller=caller,result=asdict(retried),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('fault',['service_disabled','service_revision','owner_disabled','owner_store'])
def test_delivery_current_authority_cannot_be_borrowed_from_saved_intent(
        flow_engine,identities,enabled,request,fault):
    setup=ready(flow_engine,identities)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        if fault.startswith('service'):
            uow.execute(update(life.authorities).where(life.authorities.c.component_id==COMPONENT).values(
                **({'enabled':False} if fault=='service_disabled' else {'enabled':False,'revision':2})))
        else:
            uow.execute(update(old.principals).where(old.principals.c.principal_id==setup['control']['owner_id']).values(
                **({'enabled':False} if fault=='owner_disabled' else {'store_id':'unrelated_store'})))
        uow.commit()
    before=snapshot(flow_engine)
    denied=service(flow_engine,identities).send(setup['work_id'])
    assert denied.status=='UNKNOWN' and snapshot(flow_engine)==before and rows(flow_engine,facts)==[]
    evidence(request.node.nodeid,fault=fault,result=asdict(denied),before=before,after=snapshot(flow_engine))
