"""Self-consistent future bundles must still match real accepted input sources."""
from io import BytesIO
from pypdf import PdfWriter
import pytest
from sqlalchemy import select,update
from returnops_domain import customer_tables as old, investigation_tables as investigation, lifecycle_tables as t
from returnops_domain.audit import identifier
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.evidence_validation import validate_evidence
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.lifecycle_events import ProposalAccepted
from returnops_domain.lifecycle_guards import LifecycleGuards
from synthetic_sources import COMPONENT,now,ready,head,claim,material,stage,bind_source,rows,proposal


@pytest.mark.parametrize('mutation',['original_identity','statement_bytes','snapshot','citation_hash','citation_location','passage_bytes'])
def test_self_consistent_hash_does_not_authorize_fabricated_inputs(flow_engine,identities,enabled,mutation):
    original=ready(flow_engine,identities);case=original['case_id'];before=rows(flow_engine,old.history)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,ProposalAccepted);h=head(uow,case);body=material('PROPOSAL',h,identities,uow=uow)['content']
        if mutation=='original_identity':
            body['packet']['original_statement_id']='not_the_real_original';body['statements'][0]['statement_id']='not_the_real_original'
            for criterion in body['evidence_matrix']+body['packet']['evidence_matrix']:criterion['statement_ids']=['not_the_real_original']
        elif mutation=='statement_bytes':body['statements'][0]['raw_text']+=' altered'
        elif mutation=='snapshot':body['order_lookup']['snapshot']['order_id']='different_order'
        elif mutation=='citation_hash':body['packet']['citations'][0]['content_sha256']='f'*64
        elif mutation=='citation_location':body['packet']['citations'][0]['location']='unrelated location'
        else:body['retrieval_result']['passages'][0]['content']+=' altered'
        source=stage(uow,h,'PROPOSAL',body);bind_source(uow,source,token)
        with pytest.raises(FlowError):LifecycleGuards(COMPONENT).apply(uow,ProposalAccepted(identifier('event'),token,source),now())
        with pytest.raises(FlowError):uow.commit()
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.events)==[]


def test_necessary_real_clarification_cannot_be_silently_omitted(flow_engine,identities,enabled):
    original=ready(flow_engine,identities,reference=None);case=original['case_id']
    view=identities.flow().get_case(case).body;group=rows(flow_engine,investigation.groups)[0]
    request={'expected_case_version':view['case_version'],'question_set_id':view['clarification']['question_set_id'],
        'answers':[{'question_id':group['reference_question_id'],'text':'SYN-1001'}],'evidence_ids':[]}
    identities.flow().clarify(case,request,'source-clarify-key',identifier('corr'))
    assert IntakeProcessor(flow_engine).run_once() and InvestigationProcessor(flow_engine).run_once()
    before=rows(flow_engine,old.history)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,ProposalAccepted);h=head(uow,case);body=material('PROPOSAL',h,identities,uow=uow)['content']
        assert len(body['statements'])==2
        body['statements']=[value for value in body['statements'] if value['kind']=='ORIGINAL']
        for criterion in body['evidence_matrix']+body['packet']['evidence_matrix']:
            criterion['statement_ids']=[body['packet']['original_statement_id']]
        source=stage(uow,h,'PROPOSAL',body);bind_source(uow,source,token)
        with pytest.raises(FlowError):LifecycleGuards(COMPONENT).apply(uow,ProposalAccepted(identifier('event'),token,source),now())
        with pytest.raises(FlowError):uow.commit()
    assert rows(flow_engine,old.history)==before
    proposal(flow_engine,identities,case)


@pytest.mark.parametrize('mutation',['omit','metadata','bytes'])
def test_real_bound_attachment_identity_metadata_and_bytes_are_required(flow_engine,identities,enabled,mutation):
    writer=PdfWriter();writer.add_blank_page(width=100,height=100);output=BytesIO();writer.write(output)
    accepted=identities.flow().stage(validate_evidence(output.getvalue(),'proof.pdf','application/pdf'),'evidence-key',identifier('corr'))
    evidence_id=accepted.body['evidence_id'];original=ready(flow_engine,identities,evidence_ids=[evidence_id]);case=original['case_id']
    before=rows(flow_engine,old.history)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,ProposalAccepted);h=head(uow,case);body=material('PROPOSAL',h,identities,uow=uow)['content']
        assert len(body['attachments'])==1
        if mutation=='omit':
            body['attachments']=[]
            for criterion in body['evidence_matrix']+body['packet']['evidence_matrix']:criterion['evidence_ids']=[]
        elif mutation=='metadata':body['attachments'][0]['filename']='fabricated.pdf'
        else:uow.execute(update(old.evidence_contents).where(old.evidence_contents.c.evidence_id==evidence_id).values(body=b'corrupted synthetic bytes'))
        source=stage(uow,h,'PROPOSAL',body);bind_source(uow,source,token)
        with pytest.raises(FlowError):LifecycleGuards(COMPONENT).apply(uow,ProposalAccepted(identifier('event'),token,source),now())
        with pytest.raises(FlowError):uow.commit()
    assert rows(flow_engine,old.history)==before
    proposal(flow_engine,identities,case)


def test_accepting_projection_preserves_source_n_receipt_and_retrieval_conflicts(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id']
    receipt=rows(flow_engine,investigation.receipts)[0];raw=rows(flow_engine,investigation.receipt_contents)[0]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,ProposalAccepted);h=head(uow,case);body=material('PROPOSAL',h,identities,uow=uow)['content']
        body['retrieval_result']['conflicts']=['Explicit synthetic conflict retained for later independent review']
        assert receipt['input_version']==1 and body['order_lookup']['input_version']==h['input_version']==2
        source=stage(uow,h,'PROPOSAL',body);bind_source(uow,source,token)
        LifecycleGuards(COMPONENT).apply(uow,ProposalAccepted(identifier('event'),token,source),now());uow.commit()
    assert rows(flow_engine,investigation.receipts)[0]==receipt and rows(flow_engine,investigation.receipt_contents)[0]==raw
    binding=next(row for row in rows(flow_engine,t.sources) if row['record_id']==source)
    assert binding['order_projection_id']==rows(flow_engine,investigation.projections)[0]['projection_id']


def test_proposal_cannot_omit_its_durable_order_projection_anchor(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id'];before=rows(flow_engine,old.history)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,ProposalAccepted);h=head(uow,case);body=material('PROPOSAL',h,identities,uow=uow)['content']
        source=stage(uow,h,'PROPOSAL',body);bind_source(uow,source,token,order_projection_id=None)
        with pytest.raises(FlowError):LifecycleGuards(COMPONENT).apply(uow,ProposalAccepted(identifier('event'),token,source),now())
        with pytest.raises(FlowError):uow.commit()
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.events)==[]
