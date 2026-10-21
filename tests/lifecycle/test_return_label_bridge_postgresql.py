"""Real PostgreSQL bridge groups G1-G6/G8/G10; synthetic upstream input is explicit."""
from copy import deepcopy
from dataclasses import asdict
import pytest
from sqlalchemy import delete, select, text, update
from returnops_domain import customer_tables as old, investigation_tables as inv, lifecycle_tables as life, storage
from returnops_domain import return_label_bridge as implementation
from returnops_domain import return_label_sources as source_reader
from returnops_domain.audit import append_event, identifier, timestamp, verify_chain
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.execution_preparation_tables import preparations
from returnops_domain.lifecycle_events import EffectObserved
from returnops_domain.lifecycle_guards import LifecycleGuards
from returnops_domain.lifecycle_sources import Sources
from returnops_domain.preview_tables import previews
from returnops_domain.registry import TrustedRegistry
from returnops_domain.retention import RetentionService
from returnops_domain.return_execution_history import append_operation
from returnops_domain.return_execution_sources import COMPONENT
from returnops_domain.return_execution_tables import controls, permissions, ledger
from returnops_domain.wire import validate
from return_label_bridge_helpers import (ready, service, accept, recover, accepted_rows,
    no_provider, assert_accepted, control, rows, snapshot, evidence)


def test_RB_G1_actual_source_acceptance_exact_delta_and_private_context(flow_engine, identities, enabled, request, monkeypatch):
    arguments, setup = ready(flow_engine, identities)
    before = snapshot(flow_engine); calls = no_provider(monkeypatch)
    result = accept(service(flow_engine, identities), arguments)
    after = assert_accepted(flow_engine, arguments, result, before)
    validate('GenerateLabelCommand', result.label_context['label_command'])
    assert calls == [] and len(rows(flow_engine, ledger)) == 1
    assert sum(row['kind']=='OPERATION' for row in rows(flow_engine, old.history)) == 3
    evidence(request.node.nodeid, result=asdict(result), before=before, after=after,
        upstream='real current production N1/N2 paths with controlled synthetic customer/proposal/review input',
        new_provider_calls=0, label_operation_artifact_outcome_notification_effects=0)


def test_RB_G1_G9_replay_recover_readonly_and_original_expected_version(flow_engine, identities, enabled, request, monkeypatch):
    arguments, _ = ready(flow_engine, identities); before = snapshot(flow_engine)
    absent = recover(service(flow_engine, identities), arguments)
    assert absent.status == 'UNKNOWN' and absent.label_context is None and snapshot(flow_engine) == before
    first = accept(service(flow_engine, identities), arguments)
    after = assert_accepted(flow_engine, arguments, first, before)
    calls = no_provider(monkeypatch)
    replay_arguments = {**arguments, 'correlation_id':'another-return-source-correlation'}
    replay = accept(service(flow_engine, identities), replay_arguments)
    recovered = recover(service(flow_engine, identities), replay_arguments)
    assert replay.status == recovered.status == 'REPLAYED'
    assert replay.event_id == recovered.event_id == first.event_id
    assert replay.label_context == recovered.label_context == first.label_context
    wrong = accept(service(flow_engine, identities), {**arguments,'expected_case_version':arguments['expected_case_version']+1})
    assert wrong.status == 'DENIED' and wrong.label_context is None
    assert snapshot(flow_engine) == after and calls == []
    first.label_context['label_command']['parameters']['parcel_id'] = 'changed-local-result'
    assert recover(service(flow_engine, identities), arguments).label_context == recovered.label_context
    assert snapshot(flow_engine) == after
    evidence(request.node.nodeid, absent=asdict(absent), replay=asdict(replay), recovered=asdict(recovered),
        wrong_expected=asdict(wrong), before=before, after=after, provider_calls=0)


@pytest.mark.parametrize('fault', ['proposal_body','review_body','approval_body','decision_body',
    'preview_body','original_statement','order_projection','order_receipt','approval_receipt','approval_refs','approval_acceptance'])
