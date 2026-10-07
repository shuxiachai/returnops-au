"""Retained accepted proposal/review proof; historical grants are not authority.

These checks read the original work, claim, audit, binding and event receipt.
Neither a JSON body nor its own digest certifies an accepted source. The fixed
adapter provenance here describes a controlled synthetic invocation only.
"""
from dataclasses import asdict
from sqlalchemy import select
from . import lifecycle_tables as t, investigation_tables as investigation
from .audit import timestamp
from .canonical import digest
from . import founder_codec as finite
from .lifecycle_events import LifecycleClaim, ProposalAccepted, EscalateReviewAccepted
from .lifecycle_sources import Sources
from .lifecycle_state import reject
from .manual_target import one

COMPONENT = 'controlled-escalate-review-v1'
PROVIDER = 'fixture-no-live-model'
MODEL = 'controlled-synthetic-escalation'
PROMPT = 'controlled-escalate-v1'


def stable_id(kind, value):
    return kind + '_' + digest(value, 'controlled-review-' + kind + '/v1')


def invocation(work, at):
    return dict(run_id=stable_id('review_run', {name:work[name] for name in
        ('work_id','claim_id','epoch','claimed_case_version','input_version','generation','authority_revision')}),
        role='RISK_REVIEWER',provider_id=PROVIDER,model_id=MODEL,prompt_version=PROMPT,
        started_at=timestamp(at),finished_at=timestamp(at),input_tokens=0,output_tokens=0)


def review_payload(work, proposal, review_hash):
    return dict(synthetic_review=True,model_called=False,component_id=COMPONENT,
        work_id=work['work_id'],claim_id=work['claim_id'],epoch=work['epoch'],
        input_version=work['input_version'],generation=work['generation'],authority_revision=work['authority_revision'],
        proposal_record_id=proposal['record_id'],proposal_hash=proposal['content_sha256'],review_hash=review_hash)


def _accepted(uow, head, sources, row, purpose, *, staged=False):
    binding = one(uow,t.sources,record_id=row['record_id'])
    work = one(uow,t.work,work_id=binding['work_id'])
    origin = sources.proof.origin(row)
    expected = dict(case_id=head['case_id'],work_id=work['work_id'],claim_id=work['claim_id'],epoch=work['epoch'],
        input_version=work['input_version'],generation=work['generation'],authority_revision=work['authority_revision'])
    if (any(binding[k]!=v for k,v in expected.items()) or work['purpose']!=purpose
            or work['case_id']!=head['case_id'] or work['store_id']!=head['store_id']
            or work['owner_id']!=head['owner_principal_id'] or work['epoch']<1
            or work['claim_id'] is None or work['authority_revision'] is None
            or work['state']!=('RUNNING' if staged else 'DONE')
            or binding['slot']!='PRIMARY' or binding['case_version']!=work['claimed_case_version']
            or row['case_version']!=binding['case_version'] or row['content_sha256']!=binding['source_hash']
            or origin['case_version']!=row['case_version'] or origin['occurred_at']!=timestamp(row['recorded_at'])):
        reject(uow)
    receipt = None
    if not staged:
        receipt = one(uow,t.events,record_id=row['record_id'])
        claim = LifecycleClaim(work['work_id'],work['claim_id'],work['epoch'],work['claimed_case_version'],
            work['input_version'],work['generation'],work['authority_revision'])
        cls = ProposalAccepted if purpose=='PROPOSAL' else EscalateReviewAccepted
        event = cls(receipt['event_id'],claim,row['record_id'])
        if (receipt['fingerprint']!=digest({'kind':purpose,**asdict(event)},'lifecycle-event/v1')
                or receipt['event_kind']!=purpose or receipt['status']!=('RISK_REVIEW' if purpose=='PROPOSAL' else 'ESCALATED')
                or receipt['case_id']!=head['case_id'] or receipt['work_id']!=work['work_id']
                or receipt['source_id']!=row['record_id'] or receipt['source_hash']!=row['content_sha256']
                or receipt['source_audit_event_id']!=origin['event_id']
                or receipt['pre_case_version']!=binding['case_version']
                or receipt['case_version']!=binding['case_version']+1
                or receipt['pre_input_version']!=work['input_version'] or receipt['input_version']!=work['input_version']
                or receipt['pre_generation']!=work['generation'] or receipt['generation']!=work['generation']
                or receipt['accepted_at']!=row['recorded_at']):
            reject(uow)
        payload = dict(event=purpose,work_id=work['work_id'],source_record_id=row['record_id'],generation=work['generation'])
        accepted_audits = [a for a in sources.proof.events if a['event_type']=='LIFECYCLE_EVENT_ACCEPTED'
            and a['correlation_id']==receipt['event_id']]
        if (len(accepted_audits)!=1 or accepted_audits[0]['payload_hash']!=digest(payload,'audit-payload/v1')
                or accepted_audits[0]['actor']!={'kind':'SERVICE','component_id':work['component_id']}
                or accepted_audits[0]['case_version']!=receipt['case_version']
                or accepted_audits[0]['occurred_at']!=timestamp(receipt['accepted_at'])):
            reject(uow)
    return dict(record=dict(row),binding=binding,work=work,event=receipt,origin=origin)


