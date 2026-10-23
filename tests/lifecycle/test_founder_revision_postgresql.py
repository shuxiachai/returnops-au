"""REV-01..08 real service acceptance; old guard fixtures remain separate."""
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from sqlalchemy import delete, select, update
from returnops_domain import customer_tables as old, lifecycle_tables as t
from returnops_domain.audit import identifier
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.revision_denial import COMPONENT, OPERATION
from returnops_domain.registry import TrustedRegistry
from manual_helpers import rows, snapshot, business, evidence, now, provision_outcome
from revision_helpers import ready, provision, service, attempt, assert_revised, mutate_authority, mutate_source
from test_manual_postgresql import observed, expire_human, UnknownCommit, installed_manual


def test_REV01_actual_proposal_review_human_revision(flow_engine, identities, enabled, observed, request):
    case, body = ready(flow_engine, identities)
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body)
    assert_revised(flow_engine, case, body, result)
    after = snapshot(flow_engine)
    assert after['lifecycle_authorities'] == before['lifecycle_authorities']
    assert after['case_heads'][0]['input_version'] == before['case_heads'][0]['input_version']
    assert after['case_lifecycle_state'][0]['generation'] == before['case_lifecycle_state'][0]['generation']+1
    decision, = [r for r in rows(flow_engine, old.history) if r['kind'] == 'DECISION']
    binding = next(r for r in rows(flow_engine, t.sources) if r['record_id'] == decision['record_id'])
    assert binding['target_record_id'] == before['case_lifecycle_state'][0]['review_record_id']
    assert all(r in after['customer_history_revisions'] for r in before['customer_history_revisions'])
    fact, = [r for r in rows(flow_engine, old.acceptances) if r['operation'] == OPERATION]
    assert fact['response_status'] == 200
    event = next(r for r in rows(flow_engine, t.events) if r['record_id'] == decision['record_id'])
    assert event['event_kind'] == 'REVISION' and event['status'] == 'POLICY_ASSESSMENT'
    assert len(after['customer_audit_events']) == len(before['customer_audit_events'])+2
    evidence(request.node.nodeid, before=before, after=after, result=asdict(result), effects=observed)



AUTH = ['human_revoked','human_disabled','human_demoted','human_store','owner','service_missing','service_revoked']
@pytest.mark.parametrize('mode', AUTH)
@pytest.mark.parametrize('phase', ['entry','final'])
def test_REV02_independent_current_authorities(flow_engine, identities, enabled, request, mode, phase):
    case, body = ready(flow_engine, identities)
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            mutate_authority(uow, identities, case, mode); uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':mutate_authority(self, identities, case, mode)
            return super().commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, uow_factory=Changed)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    if phase == 'entry' and mode != 'owner':assert result.audit == 'NOT_RECORDED'
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('mode', ['service_revision','claim','epoch','lease','authority','generation','human_expiry','lease_expiry'])
def test_REV02_final_original_claim(flow_engine, identities, enabled, request, monkeypatch, mode):
    case, body = ready(flow_engine, identities)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if mode == 'human_expiry':expire_human(monkeypatch)
            elif mode == 'lease_expiry':caller.guard.clock = lambda:now()+timedelta(seconds=1000)
            else:mutate_authority(self, identities, case, mode)
            return super().commit()
    caller = service(flow_engine, identities, uow_factory=Changed)
    before = snapshot(flow_engine); result = caller.accept(case, body, 'original-revision-key', 'revision_correlation')
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


SOURCES = ['review_event','proposal_event','review_binding','review_claim','review_generation','review_projection',
    'review_body','proposal_body','order_raw','order_claim','order_available','raw_statement','input','generation','preview','failure','block']
