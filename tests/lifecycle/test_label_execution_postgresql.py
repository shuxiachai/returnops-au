"""N3 G1–G5/G8/G10 actual service/storage acceptance; no collection-as-proof."""
from copy import deepcopy
from dataclasses import asdict
import pytest
from sqlalchemy import inspect,select,text,update,delete
from returnops_domain import customer_tables as old,lifecycle_tables as life,storage,founder_codec as finite
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown,FlowError
from returnops_domain.core_label_mock import CoreLabelMock
from returnops_domain.label_execution_tables import metadata,controls,permissions,ledger,artifact_work
from returnops_domain.label_execution_sources import COMPONENT
from returnops_domain.lifecycle_schema import EXECUTION,LABEL,version
from returnops_domain.registry import TrustedRegistry
from label_execution_helpers import ready,provision,service,execute,reconcile,reserve,control,assert_complete,rows,snapshot,evidence
from conftest import migrate


@pytest.mark.parametrize('flow_engine',[EXECUTION],indirect=True)
def test_LE_G1_retained0011_upgrade_preserves_original_rows_and_grants(flow_engine,identities,enabled,request):
    args,setup=ready(flow_engine,identities,grants=False);before=snapshot(flow_engine)
    migrate(flow_engine,LABEL);migrate(flow_engine,LABEL);after=snapshot(flow_engine)
    assert set(after)-set(before)==set(metadata.tables) and all(after[name]==[] for name in metadata.tables)
    assert {n:v for n,v in before.items() if n!='alembic_version'}=={n:v for n,v in after.items() if n not in {*metadata.tables,'alembic_version'}}
    with flow_engine.connect() as connection:
        assert version(connection)==LABEL and len(inspect(connection).get_table_names())==56
        assert inspect(connection).get_foreign_keys(ledger.name)==[]
    provision(flow_engine,identities);prior=snapshot(flow_engine)
    result=execute(service(flow_engine,identities),args);assert_complete(flow_engine,args,result,prior)
    evidence(request.node.nodeid,before0011=before,after0012=after,result=asdict(result))


@pytest.mark.parametrize('flow_engine',[EXECUTION],indirect=True)
def test_LE_G1_upgrade_rejects_incomplete0011_without_creating_any_label_table(flow_engine,identities,enabled,request):
    ready(flow_engine,identities,grants=False)
    with flow_engine.begin() as connection:connection.execute(text('ALTER TABLE return_provider_permissions DROP CONSTRAINT ck_return_permission_command'))
    before=snapshot(flow_engine)
    with pytest.raises(RuntimeError,match='exact complete 0011'):migrate(flow_engine,LABEL)
    assert snapshot(flow_engine)==before and not set(metadata.tables)&set(inspect(flow_engine).get_table_names())
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('fault',['extra_table','nullable','collation','missing_check','weaker_check','ledger_fk','extra_index','composite_fk','default','trigger'])
def test_LE_G1_exact0012_descriptor_rejects_counterfeit_schema(flow_engine,identities,enabled,request,fault):
    args,_=ready(flow_engine,identities)
    sql={
        'extra_table':'CREATE TABLE unexpected_label_table (id integer)',
        'nullable':'ALTER TABLE lifecycle_label_execution_controls ALTER COLUMN binding_hash DROP NOT NULL',
        'collation':'ALTER TABLE lifecycle_label_execution_controls ALTER COLUMN binding_hash TYPE varchar(64) COLLATE "C"',
        'missing_check':'ALTER TABLE core_mock_label_ledger DROP CONSTRAINT ck_mock_label_status',
        'weaker_check':"ALTER TABLE core_mock_label_ledger DROP CONSTRAINT ck_mock_label_status; ALTER TABLE core_mock_label_ledger ADD CONSTRAINT ck_mock_label_status CHECK (status <> '')",
        'ledger_fk':'ALTER TABLE core_mock_label_ledger ADD CONSTRAINT forbidden_label_fk FOREIGN KEY (dispatch_record_id) REFERENCES customer_history_revisions(record_id)',
        'extra_index':'CREATE INDEX unexpected_label_index ON core_mock_label_ledger (store_id)',
        'composite_fk':'ALTER TABLE lifecycle_label_artifact_work DROP CONSTRAINT fk_label_artifact_control_case',
        'default':'ALTER TABLE lifecycle_label_artifact_work ALTER COLUMN epoch SET DEFAULT 0',
        'trigger':"CREATE FUNCTION label_probe_trigger() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$; CREATE TRIGGER unexpected_label_trigger BEFORE INSERT ON core_mock_label_ledger FOR EACH ROW EXECUTE FUNCTION label_probe_trigger()",
    }[fault]
    with flow_engine.begin() as connection:
        if fault=='trigger':
            connection.execute(text("CREATE FUNCTION label_probe_trigger() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$"))
            connection.execute(text('CREATE TRIGGER unexpected_label_trigger BEFORE INSERT ON core_mock_label_ledger FOR EACH ROW EXECUTE FUNCTION label_probe_trigger()'))
        else:
            for statement in sql.split('; '):connection.execute(text(statement))
        assert version(connection) is None
    before=snapshot(flow_engine);result=execute(service(flow_engine,identities),args)
    assert result.status=='DENIED' and snapshot(flow_engine)==before and rows(flow_engine,ledger)==[]
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))