def test_RB_G2_real_retained_source_categories_reject(flow_engine, identities, enabled, request, fault):
    arguments, _ = ready(flow_engine, identities)
    current = control(flow_engine)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        if fault in {'proposal_body','review_body','approval_body','decision_body'}:
            kind = fault.split('_')[0].upper()
            record = uow.execute(select(old.history).where(old.history.c.kind == kind)).mappings().one()
            assert uow.execute(delete(old.history_contents).where(old.history_contents.c.record_id == record['record_id'])).rowcount == 1
        elif fault == 'preview_body':
            assert uow.execute(update(previews).values(body=None, available=False, removal_reason='OWNER_REQUEST')).rowcount == 1
        elif fault == 'original_statement':
            assert uow.execute(update(storage.original_statement_contents).values(raw_text=b'changed underlying retained customer source')).rowcount == 1
        elif fault == 'order_projection':
            assert uow.execute(update(inv.projection_contents).values(body=b'changed actual order projection')).rowcount >= 1
        elif fault == 'order_receipt':
            assert uow.execute(update(inv.receipt_contents).values(body=b'changed actual order receipt')).rowcount >= 1
        elif fault == 'approval_receipt':
            assert uow.execute(update(old.receipts).where(old.receipts.c.acceptance_id == current['approval_acceptance_id'])
                .values(body=None,available=False)).rowcount == 1
        elif fault == 'approval_refs':
            assert uow.execute(delete(old.receipt_refs).where(old.receipt_refs.c.acceptance_id == current['approval_acceptance_id'],
                old.receipt_refs.c.kind == 'CASE')).rowcount == 1
        else:
            assert uow.execute(update(old.acceptances).where(old.acceptances.c.acceptance_id == current['approval_acceptance_id'])
                .values(fingerprint='0'*64)).rowcount == 1
        uow.commit()
    before = snapshot(flow_engine); result = accept(service(flow_engine, identities), arguments)
    assert result.status in {'DENIED','UNKNOWN'} and result.label_context is None
    assert snapshot(flow_engine) == before and accepted_rows(flow_engine) == []
    evidence(request.node.nodeid, fault=fault, result=asdict(result), before=before, after=snapshot(flow_engine))


@pytest.mark.parametrize('fault', ['extra_operation','missing_operation_body','missing_v1','missing_origin','extra_origin','wrong_n2_producer',
    'control_binding','control_command','ledger_fact','ledger_result','effect_identity','effect_dispatch','orphan_work'])
