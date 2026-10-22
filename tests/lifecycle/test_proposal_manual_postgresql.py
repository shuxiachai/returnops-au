"""Real accepted ESCALATE then separate HUMAN/F.03 + OUTCOME manual entry."""
from dataclasses import asdict
from datetime import timedelta
import pytest
from sqlalchemy import delete,select,update
from returnops_domain import customer_tables as old,lifecycle_tables as t
from returnops_domain import founder_codec as finite
from returnops_domain.review_sources import COMPONENT
from controlled_escalate_reviewer import ready_manual,ready_review,receiver,ControlledReviewer
from manual_helpers import rows,snapshot,business,evidence,service,assert_pending,now
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.registry import TrustedRegistry
from test_manual_postgresql import mutate_authority,expire_human,observed,UnknownCommit,installed_manual


def test_group07_actual_review_then_separate_human_manual(flow_engine,identities,enabled,request):
    case,body=ready_manual(flow_engine,identities);before=snapshot(flow_engine)
    result=service(flow_engine,identities).accept(case,body,'original-manual-key','manual_correlation')
    assert_pending(flow_engine,case,body,result)
    after=snapshot(flow_engine);state=rows(flow_engine,t.state)[0]
    decision=next(r for r in rows(flow_engine,t.sources) if r['record_id']==state['outcome_record_id'])
    review=next(r for r in rows(flow_engine,t.sources) if r['record_id']==state['review_record_id'])
    assert decision['target_record_id']==review['record_id'] and review['target_record_id']==state['proposal_record_id']
    assert after['lifecycle_authorities']==before['lifecycle_authorities']
    assert state['generation']==before['case_lifecycle_state'][0]['generation']
    assert rows(flow_engine,old.case_heads)[0]['input_version']==before['case_heads'][0]['input_version']
    evidence(request.node.nodeid,before=before,after=after,result=asdict(result),review_claim=review,independent_outcome_claim=decision)


@pytest.mark.parametrize('mode',['wrong_id','wrong_version','mixed','actor','input','generation','preview','stale',
    'missing_review_event','missing_review_binding','review_claim','review_generation','review_projection','review_bytes',
    'review_hash','missing_proposal_event','AWAITING_APPROVAL','RISK_REVIEW','NOTIFICATION_PENDING'])
def test_group08_proposal_requires_accepted_review(flow_engine,identities,enabled,request,mode):
    case,body=ready_manual(flow_engine,identities)
    state=rows(flow_engine,t.state)[0];rid=state['review_record_id']
    if mode=='wrong_id':body['proposal_id']='wrong_proposal'
    elif mode=='wrong_version':body['proposal_version']+=1
    elif mode=='mixed':body['processing_failure_id']='injected_failure'
    elif mode in {'actor','input','generation','preview'}:body[mode]=1
    elif mode=='stale':body['expected_case_version']-=1
    else:
        with flow_engine.begin() as c:
            if mode=='missing_review_event':c.execute(delete(t.events).where(t.events.c.record_id==rid))
            elif mode=='missing_review_binding':c.execute(delete(t.sources).where(t.sources.c.record_id==rid))
            elif mode=='missing_proposal_event':c.execute(delete(t.events).where(t.events.c.record_id==state['proposal_record_id']))
            elif mode in {'review_claim','review_generation'}:c.execute(update(t.work).where(t.work.c.purpose=='REVIEW').values(
                **({'claim_id':'false_claim'} if mode=='review_claim' else {'generation':999})))
            elif mode=='review_projection':c.execute(update(t.sources).where(t.sources.c.record_id==rid).values(order_projection_id=None))
            elif mode=='review_bytes':c.execute(update(old.history_contents).where(old.history_contents.c.record_id==rid).values(body=b'{}'))
            elif mode=='review_hash':c.execute(update(t.events).where(t.events.c.record_id==rid).values(source_hash='0'*64))
            else:c.execute(update(old.case_heads).values(status=mode))
    before=snapshot(flow_engine);result=service(flow_engine,identities).accept(case,body,'original-manual-key','manual_correlation')
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),negative_fixture=mode)


def test_group08_lowlevel_outcome_does_not_trust_outer_service_check(flow_engine,identities,enabled,request,monkeypatch):
    from returnops_domain import manual_decision
    case,body=ready_manual(flow_engine,identities);rid=rows(flow_engine,t.state)[0]['review_record_id']
    review=next(r for r in rows(flow_engine,old.history) if r['record_id']==rid)
    with flow_engine.begin() as c:c.execute(delete(t.events).where(t.events.c.record_id==rid))
    monkeypatch.setattr(manual_decision,'read_target',lambda *args,**kwargs:dict(record=review))
    before=snapshot(flow_engine);result=service(flow_engine,identities).accept(case,body,'original-manual-key','bypass_correlation')
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),
        outer_check='deliberately bypassed; real low-level OutcomeAccepted guard rejects absent REVIEW receipt')


