"""G5/G9: real final-read expiry and authority, without assigned fake clocks."""
from dataclasses import asdict
from datetime import datetime
from time import monotonic,sleep
from uuid import uuid4
import jwt
import pytest
from sqlalchemy import select,text,update
from returnops_api.private_return_label_bridge import compose_private_return_label_bridge
from returnops_domain import customer_tables as old,lifecycle_tables as life
from returnops_domain import return_label_bridge as implementation
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.registry import TrustedRegistry
from returnops_domain.return_execution_sources import COMPONENT
from returnops_domain.return_execution_tables import permissions
from return_label_bridge_helpers import ready,service,accept,recover,rows,snapshot,evidence,no_provider,assert_accepted


def short_session(engine,identities,**options):
    with engine.connect() as connection:now=connection.execute(text('SELECT clock_timestamp()')).scalar_one()
    issued=int(now.timestamp());expires=issued+20;session_id='bridge_'+uuid4().hex
    principal=identities.people['founder']['principal_id'];config=identities.auth_config
    TrustedRegistry(engine).register_session(principal,session_id,issued,issued,expires)
    token=jwt.encode(dict(iss=config.issuer,aud=config.audience,sub=principal,jti=session_id,
        iat=issued,nbf=issued,exp=expires),config.signing_key,algorithm='HS256')
    return compose_private_return_label_bridge(engine,config,'Bearer '+token,**options),session_id,expires


@pytest.mark.parametrize('branch',['new_accept','replay','absent_recover'])
def test_RB_G5_actual_session_expiry_after_last_source_read(flow_engine,identities,enabled,request,monkeypatch,branch):
    arguments,_=ready(flow_engine,identities)
    if branch=='replay':assert accept(service(flow_engine,identities),arguments).status=='ACCEPTED'
    caller,session_id,expires=short_session(flow_engine,identities)
    before=snapshot(flow_engine);calls=no_provider(monkeypatch);original=implementation.closure;reads=[];boundary=[]
    def slow(uow,case_id):
        value=original(uow,case_id);reads.append(len(reads)+1)
        if len(reads)==5:
            first=uow.execute(text('SELECT clock_timestamp()')).scalar_one();assert first.timestamp()<expires
            started=monotonic()
            while True:
                at=uow.execute(text('SELECT clock_timestamp()')).scalar_one()
                if at.timestamp()>=expires:break
                assert monotonic()-started<22;sleep(.02)
            boundary.append(dict(first=first,expires=expires,actual_at=at))
        return value
    monkeypatch.setattr(implementation,'closure',slow)
    result=recover(caller,arguments) if branch=='absent_recover' else accept(caller,arguments)
    assert reads==[1,2,3,4,5] and len(boundary)==1
    assert result.status=='DENIED' and result.label_context is None and calls==[]
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,branch=branch,new_session=session_id,boundary=boundary,result=asdict(result),before=before,after=snapshot(flow_engine))


def test_RB_G5_actual_claim_lease_expires_after_last_source_read(flow_engine,identities,enabled,request,monkeypatch):
    arguments,_=ready(flow_engine,identities);before=snapshot(flow_engine)
    original=implementation.closure;reads=[];boundary=[];lease=[]
    class Observed(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            result=super().execute(statement,parameters)
            if getattr(statement,'is_update',False) and getattr(statement,'table',None) is life.work and not lease:
                current=super().execute(select(life.work).where(life.work.c.purpose=='EFFECT')).mappings().one()
                if current['state']=='RUNNING':lease.append(current['lease_expires_at'])
            return result
    def slow(uow,case_id):
        value=original(uow,case_id);reads.append(len(reads)+1)
        if len(reads)==5:
            assert len(lease)==1
            first=uow.execute(text('SELECT clock_timestamp()')).scalar_one();assert first<lease[0]
            started=monotonic()
            while True:
                at=uow.execute(text('SELECT clock_timestamp()')).scalar_one()
                if at>=lease[0]:break
                assert monotonic()-started<12;sleep(.02)
            boundary.append(dict(first=first,lease=lease[0],actual_at=at))
        return value
    monkeypatch.setattr(implementation,'closure',slow)
    result=accept(service(flow_engine,identities,uow_factory=Observed,lease_seconds=10),arguments)
    assert reads==[1,2,3,4,5] and len(boundary)==1
    assert result.status=='DENIED' and result.label_context is None and snapshot(flow_engine)==before
    evidence(request.node.nodeid,boundary=boundary,result=asdict(result),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('revocation',['session','effect','query'])
def test_RB_G5_current_registry_and_grants_reread_after_full_proof(flow_engine,identities,enabled,request,monkeypatch,revocation):
    arguments,_=ready(flow_engine,identities);before=snapshot(flow_engine);reads=[];original=implementation.closure
    def revoke_after_proof(uow,case_id):
        value=original(uow,case_id);reads.append(len(reads)+1)
        if len(reads)==4:
            statement=(update(old.sessions).where(old.sessions.c.session_id==identities.sessions['founder']['session_id']).values(revoked=True)
                if revocation=='session' else update(life.authorities).where(life.authorities.c.component_id==COMPONENT,
                    life.authorities.c.purpose=='EFFECT').values(enabled=False,revision=2)
                if revocation=='effect' else update(permissions).values(query_enabled=False,revision=2))
            assert uow.execute(statement).rowcount==1
        return value
    monkeypatch.setattr(implementation,'closure',revoke_after_proof)
    result=accept(service(flow_engine,identities),arguments)
    assert reads==[1,2,3,4] and result.status=='DENIED' and result.label_context is None
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,revocation=revocation,injection='same fenced transaction after full source proof',
        result=asdict(result),before=before,after=snapshot(flow_engine))


def test_RB_G9_natural_approval_expiry_retained_success_remains_acceptable_with_current_query(flow_engine,identities,enabled,request,monkeypatch):
    arguments,setup=ready(flow_engine,identities)
    expires=datetime.fromisoformat(setup['action']['scope']['expires_at'].replace('Z','+00:00'))
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert uow.execute(update(life.authorities).where(life.authorities.c.component_id==COMPONENT,
            life.authorities.c.purpose=='EXECUTION').values(enabled=False,revision=2)).rowcount==1
        assert uow.execute(update(permissions).values(create_enabled=False,revision=2)).rowcount==1;uow.commit()
    started=monotonic()
    while True:
        with flow_engine.connect() as connection:at=connection.execute(text('SELECT clock_timestamp()')).scalar_one()
        if at>=expires:break
        assert 0<(expires-at).total_seconds()<=301 and monotonic()-started<330
        sleep(min(1,(expires-at).total_seconds()))
    before=snapshot(flow_engine);calls=no_provider(monkeypatch)
    first=accept(service(flow_engine,identities),arguments);after=assert_accepted(flow_engine,arguments,first,before)
    replay=recover(service(flow_engine,identities),arguments)
    assert replay.status=='REPLAYED' and replay.event_id==first.event_id and calls==[] and snapshot(flow_engine)==after
    evidence(request.node.nodeid,actual_database_time=at,approval_expires_at=expires,expiry_was_not_rewritten=True,
        execution_and_create_disabled=True,result=asdict(first),replay=asdict(replay),before=before,after=after)
