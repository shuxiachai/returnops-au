"""EXPLICIT PRIVATE TEST PRODUCERS. No real proposal/Risk/decision/provider ran.

Each future source and causal binding is staged on the guard's uncommitted
fenced transaction. Unlike the earlier Founder reader fixture, this helper
never forces case_version=10 or writes a case transition.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from sqlalchemy import select, update
from returnops_domain import customer_tables as old, founder_tables as finite_tables, lifecycle_tables as t
from returnops_domain import founder_codec as finite
from returnops_domain.audit import append_event, identifier, timestamp
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.lifecycle_guards import LifecycleGuards, PURPOSES
from returnops_domain.lifecycle_events import ProposalAccepted, OutcomeAccepted, NotificationObserved

COMPONENT = 'synthetic_lifecycle_producer'
EXAMPLES = {item['name']:item['value'] for item in json.loads(
    (Path(__file__).resolve().parents[2]/'contracts/v1/examples.json').read_text(encoding='utf-8'))['positive']}
KINDS = ('PROPOSAL','REVIEW','DECISION','APPROVAL','OPERATION','NOTIFICATION')
NAMES = ('history-proposal','history-risk-review','history-decision','history-approval','history-operation','history-notification')
EVENTS = dict(zip(KINDS,('PROPOSAL_ACCEPTED','RISK_REVIEW_ACCEPTED','FOUNDER_DECISION_ACCEPTED',
    'FOUNDER_APPROVAL_ISSUED','OPERATION_REVISION_RECORDED','NOTIFICATION_REVISION_RECORDED')))


def now():
    return datetime.now(timezone.utc)


def rows(engine, table):
    with engine.connect() as connection:
        return list(connection.execute(select(table)).mappings())


def head(uow, case_id):
    return uow.execute(select(old.case_heads).where(old.case_heads.c.case_id==case_id)).mappings().one()


def ready(engine, identities, *, reference='SYN-1001', key='lifecycle-create', evidence_ids=None):
    request={'original_message':'synthetic lifecycle original'}
    if reference is not None:
        request['order_reference']=reference
    if evidence_ids is not None:
        request['evidence_ids']=evidence_ids
    original=identities.flow().create(request,key,identifier('corr'))
    assert IntakeProcessor(engine).run_once()
    assert InvestigationProcessor(engine).run_once()
    with CustomerUnitOfWork(engine,write=True) as uow:
        for purpose in PURPOSES.values():
            if purpose=='REVIEW':
                continue  # Controlled REVIEW has its own explicit test authority.
            if not uow.execute(select(t.authorities).where(t.authorities.c.store_id==identities.people['customer_a']['store_id'],
                    t.authorities.c.component_id==COMPONENT,t.authorities.c.purpose==purpose)).first():
                uow.execute(t.authorities.insert().values(store_id=identities.people['customer_a']['store_id'],
                    component_id=COMPONENT,purpose=purpose,revision=1,enabled=True))
        uow.commit()
    return original.body


def material(kind, h, identities, *, object_version=1, proposal_record_id=None, uow=None):
    fixture=deepcopy(EXAMPLES[NAMES[KINDS.index(kind)]])
    def bind(value):
        if isinstance(value,dict):
            result={key:bind(item) for key,item in value.items()}
            for key,new in [('case_id',h['case_id']),('case_version',h['case_version']),('input_version',h['input_version'])]:
                if key in result:
                    result[key]=new
            if 'principal_id' in result:
                result['principal_id']=identities.people['founder']['principal_id']
            return result
        if isinstance(value,list):
            return [bind(item) for item in value]
        return value
    fixture=bind(fixture)
    fixture['object_version']=object_version
    body=fixture['content']
    if kind=='PROPOSAL':
        assert uow is not None
        from returnops_domain.lifecycle_proposal import live_material
        from returnops_domain.lifecycle_sources import Sources
        original,statements,evidence,lookup,_=live_material(uow,h,Sources(uow,h,COMPONENT))
        body['statements']=list(statements.values());body['attachments']=list(evidence.values())
        body['packet']['original_statement_id']=original
        for criterion in body['evidence_matrix']:
            criterion['statement_ids']=list(statements)
            criterion['evidence_ids']=list(evidence)
        body['packet']['evidence_matrix']=deepcopy(body['evidence_matrix'])
        body['order_lookup']=lookup
        body['packet']['proposal_version']=object_version
        body['citation_verification']['proposal_version']=object_version
    if kind=='REVIEW':
        body['proposal_record_id']=proposal_record_id
        body['review']['proposal_version']=object_version
    return fixture


def stage(uow, h, kind, body, *, object_version=1, actor=None, recorded_at=None):
    finite.validate({'PROPOSAL':'HistoricalProposalBundle','REVIEW':'HistoricalRiskReview',
        'DECISION':'FounderDecisionRecord','APPROVAL':'ApprovalRecord','OPERATION':'OperationAttempt',
        'NOTIFICATION':'NotificationRecord'}[kind],body)
    inner=body['packet'] if kind=='PROPOSAL' else body['review'] if kind=='REVIEW' else body
    identity={'PROPOSAL':'proposal_id','REVIEW':'review_id','DECISION':'decision_id','APPROVAL':'approval_id',
              'OPERATION':'operation_id','NOTIFICATION':'notification_id'}[kind]
    if actor is None:
        if kind in {'DECISION','APPROVAL'}:
            actor={'kind':'HUMAN','role':'FOUNDER','principal_id':body['principal_id']}
        elif 'model_run' in inner:
            actor={'kind':'MODEL','model_run':inner['model_run']}
        else:
            actor={'kind':'SERVICE','component_id':COMPONENT}
    at=recorded_at or now(); h=head(uow,h['case_id']);record_id=identifier('synthetic_source')
    ref=dict(record_id=record_id,kind=kind,object_id=inner[identity],object_version=object_version)
    source_hash=finite.digest(body)
    uow.execute(old.history.insert().values(**ref,case_id=h['case_id'],case_version=h['case_version'],
        recorded_sequence=h['history_sequence']+1,recorded_at=at,content_sha256=source_hash,
        retention_state='AVAILABLE',removal_reason=None))
    uow.execute(old.history_contents.insert().values(record_id=record_id,body=finite.encode_document(body)))
    uow.execute(finite_tables.encodings.insert().values(record_id=record_id,profile=finite.PROFILE,
        source_content_sha256=source_hash,projected_content_sha256=source_hash,receipt_id=None))
    uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==h['case_id']).values(history_sequence=h['history_sequence']+1))
    append_event(uow,h['case_id'],actor=actor,event_type=EVENTS[kind],correlation_id=identifier('corr'),
        payload={'private_synthetic_source':True},object_ids=[ref['object_id']],history_refs=[ref],now=at)
    return record_id


def bind_source(uow, record_id, claim, *, target_record_id=None, slot='PRIMARY', **extra):
    source=uow.execute(select(old.history).where(old.history.c.record_id==record_id)).mappings().one()
    if source['kind']=='PROPOSAL' and 'order_projection_id' not in extra:
        from returnops_domain import investigation_tables as investigation
        extra['order_projection_id']=uow.execute(select(investigation.state.c.current_projection_id).where(
            investigation.state.c.case_id==source['case_id'])).scalar_one_or_none()
    uow.execute(t.sources.insert().values(record_id=record_id,case_id=source['case_id'],work_id=claim.work_id,
        claim_id=claim.claim_id,epoch=claim.epoch,generation=claim.generation,input_version=claim.input_version,
        case_version=claim.case_version,source_hash=source['content_sha256'],authority_revision=claim.authority_revision,
        target_record_id=target_record_id,slot=slot,**extra))


def claim(uow, case_id, event_type, *, target_record_id=None, component=COMPONENT):
    h=head(uow,case_id); guard=LifecycleGuards(component)
    work=guard.prepare(uow,case_id,h['case_version'],event_type,now(),target_record_id=target_record_id)
    return guard.claim(uow,work,now())


def proposal(engine, identities, case_id, *, version=1):
    with CustomerUnitOfWork(engine,write=True) as uow:
        token=claim(uow,case_id,ProposalAccepted);h=head(uow,case_id)
        body=material('PROPOSAL',h,identities,object_version=version,uow=uow)['content']
        source=stage(uow,h,'PROPOSAL',body,object_version=version)
        bind_source(uow,source,token)
        event=ProposalAccepted(identifier('event'),token,source)
        result=LifecycleGuards(COMPONENT).apply(uow,event,now());uow.commit()
        return event,result


def outcome(engine, identities, case_id, *, decision='MANUAL_HANDLING', target_kind='PROPOSAL', fixture_prepare=True):
    with CustomerUnitOfWork(engine,write=True) as uow:
        # Explicit future-A2 starting condition. No Risk PASS producer or its
        # transition is claimed as tested by this A1.03 component fixture.
        if fixture_prepare and head(uow,case_id)['status']=='RISK_REVIEW':
            uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case_id).values(status='AWAITING_APPROVAL'))
        token=claim(uow,case_id,OutcomeAccepted);h=head(uow,case_id)
        body=material('DECISION',h,identities)['content'];body.pop('approval_id',None);body['decision']=decision
        body['decision_id']=identifier('synthetic_decision')
        if target_kind!='PROPOSAL':
            body.pop('proposal_id');body.pop('proposal_version')
            if target_kind=='PROCESSING_FAILURE':
                body['processing_failure_id']=h['current_failure_id']
            else:
                from returnops_domain import investigation_tables as investigation
                body['order_lookup_block_id']=uow.execute(select(investigation.state.c.current_block_id).where(
                    investigation.state.c.case_id==case_id)).scalar_one()
        source=stage(uow,h,'DECISION',body);bind_source(uow,source,token)
        note=material('NOTIFICATION',h,identities)['content']
        note['notification_id']=identifier('synthetic_notification')
        note.update(status='PENDING',outcome='REJECTED' if decision=='REJECT' else 'MANUAL_HANDLED',attempt_count=0)
        note.pop('sent_at',None);note.pop('error',None)
        notification=stage(uow,h,'NOTIFICATION',note)
        bind_source(uow,notification,token,target_record_id=source,slot='NOTIFICATION')
        event=OutcomeAccepted(identifier('event'),token,source,notification)
        receipt=LifecycleGuards(COMPONENT).apply(uow,event,now());uow.commit()
        return event,receipt


def notify(engine, identities, case_id, status, *, mutate=None, component=COMPONENT):
    with CustomerUnitOfWork(engine,write=True) as uow:
        token=claim(uow,case_id,NotificationObserved,component=component);h=head(uow,case_id)
        state=uow.execute(select(t.state).where(t.state.c.case_id==case_id)).mappings().one()
        previous=uow.execute(select(old.history).where(old.history.c.record_id==state['notification_record_id'])).mappings().one()
        raw=uow.execute(select(old.history_contents.c.body).where(old.history_contents.c.record_id==previous['record_id'])).scalar_one()
        body=finite.decode_document(raw);body.update(status=status,case_version=h['case_version'],updated_at=timestamp(now()))
        body.pop('sent_at',None);body.pop('error',None)
        if status=='SENT':
            body['sent_at']=timestamp(now())
        if mutate:
            mutate(body)
        source=stage(uow,h,'NOTIFICATION',body,object_version=previous['object_version']+1,
            actor={'kind':'SERVICE','component_id':component})
        bind_source(uow,source,token,target_record_id=state['outcome_record_id'])
        event=NotificationObserved(identifier('event'),token,source)
        receipt=LifecycleGuards(component).apply(uow,event,now());uow.commit()
        return event,receipt