@pytest.mark.parametrize('mode',['missing_receipt','wrong_kind','accepted_escalate'])
def test_group08_modern_awaiting_nonempty_review_cannot_use_legacy_edge(flow_engine,identities,enabled,request,mode):
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from returnops_domain.lifecycle_events import OutcomeAccepted
    from returnops_domain.manual_denial import COMPONENT as manual_component
    from returnops_domain.manual_decision import FounderDecisionService
    from returnops_domain.audit import identifier,timestamp
    case,request_body=ready_manual(flow_engine,identities);state=rows(flow_engine,t.state)[0]
    rid=state['review_record_id']
    with flow_engine.begin() as c:
        c.execute(update(old.case_heads).values(status='AWAITING_APPROVAL'))  # Explicit negative state mismatch.
        if mode=='missing_receipt':c.execute(delete(t.events).where(t.events.c.record_id==rid))
        elif mode=='wrong_kind':c.execute(update(t.events).where(t.events.c.record_id==rid).values(event_kind='REVISION'))
    before=snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        head=uow.execute(select(old.case_heads).where(old.case_heads.c.case_id==case)).mappings().one()
        guard=LifecycleGuards(manual_component)
        work=guard.prepare(uow,case,head['case_version'],OutcomeAccepted,now());claim=guard.claim(uow,work,now())
        decision=dict(decision_id=identifier('manual_decision'),case_id=case,decision='MANUAL_HANDLING',
            principal_id=identities.people['founder']['principal_id'],reason='Explicit low-level negative.',decided_at=timestamp(now()),
            proposal_id=request_body['proposal_id'],proposal_version=request_body['proposal_version'])
        record,content_hash=FounderDecisionService._append(uow,case,'DECISION',decision,
            {'kind':'HUMAN','role':'FOUNDER','principal_id':decision['principal_id']},'negative_correlation',now())
        uow.execute(t.sources.insert().values(record_id=record,case_id=case,**asdict(claim),source_hash=content_hash,
            target_record_id=rid,slot='PRIMARY'))
        note=dict(notification_id=identifier('manual_note'),case_id=case,case_version=head['case_version'],status='PENDING',
            outcome='MANUAL_HANDLED',message='Manual handling pending.',next_steps=[],attempt_count=0,updated_at=timestamp(now()))
        note_id,note_hash=FounderDecisionService._append(uow,case,'NOTIFICATION',note,
            {'kind':'SERVICE','component_id':manual_component},'negative_note',now())
        uow.execute(t.sources.insert().values(record_id=note_id,case_id=case,**asdict(claim),source_hash=note_hash,
            target_record_id=record,slot='NOTIFICATION'))
        with pytest.raises(FlowError):guard.apply(uow,OutcomeAccepted(identifier('manual_event'),claim,record,note_id),now())
        with pytest.raises(FlowError):uow.commit()
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),modern_negative=mode,
        retained_review='schema-valid original body, deliberate missing/wrong receipt or ESCALATE paired with wrong state')


def test_group08_modern_ghost_pass_execution_is_not_accepted_escalation(flow_engine,identities,enabled,request):
    from synthetic_sources import ready,outcome
    from synthetic_effects import existing_execution
    case=ready(flow_engine,identities)['case_id'];existing_execution(flow_engine,identities,case)
    with flow_engine.begin() as c:c.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(status='ESCALATED'))
    before=snapshot(flow_engine)
    with pytest.raises(FlowError):outcome(flow_engine,identities,case)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),
        negative_fixture='old private synthetic PASS/approval/effect facts plus forced ESCALATED; never accepted modern REVIEW')


@pytest.mark.parametrize('mode',['human_revoked','human_disabled','human_demoted','human_store','owner',
    'service_missing','service_revoked','service_revision','claim','lease','human_expired','claim_expired'])
def test_group09_independent_authorities_final(flow_engine,identities,enabled,request,monkeypatch,mode):
    case,body=ready_manual(flow_engine,identities)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if mode=='human_expired':expire_human(monkeypatch)
            elif mode=='claim_expired':caller.guard.clock=lambda:now()+timedelta(seconds=1000)
            else:mutate_authority(self,identities,case,mode)
            return super().commit()
    caller=service(flow_engine,identities,uow_factory=Changed)
    before=snapshot(flow_engine);result=caller.accept(case,body,'original-manual-key','manual_correlation')
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


@pytest.mark.parametrize('mode',['human_revoked','human_disabled','human_demoted','human_store','service_missing','service_revoked'])
def test_group09_independent_authorities_entry(flow_engine,identities,enabled,request,mode):
    case,body=ready_manual(flow_engine,identities)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        mutate_authority(uow,identities,case,mode);uow.commit()
    before=snapshot(flow_engine);result=service(flow_engine,identities).accept(case,body,'original-manual-key','manual_correlation')
    assert result.status=='DENIED' and result.audit=='NOT_RECORDED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