@pytest.mark.parametrize('mode', SOURCES)
@pytest.mark.parametrize('phase', ['entry','final'])
def test_REV02_retained_source_chain(flow_engine, identities, enabled, request, mode, phase):
    case, body = ready(flow_engine, identities)
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:mutate_source(uow, mode); uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':mutate_source(self, mode)
            return super().commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, uow_factory=Changed)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('mode', ['wrong_id','wrong_version','stale','actor','generation','review','grant','failure_target',
    'APPROVE','REJECT','MANUAL_HANDLING','AWAITING_APPROVAL','RISK_REVIEW','NOTIFICATION_PENDING'])
def test_REV02_request_and_state_scope(flow_engine, identities, enabled, request, mode):
    case, body = ready(flow_engine, identities)
    if mode == 'wrong_id':body['proposal_id'] = 'wrong_proposal'
    elif mode == 'wrong_version':body['proposal_version'] += 1
    elif mode == 'stale':body['expected_case_version'] -= 1
    elif mode in {'actor','generation','review','grant'}:body[mode] = 'injected'
    elif mode == 'failure_target':
        body.pop('proposal_id'); body.pop('proposal_version'); body['processing_failure_id'] = 'failure_target'
    elif mode in {'APPROVE','REJECT','MANUAL_HANDLING'}:body['decision'] = mode
    else:
        with flow_engine.begin() as c:c.execute(update(old.case_heads).values(status=mode))
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('layer', ['service','guard'])
@pytest.mark.parametrize('mode', ['human_expiry','lease_expiry','human_revoked','service_revision'])
def test_REV02_after_last_source_read(flow_engine, identities, enabled, request, monkeypatch, layer, mode):
    from returnops_domain import revision_decision, revision_sources
    case, body = ready(flow_engine, identities)
    module = revision_decision if layer == 'service' else revision_sources
    original = module.read_target
    injected = []
    def delayed(uow, head, state, request_body, component, **options):
        value = original(uow, head, state, request_body, component, **options)
        if options.get('original_state') is not None:
            if mode == 'human_expiry':expire_human(monkeypatch)
            elif mode == 'lease_expiry':caller.clock = caller.guard.clock = lambda:now()+timedelta(seconds=1000)
            elif mode == 'raw_statement':mutate_source(uow, mode)
            else:mutate_authority(uow, identities, case, mode)
            injected.append(mode)
        return value
    monkeypatch.setattr(module, 'read_target', delayed)
    caller = service(flow_engine, identities)
    before = snapshot(flow_engine); result = caller.accept(case, body, 'original-revision-key', 'revision_correlation')
    assert injected and result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=injected)


@pytest.mark.parametrize('phase', ['entry','final'])
@pytest.mark.parametrize('mode', ['review_event','raw_statement','review_binding'])
def test_REV02_lowlevel_cannot_bypass_source_proof(flow_engine, identities, enabled, request, monkeypatch, phase, mode):
    from returnops_domain import revision_decision
    from returnops_domain.lifecycle_state import current
    case, body = ready(flow_engine, identities)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        h = uow.execute(select(old.case_heads)).mappings().one()
        seal = revision_decision.read_target(uow, h, current(uow,h), body, COMPONENT)
    monkeypatch.setattr(revision_decision, 'read_target', lambda *args, **kwargs:seal)
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:mutate_source(uow,mode); uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':mutate_source(self,mode)
            return super().commit()
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body, uow_factory=Changed)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), outer_check='bypassed deliberately')