def test_LE_G2_G5_actual_chain_exact_independent_T2_delta_and_no_artifact_result(flow_engine,identities,enabled,request):
    args,_=ready(flow_engine,identities);before=snapshot(flow_engine);observations=[]
    class Observed(CoreLabelMock):
        def perform(self,ticket,callback):
            initial=snapshot(self.engine);reply=super().perform(ticket,callback);after=snapshot(self.engine)
            assert reply.status=='FOUND',asdict(reply)
            assert {n:v for n,v in initial.items() if n!=ledger.name}=={n:v for n,v in after.items() if n!=ledger.name}
            assert len(after[ledger.name])==len(initial[ledger.name])+1
            observations.append((initial,after));return reply
    result=execute(service(flow_engine,identities,mock_factory=Observed),args)
    after=assert_complete(flow_engine,args,result,before);assert len(observations)==1
    t1,t2=observations[0];t1head,=t1[old.case_heads.name];finalhead,=after[old.case_heads.name]
    assert {k:v for k,v in t1head.items() if k not in {'history_sequence','audit_sequence','audit_head'}}=={
        k:v for k,v in finalhead.items() if k not in {'history_sequence','audit_sequence','audit_head'}}
    assert t1head['history_sequence']+1==finalhead['history_sequence']
    evidence(request.node.nodeid,result=asdict(result),before=before,T1=t1,T2=t2,after=after,
        stop='durable mock label fact; EXECUTING no result; unclaimed artifact PENDING')


def test_LE_G8_G10_confirmed_replay_and_original_N1_N2_bridge_remain_exact(flow_engine,identities,enabled,request,monkeypatch):
    from preparation_helpers import service as prepare_service
    from create_return_execution_helpers import service as return_service,reconcile as return_reconcile
    from return_label_bridge_helpers import service as bridge_service,accept as bridge_accept
    from returnops_domain.core_return_mock import CoreReturnMock
    args,setup=ready(flow_engine,identities);caller=service(flow_engine,identities)
    first=execute(caller,args);assert first.status=='COMMITTED',asdict(first);before=snapshot(flow_engine)
    def forbidden(*a,**k):raise AssertionError('Confirmed replay must not call provider')
    monkeypatch.setattr(CoreLabelMock,'perform',forbidden);monkeypatch.setattr(CoreReturnMock,'perform',forbidden)
    replay=execute(caller,args);recovery=reconcile(caller,args)
    n1=prepare_service(flow_engine,identities).prepare(**setup['upstream'])
    n2=return_reconcile(return_service(flow_engine,identities),setup['upstream'])
    bridge=bridge_accept(bridge_service(flow_engine,identities),setup['bridge_arguments'])
    assert [replay.status,recovery.status,n1.status,n2.status,bridge.status]==['REPLAYED']*5
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,results=[asdict(r) for r in (replay,recovery,n1,n2,bridge)],before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('fault',['no_session','customer','wrong_key','wrong_version','missing_grants','session_revoked','owner_disabled',
    'execution_revoked','effect_revoked','provider_create','provider_query','provider_config','return_effect','return_query'])