@pytest.mark.parametrize('mode',['human_expiry','lease_expiry','human_revoked','grant_revision'])
def test_group09_final_expensive_read_rechecks(flow_engine,identities,enabled,request,monkeypatch,mode):
    from returnops_domain import manual_decision
    case,body=ready_manual(flow_engine,identities);original=manual_decision.read_target
    def delayed(uow,head,state,body,component,**options):
        value=original(uow,head,state,body,component,**options)
        if options.get('original_state') is not None:
            if mode=='human_expiry':expire_human(monkeypatch)
            elif mode=='lease_expiry':caller.clock=lambda:now()+timedelta(seconds=1000)
            else:mutate_authority(uow,identities,case,'human_revoked' if mode=='human_revoked' else 'service_revision')
        return value
    monkeypatch.setattr(manual_decision,'read_target',delayed)
    caller=service(flow_engine,identities);before=snapshot(flow_engine)
    result=caller.accept(case,body,'original-manual-key','manual_correlation')
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


def test_groups09_16_historical_reviewer_is_not_current_authority(flow_engine,identities,enabled,request):
    from returnops_api.customer_authority import CurrentRequestAuthority
    from returnops_domain.founder_service import FounderQueries
    case,body=ready_manual(flow_engine,identities)
    with flow_engine.begin() as c:c.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(enabled=False,revision=2))
    before=snapshot(flow_engine);result=service(flow_engine,identities).accept(case,body,'original-manual-key','manual_correlation')
    assert_pending(flow_engine,case,body,result)
    reader=FounderQueries(flow_engine,CurrentRequestAuthority(identities.auth_config,'Bearer '+identities.tokens['founder']))
    read_before=snapshot(flow_engine)
    detail=reader.read('getFounderCase',case).body
    assert detail['current_review']['outcome']=='ESCALATE'
    reader.read('listFounderCaseHistory',case,{'kind':'REVIEW'});reader.read('listCaseAudit',case)
    read_after=snapshot(flow_engine)
    assert {k:v for k,v in read_before.items() if not k.startswith('founder_')}=={k:v for k,v in read_after.items() if not k.startswith('founder_')}
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),read_before=read_before,read_after=read_after)


def test_group10_original_keys_replay_after_manual(flow_engine,identities,enabled,request,observed):
    case,version=ready_review(flow_engine,identities);adapter=ControlledReviewer();reviewer=receiver(flow_engine,adapter)
    review=reviewer.accept(case,version,'original-review-key','review_correlation');assert review.status=='ACCEPTED'
    from manual_helpers import provision_outcome
    provision_outcome(flow_engine,identities)
    proposal=next(r for r in rows(flow_engine,old.history) if r['kind']=='PROPOSAL')
    body=dict(expected_case_version=version+1,decision='MANUAL_HANDLING',reason='Explicit manual.',
        proposal_id=proposal['object_id'],proposal_version=proposal['object_version'])
    caller=service(flow_engine,identities);manual=caller.accept(case,body,'original-manual-key','manual_correlation')
    assert_pending(flow_engine,case,body,manual);before=snapshot(flow_engine)
    assert reviewer.accept(case,version,'original-review-key','another_correlation').receipt==review.receipt
    assert caller.accept(case,body,'original-manual-key','another_correlation').receipt==manual.receipt
    assert snapshot(flow_engine)==before and len(adapter.calls)==1
    conflicts=[reviewer.accept(case,version+1,'original-review-key','review_correlation'),
        caller.accept(case,{**body,'reason':'changed'},'original-manual-key','manual_correlation')]
    assert all(r.status=='DENIED' and r.safe_code=='IDEMPOTENCY_CONFLICT' for r in conflicts)
    replacements=[reviewer.accept(case,version+2,'replacement-review-key','review_correlation'),
        caller.accept(case,{**body,'expected_case_version':version+2},'replacement-manual-key','manual_correlation')]
    assert all(r.status=='DENIED' for r in replacements)
    assert business(snapshot(flow_engine))==business(before) and len(adapter.calls)==1
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),review=asdict(review),manual=asdict(manual),
        conflicts=[asdict(r) for r in conflicts],replacement=[asdict(r) for r in replacements],effects=observed)


def prepare_entry(engine,identities,entry,**options):
    if entry=='review':
        case,body=ready_review(engine,identities)
        caller=receiver(engine,**options);key='original-review-key'
    else:
        case,body=ready_manual(engine,identities)
        caller=service(engine,identities,**options);key='original-manual-key'
    return case,body,caller,key