def test_REV03_replay_conflicts_and_later_real_generation(flow_engine, identities, enabled, observed, request):
    from returnops_domain.proposal_processor import FixedProposalProcessor
    from controlled_escalate_reviewer import receiver
    from manual_helpers import service as manual
    case, body = ready(flow_engine, identities); caller = service(flow_engine, identities)
    accepted = caller.accept(case,body,'original-revision-key','first_revision'); assert_revised(flow_engine,case,body,accepted)
    before = snapshot(flow_engine)
    assert caller.accept(case,body,'original-revision-key','replay').receipt == accepted.receipt
    assert caller.recover(case,body,'original-revision-key').receipt == accepted.receipt
    assert snapshot(flow_engine) == before
    for field, value in [('reason','changed'),('expected_case_version',body['expected_case_version']+1),
                         ('proposal_id','changed'),('proposal_version',body['proposal_version']+1)]:
        result = caller.accept(case,{**body,field:value},'original-revision-key','conflict')
        assert result.status == 'DENIED' and result.safe_code == 'IDEMPOTENCY_CONFLICT'
    provision_outcome(flow_engine,identities)
    conflict = manual(flow_engine,identities).accept(case,{**body,'decision':'MANUAL_HANDLING'},'original-revision-key','cross_decision')
    assert conflict.status == 'DENIED' and conflict.safe_code == 'IDEMPOTENCY_CONFLICT'
    replacement = caller.accept(case,{**body,'expected_case_version':body['expected_case_version']+1},'replacement-key','replacement')
    assert replacement.status == 'DENIED'
    # Explicit test caller produces a later real generation; revision never does.
    processor = FixedProposalProcessor(flow_engine)
    assert processor.process(processor.prepare(case)).status == 'ACCEPTED'
    h = rows(flow_engine,old.case_heads)[0]
    assert receiver(flow_engine).accept(case,h['case_version'],'second-review-key','second_review').status == 'ACCEPTED'
    advanced = snapshot(flow_engine)
    assert caller.accept(case,body,'original-revision-key','old_receipt').receipt == accepted.receipt
    assert snapshot(flow_engine) == advanced
    evidence(request.node.nodeid, before=before, advanced=advanced, accepted=asdict(accepted), cross_decision=asdict(conflict), effects=observed)


@pytest.mark.parametrize('first', ['revision','manual'])
def test_REV04_both_serial_orders_and_cross_decision_key(flow_engine, identities, enabled, observed, request, first):
    from manual_helpers import service as manual
    case, body = ready(flow_engine,identities); provision_outcome(flow_engine,identities)
    calls = dict(revision=service(flow_engine,identities),manual=manual(flow_engine,identities))
    requests = dict(revision=body,manual={**body,'decision':'MANUAL_HANDLING'})
    second = 'manual' if first == 'revision' else 'revision'
    result = calls[first].accept(case,requests[first],'shared-decision-key','first')
    assert result.status == 'ACCEPTED'
    before = snapshot(flow_engine)
    conflict = calls[second].accept(case,requests[second],'shared-decision-key','conflict')
    late = calls[second].accept(case,requests[second],'different-decision-key','late')
    assert conflict.safe_code == 'IDEMPOTENCY_CONFLICT' and conflict.status == 'DENIED' and late.status == 'DENIED'
    assert business(snapshot(flow_engine)) == business(before)
    assert len([r for r in rows(flow_engine,old.history) if r['kind']=='DECISION']) == 1
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), first=asdict(result), late=asdict(late), conflict=asdict(conflict), effects=observed)


def child_config(engine, identities, case, body):
    c = identities.auth_config
    return dict(case=case,request=body,schema=engine._customer_test_schema,issuer=c.issuer,audience=c.audience,
        signing_key=c.signing_key.hex(),token=identities.tokens['founder'])