def test_LE_G3_G4_current_identity_and_independent_permissions_deny_zero_effect(flow_engine,identities,enabled,request,fault):
    from returnops_domain.return_execution_tables import permissions as rp
    from returnops_domain.return_execution_sources import COMPONENT as RC
    args,_=ready(flow_engine,identities,grants=fault!='missing_grants')
    name=None if fault=='no_session' else 'customer_a' if fault=='customer' else 'founder'
    if fault=='wrong_key':args['original_approval_key']='replacement-original-key'
    elif fault=='wrong_version':args['expected_case_version']+=1
    elif fault=='session_revoked':TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    elif fault=='owner_disabled':TrustedRegistry(flow_engine).change_principal(identities.people['customer_a']['principal_id'],enabled=False)
    elif fault in {'execution_revoked','effect_revoked','provider_create','provider_query','provider_config','return_effect','return_query'}:
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            if fault in {'execution_revoked','effect_revoked','return_effect'}:
                statement=update(life.authorities).where(life.authorities.c.component_id== (RC if fault=='return_effect' else COMPONENT),
                    life.authorities.c.purpose==('EXECUTION' if fault=='execution_revoked' else 'EFFECT')).values(enabled=False,revision=2)
            elif fault=='return_query':statement=update(rp).values(query_enabled=False,revision=2)
            else:statement=update(permissions).values(**({'create_enabled':False,'revision':2} if fault=='provider_create' else {'query_enabled':False,'revision':2} if fault=='provider_query' else {'config_hash':'0'*64}))
            assert uow.execute(statement).rowcount==1;uow.commit()
    before=snapshot(flow_engine);result=execute(service(flow_engine,identities,name),args)
    assert result.status=='DENIED',asdict(result)
    assert snapshot(flow_engine)==before and rows(flow_engine,controls)==rows(flow_engine,ledger)==rows(flow_engine,artifact_work)==[]
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('fault',['source_bytes','bridge_receipt','bridge_binding','bridge_work','return_fact','return_origin','extra_operation','orphan_label_ledger','cross_case_effect','cross_case_operation'])
def test_LE_G3_G10_full_source_corruption_is_not_a_new_label(flow_engine,identities,enabled,request,fault):
    from returnops_domain.return_execution_tables import controls as returns,ledger as return_ledger
    from returnops_domain.canonical import encode_document,decode_document
    args,_=ready(flow_engine,identities);mock_calls=[]
    class ObservedMock(CoreLabelMock):
        def perform(self,ticket,callback):
            mock_calls.append(ticket.kind)
            return super().perform(ticket,callback)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        if fault=='source_bytes':statement=update(storage.original_statement_contents).values(raw_text=b'altered retained source')
        elif fault=='bridge_receipt':statement=update(life.events).where(life.events.c.event_kind=='RETURN_SOURCE').values(source_audit_event_id='wrong_audit_original')
        elif fault=='bridge_binding':statement=update(life.sources).where(life.sources.c.dispatch_source_record_id.is_not(None)).values(provider_operation_id='wrong_provider_original')
        elif fault=='bridge_work':statement=update(life.work).where(life.work.c.purpose=='EFFECT').values(target_hash='0'*64)
        elif fault=='return_fact':statement=update(return_ledger).values(fact_hash='0'*64)
        elif fault=='return_origin':
            ret=uow.execute(select(returns)).mappings().one();statement=update(returns).values(result_audit_id=ret['dispatch_audit_id'])
        elif fault=='extra_operation':
            record=dict(uow.execute(select(old.history).where(old.history.c.kind=='OPERATION')).mappings().first())
            head=uow.execute(select(old.case_heads)).mappings().one()
            record.update(record_id='orphan_operation_record',object_id='orphan_operation_id',recorded_sequence=head['history_sequence']+1)
            uow.execute(old.history.insert().values(**record));statement=update(old.case_heads).values(history_sequence=head['history_sequence']+1)
        else:
            # Deliberately hostile orphan fact: authoritative case_id is present,
            # but no Domain control. It must fail before creating a reservation.
            values={str(c.name):'orphan_original' for c in ledger.columns if c.name.endswith('_id')}
            values.update({str(c.name):'0'*64 for c in ledger.columns if c.name.endswith('_hash') or c.name.endswith('_fingerprint')})
            values.update(case_id=args['case_id'],effect_key='orphan_effect_original',status='SUCCEEDED',error_code=None,
                accepted_at=uow.execute(text('SELECT clock_timestamp()')).scalar_one())
            if fault.startswith('cross_case'):
                from returnops_domain.label_execution_sources import identities as label_ids
                values['case_id']='foreign_case_original'
                field='effect_key' if fault=='cross_case_effect' else 'operation_id'
                values[field]=label_ids(args['execution_work_id'])[field]
            statement=ledger.insert().values(**values)
        uow.execute(statement);uow.commit()
    before=snapshot(flow_engine);result=execute(service(flow_engine,identities,mock_factory=ObservedMock),args)
    assert result.status=='DENIED',asdict(result)
    assert snapshot(flow_engine)==before and rows(flow_engine,controls)==[]
    if fault=='source_bytes':
        assert result.safe_code=='INVALID_STATE',asdict(result)
        assert mock_calls==[]
        assert rows(flow_engine,ledger)==[] and rows(flow_engine,artifact_work)==[]
    evidence(request.node.nodeid,fault=fault,result=asdict(result),mock_calls=mock_calls,before=before,after=snapshot(flow_engine),hostile_fixture=True)