@pytest.mark.parametrize('entry',['review','manual'])
@pytest.mark.parametrize('committed',[True,False])
@pytest.mark.parametrize('revoked',[False,True])
def test_groups13_14_acceptance_unknown_actual_commit_or_rollback(flow_engine,identities,enabled,request,entry,committed,revoked):
    class Unknown(UnknownCommit):actual_commit=committed
    case,body,caller,key=prepare_entry(flow_engine,identities,entry,uow_factory=Unknown)
    before=snapshot(flow_engine);result=caller.accept(case,body,key,'unknown_correlation')
    assert result.status=='UNKNOWN' and result.audit=='NOT_ATTEMPTED'
    actual=snapshot(flow_engine)
    actual_records=[r for r in rows(flow_engine,t.events) if r['event_kind']==('REVIEW' if entry=='review' else 'OUTCOME')]
    assert len(actual_records)==int(committed)
    if not committed:assert actual==before
    if revoked:
        if entry=='manual':TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
        else:
            with flow_engine.begin() as c:c.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(enabled=False))
    recovery_before=snapshot(flow_engine);recovered=caller.recover(case,body,key)
    assert snapshot(flow_engine)==recovery_before and recovered.audit=='NOT_ATTEMPTED'
    if committed and not revoked:assert recovered.status=='ACCEPTED'
    else:assert recovered.status=='UNKNOWN' and recovered.receipt is None
    retry=None
    if not committed and not revoked:
        newcaller=receiver(flow_engine) if entry=='review' else service(flow_engine,identities)
        retry=newcaller.accept(case,body,key,'retry_correlation');assert retry.status=='ACCEPTED'
    evidence(request.node.nodeid,before=before,actual=actual,result=asdict(result),recovered=asdict(recovered),
        retry=None if retry is None else asdict(retry),actual_transaction='COMMIT' if committed else 'ROLLBACK')


@pytest.mark.parametrize('entry',['review','manual'])
def test_group14_absence_never_proves_rollback(flow_engine,identities,enabled,request,entry):
    case,body,caller,key=prepare_entry(flow_engine,identities,entry)
    before=snapshot(flow_engine);result=caller.recover(case,body,key)
    assert result.status=='UNKNOWN' and result.receipt is None and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),rollback_proof=False)


@pytest.mark.parametrize('entry',['review','manual'])
def test_group15_every_write_and_final_rollback(flow_engine,identities,enabled,request,observed,entry):
    case,body,_,key=prepare_entry(flow_engine,identities,entry)
    trace=[]
    class Probe(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                trace.append(statement.table.name+(' INSERT' if statement.is_insert else ' UPDATE' if statement.is_update else ' DELETE'))
            return super().execute(statement,parameters)
        def commit(self):
            for check in self._commit_checks:check()
            self.poison();raise FlowError('INVALID_STATE')
    def invoke(factory):
        caller=receiver(flow_engine,uow_factory=factory) if entry=='review' else service(flow_engine,identities,uow_factory=factory)
        return caller.accept(case,body,key,'fault_correlation')
    before=snapshot(flow_engine);probe=invoke(Probe)
    assert probe.status=='DENIED' and len(trace)>=10 and business(snapshot(flow_engine))==business(before)
    results=[]
    for point in range(1,len(trace)+1):
        class Fault(CustomerUnitOfWork):
            writes=0
            def execute(self,statement,parameters=None):
                if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                    self.writes+=1
                    if self.writes==point:
                        self.poison();raise RuntimeError('RAW-SQL-BODY-TOKEN-MUST-NOT-ESCAPE')
                return super().execute(statement,parameters)
        original=snapshot(flow_engine);result=invoke(Fault);after=snapshot(flow_engine)
        assert result.status=='DENIED' and business(original)==business(after)
        assert 'RAW-SQL' not in str(asdict(result))
        results.append(dict(point=point,statement=trace[point-1],before=original,after=after,result=asdict(result)))
    evidence(request.node.nodeid,before=before,trace=trace,probe=asdict(probe),faults=results,effects=observed)


@pytest.mark.parametrize('entry',['review','manual'])
@pytest.mark.parametrize('mode',['recorded','revoked','audit_committed_unknown','audit_rolledback_unknown'])
def test_group17_fresh_denial_after_close(flow_engine,identities,enabled,request,entry,mode):
    case,body,_,key=prepare_entry(flow_engine,identities,entry)
    class Original(CustomerUnitOfWork):
        exited=False
        def __exit__(self,*args):
            value=super().__exit__(*args);type(self).exited=True
            if mode=='revoked':
                if entry=='manual':TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
                else:
                    with flow_engine.begin() as c:c.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(enabled=False))
            return value
    class Audit(UnknownCommit if 'unknown' in mode else CustomerUnitOfWork):
        actual_commit=mode=='audit_committed_unknown';enters=0
        def __enter__(self):
            assert Original.exited;type(self).enters+=1;return super().__enter__()
    caller=receiver(flow_engine,uow_factory=Original,audit_uow=Audit) if entry=='review' else service(flow_engine,identities,uow_factory=Original,audit_uow=Audit)
    if entry=='review':body-=1
    else:body={**body,'expected_case_version':body['expected_case_version']-1}
    before=snapshot(flow_engine);result=caller.accept(case,body,key,'denial_correlation');after=snapshot(flow_engine)
    assert result.status=='DENIED' and Audit.enters==1
    assert result.audit==('RECORDED' if mode=='recorded' else 'NOT_RECORDED' if mode=='revoked' else 'UNKNOWN')
    assert len(after['customer_audit_events'])-len(before['customer_audit_events'])==int(mode in {'recorded','audit_committed_unknown'})
    if mode!='revoked':assert business(after)==business(before)
    from returnops_domain.canonical import decode_document,digest
    for row in rows(flow_engine,old.audit):
        event=decode_document(row['body'])
        if event['correlation_id'].startswith(('review_denial_','denial_corr_')):
            assert event['payload_hash']==digest(dict(purpose='REVIEW' if entry=='review' else 'OUTCOME',reason='STALE_CASE_VERSION'),'audit-payload/v1')
            assert event['history_refs']==[] and event['object_ids']==[] and 'payload' not in event
    evidence(request.node.nodeid,before=before,after=after,result=asdict(result),audit_enters=Audit.enters)