def test_RB_G3_exact_modern_origin_control_ledger_result_effect_closure(flow_engine, identities, enabled, request, fault):
    arguments, _ = ready(flow_engine, identities); current = control(flow_engine)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        if fault == 'extra_operation':
            head = dict(uow.execute(select(old.case_heads)).mappings().one())
            source = Sources(uow, head, COMPONENT)
            _, body = source.read(current['result_record_id'], {'OPERATION'}, current_actor=False)
            now = uow.execute(text('SELECT clock_timestamp()')).scalar_one()
            body = {**body, 'updated_at':timestamp(now)}
            append_operation(uow, head, identifier('extra_operation'), body, 4,
                {'synthetic_extra_revision':True}, identifier('extra_corr'), now)
        elif fault == 'missing_operation_body':
            assert uow.execute(delete(old.history_contents).where(old.history_contents.c.record_id == current['result_record_id'])).rowcount == 1
        elif fault == 'missing_v1':
            # Preserve all foreign-key relationships while removing the required
            # v1 position from the actual OPERATION inventory.
            assert uow.execute(update(old.history).where(old.history.c.record_id==current['first_record_id'])
                .values(object_version=4)).rowcount==1
        elif fault == 'extra_origin':
            record=uow.execute(select(old.history).where(old.history.c.record_id==current['result_record_id'])).mappings().one()
            append_event(uow,arguments['case_id'],actor={'kind':'SERVICE','component_id':COMPONENT},
                event_type='OPERATION_REVISION_RECORDED',correlation_id=identifier('duplicate_origin'),
                payload={'synthetic_duplicate_origin':True},object_ids=[record['object_id']],
                history_refs=[{name:record[name] for name in ('record_id','kind','object_id','object_version')}],now=record['recorded_at'])
        elif fault in {'wrong_n2_producer','missing_origin'}:
            from returnops_domain.canonical import decode_document, encode_document, digest
            records = list(uow.execute(select(old.audit).order_by(old.audit.c.sequence)).mappings())
            previous = None
            for row in records:
                event = decode_document(row['body'])
                event.pop('event_hash'); event.pop('previous_event_hash', None)
                if event['event_id'] == current['result_audit_id']:
                    if fault=='wrong_n2_producer':event['actor'] = {'kind':'SERVICE','component_id':'wrong-modern-producer'}
                    else:event['history_refs']=[]
                if previous is not None: event['previous_event_hash'] = previous
                event['event_hash'] = digest({'sequence':row['sequence'],'event':event},'audit/v1')
                assert uow.execute(update(old.audit).where(old.audit.c.event_id == row['event_id']).values(
                    body=encode_document(event),event_hash=event['event_hash'])).rowcount == 1
                previous = event['event_hash']
            assert uow.execute(update(old.case_heads).values(audit_head=previous)).rowcount == 1
        elif fault == 'control_binding':
            assert uow.execute(update(controls).values(binding_hash='0'*64)).rowcount == 1
        elif fault == 'control_command':
            assert uow.execute(update(controls).values(command_id='foreign-command')).rowcount == 1
        elif fault == 'ledger_fact':
            assert uow.execute(update(ledger).values(fact_hash='0'*64)).rowcount == 1
        elif fault == 'ledger_result':
            assert uow.execute(update(ledger).values(provider_return_id='foreign-provider-return')).rowcount == 1
        elif fault == 'effect_identity':
            assert uow.execute(update(life.effects).values(identity_hash='0'*64)).rowcount == 1
        elif fault == 'effect_dispatch':
            assert uow.execute(update(life.effects).values(dispatch_source_record_id=current['first_record_id'])).rowcount == 1
        else:
            head = dict(uow.execute(select(old.case_heads)).mappings().one())
            state = dict(uow.execute(select(life.state)).mappings().one())
            uow.execute(life.work.insert().values(work_id='orphan-return-source-work',case_id=head['case_id'],component_id=COMPONENT,
                store_id=head['store_id'],owner_id=head['owner_principal_id'],purpose='EFFECT',input_version=head['input_version'],
                generation=state['generation'],target_hash='0'*64,target_record_id=current['result_record_id'],state='PENDING',
                claim_id=None,epoch=0,claimed_case_version=None,authority_revision=None,idempotency_key='orphan-return-source-key',
                lease_expires_at=None,created_at=uow.execute(text('SELECT clock_timestamp()')).scalar_one()))
        assert verify_chain(uow,arguments['case_id']) is True
        uow.commit()
    before = snapshot(flow_engine); result = accept(service(flow_engine, identities), arguments)
    assert result.status in {'DENIED','UNKNOWN'} and result.label_context is None
    assert snapshot(flow_engine) == before and accepted_rows(flow_engine) == []
    evidence(request.node.nodeid, fault=fault, actual_source_corruption=True, result=asdict(result), before=before, after=snapshot(flow_engine))


@pytest.mark.parametrize('fault', ['no_session','customer','wrong_key','wrong_version','revoked_session','owner_disabled',
    'changed_owner','changed_store','effect_revoked','query_revoked','provider_config'])
