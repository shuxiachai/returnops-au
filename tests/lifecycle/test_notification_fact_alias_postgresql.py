"""Explicit hostile independent-fact aliases must stop send/query/acceptance."""
from datetime import timedelta
import pytest
from returnops_domain.canonical import decode_document,encode_document,digest
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.notification_mock import CoreMockNotification,fact_payload
from returnops_domain.notification_tables import controls,facts
from notification_helpers import ready,service,rows,snapshot,evidence
from test_notification_delivery_postgresql import NoSend,LostReply


def _foreign(control,alias=None):
    core=decode_document(control['reservation_core'])
    replacements=dict(notification_work_id='foreign_notification_work',notification_id='foreign_notification',
        logical_key='foreign_notification_key',intent_hash='b'*64,reservation_id='foreign_notification_reservation')
    if alias is not None:
        replacements[alias]=control[alias]
    core={**core,**replacements}
    value={name:control[name] for name in ('notification_work_id','notification_id','case_id','store_id','owner_id',
        'logical_key','outcome','profile','channel','profile_hash','payload_hash','intent_hash')}
    value.update(replacements)
    value.update(fact_id='n_fact_'+digest({'reservation_id':core['reservation_id']},'core-mock-notification-id/v1'),
        reservation_hash=digest(core,'notification-reservation/v2'),reservation_core=encode_document(core),
        attempt_count=control['attempt_count'],status='SENT',success_work_id=value['notification_work_id'],
        accepted_at=control['reservation_at']+timedelta(microseconds=1),fact_hash='0'*64)
    value['fact_hash']=digest(fact_payload(value),'core-mock-notification-fact/v1')
    return value


@pytest.mark.parametrize('alias',['notification_id','logical_key','intent_hash'])
@pytest.mark.parametrize('phase',['before_t2','before_t3'])
def test_logically_linked_foreign_work_fact_denies_every_sending_and_acceptance_path(
        flow_engine,identities,enabled,request,alias,phase):
    setup=ready(flow_engine,identities)
    mock=NoSend(flow_engine) if phase=='before_t2' else LostReply(flow_engine)
    assert service(flow_engine,identities,mock=mock).send(setup['work_id']).status=='UNKNOWN'
    control=rows(flow_engine,controls)[0]
    inserted=_foreign(control,alias)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(facts.insert().values(**inserted));uow.commit()
    before=snapshot(flow_engine);calls=[]
    class ForbiddenInsert(CoreMockNotification):
        def _insert(self,*args):
            calls.append(True);pytest.fail('Aliased ledger was ignored before sending')
    adapter=ForbiddenInsert(flow_engine)
    assert adapter.query(control['reservation_id']) is None
    assert adapter.deliver(control['reservation_id']) is None
    assert service(flow_engine,identities,mock=adapter).reconcile(setup['work_id']).status=='UNKNOWN'
    assert not calls and snapshot(flow_engine)==before
    evidence(request.node.nodeid,phase=phase,alias=alias,synthetic_hostile_fact=True,
        before=before,after=snapshot(flow_engine))


def test_unrelated_fact_is_not_a_global_notification_denial(flow_engine,identities,enabled,request):
    setup=ready(flow_engine,identities)
    assert service(flow_engine,identities,mock=NoSend(flow_engine)).send(setup['work_id']).status=='UNKNOWN'
    control=rows(flow_engine,controls)[0]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(facts.insert().values(**_foreign(control)));uow.commit()
    delivered=CoreMockNotification(flow_engine).deliver(control['reservation_id'])
    assert delivered is not None and delivered['notification_work_id']==setup['work_id']
    assert service(flow_engine,identities).reconcile(setup['work_id']).status=='SENT'
    assert len(rows(flow_engine,facts))==2
    evidence(request.node.nodeid,synthetic_unrelated_fact=True,facts=rows(flow_engine,facts))