@pytest.mark.parametrize('removed',['STATEMENT','EVIDENCE'])
def test_group16_retention_no_reconstructed_review_or_receipt(flow_engine,identities,enabled,request,removed):
    from io import BytesIO
    from pypdf import PdfWriter
    from returnops_domain.evidence_validation import validate_evidence
    from returnops_domain.retention import RetentionService
    from manual_helpers import provision_outcome
    buffer=BytesIO();pdf=PdfWriter();pdf.add_blank_page(width=100,height=100);pdf.write(buffer)
    evidence_id=identities.flow().stage(validate_evidence(buffer.getvalue(),'proof.pdf','application/pdf'),'upload_evidence','upload_correlation').body['evidence_id']
    case,version=ready_review(flow_engine,identities,evidence_ids=[evidence_id]);reviewer=receiver(flow_engine)
    assert reviewer.accept(case,version,'original-review-key','review_correlation').status=='ACCEPTED'
    proposal=next(r for r in rows(flow_engine,old.history) if r['kind']=='PROPOSAL')
    body=dict(expected_case_version=version+1,decision='MANUAL_HANDLING',reason='Retained source manual.',
        proposal_id=proposal['object_id'],proposal_version=proposal['object_version'])
    provision_outcome(flow_engine,identities);caller=service(flow_engine,identities)
    manual=caller.accept(case,body,'original-manual-key','manual_correlation');assert_pending(flow_engine,case,body,manual)
    before=snapshot(flow_engine)
    object_id=evidence_id if removed=='EVIDENCE' else next(r['object_id'] for r in rows(flow_engine,old.history) if r['kind']=='STATEMENT')
    RetentionService(flow_engine).remove(removed,object_id)
    retained=snapshot(flow_engine)
    results=[reviewer.accept(case,version,'original-review-key','review_correlation'),caller.accept(case,body,'original-manual-key','manual_correlation')]
    assert all(r.status=='DENIED' for r in results) and snapshot(flow_engine)==retained
    assert reviewer.recover(case,version,'original-review-key').status=='UNKNOWN'
    assert caller.recover(case,body,'original-manual-key').status=='UNKNOWN'
    assert snapshot(flow_engine)==retained
    ids={r['record_id'] for r in rows(flow_engine,old.history) if r['kind'] in {'PROPOSAL','REVIEW','DECISION','NOTIFICATION'}}
    assert not any(r['record_id'] in ids for r in rows(flow_engine,old.history_contents))
    assert all(r['body'] is None for r in rows(flow_engine,old.receipts) if not r['available'])
    evidence(request.node.nodeid,before=before,retained=retained,results=[asdict(r) for r in results])


@pytest.mark.parametrize('mode',['deleted','wrong_kind'])
def test_group16_founder_current_review_requires_accepted_receipt(flow_engine,identities,enabled,request,mode):
    from returnops_api.customer_authority import CurrentRequestAuthority
    from returnops_domain.founder_service import FounderQueries
    case,body=ready_manual(flow_engine,identities);rid=rows(flow_engine,t.state)[0]['review_record_id']
    with flow_engine.begin() as c:
        if mode=='deleted':c.execute(delete(t.events).where(t.events.c.record_id==rid))
        else:c.execute(update(t.events).where(t.events.c.record_id==rid).values(event_kind='REVISION'))
    before=snapshot(flow_engine)
    reader=FounderQueries(flow_engine,CurrentRequestAuthority(identities.auth_config,'Bearer '+identities.tokens['founder']))
    with pytest.raises(FlowError):reader.read('getFounderCase',case)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),negative_receipt=mode)


def child_config(engine,identities,case,entry,*,body=None,version=None):
    config=identities.auth_config
    return dict(case=case,entry=entry,request=body,version=version,schema=engine._customer_test_schema,
        issuer=config.issuer,audience=config.audience,signing_key=config.signing_key.hex(),token=identities.tokens['founder'])


def _original_key_race_failure(outputs,entry):
    """Failure-only closed status vector; never render child data or replace the assertion."""
    fallback='Original-key race status diagnostic unavailable.'
    try:
        import json
        if type(outputs) is not list or len(outputs)!=2 or type(entry) is not str or entry not in {'review','manual'}:
            return fallback
        statuses={'ACCEPTED','DENIED','UNKNOWN'}
        codes={'UNAUTHENTICATED','FORBIDDEN','NOT_FOUND','VALIDATION_ERROR','STALE_CASE_VERSION',
            'IDEMPOTENCY_CONFLICT','INVALID_STATE','REQUEST_TOO_LARGE','UNSUPPORTED_MEDIA_TYPE','INTERNAL_ERROR'}
        callers=[]
        for index,output in enumerate(outputs):
            results=output.get('results') if type(output) is dict else None
            result=results.get(entry) if type(results) is dict else None
            status=result.get('status') if type(result) is dict else None
            code=result.get('safe_code') if type(result) is dict else 'OTHER'
            callers.append(dict(caller=index,
                status=status if type(status) is str and status in statuses else 'OTHER',
                safe_code=None if code is None else code if type(code) is str and code in codes else 'OTHER'))
        rendered=json.dumps({'callers':callers},ensure_ascii=True,separators=(',',':'))
        return rendered if len(rendered.encode('utf-8'))<=512 else fallback
    except Exception:
        return fallback