def test_RB_G4_current_identity_authority_query_and_key_fail_closed(flow_engine, identities, enabled, request, fault):
    arguments, _ = ready(flow_engine, identities)
    name = None if fault == 'no_session' else 'customer_a' if fault == 'customer' else 'founder'
    if fault == 'wrong_key': arguments['original_approval_key']='replacement-original-key'
    elif fault == 'wrong_version': arguments['expected_case_version']+=1
    elif fault == 'revoked_session': TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    elif fault == 'owner_disabled': TrustedRegistry(flow_engine).change_principal(identities.people['customer_a']['principal_id'],enabled=False)
    elif fault in {'changed_owner','changed_store','effect_revoked','query_revoked','provider_config'}:
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            if fault == 'changed_owner':
                statement=update(old.case_heads).values(owner_principal_id=identities.people['customer_b']['principal_id'])
            elif fault == 'changed_store':
                statement=update(old.case_heads).values(store_id='foreign-store')
            elif fault == 'effect_revoked':
                statement=update(life.authorities).where(life.authorities.c.component_id==COMPONENT,life.authorities.c.purpose=='EFFECT').values(enabled=False,revision=2)
            else:
                statement=update(permissions).values(**({'query_enabled':False,'revision':2} if fault=='query_revoked' else {'config_hash':'0'*64}))
            assert uow.execute(statement).rowcount==1;uow.commit()
    before=snapshot(flow_engine);result=accept(service(flow_engine,identities,name),arguments)
    assert result.status=='DENIED' and result.label_context is None and snapshot(flow_engine)==before
    assert accepted_rows(flow_engine)==[]
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))


def test_RB_G4_G9_create_permission_not_needed_and_reenabled_revision_is_independent(flow_engine,identities,enabled,request):
    arguments,_=ready(flow_engine,identities)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert uow.execute(update(life.authorities).where(life.authorities.c.component_id==COMPONENT,life.authorities.c.purpose=='EXECUTION').values(enabled=False,revision=2)).rowcount==1
        assert uow.execute(update(permissions).values(create_enabled=False,revision=2)).rowcount==1
        uow.commit()
    first=accept(service(flow_engine,identities),arguments)
    assert first.status=='ACCEPTED',asdict(first)
    receipt,=accepted_rows(flow_engine)
    work=next(row for row in rows(flow_engine,life.work) if row['work_id']==receipt['work_id'])
    original_revision=work['authority_revision']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(life.authorities).where(life.authorities.c.component_id==COMPONENT,life.authorities.c.purpose=='EFFECT').values(enabled=False,revision=original_revision+1))
        uow.commit()
    before=snapshot(flow_engine);denied=recover(service(flow_engine,identities),arguments)
    assert denied.status=='DENIED' and denied.label_context is None and snapshot(flow_engine)==before
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(life.authorities).where(life.authorities.c.component_id==COMPONENT,life.authorities.c.purpose=='EFFECT').values(enabled=True,revision=original_revision+2))
        uow.execute(update(permissions).values(query_enabled=True,revision=3));uow.commit()
    before=snapshot(flow_engine);replay=recover(service(flow_engine,identities),arguments)
    assert replay.status=='REPLAYED' and replay.event_id==first.event_id and snapshot(flow_engine)==before
    assert next(row for row in rows(flow_engine,life.work) if row['work_id']==receipt['work_id'])['authority_revision']==original_revision
    evidence(request.node.nodeid,first=asdict(first),denied=asdict(denied),replay=asdict(replay),
        saved_revision=original_revision,current_revision=original_revision+2,after=before)


