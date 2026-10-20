"""Legacy v1 remains readable/HOLD; migration never invents a sending fact.

PENDING comes from the actual old rejection producer. FAILED/SENT below are
explicit synthetic old guard fixtures, not historical production deliveries.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import select, update
from returnops_domain import customer_tables as old
from returnops_domain.audit import identifier, timestamp
from returnops_domain.canonical import digest, encode_document
from returnops_domain import lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.lifecycle_guards import LifecycleGuards
from returnops_domain.lifecycle_schema import ARTIFACT, NOTIFICATION
from returnops_domain.notification_tables import controls, facts
from conftest import migrate
from reject_helpers import ready,attempt,assert_rejected,provision_notification,COMPONENT
from synthetic_sources import notify,now
from notification_helpers import service,provision,rows,snapshot,evidence


@pytest.mark.parametrize('flow_engine',[ARTIFACT],indirect=True)
@pytest.mark.parametrize('legacy_status',['PENDING','FAILED','SENT'])
def test_original_v1_bytes_identity_and_hold_survive_0014(
        flow_engine,identities,enabled,request,legacy_status):
    case,body=ready(flow_engine,identities)
    assert_rejected(flow_engine,case,body,attempt(flow_engine,identities,case,body))
    provision_notification(flow_engine,identities)
    if legacy_status!='PENDING':
        notify(flow_engine,identities,case,legacy_status,component=COMPONENT)
    original=snapshot(flow_engine)
    original_work=next(row for row in rows(flow_engine,life.work) if row['purpose']=='NOTIFICATION')
    migrate(flow_engine,NOTIFICATION)
    assert rows(flow_engine,controls)==[] and rows(flow_engine,facts)==[]
    migrated=snapshot(flow_engine)
    assert {name:value for name,value in original.items() if name!='alembic_version'}=={
        name:value for name,value in migrated.items()
        if name not in {'alembic_version',controls.name,facts.name}}
    provision(flow_engine,identities)
    before=snapshot(flow_engine)
    assert service(flow_engine,identities).send(original_work['work_id']).status=='HOLD'
    assert service(flow_engine,identities).reconcile(original_work['work_id']).status=='HOLD'
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError):
            LifecycleGuards(COMPONENT).claim(uow,original_work['work_id'],now())
        with pytest.raises(FlowError):uow.commit()
    assert snapshot(flow_engine)==before
    assert next(row for row in rows(flow_engine,life.work) if row['work_id']==original_work['work_id'])==original_work
    evidence(request.node.nodeid,legacy_status=legacy_status,
        synthetic_compatibility_only=legacy_status!='PENDING',original=original,migrated=migrated,
        before=before,after=snapshot(flow_engine))


def _legacy_message(uow, case_id, *, disposition='AVAILABLE'):
    """Explicit old compatibility row; never a claimed historical real sender."""
    head=uow.execute(select(old.case_heads).where(old.case_heads.c.case_id==case_id)).mappings().one()
    at=datetime.now(timezone.utc)
    body=dict(notification_id=identifier('old_notification'),outcome='REJECTED',
              message='Synthetic legacy customer message.',next_steps=[],sent_at=timestamp(at))
    record=dict(record_id=identifier('old_message'),case_id=case_id,kind='OUTCOME_MESSAGE',
        object_id=body['notification_id'],object_version=1,case_version=head['case_version'],
        recorded_sequence=head['history_sequence']+1,recorded_at=at,
        content_sha256=digest(body,'history/v1'),retention_state=disposition,
        removal_reason=None if disposition=='AVAILABLE' else 'RETENTION_POLICY')
    uow.execute(old.history.insert().values(**record))
    if disposition=='AVAILABLE':
        uow.execute(old.history_contents.insert().values(record_id=record['record_id'],body=encode_document(body)))
    uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case_id).values(
        history_sequence=record['recorded_sequence']))
    return record


def _legacy_read_oracle(identities,case,count):
    page=identities.flow().history(case,{'kind':'OUTCOME_MESSAGE'}).body
    assert len(page['items'])==count
    assert 'outcome_message' not in identities.flow().get_case(case).body
    return page['items']


@pytest.mark.parametrize('flow_engine',[ARTIFACT],indirect=True)
def test_legacy_customer_messages_and_tombstones_keep_original_reads_after_migration(
        flow_engine,identities,enabled,request):
    case=identities.flow().create({'original_message':'Synthetic legacy messages.'},
        'legacy-message-create','legacy_message_corr').body['case_id']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        original=[_legacy_message(uow,case,disposition=state) for state in ('AVAILABLE','DELETED','REDACTED')]
        uow.commit()
    old_items=_legacy_read_oracle(identities,case,3)
    original_rows=rows(flow_engine,old.history)
    original_contents=rows(flow_engine,old.history_contents)
    migrate(flow_engine,NOTIFICATION)
    assert rows(flow_engine,controls)==[] and rows(flow_engine,facts)==[]
    assert rows(flow_engine,old.history)==original_rows
    assert rows(flow_engine,old.history_contents)==original_contents
    assert _legacy_read_oracle(identities,case,3)==old_items
    assert rows(flow_engine,controls)==[] and rows(flow_engine,facts)==[]
    evidence(request.node.nodeid,synthetic_compatibility_only=True,legacy=original,
             old_items=old_items,migrated_items=_legacy_read_oracle(identities,case,3))


@pytest.mark.parametrize('insertion',['before_admission','after_admission'])
def test_legacy_customer_row_blocks_modern_admission_before_commit_and_sender(
        flow_engine,identities,enabled,request,monkeypatch,insertion):
    from returnops_domain import notification_intent as intent
    from returnops_domain import notification_customer_origin as customer_origin
    from returnops_domain.notification_mock import CoreMockNotification
    from notification_helpers import pdf_call_counts
    case,body=ready(flow_engine,identities)
    if insertion=='before_admission':
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            _legacy_message(uow,case)
            uow.commit()
    before=snapshot(flow_engine)
    observed={'initial_returned':False,'commit':False,'final_denial':False,'sender':0}
    actual_create=intent.create_control
    actual_check=customer_origin.forbid_existing_messages
    def checked(uow,case_id):
        try:
            return actual_check(uow,case_id)
        except FlowError:
            observed['final_denial']=observed['commit']
            raise
    def injected(*args,**kwargs):
        result=actual_create(*args,**kwargs)
        observed['initial_returned']=True
        if insertion=='after_admission':
            _legacy_message(args[0],case)
        return result
    class ObservedUow(CustomerUnitOfWork):
        def commit(self):
            observed['commit']=True
            return super().commit()
    def forbidden_send(*args,**kwargs):
        observed['sender']+=1
        pytest.fail('Blocked modern admission reached T2')
    monkeypatch.setattr(customer_origin,'forbid_existing_messages',checked)
    monkeypatch.setattr(intent,'create_control',injected)
    monkeypatch.setattr(CoreMockNotification,'deliver',forbidden_send)
    with pdf_call_counts() as calls:
        result=attempt(flow_engine,identities,case,body,uow_factory=ObservedUow)
    assert result.status=='DENIED' and not result.receipt
    assert observed['sender']==0 and not rows(flow_engine,controls) and not rows(flow_engine,facts)
    assert observed['initial_returned']==(insertion=='after_admission')
    if insertion=='after_admission':
        assert observed['final_denial']
    after=snapshot(flow_engine)
    for table in (old.history,old.history_contents,life.state,life.work,life.sources,life.events,life.effects):
        assert after[table.name]==before[table.name],table.name
    for old_head,new_head in zip(before[old.case_heads.name],after[old.case_heads.name],strict=True):
        assert {k:v for k,v in old_head.items() if k not in {'audit_head','audit_sequence'}}=={
            k:v for k,v in new_head.items() if k not in {'audit_head','audit_sequence'}}
    assert all(calls[name]==0 for name in ('render','text_line','assembly','expected_pdf',
                                          'return_provider','label_provider','artifact_retrieval'))
    _legacy_read_oracle(identities,case,int(insertion=='before_admission'))
    evidence(request.node.nodeid,insertion=insertion,observed=observed,before=before,after=after,
             actual_calls=calls,denial_audit_may_be_appended=True)