@pytest.mark.parametrize('entry',['review','manual'])
def test_group11_independent_process_original_key_race(flow_engine,identities,enabled,request,tmp_path,entry):
    import json,os,subprocess,sys
    from pathlib import Path
    case,body,_,_=prepare_entry(flow_engine,identities,entry)
    path=tmp_path/'synthetic-child-config.json'
    path.write_text(json.dumps(child_config(flow_engine,identities,case,entry,
        version=body if entry=='review' else None,body=body if entry=='manual' else None)),encoding='utf-8')
    args=[sys.executable,'-B',str(Path(__file__).with_name('review_manual_process_probe.py')),str(path)]
    before=snapshot(flow_engine)
    processes=[subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=os.environ.copy()) for _ in range(2)]
    outputs=[]
    for process in processes:
        out,err=process.communicate(timeout=60)
        assert process.returncode==0 and err==b''
        outputs.append(json.loads(out))
    assert all(x['results'][entry]['status']=='ACCEPTED' for x in outputs), _original_key_race_failure(outputs,entry)
    assert outputs[0]['results']==outputs[1]['results']
    assert sum(x['claims']['REVIEW' if entry=='review' else 'OUTCOME'] for x in outputs)==1
    assert sum(x['adapter_calls'] for x in outputs)==int(entry=='review')
    assert all(not any(x['effects'].values()) for x in outputs)
    assert len([r for r in rows(flow_engine,t.events) if r['event_kind']==('REVIEW' if entry=='review' else 'OUTCOME')])==1
    assert len([r for r in rows(flow_engine,t.work) if r['purpose']=='NOTIFICATION'])==int(entry=='manual')
    after=snapshot(flow_engine)
    assert after['lifecycle_authorities']==before['lifecycle_authorities']
    evidence(request.node.nodeid,before=before,after=after,outputs=outputs,actual_processes=2)


def test_group18_installed_wheel_actual_both_entries(flow_engine,identities,enabled,request,tmp_path,installed_manual):
    import json,os,subprocess,sys
    from pathlib import Path
    from hashlib import sha256
    from manual_helpers import provision_outcome
    case,version=ready_review(flow_engine,identities);provision_outcome(flow_engine,identities)
    proposal=next(r for r in rows(flow_engine,old.history) if r['kind']=='PROPOSAL')
    body=dict(expected_case_version=version+1,decision='MANUAL_HANDLING',reason='Installed private actual caller.',
        proposal_id=proposal['object_id'],proposal_version=proposal['object_version'])
    path=tmp_path/'synthetic-installed-config.json'
    path.write_text(json.dumps(child_config(flow_engine,identities,case,'both',body=body,version=version)),encoding='utf-8')
    root=Path(__file__).resolve().parents[2]
    hashes={}
    for name in ['review_escalation.py','review_sources.py','review_denial.py','lifecycle_schema.py','manual_decision.py','manual_target.py','lifecycle_guards.py']:
        source=root/'packages/returnops_domain'/name;installed=installed_manual/'returnops_domain'/name
        assert source.read_bytes()==installed.read_bytes();hashes[name]=sha256(installed.read_bytes()).hexdigest()
    assert not (installed_manual/'tests').exists() and not (installed_manual/'controlled_escalate_reviewer.py').exists()
    before=snapshot(flow_engine)
    result=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).with_name('review_manual_process_probe.py')),
        str(path),str(installed_manual)],cwd=tmp_path,env=os.environ.copy(),capture_output=True,timeout=60)
    assert result.returncode==0 and result.stderr==b''
    output=json.loads(result.stdout)
    assert all(r['status']=='ACCEPTED' for r in output['results'].values())
    assert output['claims']==dict(REVIEW=1,OUTCOME=1) and output['adapter_calls']==1 and not any(output['effects'].values())
    after=snapshot(flow_engine);assert after['lifecycle_authorities']==before['lifecycle_authorities']
    assert rows(flow_engine,old.case_heads)[0]['status']=='NOTIFICATION_PENDING' and not rows(flow_engine,t.effects)
    evidence(request.node.nodeid,before=before,after=after,output=output,installed_hashes=hashes,
        fixture='external explicit controlled synthetic adapter; not in wheel',isolated_python=True)