@pytest.mark.parametrize('point',range(1,9))
def test_RB_G8_each_bridge_write_rolls_back_without_touching_return(flow_engine,identities,enabled,request,point):
    arguments,_=ready(flow_engine,identities);before=snapshot(flow_engine);writes=[];commit_attempts=[]
    expected_writes=[life.work.name,life.work.name,life.sources.name,life.events.name,
        old.case_heads.name,old.audit.name,old.case_heads.name,life.work.name]
    class Fault(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                writes.append(statement.table.name)
                if len(writes)==point:
                    # Match CustomerUnitOfWork.execute's actual SQLAlchemyError
                    # wrapper; commit-ACK uncertainty is tested separately.
                    self.poison();raise FlowError('INTERNAL_ERROR')
            return super().execute(statement,parameters)
        def commit(self):
            commit_attempts.append('commit');return super().commit()
    result=accept(service(flow_engine,identities,uow_factory=Fault),arguments)
    assert result.status=='UNKNOWN' and result.safe_code=='INTERNAL_ERROR' and result.label_context is None
    assert len(writes)==point and writes==expected_writes[:point] and commit_attempts==[]
    assert snapshot(flow_engine)==before and len(rows(flow_engine,ledger))==1
    recovered=recover(service(flow_engine,identities),arguments)
    assert recovered.status=='UNKNOWN' and recovered.label_context is None and snapshot(flow_engine)==before
    evidence(request.node.nodeid,write_point=point,writes=writes,commit_attempts=commit_attempts,
        injected_contract='CustomerUnitOfWork.execute SQLAlchemyError wrapper: poison plus FlowError(INTERNAL_ERROR)',
        result=asdict(result),recovered=asdict(recovered),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('fault',['uncommitted','committed_ack_lost','close_after_commit'])
def test_RB_G8_real_commit_and_close_uncertainty_recovery_is_readonly(flow_engine,identities,enabled,request,fault):
    arguments,_=ready(flow_engine,identities);before=snapshot(flow_engine);commits=[]
    class Fault(CustomerUnitOfWork):
        def commit(self):
            commits.append('attempt')
            if fault=='uncommitted':
                self.poison();raise AcceptanceOutcomeUnknown()
            super().commit();commits.append('actual_commit_returned')
            if fault=='committed_ack_lost':raise AcceptanceOutcomeUnknown()
        def __exit__(self,*args):
            answer=super().__exit__(*args)
            if fault=='close_after_commit':raise AcceptanceOutcomeUnknown()
            return answer
    result=accept(service(flow_engine,identities,uow_factory=Fault),arguments)
    assert result.status=='UNKNOWN' and result.label_context is None
    after=snapshot(flow_engine)
    assert len(accepted_rows(flow_engine))==(0 if fault=='uncommitted' else 1)
    if fault=='uncommitted':assert after==before
    recovered=recover(service(flow_engine,identities),arguments)
    assert recovered.status==('UNKNOWN' if fault=='uncommitted' else 'REPLAYED')
    assert (recovered.label_context is None)==(fault=='uncommitted')
    assert snapshot(flow_engine)==after
    evidence(request.node.nodeid,fault=fault,commits=commits,result=asdict(result),recovered=asdict(recovered),
        before=before,actual_after_unknown=after,after_recovery=snapshot(flow_engine))


@pytest.mark.parametrize('fault',['claim','epoch','binding','receipt','original_source','control'])
def test_RB_G6_final_seal_rejects_staged_and_original_tampering(flow_engine,identities,enabled,request,fault):
    arguments,_=ready(flow_engine,identities);before=snapshot(flow_engine);injected=[]
    class Fault(CustomerUnitOfWork):
        def before_commit(self,check):
            if not injected:
                injected.append(fault)
                work=self.execute(select(life.work).where(life.work.c.purpose=='EFFECT')).mappings().one()
                if fault=='claim':statement=update(life.work).where(life.work.c.work_id==work['work_id']).values(claim_id='changed-claim')
                elif fault=='epoch':statement=update(life.work).where(life.work.c.work_id==work['work_id']).values(epoch=2)
                elif fault=='binding':statement=update(life.sources).where(life.sources.c.work_id==work['work_id']).values(source_hash='0'*64)
                elif fault=='receipt':statement=update(life.events).where(life.events.c.work_id==work['work_id']).values(fingerprint='0'*64)
                elif fault=='original_source':statement=update(storage.original_statement_contents).values(raw_text=b'late source change')
                else:statement=update(controls).values(binding_hash='0'*64)
                assert self.execute(statement).rowcount==1
            return super().before_commit(check)
    result=accept(service(flow_engine,identities,uow_factory=Fault),arguments)
    assert injected==[fault] and result.status=='DENIED' and result.label_context is None
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,injection='inside real fenced transaction before final guard',
        result=asdict(result),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('when',['before_bridge','after_bridge'])
def test_RB_G10_actual_retention_denies_context_and_keeps_existing_receipt(flow_engine,identities,enabled,request,when):
    from create_return_execution_helpers import reconcile,service as n2_service
    arguments,setup=ready(flow_engine,identities)
    first=None
    if when=='after_bridge':
        first=accept(service(flow_engine,identities),arguments);assert first.status=='ACCEPTED',asdict(first)
    original=next(row for row in rows(flow_engine,old.history) if row['kind']=='STATEMENT')
    assert RetentionService(flow_engine).remove('STATEMENT',original['object_id']) is True
    before=snapshot(flow_engine)
    result=recover(service(flow_engine,identities),arguments)
    assert result.status in {'DENIED','UNKNOWN'} and result.label_context is None
    assert snapshot(flow_engine)==before and len(accepted_rows(flow_engine))==(when=='after_bridge')
    late=reconcile(n2_service(flow_engine,identities),setup['upstream'])
    assert late.status in {'REPLAYED','FACT_REPLAYED'} and snapshot(flow_engine)==before
    evidence(request.node.nodeid,when=when,first=None if first is None else asdict(first),
        denied_context=asdict(result),old_n2_late_query=asdict(late),before=before,after=snapshot(flow_engine))


def test_RB_G10_new_receipt_cannot_be_reinterpreted_as_generic_effect(flow_engine,identities,enabled,request):
    from returnops_domain.lifecycle_events import LifecycleClaim
    arguments,_=ready(flow_engine,identities)
    first=accept(service(flow_engine,identities),arguments);assert first.status=='ACCEPTED',asdict(first)
    receipt,=accepted_rows(flow_engine)
    work=next(row for row in rows(flow_engine,life.work) if row['work_id']==receipt['work_id'])
    claim=LifecycleClaim(work['work_id'],work['claim_id'],work['epoch'],work['claimed_case_version'],
        work['input_version'],work['generation'],work['authority_revision'])
    event=EffectObserved(receipt['event_id'],claim,receipt['record_id'])
    before=snapshot(flow_engine)
    from returnops_domain.errors import FlowError
    with pytest.raises(FlowError):
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            LifecycleGuards(COMPONENT).apply(uow,event,uow.execute(text('SELECT clock_timestamp()')).scalar_one())
            uow.commit()
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,rejected_generic_effect=True,before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('when',['before_bridge','after_bridge'])
def test_RB_G10_protected_terminal_fixture_is_not_reopened(flow_engine,identities,enabled,request,when):
    arguments,_=ready(flow_engine,identities)
    if when=='after_bridge':assert accept(service(flow_engine,identities),arguments).status=='ACCEPTED'
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        # Explicit test-only protective metadata, not a claimed real manual
        # acceptance or a HUMAN event after the current approved return path.
        assert uow.execute(update(old.case_heads).values(status='MANUAL_HANDLED')).rowcount==1
        assert uow.execute(update(life.state).values(outcome='MANUAL_HANDLED')).rowcount==1;uow.commit()
    before=snapshot(flow_engine);result=recover(service(flow_engine,identities),arguments)
    assert result.status in {'DENIED','UNKNOWN'} and result.label_context is None and snapshot(flow_engine)==before
    assert len(accepted_rows(flow_engine))==(when=='after_bridge')
    evidence(request.node.nodeid,fixture_origin='TEST_ONLY_SYNTHETIC_PROTECTIVE_TERMINAL_METADATA',
        when=when,result=asdict(result),before=before,after=snapshot(flow_engine))


def test_RB_G11_default_app_has_no_bridge_route_or_automatic_acceptance(flow_engine,identities,enabled,request):
    from returnops_api.main import create_app
    arguments,_=ready(flow_engine,identities);before=snapshot(flow_engine)
    app=create_app(engine=flow_engine,auth_config=identities.auth_config)
    route_modules=[getattr(getattr(route,'endpoint',None),'__module__','') for route in app.routes]
    assert not any('return_label_bridge' in name for name in route_modules)
    assert not any('return-source' in route.path or 'label-bridge' in route.path for route in app.routes)
    assert accepted_rows(flow_engine)==[] and snapshot(flow_engine)==before
    evidence(request.node.nodeid,default_routes=[route.path for route in app.routes],endpoint_modules=route_modules,
        no_default_acceptance=True,before=before,after=snapshot(flow_engine))