def test_REV04_independent_process_same_key(flow_engine, identities, enabled, request, tmp_path):
    case,body=ready(flow_engine,identities)
    path=tmp_path/'synthetic-revision-child.json';path.write_text(json.dumps(child_config(flow_engine,identities,case,body)),encoding='utf-8')
    args=[sys.executable,'-B',str(Path(__file__).with_name('revision_process_probe.py')),str(path)]
    before=snapshot(flow_engine)
    children=[subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=os.environ.copy()) for _ in range(2)]
    outputs=[]
    for child in children:
        out,err=child.communicate(timeout=60)
        assert child.returncode==0 and err==b''
        outputs.append(json.loads(out))
    diagnostics=json.dumps([{name:x.get(name) for name in ('status','safe_code','audit','revision_claims','attempts')} for x in outputs],sort_keys=True)
    for x in outputs:
        assert 1<=len(x['attempts'])<=3 and x['attempts'][-1]['status']==x['status'], diagnostics
        for earlier in x['attempts'][:-1]:
            assert (earlier['status'],earlier['safe_code'])==('DENIED','INTERNAL_ERROR'), diagnostics
    assert all(x['status']=='ACCEPTED' and not any(x['effects'].values()) for x in outputs), diagnostics
    assert outputs[0]['receipt']==outputs[1]['receipt'] and sum(x['revision_claims'] for x in outputs)==1, diagnostics
    assert len([r for r in rows(flow_engine,old.acceptances) if r['operation']==OPERATION])==1
    assert len([r for r in rows(flow_engine,t.events) if r['event_kind']=='REVISION'])==1
    assert snapshot(flow_engine)['lifecycle_authorities']==before['lifecycle_authorities']
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),outputs=outputs,independent_processes=2)


@pytest.mark.parametrize('committed',[True,False])
@pytest.mark.parametrize('revoked',[True,False])
def test_REV05_unknown_and_fresh_recovery(flow_engine,identities,enabled,request,committed,revoked):
    case,body=ready(flow_engine,identities)
    class Unknown(UnknownCommit):actual_commit=committed
    caller=service(flow_engine,identities,uow_factory=Unknown)
    before=snapshot(flow_engine); result=caller.accept(case,body,'original-revision-key','unknown')
    assert result.status=='UNKNOWN' and result.audit=='NOT_ATTEMPTED'
    actual=snapshot(flow_engine)
    assert len([r for r in rows(flow_engine,old.acceptances) if r['operation']==OPERATION])==int(committed)
    if not committed:assert actual==before
    if revoked:TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    recovery_before=snapshot(flow_engine); recovered=caller.recover(case,body,'original-revision-key')
    assert snapshot(flow_engine)==recovery_before and recovered.audit=='NOT_ATTEMPTED'
    assert recovered.status==('ACCEPTED' if committed and not revoked else 'UNKNOWN')
    retry=None
    if not committed and not revoked:
        # Independently completed actual rollback plus every-table equality;
        # recovery's absence alone does not permit this explicit caller action.
        retry=attempt(flow_engine,identities,case,body);assert_revised(flow_engine,case,body,retry)
    evidence(request.node.nodeid,before=before,actual=actual,result=asdict(result),recovered=asdict(recovered),
        retry=None if retry is None else asdict(retry),completion_proof='actual commit' if committed else 'actual rollback + all table equality')


def test_REV05_absence_remains_unknown(flow_engine,identities,enabled,request):
    case,body=ready(flow_engine,identities); before=snapshot(flow_engine)
    result=service(flow_engine,identities).recover(case,body,'never-observed-key')
    assert result.status=='UNKNOWN' and result.audit=='NOT_ATTEMPTED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),rollback_proof=False)