def test_group18_default_composition_no_grants_or_public_entry(flow_engine,identities,enabled,request,observed):
    from returnops_api.main import create_app
    case,version=ready_review(flow_engine,identities,grant=False)
    before=snapshot(flow_engine);app=create_app(engine=flow_engine,auth_config=identities.auth_config)
    assert not any('POST' in getattr(r,'methods',set()) and ('decision' in r.path or 'review' in r.path) for r in app.routes)
    result=receiver(flow_engine).accept(case,version,'original-review-key','review_correlation')
    assert result.status=='DENIED' and result.audit=='NOT_RECORDED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),effects=observed,default_routes=[r.path for r in app.routes])


def accepted_revision(engine,identities,case):
    """Explicit private revision fixture uses actual RevisionRequested guard."""
    from synthetic_sources import COMPONENT as synthetic,stage,bind_source,material,head
    from returnops_domain.lifecycle_events import RevisionRequested
    from returnops_domain.lifecycle_guards import LifecycleGuards
    with CustomerUnitOfWork(engine,write=True) as uow:
        if not uow.execute(select(t.authorities).where(t.authorities.c.component_id==synthetic,t.authorities.c.purpose=='REVISION')).first():
            uow.execute(t.authorities.insert().values(component_id=synthetic,purpose='REVISION',
                store_id=identities.people['founder']['store_id'],enabled=True,revision=1))
        h=head(uow,case);state=uow.execute(select(t.state).where(t.state.c.case_id==case)).mappings().one()
        proposal=uow.execute(select(old.history).where(old.history.c.record_id==state['proposal_record_id'])).mappings().one()
        guard=LifecycleGuards(synthetic)
        at=now()
        work=guard.prepare(uow,case,h['case_version'],RevisionRequested,at);claim=guard.claim(uow,work,at)
        if h['status']=='RISK_REVIEW':
            kind='REVIEW';body=material(kind,h,identities,proposal_record_id=proposal['record_id'])['content']
            packet=finite.decode_document(uow.execute(select(old.history_contents.c.body).where(
                old.history_contents.c.record_id==proposal['record_id'])).scalar_one())['packet']
            body['review'].update({k:packet[k] for k in ('case_id','input_version','proposal_id','proposal_version','corpus_version')})
            body['review'].update(outcome='REVISE',revision_requests=['Controlled synthetic revision request.'],questions=[])
        else:
            kind='DECISION';body=dict(decision_id='synthetic_revision_decision',case_id=case,decision='REQUEST_REVISION',
                principal_id=identities.people['founder']['principal_id'],reason='Controlled synthetic revision request.',
                decided_at=__import__('returnops_domain.audit',fromlist=['timestamp']).timestamp(at),
                proposal_id=proposal['object_id'],proposal_version=proposal['object_version'])
        source=stage(uow,h,kind,body,recorded_at=at)
        # This remains a direct-guard synthetic fixture, not FounderRevisionService.
        # Modern ESCALATED HUMAN decisions bind the actual accepted review.
        bind_source(uow,source,claim,target_record_id=state['review_record_id']
            if kind=='DECISION' and h['status']=='ESCALATED' else proposal['record_id'])
        result=guard.apply(uow,RevisionRequested('synthetic_revision_event',claim,source),at);uow.commit()
    return result


@pytest.mark.parametrize('entry',['review','manual'])
@pytest.mark.parametrize('order',['revision_first','entry_first'])
def test_group12_same_input_revision_serial_orders(flow_engine,identities,enabled,request,entry,order):
    case,body,caller,key=prepare_entry(flow_engine,identities,entry)
    before=snapshot(flow_engine);revision=None
    if order=='revision_first':
        revision=accepted_revision(flow_engine,identities,case)
        changed=snapshot(flow_engine)
        assert changed['case_lifecycle_state'][0]['generation']==before['case_lifecycle_state'][0]['generation']+1
        assert changed['case_heads'][0]['input_version']==before['case_heads'][0]['input_version']
        result=caller.accept(case,body,key,'late_entry');assert result.status=='DENIED'
        assert business(snapshot(flow_engine))==business(changed)
    else:
        result=caller.accept(case,body,key,'first_entry');assert result.status=='ACCEPTED'
        accepted=snapshot(flow_engine)
        if entry=='review':
            revision=accepted_revision(flow_engine,identities,case)
            assert rows(flow_engine,t.state)[0]['review_record_id'] is None
            assert caller.accept(case,body,key,'replay_after_revision').receipt==result.receipt
            assert any(r['event_kind']=='REVIEW' for r in rows(flow_engine,t.events))
        else:
            with pytest.raises(FlowError):accepted_revision(flow_engine,identities,case)
            assert snapshot(flow_engine)==accepted
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),revision=revision,
        scope='same-input actual RevisionRequested guard only; not APPROVE race')


