"""TEST ONLY controlled synthetic adapter; no C implementation or live model."""
from copy import deepcopy
from sqlalchemy import select
from returnops_api.private_review import compose_private_review
from returnops_domain import customer_tables as old,lifecycle_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.proposal_processor import FixedProposalProcessor
from returnops_domain.review_sources import COMPONENT
from manual_helpers import rows,provision_outcome


class ControlledReviewer:
    def __init__(self,mutate=None):
        self.calls=[];self.mutate=mutate

    def __call__(self,request,invocation,review_id):
        self.calls.append(deepcopy(request))
        packet=request['packet']
        review={key:packet[key] for key in ('case_id','input_version','proposal_id','proposal_version','corpus_version')}
        review.update(review_id=review_id,outcome='ESCALATE',revision_requests=[],questions=[],
            findings=[dict(finding_id='synthetic_block',category='AUTHORITY',severity='BLOCK',
                message='Controlled synthetic escalation requires explicit Founder handling.',
                citation_ids=[c['citation_id'] for c in packet['citations']],
                evidence_ids=[e['evidence_id'] for e in request['attachments']])],
            reviewed_at=invocation['finished_at'],model_run=deepcopy(invocation))
        if self.mutate:self.mutate(review)
        return review


def provision_review(engine,identities):
    with CustomerUnitOfWork(engine,write=True) as uow:
        if not uow.execute(select(t.authorities).where(t.authorities.c.component_id==COMPONENT,
                t.authorities.c.purpose=='REVIEW')).first():
            uow.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],
                component_id=COMPONENT,purpose='REVIEW',revision=1,enabled=True))
        uow.commit()


def ready_review(engine,identities,*,grant=True,evidence_ids=None):
    from test_proposal_runtime_postgresql import ready
    case=ready(engine,identities,evidence_ids=evidence_ids)
    processor=FixedProposalProcessor(engine)
    assert processor.process(processor.prepare(case)).status=='ACCEPTED'
    if grant:provision_review(engine,identities)
    head=next(r for r in rows(engine,old.case_heads) if r['case_id']==case)
    assert head['status']=='RISK_REVIEW'
    return case,head['case_version']


def receiver(engine,adapter=None,**options):
    return compose_private_review(engine,adapter or ControlledReviewer(),**options)


def ready_manual(engine,identities):
    case,version=ready_review(engine,identities)
    result=receiver(engine).accept(case,version,'original-review-key','review_correlation')
    assert result.status=='ACCEPTED',(result.status,result.safe_code,result.audit)
    state=next(r for r in rows(engine,t.state) if r['case_id']==case)
    record=next(r for r in rows(engine,old.history) if r['record_id']==state['proposal_record_id'])
    provision_outcome(engine,identities)
    return case,dict(expected_case_version=version+1,decision='MANUAL_HANDLING',reason='Explicit Founder manual request.',
        proposal_id=record['object_id'],proposal_version=record['object_version'])
