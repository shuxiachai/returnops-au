"""EP G5..G9 late proofs and real fence ordering; cloud-only database tests."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import event, select, text, update
from returnops_domain import customer_tables as old, lifecycle_tables as life, storage
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown
from returnops_domain.execution_preparation_tables import preparations
from returnops_domain.lifecycle_state import invalidate
from returnops_domain.preview_profile import APPROVAL_COMPONENT
from returnops_domain.retention import RetentionService
from manual_helpers import evidence, rows, snapshot
from preparation_helpers import ready, service, recovered, unchanged, assert_delta
from test_founder_approve_late_postgresql import _overlap_at_actual_fence
from test_approval_admission_late_postgresql import _short_signed_session, _authentication_wall


@pytest.mark.parametrize('change',['source','head','sidecar','receipt','work','execution_grant','schema','expiry','backwards','uncertain'])
def test_EP_G7_final_staged_proof_followed_by_mutation_cannot_commit(flow_engine,identities,enabled,monkeypatch,request,change):
    from returnops_domain import execution_preparation as implementation
    arguments,setup=ready(flow_engine,identities); initial=datetime.now(timezone.utc); wall=[initial]
    expiry=datetime.fromisoformat(setup['action']['scope']['expires_at'].replace('Z','+00:00'))
    original=implementation.current_staged; calls=[]
    def fault(reads,*args):
        value=original(reads,*args); calls.append(len(calls)+1)
        if len(calls)==2:
            if change=='expiry': wall[0]=expiry
            elif change=='backwards': wall[0]=initial-timedelta(microseconds=1)
            elif change=='uncertain': raise AcceptanceOutcomeUnknown()
            else:
                if change=='source':
                    ids=select(storage.original_statement_records.c.statement_id).where(storage.original_statement_records.c.case_id==setup['case'])
                    statement=update(storage.original_statement_contents).where(storage.original_statement_contents.c.statement_id.in_(ids)).values(raw_text=b'late changed source')
                elif change=='head': statement=update(old.case_heads).where(old.case_heads.c.case_id==setup['case']).values(updated_at=initial)
                elif change=='sidecar': statement=update(preparations).where(preparations.c.case_id==setup['case']).values(binding_hash='0'*64)
                elif change=='receipt':
                    ids=select(old.acceptances.c.acceptance_id).where(old.acceptances.c.target==setup['case'],old.acceptances.c.operation=='recordFounderDecision')
                    statement=update(old.receipts).where(old.receipts.c.acceptance_id.in_(ids)).values(body=None,available=False)
                elif change=='work': statement=update(life.work).where(life.work.c.work_id==arguments['execution_work_id']).values(epoch=1)
                elif change=='execution_grant': statement=update(life.authorities).where(life.authorities.c.purpose=='EXECUTION').values(revision=2)
                else: statement=text("UPDATE alembic_version SET version_num='corrupt_preparation_schema'")
                assert reads._uow.execute(statement).rowcount==1
        return value
    monkeypatch.setattr(implementation,'current_staged',fault)
    result=unchanged(flow_engine,service(flow_engine,identities,clock=lambda:wall[0]),arguments,
        'UNKNOWN' if change=='uncertain' else 'DENIED')
    assert calls==[1,2]
    evidence(request.node.nodeid,change=change,proof_calls=calls,result=asdict(result))


@pytest.mark.parametrize('change',['session_expiry','revocation','replacement_dates'])
def test_EP_G7_last_real_f03_is_final_io_and_strict_session_boundary(flow_engine,identities,enabled,monkeypatch,request,change):
    from dataclasses import replace
    from returnops_api.private_execution_preparation import compose_private_execution_preparation
    deadline=_short_signed_session(flow_engine,identities)
    arguments,_=ready(flow_engine,identities)
    wall=[datetime.now(timezone.utc)]; _authentication_wall(monkeypatch,wall)
    config=replace(identities.auth_config,leeway_seconds=5)
    caller=compose_private_execution_preparation(flow_engine,config,'Bearer '+identities.tokens['founder'],clock=lambda:wall[0])
    authority=caller.authority; calls=[]; last=[]; later=[]
    def current(connection,operation,resource=None):
        if operation=='getSession':
            calls.append(len(calls)+1)
            if len(calls)==3:
                if change=='session_expiry': wall[0]=deadline
                else:
                    values={'revoked':True} if change=='revocation' else {'issued_at':identities.sessions['founder']['issued_at']-1}
                    assert connection.execute(update(old.sessions).where(old.sessions.c.session_id==identities.sessions['founder']['session_id']).values(**values)).rowcount==1
        result=authority(connection,operation,resource)
        if operation=='getSession' and len(calls)==3: last.append(True)
        return result
    def observe(*args):
        if last: later.append('SQL-after-final-session')
    caller.authority=current
    before=snapshot(flow_engine); event.listen(flow_engine,'before_cursor_execute',observe)
    try: result=caller.prepare(**arguments)
    finally: event.remove(flow_engine,'before_cursor_execute',observe)
    assert result.status=='DENIED' and snapshot(flow_engine)==before
    assert calls==[1,2,3] and not later
    if change=='session_expiry': assert last==[True]
    evidence(request.node.nodeid,change=change,result=asdict(result),session_calls=calls,last_returned=last,no_later_sql=not later)


def test_EP_G5_current_grant_replay_and_invalidation_never_restore_pending(flow_engine,identities,enabled,request):
    arguments,_=ready(flow_engine,identities); caller=service(flow_engine,identities)
    first=caller.prepare(**arguments); assert first.status=='PREPARED'
    original,=rows(flow_engine,preparations)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        # Original supported fence and invalidation helper, no fixture claim.
        head=uow.execute(select(old.case_heads).where(old.case_heads.c.case_id==arguments['case_id'])).mappings().one()
        invalidate(uow,head); uow.commit()
    after=snapshot(flow_engine); invalidated,=rows(flow_engine,preparations)
    assert invalidated=={**original,'state':'SUPERSEDED'}
    replay=caller.prepare(**arguments)
    assert replay.status=='REPLAYED' and replay.state=='SUPERSEDED'
    assert snapshot(flow_engine)==after and replay.created_at==first.created_at
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert uow.execute(update(life.authorities).where(life.authorities.c.component_id==APPROVAL_COMPONENT,
            life.authorities.c.purpose=='EXECUTION').values(enabled=False,revision=2)).rowcount==1
        uow.commit()
    unchanged(flow_engine,caller,arguments)
    evidence(request.node.nodeid,original=original,invalidated=invalidated,replayed=asdict(replay),after=after)


def test_EP_G5_actual_retention_erases_bodies_and_pauses_identity_without_reconstruction(flow_engine,identities,enabled,request):
    arguments,_=ready(flow_engine,identities); caller=service(flow_engine,identities)
    first=caller.prepare(**arguments); assert first.status=='PREPARED'
    original,=rows(flow_engine,preparations)
    statement,=[r for r in rows(flow_engine,old.history) if r['case_id']==arguments['case_id'] and r['kind']=='STATEMENT']
    assert RetentionService(flow_engine).remove('STATEMENT',statement['object_id']) is True
    saved,=rows(flow_engine,preparations); assert saved=={**original,'state':'PAUSED'}
    assert not [r for r in rows(flow_engine,old.history_contents) if r['record_id']==first.first_operation_record_id]
    after=snapshot(flow_engine); unchanged(flow_engine,caller,arguments)
    assert recovered(caller,arguments).status=='UNKNOWN' and snapshot(flow_engine)==after
    evidence(request.node.nodeid,original=original,paused=saved,after=after)


@pytest.mark.parametrize('first',['prepare','mutation'])
@pytest.mark.parametrize('mutation',['retention','revocation'])
def test_EP_G7_G9_actual_fence_orders_supported_preparation_and_mutation(flow_engine,identities,enabled,monkeypatch,request,first,mutation):
    arguments,_=ready(flow_engine,identities); caller=service(flow_engine,identities)
    statement,=[r for r in rows(flow_engine,old.history) if r['case_id']==arguments['case_id'] and r['kind']=='STATEMENT']
    def mutate():
        if mutation=='retention': return RetentionService(flow_engine).remove('STATEMENT',statement['object_id'])
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            assert uow.execute(update(life.authorities).where(life.authorities.c.purpose=='EXECUTION').values(enabled=False,revision=2)).rowcount==1
            uow.commit()
        return True
    before=snapshot(flow_engine)
    results,overlap=_overlap_at_actual_fence(flow_engine,monkeypatch,
        dict(prepare=lambda:caller.prepare(**arguments),mutation=mutate),first=first)
    assert results['mutation'] is True
    assert results['prepare'].status==('PREPARED' if first=='prepare' else 'DENIED')
    saved=rows(flow_engine,preparations)
    assert len(saved)==(1 if first=='prepare' else 0)
    if saved: assert saved[0]['state']==('PAUSED' if mutation=='retention' else 'PENDING')
    assert rows(flow_engine,life.effects)==[]
    unchanged(flow_engine,caller,arguments)
    evidence(request.node.nodeid,first=first,mutation=mutation,before=before,after=snapshot(flow_engine),
        overlap=overlap,prepare=asdict(results['prepare']))
