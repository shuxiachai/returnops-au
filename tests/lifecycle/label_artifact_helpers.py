"""Synthetic original business chain; explicit independent artifact test grants."""
from dataclasses import asdict
from sqlalchemy import select
from returnops_api.private_label_artifact import compose_private_label_artifact
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain.customer_service import CustomerFlow
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain import customer_tables as old,lifecycle_tables as life
from returnops_domain.label_artifact_tables import permissions,controls,artifacts,contents,claims
from returnops_domain.label_artifact_sources import COMPONENT,CONFIG,profile_hash
from returnops_domain.label_pdf import PDF_PROFILE_ID
from returnops_domain.core_label_artifact_mock import ArtifactTicket
from label_execution_helpers import ready as label_ready,service as label_service,execute
from manual_helpers import rows,snapshot,evidence

def pdf_call_counts(*,forbid_render=True,forbid_validation=False,forbid_removed_dto=False):
    """Profile actual function code, including preexisting import aliases.

    Positive fixtures are prepared first. This does not replace renderer
    attributes or the T2 port; each observation starts with fresh counts.
    """
    from contextlib import contextmanager
    from inspect import unwrap
    import sys
    from returnops_domain import label_pdf as pdf,label_pdf_validation as validation,label_artifact_sources as sources
    from returnops_domain import label_artifact_history as history
    from returnops_domain.core_return_mock import CoreReturnMock
    from returnops_domain.core_label_mock import CoreLabelMock
    from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock
    functions=dict(render=pdf.render_label_pdf,text_line=pdf._text_line,assembly=pdf._assemble_pdf,
        expected_pdf=sources.expected_pdf,validation=unwrap(validation.verify_label_pdf),
        return_provider=CoreReturnMock.perform,label_provider=CoreLabelMock.perform,
        artifact_retrieval=CoreLabelArtifactMock.retrieve_original_label,
        evidence_dto=history.evidence_body,result_dto=history.result_body)
    codes={function.__code__:name for name,function in functions.items()}
    forbidden={'return_provider','label_provider','artifact_retrieval'}
    if forbid_render:forbidden|={'render','text_line','assembly','expected_pdf'}
    if forbid_validation:forbidden.add('validation')
    if forbid_removed_dto:forbidden|={'evidence_dto','result_dto'}
    @contextmanager
    def observe():
        counts={name:0 for name in functions};previous=sys.getprofile()
        def profile(frame,event,arg):
            if event=='call' and frame.f_code in codes:
                name=codes[frame.f_code];counts[name]+=1
                if name in forbidden:raise AssertionError('Forbidden actual PDF/provider code: '+name)
            if previous is not None:previous(frame,event,arg)
        sys.setprofile(profile)
        try:yield counts
        finally:sys.setprofile(previous)
    return observe()

def provision(engine,identities):
    with CustomerUnitOfWork(engine,write=True) as uow:
        store=identities.people['founder']['store_id']
        uow.execute(life.authorities.insert().values(store_id=store,component_id=COMPONENT,purpose='EFFECT',revision=1,enabled=True))
        uow.execute(permissions.insert().values(store_id=store,component_id=COMPONENT,provider_id=CONFIG['provider_id'],
            config_id=CONFIG['config_id'],pdf_profile_id=PDF_PROFILE_ID,profile_hash=profile_hash(),revision=1,
            read_existing_enabled=True,store_enabled=True))
        uow.commit()

def ready(engine,identities,*,grants=True):
    args,setup=label_ready(engine,identities)
    result=execute(label_service(engine,identities),args)
    assert result.status=='COMMITTED' and result.operation_state=='EXECUTING',asdict(result)
    if grants:provision(engine,identities)
    return dict(case_id=args['case_id'],artifact_work_id=result.artifact_work_id,
        original_approval_key=args['original_approval_key'],correlation_id='artifact-complete-correlation'),dict(label_args=args,upstream=setup,label=result)

def service(engine,identities,name='founder',**options):
    return compose_private_label_artifact(engine,identities.auth_config,
        None if name is None else 'Bearer '+identities.tokens[name],**options)

def customer(engine,identities,name='customer_a',**options):
    return CustomerFlow(engine,CurrentRequestAuthority(identities.auth_config,'Bearer '+identities.tokens[name]),**options)

def complete(caller,args):return caller.complete_label_artifact(**args)
def recover(caller,args):return caller.recover_label_artifact(**args)
def claim(caller,args):
    value=caller._claim(*(args[n] for n in ('case_id','artifact_work_id','original_approval_key','correlation_id')))
    assert type(value) is ArtifactTicket,asdict(value)
    return value

def assert_delta(engine,before,result):
    assert result.status=='COMMITTED' and result.operation_state=='SUCCEEDED',asdict(result)
    after=snapshot(engine)
    changed={n for n in before if before[n]!=after[n]}
    assert changed=={old.case_heads.name,old.history.name,old.history_contents.name,old.audit.name,
        'founder_history_encodings',controls.name,claims.name,artifacts.name,contents.name,life.effects.name}
    a,=before[old.case_heads.name];b,=after[old.case_heads.name]
    assert {n:v for n,v in a.items() if n not in {'history_sequence','audit_sequence','audit_head'}}=={
        n:v for n,v in b.items() if n not in {'history_sequence','audit_sequence','audit_head'}}
    assert b['history_sequence']==a['history_sequence']+2 and b['audit_sequence']==a['audit_sequence']+2
    assert len(after[old.history.name])==len(before[old.history.name])+2
    assert len(after[old.audit.name])==len(before[old.audit.name])+2
    assert len(after[life.effects.name])==len(before[life.effects.name])+1
    assert len(after[artifacts.name])==len(after[contents.name])==len(after[claims.name])==1
    return after
