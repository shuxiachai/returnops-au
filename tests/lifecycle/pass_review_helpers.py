"""TEST ONLY positive catalogue, complete-material builder and risk adapter.

These helpers are never packaged or registered as default runtime producers.
"""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pypdf import PdfWriter
from sqlalchemy import select
from returnops_api.private_pass_review import compose_private_pass_review
from returnops_domain import customer_tables as old,lifecycle_tables as t
from returnops_domain.audit import identifier,timestamp
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.evidence_validation import validate_evidence
from returnops_domain.fixed_proposal import build_fixed_proposal
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.investigation_policy import InvestigationPolicy
from returnops_domain.mock_orders import SyntheticCatalogue
from returnops_domain.proposal_policy import FixedProposalPolicy
from returnops_domain.proposal_processor import FixedProposalProcessor
from returnops_domain.pass_review_sources import COMPONENT
from returnops_domain.pass_scenario import SCENARIO,MESSAGE,POLICY
from manual_helpers import rows,now


def catalogue(identities):
    at=timestamp(now())
    return SyntheticCatalogue.from_document(dict(is_synthetic=True,format_version=1,
        dataset_version=SCENARIO,provider_id='synthetic_commerce',provider_version='mock-orders-v1',orders=[dict(
            store_id=identities.people['customer_a']['store_id'],owner_principal_id=identities.people['customer_a']['principal_id'],
            order_reference='SYN-CUPS-PASS',snapshot=dict(snapshot_id=identifier('cups_snapshot'),order_id=identifier('cups_order'),
                provider_id='synthetic_commerce',snapshot_version=1,purchased_at=at,currency='AUD',retrieved_at=at,
                line_items=[dict(line_item_id='line-mug-blue',sku='SYN-CUP-BLUE',description='Synthetic blue cup',quantity=1,unit_price_minor=1000),
                            dict(line_item_id='line-mug-white',sku='SYN-CUP-WHITE',description='Synthetic white cup',quantity=1,unit_price_minor=1000)]))]))


def build_positive(material,work,proposal_version,at):
    body=build_fixed_proposal(material,work,proposal_version,at)
    packet=body['packet']; date=timestamp(at)
    matrix=[dict(criterion_id='synthetic-cups-condition',status='PRESENT',
        statement_ids=[s['statement_id'] for s in material.statements],evidence_ids=[a['evidence_id'] for a in material.attachments],
        rationale='Synthetic customer statement and uploaded evidence are retained; no legal finding.')]
    passage=dict(passage_id='synthetic-cups-policy',document_id='synthetic-cups-document',source_type='STORE_POLICY',
        title='Synthetic cups free-return policy',source_uri='urn:returnops:synthetic:cups:v1',accessed_on=date[:10],
        source_version=SCENARIO,corpus_version=SCENARIO,location='synthetic-section-1',content=POLICY,
        content_sha256=sha256(POLICY.encode()).hexdigest(),retrieved_at=date,is_synthetic=True)
    citation={k:passage[k] for k in ('passage_id','document_id','source_version','corpus_version','content_sha256','location')}
    citation['citation_id']='synthetic-cups-citation'
    packet.update(corpus_version=SCENARIO,
        facts=dict(issue_category='FAULTY_OR_QUALITY_ISSUE',customer_requested_outcome='RETURN',possible_basis='STORE_POLICY',
            assessment_status='SUPPORTED',line_items=[dict(line_item_id='line-mug-blue',quantity=1),dict(line_item_id='line-mug-white',quantity=1)],
            summary='Synthetic customer reports chips in two cups; no responsibility determination is made.'),
        evidence_matrix=deepcopy(matrix),recommended_action='PROPOSE_RETURN',
        rationale='Propose one free simulated return for both cups, subject to independent review and Founder approval.',
        alternatives=['Refer for manual handling if evidence conflicts.'],
        conditions=['Synthetic order quantities must match.','No chargeable label or refund may be issued.'],
        cost_responsibility_note='The mock return and label are free; no real allocation of legal costs is decided.',
        citations=[citation],confidence=0.8,unresolved_questions=[])
    packet['model_run']['prompt_version']='synthetic-cups-builder-v1'
    binding={k:packet[k] for k in ('case_id','input_version','corpus_version')}
    body.update(evidence_matrix=matrix,retrieval_result=dict(**binding,status='MATCHED',passages=[passage],conflicts=[],retrieved_at=date),
        citation_verification=dict(**binding,proposal_id=packet['proposal_id'],proposal_version=proposal_version,
            checks=[dict(citation_id=citation['citation_id'],result='VALID',message='Exact synthetic policy identity, version, location and hash.')],checked_at=date))
    return body


class ControlledPassReviewer:
    def __init__(self,outcome='PASS',mutate=None):
        self.outcome,self.mutate=outcome,mutate;self.calls=[]

    def __call__(self,request,context,review_id):
        self.calls.append(deepcopy(request));packet=request['packet']
        result={k:packet[k] for k in ('case_id','input_version','proposal_id','proposal_version','corpus_version')}
        findings=[] if self.outcome=='PASS' else [dict(finding_id='synthetic_low_confidence',category='LOW_CONFIDENCE',
            severity='WARNING',message='Synthetic evidence is imperfect; retain this warning for the Founder.',
            citation_ids=[c['citation_id'] for c in packet['citations']],evidence_ids=[e['evidence_id'] for e in request['attachments']])]
        result.update(review_id=review_id,outcome=self.outcome,findings=findings,revision_requests=[],questions=[],
            reviewed_at=context['finished_at'],model_run=deepcopy(context))
        if self.mutate:self.mutate(result,request,context)
        return result


def provision_review(engine,identities):
    with CustomerUnitOfWork(engine,write=True) as uow:
        if not uow.execute(select(t.authorities).where(t.authorities.c.component_id==COMPONENT,t.authorities.c.purpose=='REVIEW')).first():
            uow.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],component_id=COMPONENT,purpose='REVIEW',revision=1,enabled=True))
        uow.commit()


def ready_pass(engine,identities,*,grant=True,builder=build_positive,message=MESSAGE):
    source=catalogue(identities)
    InvestigationPolicy(engine).configure(identities.people['founder']['store_id'],catalogue=source)
    pdf=PdfWriter();pdf.add_blank_page(width=100,height=100);buffer=BytesIO();pdf.write(buffer)
    uploaded=identities.flow().stage(validate_evidence(buffer.getvalue(),'synthetic-cups.pdf','application/pdf'),identifier('upload'),identifier('corr'))
    case=identities.flow().create(dict(original_message=message,requested_outcome='RETURN',order_reference='SYN-CUPS-PASS',
        evidence_ids=[uploaded.body['evidence_id']]),identifier('create'),identifier('corr')).body['case_id']
    assert IntakeProcessor(engine).run_once()
    assert InvestigationProcessor(engine,catalogue=source).run_once()
    FixedProposalPolicy(engine).grant(identities.people['founder']['store_id'],synthetic_demo=True,enabled=True)
    processor=FixedProposalProcessor(engine,build=builder)
    result=processor.process(processor.prepare(case));assert result.status=='ACCEPTED',result.status
    if grant:provision_review(engine,identities)
    head=next(r for r in rows(engine,old.case_heads) if r['case_id']==case)
    assert head['status']=='RISK_REVIEW'
    return case,head['case_version']


def receiver(engine,adapter=None,**options):
    return compose_private_pass_review(engine,adapter or ControlledPassReviewer(),**options)
