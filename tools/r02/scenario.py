"""Controlled PASS receiver + risk stub inputs for the R.02 driver; not installed.

build_positive and ControlledPassReviewer are copied unchanged from
tests/lifecycle/pass_review_helpers.py (A2.01, docs/33): the fixed two-cups
proposal builder for FixedProposalProcessor(build=...) and the explicit
synthetic adapter for PassReviewReceiver. Behaviour is identical; only the
module differs, so the driver never imports tests/ at runtime. evidence_pdf()
is the same one-page synthetic PDF that ready_pass() uploads.

This is the fixed proposal plus fixed risk result of docs/08 Gate 1. It is not
an independent risk assessment, a default producer or a registered component.
"""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO

from pypdf import PdfWriter

from returnops_domain.audit import timestamp
from returnops_domain.fixed_proposal import build_fixed_proposal
from returnops_domain.pass_scenario import SCENARIO, POLICY


def evidence_pdf():
    pdf=PdfWriter();pdf.add_blank_page(width=100,height=100);buffer=BytesIO();pdf.write(buffer)
    return buffer.getvalue()


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