def test_REV05_every_write_and_final_rolls_back(flow_engine,identities,enabled,observed,request):
    case,body=ready(flow_engine,identities); trace=[]
    class Probe(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                trace.append(statement.table.name+(' INSERT' if statement.is_insert else ' UPDATE' if statement.is_update else ' DELETE'))
            return super().execute(statement,parameters)
        def commit(self):
            for check in self._commit_checks:check()
            self.poison();raise FlowError('INVALID_STATE')
    before=snapshot(flow_engine); result=attempt(flow_engine,identities,case,body,uow_factory=Probe)
    assert result.status=='DENIED' and len(trace)>=15 and business(snapshot(flow_engine))==business(before)
    results=[]
    for point in range(1,len(trace)+1):
        class Fault(CustomerUnitOfWork):
            writes=0
            def execute(self,statement,parameters=None):
                if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                    self.writes+=1
                    if self.writes==point:self.poison();raise RuntimeError('RAW-SENSITIVE-FAULT')
                return super().execute(statement,parameters)
        before=snapshot(flow_engine); result=attempt(flow_engine,identities,case,body,uow_factory=Fault); after=snapshot(flow_engine)
        assert result.status=='DENIED' and business(after)==business(before) and 'RAW-SENSITIVE' not in str(asdict(result))
        results.append(dict(point=point,write=trace[point-1],before=before,after=after,result=asdict(result)))
    evidence(request.node.nodeid,trace=trace,results=results,effects=observed)


@pytest.mark.parametrize('mode',['recorded','revoked','audit_committed_unknown','audit_rolledback_unknown'])
def test_REV05_fresh_denial_after_original_closed(flow_engine,identities,enabled,request,mode):
    case,body=ready(flow_engine,identities)
    class Original(CustomerUnitOfWork):
        exited=False
        def __exit__(self,*args):
            result=super().__exit__(*args);type(self).exited=True
            if mode=='revoked':TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
            return result
    class Audit(UnknownCommit if 'unknown' in mode else CustomerUnitOfWork):
        actual_commit=mode=='audit_committed_unknown';enters=0
        def __enter__(self):
            assert Original.exited;type(self).enters+=1;return super().__enter__()
    before=snapshot(flow_engine)
    result=attempt(flow_engine,identities,case,{**body,'expected_case_version':body['expected_case_version']-1},uow_factory=Original,audit_uow=Audit)
    after=snapshot(flow_engine)
    assert result.status=='DENIED' and Audit.enters==1
    assert result.audit==('RECORDED' if mode=='recorded' else 'NOT_RECORDED' if mode=='revoked' else 'UNKNOWN')
    assert len(after['customer_audit_events'])-len(before['customer_audit_events'])==int(mode in {'recorded','audit_committed_unknown'})
    if mode!='revoked':assert business(after)==business(before)
    from returnops_domain.canonical import decode_document,digest
    for row in rows(flow_engine,old.audit):
        event=decode_document(row['body'])
        if event['event_type']=='FOUNDER_REVISION_DENIED':
            assert event['payload_hash']==digest(dict(purpose='REVISION',reason='STALE_CASE_VERSION'),'audit-payload/v1')
            assert event['history_refs']==[] and event['object_ids']==[] and 'payload' not in event
    evidence(request.node.nodeid,before=before,after=after,result=asdict(result),audit_enters=Audit.enters)


@pytest.mark.parametrize('removed',['STATEMENT','EVIDENCE'])
def test_REV06_retention_no_reconstruction(flow_engine,identities,enabled,request,removed):
    from io import BytesIO
    from pypdf import PdfWriter
    from returnops_domain.evidence_validation import validate_evidence
    from returnops_domain.retention import RetentionService
    b=BytesIO();p=PdfWriter();p.add_blank_page(width=100,height=100);p.write(b)
    eid=identities.flow().stage(validate_evidence(b.getvalue(),'revision.pdf','application/pdf'),'revision-upload-key','upload_corr').body['evidence_id']
    case,body=ready(flow_engine,identities,evidence_ids=[eid]);caller=service(flow_engine,identities)
    accepted=caller.accept(case,body,'original-revision-key','revision');assert_revised(flow_engine,case,body,accepted)
    before=snapshot(flow_engine)
    oid=eid if removed=='EVIDENCE' else next(r['object_id'] for r in rows(flow_engine,old.history) if r['kind']=='STATEMENT')
    RetentionService(flow_engine).remove(removed,oid);retained=snapshot(flow_engine)
    replay=caller.accept(case,body,'original-revision-key','retained');recovered=caller.recover(case,body,'original-revision-key')
    assert replay.status=='DENIED' and recovered.status=='UNKNOWN' and snapshot(flow_engine)==retained
    ids={r['record_id'] for r in rows(flow_engine,old.history) if r['kind'] in {'PROPOSAL','REVIEW','DECISION'}}
    assert not any(r['record_id'] in ids for r in rows(flow_engine,old.history_contents))
    assert all(r['body'] is None for r in rows(flow_engine,old.receipts) if not r['available'])
    evidence(request.node.nodeid,before=before,retained=retained,replay=asdict(replay),recovery=asdict(recovered))


def test_REV06_founder_current_history_read_only(flow_engine,identities,enabled,request):
    from returnops_api.customer_authority import CurrentRequestAuthority
    from returnops_domain.founder_service import FounderQueries
    case,body=ready(flow_engine,identities);accepted=attempt(flow_engine,identities,case,body);assert_revised(flow_engine,case,body,accepted)
    reader=FounderQueries(flow_engine,CurrentRequestAuthority(identities.auth_config,'Bearer '+identities.tokens['founder']))
    before=snapshot(flow_engine);detail=reader.read('getFounderCase',case).body
    assert 'current_review' not in detail and 'current_proposal' not in detail
    for kind in ['PROPOSAL','REVIEW','DECISION']:reader.read('listFounderCaseHistory',case,{'kind':kind})
    reader.read('listCaseAudit',case);after=snapshot(flow_engine)
    assert {k:v for k,v in before.items() if not k.startswith('founder_')}=={k:v for k,v in after.items() if not k.startswith('founder_')}
    evidence(request.node.nodeid,before=before,after=after,detail=detail)


def test_REV07_installed_actual_private_call(flow_engine,identities,enabled,request,tmp_path,installed_manual):
    case,body=ready(flow_engine,identities)
    path=tmp_path/'synthetic-revision-installed.json';path.write_text(json.dumps(child_config(flow_engine,identities,case,body)),encoding='utf-8')
    root=Path(__file__).resolve().parents[2];hashes={}
    modules=['revision_decision.py','revision_denial.py','revision_sources.py','lifecycle_guards.py','review_sources.py','lifecycle_proposal.py']
    for name in modules:
        source=root/'packages/returnops_domain'/name;target=installed_manual/'returnops_domain'/name
        assert source.read_bytes()==target.read_bytes();hashes[name]=sha256(target.read_bytes()).hexdigest()
    assert (root/'apps/api/returnops_api/private_revision.py').read_bytes()==(installed_manual/'returnops_api/private_revision.py').read_bytes()
    assert not (installed_manual/'tests').exists() and not (installed_manual/'revision_helpers.py').exists()
    before=snapshot(flow_engine)
    result=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).with_name('revision_process_probe.py')),str(path),str(installed_manual)],
        cwd=tmp_path,env=os.environ.copy(),capture_output=True,timeout=60)
    assert result.returncode==0 and result.stderr==b''
    output=json.loads(result.stdout)
    assert output['status']=='ACCEPTED' and output['revision_claims']==1 and not any(output['effects'].values())
    after=snapshot(flow_engine);assert after['lifecycle_authorities']==before['lifecycle_authorities']
    assert rows(flow_engine,old.case_heads)[0]['status']=='POLICY_ASSESSMENT' and not rows(flow_engine,t.effects)
    evidence(request.node.nodeid,before=before,after=after,output=output,installed_hashes=hashes,isolated_python=True,cwd=str(tmp_path))