def accepted_proposal(uow, head, state, component, *, record_id=None, current=True):
    sources = Sources(uow,head,component)
    row,bundle = sources.read(record_id or state['proposal_record_id'],{'PROPOSAL'},current_actor=False)
    seal = _accepted(uow,head,sources,row,'PROPOSAL')
    packet = bundle['packet']
    if (seal['origin']['event_type']!='PROPOSAL_ACCEPTED' or seal['binding']['target_record_id'] is not None
            or packet['input_version']!=seal['work']['input_version']
            or row['object_version']!=packet['proposal_version']):
        reject(uow)
    if current:
        if (not state['available'] or row['record_id']!=state['proposal_record_id']
                or seal['work']['generation']!=state['generation'] or packet['input_version']!=head['input_version']
                or packet['proposal_version']!=state['proposal_version']):
            reject(uow)
        from .lifecycle_proposal import verify
        verify(uow,head,sources,bundle,seal['binding']['order_projection_id'])
    # Complete immutable retained source and protected actual acceptance, never
    # current authority of the historical proposal component.
    seal['body']=bundle
    return seal


def check_review(uow, body, proposal, work, at):
    finite.validate('HistoricalRiskReview',body)
    review = body['review']; packet = proposal['body']['packet']
    if (body['proposal_record_id']!=proposal['record']['record_id']
            or any(review[k]!=packet[k] for k in ('case_id','input_version','proposal_id','proposal_version','corpus_version'))
            or review['outcome']!='ESCALATE' or not any(f['severity']=='BLOCK' for f in review['findings'])
            or review['model_run']!=invocation(work,at) or review['reviewed_at']!=timestamp(at)
            or review['review_id']!=stable_id('review',work['work_id'])):
        reject(uow)
    citations={c['citation_id'] for c in packet['citations']}
    evidence={e['evidence_id'] for e in proposal['body']['attachments']}
    if len({f['finding_id'] for f in review['findings']})!=len(review['findings']):
        reject(uow)
    for finding in review['findings']:
        if not set(finding['citation_ids'])<=citations or not set(finding['evidence_ids'])<=evidence:
            reject(uow)


def verify_staged_review(uow, head, state, row, body, binding, work):
    if (head['status']!='RISK_REVIEW' or head['current_failure_id'] is not None
            or work['component_id']!=COMPONENT or work['purpose']!='REVIEW'
            or any(state[n] is not None for n in ('review_record_id','preview_id','approval_record_id','outcome_record_id','outcome'))):
        reject(uow)
    block = uow.execute(select(investigation.state.c.current_block_id).where(
        investigation.state.c.case_id==head['case_id'])).scalar_one_or_none()
    if block is not None:
        reject(uow)
    proposal=accepted_proposal(uow,head,state,COMPONENT)
    sources=Sources(uow,head,COMPONENT)
    seal=_accepted(uow,head,sources,row,'REVIEW',staged=True)
    _review_relation(uow,head,proposal,seal,body)
    if proposal['event']['case_version']!=head['case_version']:
        reject(uow)
    return proposal


def _review_relation(uow, head, proposal, seal, body):
    row,work,binding,origin=(seal[n] for n in ('record','work','binding','origin'))
    check_review(uow,body,proposal,work,row['recorded_at'])
    from .lifecycle_guards import target
    original_head={**head,'input_version':work['input_version']}
    original_state=dict(generation=work['generation'],proposal_record_id=proposal['record']['record_id'],
        review_record_id=None,approval_record_id=None)
    if (work['component_id']!=COMPONENT or binding['target_record_id']!=proposal['record']['record_id']
            or work['target_record_id'] is not None or work['target_hash']!=target(original_head,original_state,'REVIEW')
            or binding['order_projection_id']!=proposal['binding']['order_projection_id']
            or work['generation']!=proposal['work']['generation']
            or work['input_version']!=proposal['work']['input_version']
            or work['claimed_case_version']!=proposal['event']['case_version']
            or origin['actor']!={'kind':'SERVICE','component_id':COMPONENT}
            or origin['event_type']!='RISK_REVIEW_ACCEPTED'
            or origin['correlation_id']!=stable_id('review_event',work['work_id'])
            or origin['payload_hash']!=digest(review_payload(work,proposal['record'],row['content_sha256']),'audit-payload/v1')):
        reject(uow)


def accepted_review(uow, head, state, component, *, record_id=None, current=True):
    sources=Sources(uow,head,component)
    row,body=sources.read(record_id or state['review_record_id'],{'REVIEW'},current_actor=False)
    seal=_accepted(uow,head,sources,row,'REVIEW')
    proposal=accepted_proposal(uow,head,state,component,record_id=body['proposal_record_id'],current=current)
    _review_relation(uow,head,proposal,seal,body)
    if current and (row['record_id']!=state['review_record_id'] or state['generation']!=seal['work']['generation']
                    or state['input_version']!=seal['work']['input_version']):
        reject(uow)
    seal.update(body=body,proposal=proposal)
    return seal


def manual_proposal_target(uow, head, state, request, component, *, accepted_version=None):
    seal=accepted_review(uow,head,state,component)
    packet=seal['proposal']['body']['packet']
    version=head['case_version'] if accepted_version is None else accepted_version
    block=uow.execute(select(investigation.state.c.current_block_id).where(
        investigation.state.c.case_id==head['case_id'])).scalar_one_or_none()
    if (request.get('decision')!='MANUAL_HANDLING' or any(request.get(k)!=packet[k] for k in ('proposal_id','proposal_version'))
            or seal['event']['case_version']!=version or head['current_failure_id'] is not None or block is not None
            or state['preview_id'] is not None or state['approval_record_id'] is not None
            or accepted_version is None and (head['status']!='ESCALATED' or state['outcome_record_id'] is not None or state['outcome'] is not None)):
        reject(uow)
    return seal