@pytest.mark.parametrize('phase,point',[('T1',p) for p in range(1,15)]+[('T3',p) for p in range(1,9)])
def test_LE_G5_every_domain_write_rolls_back_and_preserves_independent_ledger(flow_engine,identities,enabled,request,phase,point):
    args,_=ready(flow_engine,identities);writes=[];mock_calls=[]
    class Fault(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                writes.append(statement.table.name)
                if len(writes)==point:
                    self.poison();raise FlowError('INTERNAL_ERROR')
            return super().execute(statement,parameters)
    if phase=='T1':
        before=snapshot(flow_engine)
        def forbidden(*a):mock_calls.append('called');raise AssertionError('Uncommitted T1 cannot dispatch')
        result=execute(service(flow_engine,identities,uow_factory=Fault,mock_factory=forbidden),args)
    else:
        caller=service(flow_engine,identities);ticket=reserve(caller,args)
        reply=CoreLabelMock(flow_engine).perform(ticket,caller.authority);assert reply.status=='FOUND',asdict(reply)
        before=snapshot(flow_engine)
        result=service(flow_engine,identities,uow_factory=Fault)._accept(ticket,reply.fact,'fault-confirmation')
    assert len(writes)==point and result.status=='UNKNOWN',asdict(result)
    assert snapshot(flow_engine)==before and mock_calls==[]
    assert len(rows(flow_engine,ledger))==(phase=='T3') and rows(flow_engine,artifact_work)==[]
    evidence(request.node.nodeid,phase=phase,point=point,writes=writes,result=asdict(result),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('fault',['t1_before_commit','t1_after_commit','t1_close','t2_lost_response','t3_before_commit','t3_after_commit','t3_close'])
def test_LE_G5_G8_actual_commit_close_uncertainty_has_exact_query_only_recovery(flow_engine,identities,enabled,request,fault):
    args,_=ready(flow_engine,identities);calls=[];mock_calls=[]
    class Fault(CustomerUnitOfWork):
        def commit(self):
            if fault.endswith('before_commit'):
                self.poison();raise AcceptanceOutcomeUnknown()
            super().commit()
            if fault.endswith('after_commit'):raise AcceptanceOutcomeUnknown()
        def __exit__(self,*a):
            result=super().__exit__(*a)
            if fault.endswith('close'):raise AcceptanceOutcomeUnknown()
            return result
    def factory(engine,**kwargs):
        calls.append(len(calls)+1);selected=fault.startswith('t1') and len(calls)==1 or fault.startswith('t3') and len(calls)==2
        return (Fault if selected else CustomerUnitOfWork)(engine,**kwargs)
    class Observed(CoreLabelMock):
        def perform(self,ticket,callback):
            mock_calls.append(ticket.kind);reply=super().perform(ticket,callback)
            if fault=='t2_lost_response':assert reply.status=='FOUND';raise AcceptanceOutcomeUnknown()
            return reply
    result=execute(service(flow_engine,identities,uow_factory=factory,mock_factory=Observed),args)
    assert result.status=='UNKNOWN',asdict(result)
    assert len(rows(flow_engine,ledger))==(not fault.startswith('t1'))
    assert len(mock_calls)==(not fault.startswith('t1'))
    before=snapshot(flow_engine);recovered=reconcile(service(flow_engine,identities),args)
    expected='UNKNOWN' if fault.startswith('t1') else 'REPLAYED' if fault in {'t3_after_commit','t3_close'} else 'COMMITTED'
    assert recovered.status==expected,asdict(recovered)
    assert len(rows(flow_engine,ledger))==(not fault.startswith('t1'))
    if fault in {'t3_after_commit','t3_close'}:assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,result=asdict(result),recovery=asdict(recovered),mock_calls=mock_calls,before_recovery=before,after=snapshot(flow_engine))


def test_LE_G8_explicit_no_effect_failure_has_no_artifact_and_no_retry(flow_engine,identities,enabled,request):
    args,_=ready(flow_engine,identities);calls=[]
    class Failed(CoreLabelMock):
        def _outcome(self,row,command):calls.append('guarded no effect');return 'FAILED'
    caller=service(flow_engine,identities,mock_factory=Failed);result=execute(caller,args)
    assert result.status=='COMMITTED' and result.operation_state=='FAILED' and result.provider_fact_status=='FAILED',asdict(result)
    assert rows(flow_engine,artifact_work)==[] and len(rows(flow_engine,ledger))==1
    before=snapshot(flow_engine);again=execute(caller,args)
    assert again.status=='REPLAYED' and snapshot(flow_engine)==before and calls==['guarded no effect']
    evidence(request.node.nodeid,result=asdict(result),again=asdict(again),after=before)


@pytest.mark.parametrize('field',['provider_label_id','provider_return_id','parcel_id','fact_hash'])
def test_LE_G3_adapter_reply_must_equal_actual_independent_ledger(flow_engine,identities,enabled,request,field):
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=reserve(caller,args)
    reply=CoreLabelMock(flow_engine).perform(ticket,caller.authority);assert reply.status=='FOUND'
    changed={**reply.fact,field:'0'*64 if field=='fact_hash' else 'foreign_original'}
    before=snapshot(flow_engine);result=caller._accept(ticket,changed,'forged-adapter-result')
    assert result.status=='DENIED' and snapshot(flow_engine)==before and rows(flow_engine,artifact_work)==[]
    recovered=reconcile(caller,args);assert recovered.status=='COMMITTED' and len(rows(flow_engine,ledger))==1
    evidence(request.node.nodeid,field=field,result=asdict(result),recovered=asdict(recovered),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('fault',['artifact_missing','artifact_binding','extra_operation','extra_fact'])
def test_LE_G3_G10_confirmed_chain_rejects_missing_mismatched_extra_records_without_repair(flow_engine,identities,enabled,request,fault):
    from returnops_domain.label_execution_history import append_operation
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities)
    assert execute(caller,args).status=='COMMITTED';row=control(flow_engine)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        if fault=='artifact_missing':uow.execute(delete(artifact_work))
        elif fault=='artifact_binding':uow.execute(update(artifact_work).values(binding_hash='0'*64))
        elif fault=='extra_fact':
            fact=dict(uow.execute(select(ledger)).mappings().one())
            fact.update(effect_key='foreign_effect_original',operation_id='foreign_operation_original',
                provider_operation_id='foreign_provider_operation',provider_label_id='foreign_provider_label')
            uow.execute(ledger.insert().values(**fact))
        else:
            head=dict(uow.execute(select(old.case_heads)).mappings().one())
            raw=uow.execute(select(old.history_contents.c.body).where(old.history_contents.c.record_id==row['confirmation_record_id'])).scalar_one()
            now=uow.execute(text('SELECT clock_timestamp()')).scalar_one();body=finite.decode_document(raw)
            from returnops_domain.audit import timestamp
            body['updated_at']=timestamp(now)
            append_operation(uow,head,'extra_label_operation',body,4,dict(synthetic_extra=True),'extra-label-origin',now)
        uow.commit()
    before=snapshot(flow_engine);result=reconcile(caller,args)
    assert result.status=='DENIED' and snapshot(flow_engine)==before,asdict(result)
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine),hostile_fixture=True)