def test_REV07_default_factory_no_grant_or_public_entry(flow_engine,identities,enabled,observed,request):
    from returnops_api.main import create_app
    case,body=ready(flow_engine,identities,grant=False)
    before=snapshot(flow_engine);app=create_app(engine=flow_engine,auth_config=identities.auth_config)
    assert not any('POST' in getattr(r,'methods',set()) and ('decision' in r.path or 'revision' in r.path) for r in app.routes)
    result=attempt(flow_engine,identities,case,body)
    assert result.status=='DENIED' and result.audit=='NOT_RECORDED' and snapshot(flow_engine)==before
    provision(flow_engine,identities);grants=rows(flow_engine,t.authorities)
    accepted=attempt(flow_engine,identities,case,body);assert_revised(flow_engine,case,body,accepted)
    assert rows(flow_engine,t.authorities)==grants
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),denied=asdict(result),accepted=asdict(accepted),effects=observed)


@pytest.mark.parametrize('phase',['entry','final'])
def test_REV02_primary_binding_requires_actual_review(flow_engine,identities,enabled,request,monkeypatch,phase):
    from returnops_domain import revision_decision
    case,body=ready(flow_engine,identities)
    proposal=next(r for r in rows(flow_engine,old.history) if r['kind']=='PROPOSAL')
    original=revision_decision.read_target
    if phase=='entry':
        def wrong(uow,*args,**kwargs):
            value=original(uow,*args,**kwargs)
            return {**value,'record':proposal}
        monkeypatch.setattr(revision_decision,'read_target',wrong)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase=='final':
                ids=select(t.work.c.work_id).where(t.work.c.component_id==COMPONENT)
                self.execute(update(t.sources).where(t.sources.c.work_id.in_(ids)).values(target_record_id=proposal['record_id']))
            return super().commit()
    before=snapshot(flow_engine);result=attempt(flow_engine,identities,case,body,uow_factory=Changed)
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),binding='proposal instead of accepted review')


