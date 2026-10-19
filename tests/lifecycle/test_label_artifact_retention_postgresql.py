"""P10/P14/P16–P18: genuine PDF/source retention and ordered write-once receipts."""
from dataclasses import asdict
import pytest
from returnops_domain import customer_tables as old,lifecycle_tables as life
from returnops_domain.retention import RetentionService
from returnops_domain.errors import FlowError
from returnops_domain.canonical import decode_document
from returnops_domain.label_artifact_tables import controls,claims,artifacts,contents
from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock
from label_artifact_helpers import ready,service,customer,complete,recover,claim,rows,snapshot,evidence

def test_LA_P10_P16_pdf_only_one_audit_exact_delta_and_stable_completion(flow_engine,identities,enabled,request):
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities)
    result=complete(caller,args);assert result.status=='COMMITTED';before=snapshot(flow_engine)
    original,=rows(flow_engine,artifacts);retention=RetentionService(flow_engine)
    assert retention.remove('EVIDENCE',result.label_evidence_id,reason='OWNER_REQUEST',redact=True)
    after=snapshot(flow_engine);meta,=rows(flow_engine,artifacts)
    assert meta['completion_hash']==original['completion_hash'] and meta['core']==original['core'] and meta['certificate']==original['certificate']
    assert meta['retention_state']=='REDACTED' and meta['removal_reason']=='OWNER_REQUEST' and not rows(flow_engine,contents)
    receipt=decode_document(meta['pdf_retention_receipt']);p=receipt['payload']
    assert p['trigger_event_id'] is p['trigger_event_hash'] is None and p['trigger_object_id']==result.label_evidence_id
    assert p['trigger_kind']=='DIRECT_GENERATED_ARTIFACT_RETENTION' and meta['source_withdrawal_receipt'] is None
    assert len(after[old.audit.name])==len(before[old.audit.name])+1 and len(after[old.history.name])==len(before[old.history.name])
    assert after['customer_scope_audit_events']==before['customer_scope_audit_events']
    assert after[life.state.name]==before[life.state.name] and after[life.effects.name]==before[life.effects.name]
    assert {n for n in before if before[n]!=after[n]}=={old.case_heads.name,old.history.name,old.history_contents.name,old.audit.name,controls.name,artifacts.name,contents.name}
    a,=before[old.case_heads.name];b,=after[old.case_heads.name]
    assert {n:v for n,v in a.items() if n not in {'audit_sequence','audit_head'}}=={n:v for n,v in b.items() if n not in {'audit_sequence','audit_head'}}
    assert b['audit_sequence']==a['audit_sequence']+1
    assert recover(caller,args).operation_state=='SUCCEEDED' and recover(caller,args).content_available is False
    with pytest.raises(FlowError):customer(flow_engine,identities).download(result.label_evidence_id)
    prior=snapshot(flow_engine)
    assert retention.remove('EVIDENCE',result.label_evidence_id,reason='RETENTION_POLICY',redact=False) is False
    assert snapshot(flow_engine)==prior and complete(caller,args).status=='REPLAYED' and snapshot(flow_engine)==prior
    evidence(request.node.nodeid,result=asdict(result),receipt=receipt,before=before,after=after)

@pytest.mark.parametrize('when',['claimed','done','pdf_removed'])
def test_LA_P10_P17_P18_source_withdrawal_minimum_marker_and_two_ordered_receipts(flow_engine,identities,enabled,request,when):
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=None;reply=None
    if when=='claimed':
        ticket=claim(caller,args);reply=CoreLabelArtifactMock(flow_engine).retrieve_original_label(ticket,caller.authority);assert reply.status=='FOUND'
    else:
        result=complete(caller,args);assert result.status=='COMMITTED'
        if when=='pdf_removed':assert RetentionService(flow_engine).remove('EVIDENCE',result.label_evidence_id,reason='OWNER_REQUEST',redact=True)
    prior_meta=None if when=='claimed' else rows(flow_engine,artifacts)[0]
    before=snapshot(flow_engine)
    statement=next(r for r in rows(flow_engine,old.history) if r['kind']=='STATEMENT')['object_id']
    assert RetentionService(flow_engine).remove('STATEMENT',statement)
    after=snapshot(flow_engine);control,=rows(flow_engine,controls)
    assert control['state']=='RETAINED' and control['active_claim_id'] is None
    receipt=decode_document(control['source_withdrawal_receipt']);p=receipt['payload']
    events=[decode_document(r['body']) for r in rows(flow_engine,old.audit)]
    trigger=next(e for e in events if e['event_id']==p['trigger_event_id'])
    retained=next(e for e in events if e['event_id']==receipt['retention_event_id'])
    assert trigger['event_type']=='CUSTOMER_CONTENT_REMOVED' and trigger['actor']==retained['actor']=={'kind':'SERVICE','component_id':'retention-v1'}
    assert events.index(trigger)<events.index(retained) and trigger['event_hash']==p['trigger_event_hash']
    assert len([e for e in events if e['event_type']=='GENERATED_LABEL_ARTIFACT_RETAINED'])==(2 if when=='pdf_removed' else 1)
    assert len(after[old.audit.name])-len(before[old.audit.name])==2
    assert all(r['retention_state']!='AVAILABLE' for r in rows(flow_engine,old.history) if r['kind']=='OPERATION')
    assert not rows(flow_engine,contents)
    observed=recover(caller,args);assert observed.status==('RETAINED' if when=='claimed' else 'REPLAYED')
    if when=='claimed':
        assert p['completion_id_or_None'] is None and p['completion_hash_or_None'] is None
        assert caller._complete(ticket,reply.content,'late-after-retention').status=='DENIED'
    else:
        meta,=rows(flow_engine,artifacts);oldmeta=prior_meta
        assert meta['completion_hash']==oldmeta['completion_hash'] and meta['source_withdrawal_receipt']==control['source_withdrawal_receipt']
        if when=='pdf_removed':
            assert meta['pdf_retention_receipt']==oldmeta['pdf_retention_receipt']
            assert p['previous_retention_receipt_hash_or_None']==decode_document(oldmeta['pdf_retention_receipt'])['receipt_hash']
            assert meta['removal_reason']=='OWNER_REQUEST' and meta['retention_state']=='REDACTED'
    prior=snapshot(flow_engine);assert RetentionService(flow_engine).remove('STATEMENT',statement) is False
    assert snapshot(flow_engine)==prior
    evidence(request.node.nodeid,when=when,receipt=receipt,recovered=asdict(observed),before=before,after=after)