@pytest.mark.parametrize('fault',['duplicate','cross_case','claimed','running'])
def test_LE_G1_artifact_database_constraints_reject_duplicate_cross_case_and_claims(flow_engine,identities,enabled,request,fault):
    from sqlalchemy.exc import IntegrityError
    args,_=ready(flow_engine,identities);assert execute(service(flow_engine,identities),args).status=='COMMITTED'
    before=snapshot(flow_engine);work,=rows(flow_engine,artifact_work)
    with pytest.raises(IntegrityError):
        with flow_engine.begin() as connection:
            if fault=='duplicate':connection.execute(artifact_work.insert().values(**{**work,'work_id':'replacement_artifact_original'}))
            elif fault=='cross_case':connection.execute(update(artifact_work).values(case_id='foreign_case_original'))
            elif fault=='claimed':connection.execute(update(artifact_work).values(claim_id='claim_original',epoch=1))
            else:connection.execute(update(artifact_work).values(state='RUNNING'))
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,before=before,after=snapshot(flow_engine),constraint_rejected=True)


def test_LE_G3_missing_original_N2_origin_is_not_replaced_by_bridge_audit(flow_engine,identities,enabled,request):
    from returnops_domain.return_execution_tables import controls as returns
    from returnops_domain.canonical import decode_document,encode_document,digest
    args,_=ready(flow_engine,identities)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        row=uow.execute(select(returns)).mappings().one();records=list(uow.execute(select(old.audit).order_by(old.audit.c.sequence)).mappings());previous=None
        for record in records:
            event=decode_document(record['body']);event.pop('event_hash');event.pop('previous_event_hash',None)
            if event['event_id']==row['result_audit_id']:event['history_refs']=[]
            if previous is not None:event['previous_event_hash']=previous
            event['event_hash']=digest(dict(sequence=record['sequence'],event=event),'audit/v1')
            uow.execute(update(old.audit).where(old.audit.c.event_id==record['event_id']).values(body=encode_document(event),event_hash=event['event_hash']))
            previous=event['event_hash']
        uow.execute(update(old.case_heads).values(audit_head=previous));uow.commit()
    before=snapshot(flow_engine);result=execute(service(flow_engine,identities),args)
    # Existing CaseProof reports an unavailable original origin as INTERNAL_ERROR.
    assert result.status=='UNKNOWN' and snapshot(flow_engine)==before and rows(flow_engine,controls)==[]
    evidence(request.node.nodeid,result=asdict(result),before=before,after=snapshot(flow_engine),hostile_rehashed_origin_fixture=True)