def test_REV04_revision_invalidates_original_unfinished_work(flow_engine,identities,enabled,request):
    from returnops_domain.lifecycle_events import OutcomeAccepted
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from returnops_domain.manual_denial import COMPONENT as MANUAL
    case,body=ready(flow_engine,identities);provision_outcome(flow_engine,identities)
    guard=LifecycleGuards(MANUAL)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        wid=guard.prepare(uow,case,body['expected_case_version'],OutcomeAccepted,now())
        claim=guard.claim(uow,wid,now());uow.commit()
    before=snapshot(flow_engine);result=attempt(flow_engine,identities,case,body);assert_revised(flow_engine,case,body,result)
    after=snapshot(flow_engine);work=next(r for r in rows(flow_engine,t.work) if r['work_id']==wid)
    assert work['state']=='SUPERSEDED' and work['claim_id'] is None and work['epoch']==claim.epoch+1
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError):guard.apply(uow,OutcomeAccepted('late_manual_event',claim,'absent_decision','absent_note'),now())
        with pytest.raises(FlowError):uow.commit()
    assert snapshot(flow_engine)==after
    evidence(request.node.nodeid,before=before,after=after,result=asdict(result),original_claim=asdict(claim),superseded=work)


@pytest.mark.parametrize('mode',['target_hash','event_generation','event_fingerprint','binding_target','claim'])
def test_REV03_replay_requires_original_revision_proof(flow_engine,identities,enabled,request,mode):
    case,body=ready(flow_engine,identities);caller=service(flow_engine,identities)
    accepted=caller.accept(case,body,'original-revision-key','revision');assert_revised(flow_engine,case,body,accepted)
    with flow_engine.begin() as c:
        if mode=='target_hash':c.execute(update(t.work).where(t.work.c.component_id==COMPONENT).values(target_hash='0'*64))
        elif mode=='claim':c.execute(update(t.work).where(t.work.c.component_id==COMPONENT).values(claim_id='replaced'))
        elif mode=='binding_target':c.execute(update(t.sources).where(t.sources.c.work_id.in_(select(t.work.c.work_id).where(t.work.c.component_id==COMPONENT))).values(target_record_id='absent_review'))
        else:c.execute(update(t.events).where(t.events.c.event_kind=='REVISION').values(**({'generation':99} if mode=='event_generation' else {'fingerprint':'0'*64})))
    before=snapshot(flow_engine);result=caller.accept(case,body,'original-revision-key','replay')
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    assert caller.recover(case,body,'original-revision-key').status=='UNKNOWN'
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),corruption=mode)
