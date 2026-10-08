"""Narrow synthetic family oracle, not a real risk policy or proposal producer.

The only positive family in this private component is two chipped cups under
an explicitly synthetic free-return policy. Complete retained inputs and the
actual accepted order/proposal proofs are checked separately; this oracle
never transforms or drops source material to make it positive.
"""
from hashlib import sha256
from .audit import timestamp
from .lifecycle_state import reject
from .proposal_policy import COMPONENT as PROPOSAL_COMPONENT, stable_id

SCENARIO = 'synthetic-cups-pass-v1'
MESSAGE = 'Synthetic scenario: the blue and white cups each arrived chipped. Please arrange a free simulated return for both.'
POLICY = 'Synthetic store policy: two chipped cups may be proposed for a free simulated return, subject to independent review and Founder approval. No live remedy, label, refund or legal conclusion is authorized.'


def verify_scenario(uow, seal):
    body=seal['body']; packet=body['packet']; work=seal['work']
    at=timestamp(seal['record']['recorded_at'])
    statements=body['statements']; attachments=body['attachments']
    if (work['component_id']!=PROPOSAL_COMPONENT
            or seal['origin']['actor']!={'kind':'SERVICE','component_id':PROPOSAL_COMPONENT}
            or len(statements)!=1 or statements[0]['kind']!='ORIGINAL'
            or statements[0]['raw_text']!=MESSAGE or statements[0]['requested_outcome']!='RETURN'
            or not attachments or any(a['status']!='BOUND' for a in attachments)
            or set(body)!={'packet','statements','attachments','evidence_matrix','order_lookup','retrieval_result','citation_verification'}):
        reject(uow)
    matrix=[dict(criterion_id='synthetic-cups-condition',status='PRESENT',
        statement_ids=[statements[0]['statement_id']],evidence_ids=[a['evidence_id'] for a in attachments],
        rationale='Synthetic customer statement and uploaded evidence are retained; no legal finding.')]
    passage=dict(passage_id='synthetic-cups-policy',document_id='synthetic-cups-document',
        source_type='STORE_POLICY',title='Synthetic cups free-return policy',
        source_uri='urn:returnops:synthetic:cups:v1',accessed_on=at[:10],source_version=SCENARIO,
        corpus_version=SCENARIO,location='synthetic-section-1',content=POLICY,
        content_sha256=sha256(POLICY.encode()).hexdigest(),retrieved_at=at,is_synthetic=True)
    citation={k:passage[k] for k in ('passage_id','document_id','source_version','corpus_version','content_sha256','location')}
    citation['citation_id']='synthetic-cups-citation'
    expected=dict(case_id=work['case_id'],input_version=work['input_version'],corpus_version=SCENARIO,
        proposal_id=stable_id('proposal',work['work_id']),proposal_version=seal['record']['object_version'],
        original_statement_id=statements[0]['statement_id'],created_at=at,
        facts=dict(issue_category='FAULTY_OR_QUALITY_ISSUE',customer_requested_outcome='RETURN',possible_basis='STORE_POLICY',
            assessment_status='SUPPORTED',line_items=[dict(line_item_id='line-mug-blue',quantity=1),dict(line_item_id='line-mug-white',quantity=1)],
            summary='Synthetic customer reports chips in two cups; no responsibility determination is made.'),
        evidence_matrix=matrix,recommended_action='PROPOSE_RETURN',
        rationale='Propose one free simulated return for both cups, subject to independent review and Founder approval.',
        alternatives=['Refer for manual handling if evidence conflicts.'],
        conditions=['Synthetic order quantities must match.','No chargeable label or refund may be issued.'],
        cost_responsibility_note='The mock return and label are free; no real allocation of legal costs is decided.',
        citations=[citation],confidence=0.8,unresolved_questions=[],
        model_run=dict(run_id=stable_id('run',work['work_id']),role='ASSESSMENT',provider_id='provider-fixture',
            model_id='fixture-no-live-model',prompt_version='synthetic-cups-builder-v1',started_at=at,finished_at=at,input_tokens=0,output_tokens=0))
    binding={k:expected[k] for k in ('case_id','input_version','corpus_version')}
    retrieval=dict(**binding,status='MATCHED',passages=[passage],conflicts=[],retrieved_at=at)
    verification=dict(**binding,proposal_id=expected['proposal_id'],proposal_version=expected['proposal_version'],
        checks=[dict(citation_id=citation['citation_id'],result='VALID',message='Exact synthetic policy identity, version, location and hash.')],checked_at=at)
    lookup=body['order_lookup']; order=lookup.get('snapshot',{})
    if (packet!=expected or body['evidence_matrix']!=matrix or body['retrieval_result']!=retrieval
            or body['citation_verification']!=verification or lookup.get('status')!='MATCHED'
            or order.get('provider_id')!='synthetic_commerce' or order.get('currency')!='AUD'
            or order.get('line_items')!=[
                dict(line_item_id='line-mug-blue',sku='SYN-CUP-BLUE',description='Synthetic blue cup',quantity=1,unit_price_minor=1000),
                dict(line_item_id='line-mug-white',sku='SYN-CUP-WHITE',description='Synthetic white cup',quantity=1,unit_price_minor=1000)]):
        reject(uow)
