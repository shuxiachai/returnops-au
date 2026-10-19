"""EP G1..G6/G8/G9 actual persisted preparation; disposable cloud PG only."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import pytest
from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from returnops_domain import customer_tables as old, founder_tables as founder, lifecycle_tables as life
from returnops_domain import founder_codec as finite
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.execution_preparation_tables import preparations
from returnops_domain.lifecycle_schema import version, APPROVAL, PREPARATION
from returnops_domain.preview_tables import previews
from approval_admission_helpers import guard, current_history
from approve_helpers import approve
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain.founder_service import FounderQueries
from manual_helpers import evidence, rows, snapshot
from preparation_helpers import ready, service, recovered, unchanged, assert_delta


@pytest.mark.parametrize('outcome', ['PASS','PASS_WITH_WARNING'])
def test_EP_G2_G3_G5_G8_G9_actual_atomic_preparation_and_original_replays(flow_engine,identities,enabled,request,outcome):
    arguments, setup = ready(flow_engine,identities,outcome=outcome)
    before = snapshot(flow_engine); caller = service(flow_engine,identities)
    first = caller.prepare(**arguments)
    assert first.status == 'PREPARED', asdict(first)
    after, row, body = assert_delta(flow_engine,before,first,arguments)
    second = caller.prepare(**{**arguments,'correlation_id':'replayed-correlation'})
    assert second.status == 'REPLAYED' and asdict(second) == {**asdict(first),'status':'REPLAYED'}
    assert recovered(caller,arguments) == second and snapshot(flow_engine) == after
    original = approve(flow_engine,identities).accept(setup['case'],setup['request'],
        arguments['original_approval_key'],'original-approval-replay')
    assert original.receipt == setup['result'].receipt and snapshot(flow_engine) == after
    expiry = datetime.fromisoformat(setup['action']['scope']['expires_at'].replace('Z','+00:00'))
    historical = service(flow_engine,identities,clock=lambda:expiry).prepare(**arguments)
    assert historical == second and snapshot(flow_engine) == after
    # Cached prior CHECKED cannot authorize another preparation after its first OP.
    admission = guard(flow_engine,identities).check(**{k:v for k,v in arguments.items() if k!='correlation_id'})
    assert admission.status == 'DENIED' and snapshot(flow_engine) == after
    founder=FounderQueries(flow_engine,CurrentRequestAuthority(identities.auth_config,'Bearer '+identities.tokens['founder']))
    page = founder.read('listFounderCaseHistory',arguments['case_id'],
        {'kind':'OPERATION','limit':100}).body
    assert len(page['items']) == 1 and page['items'][0]['content'] == body
    evidence(request.node.nodeid,before=before,after=after,result=asdict(first),row=row,body=body,
        original_approve=asdict(original),historical=asdict(historical),founder_operation_page=page)


def test_EP_G2_G4_exact_parameters_keys_roles_versions_and_no_cached_token(flow_engine,identities,enabled,request):
    arguments,_ = ready(flow_engine,identities); caller=service(flow_engine,identities)
    variants=[]
    for field,value in [('case_id','case_missing'),('expected_case_version',arguments['expected_case_version']+1),
        ('execution_work_id','execution_missing'),('original_approval_key','unknown-original-key')]:
        variants.append((field,{**arguments,field:value},'UNKNOWN' if field=='original_approval_key' else 'DENIED'))
    for field,value in [('type','GENERATE_LABEL'),('provider_id','provider_other'),('command_id','command_other')]:
        candidate=deepcopy(arguments['candidate_command']); candidate[field]=value
        variants.append((field,{**arguments,'candidate_command':candidate},'DENIED'))
    candidate=deepcopy(arguments['candidate_command']); candidate['parameters']['line_items'][0]['quantity']+=1
    variants.append(('quantity',{**arguments,'candidate_command':candidate},'DENIED'))
    results={name:asdict(unchanged(flow_engine,caller,args,status)) for name,args,status in variants}
    for name in (None,'customer_a','customer_b'):
        unchanged(flow_engine,service(flow_engine,identities,name),arguments)
    before=snapshot(flow_engine); first=caller.prepare(**arguments)
    assert first.status=='PREPARED'; after,_,_=assert_delta(flow_engine,before,first,arguments)
    conflict=unchanged(flow_engine,caller,{**arguments,'candidate_command':candidate})
    assert conflict.safe_code=='IDEMPOTENCY_CONFLICT' and snapshot(flow_engine)==after
    evidence(request.node.nodeid,variants=results,conflict=asdict(conflict),before=before,after=after)


@pytest.mark.parametrize('flow_engine',['0007_lifecycle_guards','0008_review_escalation'],indirect=True)
def test_EP_G1_exact_legacy_descriptors_remain_distinct(flow_engine,request):
    from returnops_api.database import readiness
    with flow_engine.connect() as connection:
        actual=connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        assert version(connection)==actual
    assert preparations.name not in inspect(flow_engine).get_table_names() and not readiness(flow_engine)
    evidence(request.node.nodeid,exact_legacy=actual,ready=False)


@pytest.mark.parametrize('flow_engine',[APPROVAL],indirect=True)
def test_EP_G1_real_0009_approval_upgrade_preserves_receipt_bytes_and_unchanged_anchor(flow_engine,identities,enabled,request):
    from conftest import migrate
    arguments,setup=ready(flow_engine,identities)
    before=snapshot(flow_engine)
    unchanged(flow_engine,service(flow_engine,identities),arguments)
    migrate(flow_engine,PREPARATION)
    after=snapshot(flow_engine)
    assert set(after)-set(before)=={preparations.name} and after[preparations.name]==[]
    assert {k:v for k,v in after.items() if k not in {preparations.name,'alembic_version'}}=={
        k:v for k,v in before.items() if k!='alembic_version'}
    replay=approve(flow_engine,identities).accept(setup['case'],setup['request'],arguments['original_approval_key'],'old-approval-replay')
    assert replay.receipt==setup['result'].receipt and snapshot(flow_engine)==after
    with flow_engine.connect() as connection: assert version(connection)==PREPARATION
    result=service(flow_engine,identities).prepare(**arguments)
    assert result.status=='PREPARED'; assert_delta(flow_engine,after,result,arguments)
    evidence(request.node.nodeid,before0009=before,after0010=after,original_replay=asdict(replay),prepared=asdict(result))


@pytest.mark.parametrize('fault', ['extra_column','default','nullable','check','not_valid','deferred_fk','cascade_fk',
    'wrong_schema_fk','unique','index','preview_check','extra_table'])
def test_EP_G1_exact_descriptor_forgery_blocks_all_n1_writes(flow_engine,identities,enabled,request,fault):
    arguments,_=ready(flow_engine,identities)
    with flow_engine.begin() as connection:
        if fault=='extra_column': sql='ALTER TABLE lifecycle_execution_preparations ADD COLUMN unwanted integer'
        elif fault=='default': sql="ALTER TABLE lifecycle_execution_preparations ALTER COLUMN state SET DEFAULT 'PENDING'"
        elif fault=='nullable': sql='ALTER TABLE lifecycle_execution_preparations ALTER COLUMN state DROP NOT NULL'
        elif fault in {'check','not_valid'}:
            connection.execute(text('ALTER TABLE lifecycle_execution_preparations DROP CONSTRAINT ck_preparation_state'))
            sql=("ALTER TABLE lifecycle_execution_preparations ADD CONSTRAINT ck_preparation_state CHECK "
                "(state IN ('PENDING','PAUSED','SUPERSEDED')"+(' OR TRUE)' if fault=='check' else ') NOT VALID'))
        elif fault in {'deferred_fk','cascade_fk','wrong_schema_fk'}:
            connection.execute(text('ALTER TABLE lifecycle_execution_preparations DROP CONSTRAINT fk_preparation_case_id'))
            target='case_heads'
            if fault=='wrong_schema_fk':
                # Public base belongs to this disposable cloud database; no local DB is used.
                target='public.case_heads'
            sql='ALTER TABLE lifecycle_execution_preparations ADD CONSTRAINT fk_preparation_case_id FOREIGN KEY (case_id) REFERENCES '+target+'(case_id)'
            sql+= ' DEFERRABLE INITIALLY DEFERRED' if fault=='deferred_fk' else ' ON DELETE CASCADE' if fault=='cascade_fk' else ''
        elif fault=='unique': sql='ALTER TABLE lifecycle_execution_preparations DROP CONSTRAINT uq_preparation_effect_key'
        elif fault=='index': sql='DROP INDEX ix_preparation_case'
        elif fault=='preview_check':
            connection.execute(text('ALTER TABLE lifecycle_action_previews DROP CONSTRAINT ck_preview_expiry'))
            sql='ALTER TABLE lifecycle_action_previews ADD CONSTRAINT ck_preview_expiry CHECK (expires_at >= issued_at)'
        else: sql='CREATE TABLE preparation_orphan (id integer)'
        connection.execute(text(sql))
    with flow_engine.connect() as connection: assert version(connection) is None
    before=snapshot(flow_engine); result=unchanged(flow_engine,service(flow_engine,identities),arguments)
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('fault', ['proposal_body','review_encoding','approval_body','approval_binding','receipt','preview',
    'source_statement','work_claim','work_epoch','profile','execution_grant','original_unknown'])
def test_EP_G2_full_actual_source_is_reverified_inside_original_fence(flow_engine,identities,enabled,monkeypatch,request,fault):
    from returnops_domain import preview_profile
    from returnops_domain import storage
    arguments,setup=ready(flow_engine,identities); injected=[]
    class Fault(CustomerUnitOfWork):
        def __enter__(self):
            super().__enter__()
            if fault=='profile': return self
            if fault in {'proposal_body','approval_body','review_encoding'}:
                kind={'proposal_body':'PROPOSAL','approval_body':'APPROVAL','review_encoding':'REVIEW'}[fault]
                record=self.execute(select(old.history.c.record_id).where(old.history.c.case_id==setup['case'],old.history.c.kind==kind)).scalar_one()
                table=founder.encodings if fault=='review_encoding' else old.history_contents
                statement=delete(table).where(table.c.record_id==record)
            elif fault=='approval_binding':
                record=self.execute(select(old.history.c.record_id).where(old.history.c.case_id==setup['case'],old.history.c.kind=='APPROVAL')).scalar_one()
                statement=update(life.sources).where(life.sources.c.record_id==record).values(source_hash='0'*64)
            elif fault=='receipt':
                ids=select(old.acceptances.c.acceptance_id).where(old.acceptances.c.target==setup['case'],old.acceptances.c.operation=='recordFounderDecision')
                statement=update(old.receipts).where(old.receipts.c.acceptance_id.in_(ids)).values(available=False,body=None)
            elif fault=='preview': statement=update(previews).where(previews.c.case_id==setup['case']).values(body_hash='0'*64)
            elif fault=='source_statement':
                ids=select(storage.original_statement_records.c.statement_id).where(storage.original_statement_records.c.case_id==setup['case'])
                statement=update(storage.original_statement_contents).where(storage.original_statement_contents.c.statement_id.in_(ids)).values(raw_text=b'corrupt original input')
            elif fault in {'work_claim','work_epoch'}:
                statement=update(life.work).where(life.work.c.work_id==arguments['execution_work_id']).values(
                    **({'claim_id':'illegal_claim'} if fault=='work_claim' else {'epoch':1}))
            elif fault=='execution_grant':
                statement=update(life.authorities).where(life.authorities.c.purpose=='EXECUTION').values(enabled=False,revision=2)
            else:
                ids=select(old.acceptances.c.acceptance_id).where(old.acceptances.c.target==setup['case'],old.acceptances.c.operation=='recordFounderDecision')
                statement=update(old.acceptances).where(old.acceptances.c.acceptance_id.in_(ids)).values(request_key='different-original-key')
            assert self.execute(statement).rowcount==1; injected.append(fault)
            return self
    if fault=='profile':
        monkeypatch.setattr(preview_profile,'profile',lambda:{**preview_profile.PROFILE,'currency':'USD'}); injected.append(fault)
    result=unchanged(flow_engine,service(flow_engine,identities,uow_factory=Fault),arguments,
        'UNKNOWN' if fault=='original_unknown' else 'DENIED')
    assert injected==[fault]
    evidence(request.node.nodeid,fault=fault,result=asdict(result),injected=injected)


@pytest.mark.parametrize('point', ['history','content','encoding','head_history','audit','head_audit','sidecar'])
def test_EP_G3_every_write_boundary_rolls_back_whole_preparation(flow_engine,identities,enabled,request,point):
    arguments,_=ready(flow_engine,identities); observed=[]
    targets={old.history.name:'history',old.history_contents.name:'content',founder.encodings.name:'encoding',
        old.audit.name:'audit',preparations.name:'sidecar'}
    class Fault(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            result=super().execute(statement,parameters)
            if getattr(statement,'is_insert',False) or getattr(statement,'is_update',False):
                name=statement.table.name
                where=targets.get(name)
                if name==old.case_heads.name:
                    where='head_history' if 'history_sequence' in statement.compile().params else 'head_audit'
                if where:
                    observed.append(where)
                    if where==point: raise FlowError('INVALID_STATE')
            return result
    unchanged(flow_engine,service(flow_engine,identities,uow_factory=Fault),arguments)
    assert observed[-1]==point
    evidence(request.node.nodeid,write_failure=point,actual_writes=observed)


@pytest.mark.parametrize('committed',[False,True])
def test_EP_G6_commit_ambiguity_and_independent_recovery_never_retry(flow_engine,identities,enabled,request,committed):
    arguments,_=ready(flow_engine,identities); calls=[]
    class Unknown(CustomerUnitOfWork):
        def __enter__(self): calls.append('enter'); return super().__enter__()
        def commit(self):
            for check in self._commit_checks: check()
            if committed: self.transaction.commit()
            else: self.transaction.rollback()
            self.finished=True; raise AcceptanceOutcomeUnknown()
    before=snapshot(flow_engine)
    result=service(flow_engine,identities,uow_factory=Unknown).prepare(**arguments)
    assert result.status=='UNKNOWN' and calls==['enter']
    after=snapshot(flow_engine); recovery=recovered(service(flow_engine,identities),arguments)
    assert snapshot(flow_engine)==after
    assert recovery.status==('REPLAYED' if committed else 'UNKNOWN')
    if committed: assert_delta(flow_engine,before,recovery,arguments)
    else: assert before==after
    evidence(request.node.nodeid,commit_happened=committed,result=asdict(result),recovery=asdict(recovery),before=before,after=after)


def test_EP_G6_close_ambiguity_keeps_unknown_after_successful_commit(flow_engine,identities,enabled):
    arguments,_=ready(flow_engine,identities); calls=[]
    class Unknown(CustomerUnitOfWork):
        def __exit__(self,*args):
            super().__exit__(*args); calls.append('close'); raise AcceptanceOutcomeUnknown()
    before=snapshot(flow_engine); result=service(flow_engine,identities,uow_factory=Unknown).prepare(**arguments)
    assert result.status=='UNKNOWN' and calls==['close']
    recovery=recovered(service(flow_engine,identities),arguments)
    assert recovery.status=='REPLAYED'; assert_delta(flow_engine,before,recovery,arguments)


@pytest.mark.parametrize('remove',['sidecar','history_body','encoding','audit_binding','request_fingerprint','first_hash','orphan_operation'])
def test_EP_G3_G5_corrupt_or_missing_preparation_never_rebuilds(flow_engine,identities,enabled,request,remove):
    arguments,_=ready(flow_engine,identities); caller=service(flow_engine,identities)
    first=caller.prepare(**arguments); assert first.status=='PREPARED'
    row,=rows(flow_engine,preparations)
    orphan=None
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        if remove=='sidecar': statement=delete(preparations).where(preparations.c.preparation_id==row['preparation_id'])
        elif remove=='history_body': statement=delete(old.history_contents).where(old.history_contents.c.record_id==row['first_operation_record_id'])
        elif remove=='encoding': statement=delete(founder.encodings).where(founder.encodings.c.record_id==row['first_operation_record_id'])
        elif remove in {'audit_binding','request_fingerprint'}:
            statement=update(preparations).where(preparations.c.preparation_id==row['preparation_id']).values(
                **({'binding_hash':'0'*64} if remove=='audit_binding' else {'request_fingerprint':'0'*64}))
        elif remove=='first_hash': statement=update(old.history).where(old.history.c.record_id==row['first_operation_record_id']).values(content_sha256='0'*64)
        else:
            original=dict(uow.execute(select(old.history).where(old.history.c.record_id==row['first_operation_record_id'])).mappings().one())
            orphan={**original,'record_id':'orphan_operation_row','object_id':'orphan_operation',
                'recorded_sequence':original['recorded_sequence']+1}
            assert uow.execute(select(old.history.c.record_id).where(
                old.history.c.record_id==orphan['record_id'])).first() is None
            statement=old.history.insert().values(**orphan).returning(*old.history.columns)
        if orphan is None:
            assert uow.execute(statement).rowcount==1
        else:
            assert dict(uow.execute(statement).mappings().one())==orphan
        uow.commit()
    if orphan is not None:
        # A separately fenced connection proves committed identity, count and
        # every column before the original rejection/recovery checks run.
        with CustomerUnitOfWork(flow_engine,write=False) as verification:
            persisted=list(verification.execute(select(old.history).where(
                old.history.c.record_id==orphan['record_id'])).mappings())
            assert len(persisted)==1 and dict(persisted[0])==orphan
            verification.commit()
    result=unchanged(flow_engine,caller,arguments)
    before=snapshot(flow_engine); recovery=recovered(caller,arguments)
    assert recovery.status=='UNKNOWN' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=remove,result=asdict(result),recovery=asdict(recovery),after=before)


@pytest.mark.parametrize('status',['PENDING','UNKNOWN','FAILED'])
def test_EP_G2_prior_operation_is_not_a_new_first_attempt(flow_engine,identities,enabled,request,status):
    from returnops_domain.audit import identifier,timestamp
    from returnops_domain.lifecycle_effects import fingerprint
    from synthetic_sources import stage,head
    arguments,setup=ready(flow_engine,identities)
    scope=setup['action']['scope']; command=scope['commands'][0]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        h=head(uow,arguments['case_id'])
        body=dict(operation_id=identifier('earlier_operation'),case_id=h['case_id'],case_version=h['case_version'],
            command_id=command['command_id'],approval_id=setup['result'].receipt['approval_id'],
            proposal_id=scope['proposal_id'],proposal_version=scope['proposal_version'],input_version=scope['input_version'],
            provider_id=command['provider_id'],operation_fingerprint=fingerprint(dict(approval_id=setup['result'].receipt['approval_id'],
                scope_fingerprint=setup['action']['scope_fingerprint'],command=command)),status=status,attempt_count=0,
            updated_at=timestamp(datetime.now(timezone.utc)),idempotency_key='earlier-original-key')
        if status in {'UNKNOWN','FAILED'}:
            body['error']={'error':dict(code='PROVIDER_UNAVAILABLE',message='Synthetic prior operation.',
                correlation_id='earlier-correlation',retryable=False,details=[])}
        stage(uow,h,'OPERATION',body); uow.commit()
    result=unchanged(flow_engine,service(flow_engine,identities),arguments,'UNKNOWN' if status=='UNKNOWN' else 'DENIED')
    assert rows(flow_engine,preparations)==[]
    evidence(request.node.nodeid,prior_status=status,legacy_count=0,result=asdict(result))


def test_EP_G3_orphan_sidecar_cannot_borrow_approval_history_as_first_operation(flow_engine,identities,enabled):
    from returnops_domain.execution_preparation_sources import identities as stable_ids,request_fingerprint
    arguments,setup=ready(flow_engine,identities)
    record=current_history(flow_engine,arguments['case_id'],'APPROVAL')
    fact,=[r for r in rows(flow_engine,old.acceptances) if r['target']==arguments['case_id'] and r['operation']=='recordFounderDecision']
    event,=[r for r in rows(flow_engine,old.audit) if r['case_id']==arguments['case_id'] and r['sequence']==1]
    identity=stable_ids(arguments['execution_work_id'])
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(preparations.insert().values(**{**identity,'first_operation_record_id':record['record_id']},
            case_id=arguments['case_id'],approval_execution_work_id=arguments['execution_work_id'],
            original_approval_acceptance_id=fact['acceptance_id'],command_type='CREATE_RETURN',
            request_fingerprint=request_fingerprint(arguments['candidate_command']),profile_hash='0'*64,
            prepared_authority_revision=1,binding_hash='0'*64,origin_audit_event_id=event['event_id'],
            created_at=datetime.now(timezone.utc),state='PENDING'))
        uow.commit()
    unchanged(flow_engine,service(flow_engine,identities),arguments)


@pytest.mark.parametrize('already_prepared',[False,True])
def test_EP_G3_orphan_operation_audit_cannot_be_ignored(flow_engine,identities,enabled,already_prepared):
    from returnops_domain.audit import append_event
    arguments,_=ready(flow_engine,identities); caller=service(flow_engine,identities)
    if already_prepared: assert caller.prepare(**arguments).status=='PREPARED'
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        append_event(uow,arguments['case_id'],actor={'kind':'SERVICE','component_id':'founder-approve-v1'},
            event_type='OPERATION_REVISION_RECORDED',correlation_id='orphan-audit-correlation',payload={},
            object_ids=['orphan-operation'],history_refs=[],now=datetime.now(timezone.utc))
        uow.commit()
    unchanged(flow_engine,caller,arguments)


@pytest.mark.parametrize('flow_engine',[APPROVAL],indirect=True)
def test_EP_G1_upgrade_requires_complete_original_0009_descriptor(flow_engine,request):
    from conftest import migrate
    with flow_engine.begin() as connection:
        connection.execute(text('ALTER TABLE lifecycle_action_previews DROP CONSTRAINT ck_preview_expiry'))
    before=snapshot(flow_engine)
    with pytest.raises(RuntimeError,match='exact 0009'):
        migrate(flow_engine,PREPARATION)
    assert snapshot(flow_engine)==before and preparations.name not in inspect(flow_engine).get_table_names()
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),upgrade_rejected=True)
