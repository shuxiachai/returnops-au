"""Private pre-existing dispatch facts, never a runtime approval/dispatch API."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
from pypdf import PdfWriter
from sqlalchemy import select, update
from returnops_domain import lifecycle_tables as t, customer_tables as old
from returnops_domain.audit import identifier, timestamp
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.lifecycle_events import LifecycleClaim, EffectObserved, OutcomeAccepted
from returnops_domain.lifecycle_effects import fingerprint
from returnops_domain.lifecycle_guards import LifecycleGuards
from synthetic_sources import COMPONENT, now, head, material, stage, bind_source, claim, proposal


def existing_execution(engine, identities, case_id):
    """Synthetic starting condition owned by later A2, explicitly not acceptance.

    Proposal acceptance is real A1.03. PASS/approval/dispatch rows below only
    prepare the saved causal facts needed to test this component's consumers.
    """
    proposal_event,_=proposal(engine,identities,case_id)
    with CustomerUnitOfWork(engine,write=True) as uow:
        h=head(uow,case_id);state=uow.execute(select(t.state).where(t.state.c.case_id==case_id)).mappings().one()
        review=material('REVIEW',h,identities,proposal_record_id=proposal_event.record_id)['content']
        review['review'].update(outcome='PASS',findings=[],revision_requests=[],questions=[])
        review_id=stage(uow,h,'REVIEW',review)
        decision=material('DECISION',h,identities)['content']
        approval=material('APPROVAL',h,identities)['content']
        decision.update(decision='APPROVE',approval_id=approval['approval_id'])
        decision_id=stage(uow,h,'DECISION',decision)
        approval['decision_id']=decision['decision_id'];approval['scope']['expires_at']=timestamp(now()+timedelta(hours=1))
        approval['scope']['review_id']=review['review']['review_id']
        approval['scope_fingerprint']=fingerprint(approval['scope'])
        approval_id=stage(uow,h,'APPROVAL',approval)
        writer=PdfWriter();writer.add_blank_page(width=100,height=100);stream=BytesIO();writer.write(stream);raw=stream.getvalue()
        evidence_id=identifier('synthetic_label');artifact_hash=sha256(raw).hexdigest()
        uow.execute(old.evidence.insert().values(evidence_id=evidence_id,uploader_id=h['owner_principal_id'],
            store_id=h['store_id'],case_id=case_id,filename=b'label.pdf',description=None,media_type='application/pdf',
            size_bytes=len(raw),sha256=artifact_hash,status='BOUND',created_at=now(),expires_at=None,available=True))
        uow.execute(old.evidence_contents.insert().values(evidence_id=evidence_id,body=raw))
        operations=[]
        for index,command in enumerate(approval['scope']['commands']):
            body=material('OPERATION',h,identities)['content']
            body.update(operation_id=identifier('synthetic_operation'),command_id=command['command_id'],
                approval_id=approval['approval_id'],provider_id=command['provider_id'],status='EXECUTING',
                provider_operation_id=identifier('synthetic_provider'),idempotency_key='synthetic-operation-key-'+str(index),
                operation_fingerprint=fingerprint({'approval_id':approval['approval_id'],
                    'scope_fingerprint':approval['scope_fingerprint'],'command':command}))
            body.pop('result',None);body.pop('error',None)
            original=stage(uow,h,'OPERATION',body)
            work=identifier('synthetic_dispatch_work');token=LifecycleClaim(work,identifier('synthetic_claim'),1,
                h['case_version'],h['input_version'],state['generation'],1)
            uow.execute(t.work.insert().values(work_id=work,case_id=case_id,component_id=COMPONENT,store_id=h['store_id'],
                owner_id=h['owner_principal_id'],purpose='EFFECT',input_version=h['input_version'],generation=state['generation'],
                target_hash='b'*64 if index==0 else 'c'*64,target_record_id=approval_id,state='DONE',claim_id=token.claim_id,
                epoch=1,claimed_case_version=h['case_version'],authority_revision=1,lease_expires_at=None,created_at=now()))
            bind_source(uow,original,token,target_record_id=approval_id,provider_operation_id=body['provider_operation_id'],
                artifact_evidence_id=evidence_id if index else None,artifact_sha256=artifact_hash if index else None)
            operations.append(dict(original=original,body=body,approval=approval_id,artifact=evidence_id if index else None,
                artifact_hash=artifact_hash if index else None,command=command))
        # Explicit initial condition for a future A2 execution branch. This is
        # not a transition claimed as performed by the component under test.
        uow.execute(update(t.state).where(t.state.c.case_id==case_id).values(review_record_id=review_id,approval_record_id=approval_id))
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case_id).values(status='ACTION_IN_PROGRESS'))
        uow.commit()
    return operations


def observe(engine, identities, case_id, operation, *, mutate=None):
    with CustomerUnitOfWork(engine,write=True) as uow:
        token=claim(uow,case_id,EffectObserved,target_record_id=operation['original']);h=head(uow,case_id)
        body=deepcopy(operation['body']);body.update(status='SUCCEEDED',case_version=h['case_version'],updated_at=timestamp(now()))
        command=operation['command']
        if command['type']=='CREATE_RETURN':
            body['result']={'type':'CREATE_RETURN','provider_return_id':identifier('saved_return'),
                'parcel_id':command['parameters']['parcel_id']}
        else:
            body['result']={'type':'GENERATE_LABEL','provider_label_id':identifier('saved_label'),
                'parcel_id':command['parameters']['parcel_id'],'label_evidence_id':operation['artifact']}
        if mutate:
            mutate(body)
        source=stage(uow,h,'OPERATION',body,object_version=2)
        bind_source(uow,source,token,target_record_id=operation['approval'],dispatch_source_record_id=operation['original'],
            provider_operation_id=operation['body']['provider_operation_id'],artifact_evidence_id=operation['artifact'],
            artifact_sha256=operation['artifact_hash'])
        event=EffectObserved(identifier('event'),token,source)
        result=LifecycleGuards(COMPONENT).apply(uow,event,now());uow.commit()
        return event,result


def return_outcome(engine,identities,case_id,return_id,label_id):
    with CustomerUnitOfWork(engine,write=True) as uow:
        token=claim(uow,case_id,OutcomeAccepted);h=head(uow,case_id)
        note=material('NOTIFICATION',h,identities)['content']
        note.update(status='PENDING',outcome='RETURN_CREATED',attempt_count=0);note.pop('sent_at',None);note.pop('error',None)
        source=stage(uow,h,'NOTIFICATION',note)
        bind_source(uow,source,token,target_record_id=source)
        event=OutcomeAccepted(identifier('event'),token,source,source,return_id,label_id)
        receipt=LifecycleGuards(COMPONENT).apply(uow,event,now());uow.commit()
        return event,receipt