@pytest.mark.parametrize('entry',['review','manual'])
def test_group12_revision_supersedes_actual_original_claim(flow_engine,identities,enabled,request,entry):
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from returnops_domain.lifecycle_events import EscalateReviewAccepted,OutcomeAccepted
    from returnops_domain.manual_denial import COMPONENT as manual_component
    from returnops_domain.audit import identifier
    case,body,_,_=prepare_entry(flow_engine,identities,entry)
    guard=LifecycleGuards(COMPONENT if entry=='review' else manual_component)
    cls=EscalateReviewAccepted if entry=='review' else OutcomeAccepted
    expected=body if entry=='review' else body['expected_case_version']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        work_id=guard.prepare(uow,case,expected,cls,now());claim=guard.claim(uow,work_id,now());uow.commit()
    before=snapshot(flow_engine);accepted_revision(flow_engine,identities,case)
    changed=snapshot(flow_engine);work=next(r for r in rows(flow_engine,t.work) if r['work_id']==work_id)
    assert work['state']=='SUPERSEDED' and work['claim_id'] is None and work['epoch']==claim.epoch+1
    event=cls(identifier('late_event'),claim,'unaccepted_original_source',*(['unaccepted_note'] if entry=='manual' else []))
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError):guard.apply(uow,event,now())
        with pytest.raises(FlowError):uow.commit()
    assert snapshot(flow_engine)==changed
    evidence(request.node.nodeid,before=before,after=changed,original_claim=asdict(claim),superseded_work=work,
        scope='actual private work prepare/claim then actual accepted revision; late original claim denied')


@pytest.mark.parametrize('entry',['review','manual'])
def test_group12_accepted_entry_then_actual_customer_input_is_state_denied(flow_engine,identities,enabled,request,entry):
    case,body,caller,key=prepare_entry(flow_engine,identities,entry)
    result=caller.accept(case,body,key,'first_entry');assert result.status=='ACCEPTED'
    h=rows(flow_engine,old.case_heads)[0];before=snapshot(flow_engine)
    with pytest.raises(FlowError) as error:
        identities.flow().clarify(case,dict(expected_case_version=h['case_version'],question_set_id='unavailable_question_set',
            answers=[dict(question_id='unavailable_question',text='A later customer message')],evidence_ids=[]),
            'late-input-key','late_input_correlation')
    assert error.value.code=='INVALID_STATE' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),
        actual_input_result=error.value.code,scope='legal state guard rejects post-review customer append; no forged input success')


@pytest.mark.parametrize('entry',['review','manual'])
def test_group12_actual_input_first_invalidates_previous_expected_version(flow_engine,identities,enabled,request,entry):
    from returnops_domain.intake_processor import IntakeProcessor
    from returnops_domain.investigation_processor import InvestigationProcessor
    from returnops_domain.proposal_policy import FixedProposalPolicy
    from returnops_domain.proposal_processor import FixedProposalProcessor
    from returnops_domain import investigation_tables as inv
    from controlled_escalate_reviewer import provision_review
    from manual_helpers import provision_outcome
    from returnops_domain.audit import identifier
    case=identities.flow().create({'original_message':'Real input before review.'},identifier('create'),identifier('corr')).body['case_id']
    assert IntakeProcessor(flow_engine).run_once() and InvestigationProcessor(flow_engine).run_once()
    initial=identities.flow().get_case(case).body;group=rows(flow_engine,inv.groups)[0]
    before_input=snapshot(flow_engine)
    input_result=identities.flow().clarify(case,dict(expected_case_version=initial['case_version'],
        question_set_id=initial['clarification']['question_set_id'],evidence_ids=[],
        answers=[dict(question_id=group['reference_question_id'],text='SYN-1001')]),'real-input-key','real_input_correlation')
    assert input_result.status==202
    after_input=snapshot(flow_engine)
    assert before_input['case_lifecycle_state']==[]
    # First real invalidation initializes generation1 and increments to2 in
    # the same accepting transaction; no earlier sidecar is invented by setup.
    assert after_input['case_lifecycle_state'][0]['generation']==2
    assert after_input['case_heads'][0]['input_version']==before_input['case_heads'][0]['input_version']+1
    assert IntakeProcessor(flow_engine).run_once() and InvestigationProcessor(flow_engine).run_once()
    FixedProposalPolicy(flow_engine).grant('synthetic_au_store',synthetic_demo=True,enabled=True)
    p=FixedProposalProcessor(flow_engine);assert p.process(p.prepare(case)).status=='ACCEPTED'
    provision_review(flow_engine,identities);version=rows(flow_engine,old.case_heads)[0]['case_version']
    if entry=='review':caller=receiver(flow_engine);body=initial['case_version'];key='late-review-key'
    else:
        assert receiver(flow_engine).accept(case,version,'original-review-key','review_correlation').status=='ACCEPTED'
        provision_outcome(flow_engine,identities);proposal=next(r for r in rows(flow_engine,old.history) if r['kind']=='PROPOSAL')
        caller=service(flow_engine,identities);body=dict(expected_case_version=initial['case_version'],decision='MANUAL_HANDLING',
            reason='Late original version.',proposal_id=proposal['object_id'],proposal_version=proposal['object_version']);key='late-manual-key'
    before=snapshot(flow_engine);result=caller.accept(case,body,key,'late_entry')
    assert result.status=='DENIED' and result.safe_code=='STALE_CASE_VERSION' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before_input=before_input,after_input=after_input,before=before,after=snapshot(flow_engine),result=asdict(result))