@pytest.mark.parametrize('fault',['nonnull_trigger','one_null','string_null','wrong_artifact','self_hash'])
def test_LA_P10_P14_typed_null_trigger_and_no_self_hash_are_enforced_before_commit(flow_engine,identities,enabled,request,monkeypatch,fault):
    from returnops_domain import label_artifact_retention as module
    args,_=ready(flow_engine,identities);result=complete(service(flow_engine,identities),args);assert result.status=='COMMITTED'
    original=module._payload
    def bad(*a,**kw):
        p=original(*a,**kw)
        if fault=='nonnull_trigger':p.update(trigger_event_id='fake_trigger_event',trigger_event_hash='0'*64)
        elif fault=='one_null':p['trigger_event_id']='fake_trigger_event'
        elif fault=='string_null':p.update(trigger_event_id='null',trigger_event_hash='null')
        elif fault=='wrong_artifact':p['trigger_object_id']='glabel_'+'0'*64
        else:p['receipt_hash']='0'*64
        return p
    monkeypatch.setattr(module,'_payload',bad);before=snapshot(flow_engine)
    with pytest.raises(FlowError):RetentionService(flow_engine).remove('EVIDENCE',result.label_evidence_id)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('kind',['pdf','source'])
@pytest.mark.parametrize('fault',['before_commit','after_commit','close'])
def test_LA_P10_retention_commit_uncertainty_recovers_original_transition_without_write(flow_engine,identities,enabled,request,monkeypatch,kind,fault):
    from returnops_domain import retention as module
    from returnops_domain.customer_uow import CustomerUnitOfWork
    from returnops_domain.errors import AcceptanceOutcomeUnknown
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities)
    result=complete(caller,args);assert result.status=='COMMITTED'
    object_id=result.label_evidence_id if kind=='pdf' else next(r for r in rows(flow_engine,old.history) if r['kind']=='STATEMENT')['object_id']
    class Fault(CustomerUnitOfWork):
        def commit(self):
            if fault=='before_commit':self.poison();raise AcceptanceOutcomeUnknown()
            super().commit()
            if fault=='after_commit':raise AcceptanceOutcomeUnknown()
        def __exit__(self,*a):
            result=super().__exit__(*a)
            if fault=='close':raise AcceptanceOutcomeUnknown()
            return result
    monkeypatch.setattr(module,'CustomerUnitOfWork',Fault)
    before=snapshot(flow_engine)
    with pytest.raises(AcceptanceOutcomeUnknown):RetentionService(flow_engine).remove('EVIDENCE' if kind=='pdf' else 'STATEMENT',object_id)
    monkeypatch.setattr(module,'CustomerUnitOfWork',CustomerUnitOfWork)
    after=snapshot(flow_engine)
    if fault=='before_commit':assert after==before
    observed=recover(caller,args)
    assert observed.status=='REPLAYED' and observed.content_available==(fault=='before_commit')
    assert snapshot(flow_engine)==after
    if fault!='before_commit':
        assert RetentionService(flow_engine).remove('EVIDENCE' if kind=='pdf' else 'STATEMENT',object_id,reason='OWNER_REQUEST',redact=True) is False
        assert snapshot(flow_engine)==after
    evidence(request.node.nodeid,kind=kind,fault=fault,recovery=asdict(observed),before=before,after=after)

def test_LA_P10_source_withdrawal_without_recovery_never_creates_generated_control(flow_engine,identities,enabled,request):
    args,_=ready(flow_engine,identities);before=snapshot(flow_engine)
    statement=next(r for r in rows(flow_engine,old.history) if r['kind']=='STATEMENT')['object_id']
    assert RetentionService(flow_engine).remove('STATEMENT',statement)
    assert not rows(flow_engine,controls) and not rows(flow_engine,claims) and not rows(flow_engine,artifacts)
    assert not [r for r in rows(flow_engine,old.audit) if decode_document(r['body'])['event_type']=='GENERATED_LABEL_ARTIFACT_RETAINED']
    prior=snapshot(flow_engine);result=complete(service(flow_engine,identities),args)
    assert result.status=='RETAINED' and snapshot(flow_engine)==prior
    evidence(request.node.nodeid,result=asdict(result),before=before,after=prior)
