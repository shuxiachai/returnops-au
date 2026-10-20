"""Legacy v1 remains readable/HOLD; migration never invents a sending fact.

PENDING comes from the actual old rejection producer. FAILED/SENT below are
explicit synthetic old guard fixtures, not historical production deliveries.
"""
import pytest
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
