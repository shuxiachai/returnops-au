"""Real PostgreSQL controlled REVIEW acceptance; planned groups map to nodes."""
from dataclasses import asdict
from copy import deepcopy
from datetime import timedelta
import pytest
from sqlalchemy import delete,select,text,update
from returnops_domain import customer_tables as old,lifecycle_tables as t,investigation_tables as inv
from returnops_domain import founder_codec as finite
from returnops_domain import preview_tables as preview
from returnops_domain.audit import identifier
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown,FlowError
from returnops_domain.lifecycle_state import installed
from returnops_domain.lifecycle_schema import version as schema_version,CURRENT,LEGACY
from returnops_domain.review_sources import COMPONENT
from returnops_api.database import readiness
from controlled_escalate_reviewer import ControlledReviewer,ready_review,receiver
from manual_helpers import rows,snapshot,business,evidence,now
from conftest import migrate


def attempt(engine,case,version,**options):
    return receiver(engine,**options).accept(case,version,'original-review-key','review_correlation')


def test_group03_actual_complete_bundle_atomic_review(flow_engine,identities,enabled,request):
    case,version=ready_review(flow_engine,identities);adapter=ControlledReviewer()
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='ACCEPTED',(result.status,result.safe_code,result.audit)
    after=snapshot(flow_engine)
    head=rows(flow_engine,old.case_heads)[0];state=rows(flow_engine,t.state)[0]
    assert head['status']=='ESCALATED' and head['case_version']==version+1
    assert head['input_version']==before['case_heads'][0]['input_version']
    assert state['generation']==before['case_lifecycle_state'][0]['generation']
    assert state['proposal_record_id']==before['case_lifecycle_state'][0]['proposal_record_id']
    raw=next(r['body'] for r in rows(flow_engine,old.history_contents) if r['record_id']==state['proposal_record_id'])
    assert adapter.calls==[finite.decode_document(raw)]
    assert after['lifecycle_authorities']==before['lifecycle_authorities']
    assert len([w for w in rows(flow_engine,t.work) if w['purpose']=='REVIEW' and w['state']=='DONE'])==1
    assert not rows(flow_engine,t.effects)
    evidence(request.node.nodeid,before=before,after=after,result=asdict(result),adapter_calls=len(adapter.calls))


@pytest.mark.parametrize('mode',['no_block','role','provider','run_id','tokens','citation','evidence','case','proposal','input',
    'corpus','malformed','PASS','PASS_WITH_WARNING','REVISE','NEEDS_INFORMATION'])
def test_group04_frozen_dto_provenance_and_references(flow_engine,identities,enabled,request,mode):
    case,version=ready_review(flow_engine,identities)
    def mutate(body):
        if mode=='no_block':body['findings'][0]['severity']='WARNING'
        elif mode in {'role','provider','run_id','tokens'}:
            name={'role':'role','provider':'provider_id','run_id':'run_id','tokens':'input_tokens'}[mode]
            body['model_run'][name]=1 if mode=='tokens' else 'ASSESSMENT' if mode=='role' else 'untrusted_value'
        elif mode in {'citation','evidence'}:body['findings'][0][mode+'_ids']=['outside_input']
        elif mode in {'case','proposal','input','corpus'}:
            key={'case':'case_id','proposal':'proposal_id','input':'input_version','corpus':'corpus_version'}[mode]
            body[key]=999 if mode=='input' else 'other_source'
        elif mode=='malformed':body['caller_actor']='untrusted'
        else:body['outcome']=mode
    adapter=ControlledReviewer(mutate);before=snapshot(flow_engine)
    result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    assert len(adapter.calls)==1
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),mutation=mode)


@pytest.mark.parametrize('mode',['event','binding','work_claim','work_epoch','work_generation','projection','audit','raw_source','bundle','owner','store'])
def test_group05_accepted_proposal_requires_actual_records(flow_engine,identities,enabled,request,mode):
    case,version=ready_review(flow_engine,identities)
    proposal=next(r for r in rows(flow_engine,old.history) if r['kind']=='PROPOSAL')
    work=next(r for r in rows(flow_engine,t.work) if r['purpose']=='PROPOSAL')
    with flow_engine.begin() as c:
        if mode=='event':c.execute(delete(t.events).where(t.events.c.work_id==work['work_id']))
        elif mode=='binding':c.execute(delete(t.sources).where(t.sources.c.record_id==proposal['record_id']))
        elif mode in {'work_claim','work_epoch','work_generation','owner','store'}:
            key={'work_claim':'claim_id','work_epoch':'epoch','work_generation':'generation','owner':'owner_id','store':'store_id'}[mode]
            c.execute(update(t.work).where(t.work.c.work_id==work['work_id']).values(**{key:99 if mode in {'work_epoch','work_generation'} else 'wrong_identity'}))
        elif mode=='projection':c.execute(update(t.sources).where(t.sources.c.record_id==proposal['record_id']).values(order_projection_id=None))
        elif mode=='audit':c.execute(update(old.audit).values(body=b'{}'))
        elif mode=='raw_source':
            from returnops_domain.storage import original_statement_contents
            c.execute(update(original_statement_contents).values(raw_text=b'corrupted source'))
        else:c.execute(update(old.history_contents).where(old.history_contents.c.record_id==proposal['record_id']).values(body=b'{}'))
    adapter=ControlledReviewer();before=snapshot(flow_engine);result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    assert not adapter.calls
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


@pytest.mark.parametrize('mode',['missing','disabled','wrong_component','owner_disabled','wrong_owner_store'])
def test_group06_review_authority_entry(flow_engine,identities,enabled,request,mode):
    case,version=ready_review(flow_engine,identities)
    with flow_engine.begin() as c:
        q=t.authorities.c.component_id==COMPONENT
        if mode=='missing':c.execute(delete(t.authorities).where(q))
        elif mode=='disabled':c.execute(update(t.authorities).where(q).values(enabled=False))
        elif mode=='wrong_component':c.execute(update(t.authorities).where(q).values(component_id='wrong_component'))
        else:c.execute(update(old.principals).where(old.principals.c.principal_id==identities.people['customer_a']['principal_id']).values(
            **({'enabled':False} if mode=='owner_disabled' else {'store_id':'wrong_store'})))
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version)
    assert result.status=='DENIED' and result.audit=='NOT_RECORDED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


@pytest.mark.parametrize('mode',['grant_revision','grant_disabled','claim','epoch','lease','owner'])
def test_group06_original_claim_and_authority_final(flow_engine,identities,enabled,request,mode):
    case,version=ready_review(flow_engine,identities)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if mode.startswith('grant_'):self.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(
                **({'revision':2} if mode=='grant_revision' else {'enabled':False})))
            elif mode=='owner':self.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(owner_principal_id='wrong_owner'))
            else:self.execute(update(t.work).where(t.work.c.purpose=='REVIEW').values(**{
                {'claim':'claim_id','epoch':'epoch','lease':'lease_expires_at'}[mode]:
                'replacement_claim' if mode=='claim' else 8 if mode=='epoch' else now()-timedelta(seconds=1)}))
            return super().commit()
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version,uow_factory=Changed)
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


@pytest.mark.parametrize('mode',['expired','grant_revision','claim','owner'])
def test_group06_slow_source_validation_expires_original_lease(flow_engine,identities,enabled,request,monkeypatch,mode):
    from returnops_domain import review_escalation
    case,version=ready_review(flow_engine,identities);caller=receiver(flow_engine)
    original=review_escalation.accepted_review
    def delayed(*args,**kwargs):
        result=original(*args,**kwargs)
        uow=args[0]
        if mode=='expired':caller.clock=lambda:now()+timedelta(seconds=1000)
        elif mode=='grant_revision':uow.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(revision=2))
        elif mode=='claim':uow.execute(update(t.work).where(t.work.c.purpose=='REVIEW').values(claim_id='replacement_claim'))
        else:uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(owner_principal_id='changed_owner'))
        return result
    monkeypatch.setattr(review_escalation,'accepted_review',delayed)
    before=snapshot(flow_engine);result=caller.accept(case,version,'original-review-key','review_correlation')
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),delay='after final complete-source validation')


@pytest.mark.parametrize('flow_engine',[LEGACY],indirect=True)
@pytest.mark.parametrize('mode',['empty','failure_manual','block_manual'])
def test_group01_legacy_empty_or_real_manual_upgrade(flow_engine,identities,enabled,request,mode):
    from manual_helpers import ready,service,assert_pending
    if mode!='empty':
        case,body=ready(flow_engine,identities,'failure' if mode=='failure_manual' else 'block')
        result=service(flow_engine,identities).accept(case,body,'legacy-manual-key','legacy_correlation')
        assert_pending(flow_engine,case,body,result)
    before=snapshot(flow_engine);migrate(flow_engine);migrate(flow_engine);after=snapshot(flow_engine)
    from returnops_domain import execution_preparation_tables, return_execution_tables, label_execution_tables
    label_added = label_execution_tables.metadata.tables
    assert set(label_added) == {
        'core_mock_label_ledger', 'label_provider_permissions',
        'lifecycle_label_artifact_work', 'lifecycle_label_execution_controls',
    }
    from returnops_domain import label_artifact_tables
    artifact_added = label_artifact_tables.metadata.tables
    assert set(artifact_added) == {
        'label_artifact_permissions', 'lifecycle_label_artifact_controls',
        'lifecycle_label_artifact_claims', 'generated_label_artifacts',
        'generated_label_artifact_contents',
    }
    added=set(artifact_added) | set(preview.metadata.tables) | set(execution_preparation_tables.metadata.tables) | set(return_execution_tables.metadata.tables) | set(label_added)
    assert {k:v for k,v in before.items() if k!='alembic_version'}=={k:v for k,v in after.items() if k!='alembic_version' and k not in added}
    assert set(after)-set(before)==added
    assert all(after[name]==[] for name in added)
    assert after['alembic_version']==[{'version_num':CURRENT}]
    assert readiness(flow_engine)
    assert not any(w['purpose']=='REVIEW' for w in rows(flow_engine,t.work))
    evidence(request.node.nodeid,before=before,after=after,legacy_mode=mode)


@pytest.mark.parametrize('flow_engine',[LEGACY],indirect=True)
def test_groups01_02_real_legacy_upgrade_no_rewrites(flow_engine,identities,enabled,request):
    case,version=ready_review(flow_engine,identities)
    before=snapshot(flow_engine)
    assert not readiness(flow_engine)
    denied=attempt(flow_engine,case,version)
    assert denied.status=='DENIED' and snapshot(flow_engine)==before
    with CustomerUnitOfWork(flow_engine,write=True) as uow:assert installed(uow);uow.commit()
    migrate(flow_engine);migrate(flow_engine)
    after=snapshot(flow_engine)
    from returnops_domain import execution_preparation_tables, return_execution_tables, label_execution_tables
    label_added = label_execution_tables.metadata.tables
    assert set(label_added) == {
        'core_mock_label_ledger', 'label_provider_permissions',
        'lifecycle_label_artifact_work', 'lifecycle_label_execution_controls',
    }
    from returnops_domain import label_artifact_tables
    artifact_added = label_artifact_tables.metadata.tables
    assert set(artifact_added) == {
        'label_artifact_permissions', 'lifecycle_label_artifact_controls',
        'lifecycle_label_artifact_claims', 'generated_label_artifacts',
        'generated_label_artifact_contents',
    }
    added=set(artifact_added) | set(preview.metadata.tables) | set(execution_preparation_tables.metadata.tables) | set(return_execution_tables.metadata.tables) | set(label_added)
    assert {k:v for k,v in before.items() if k!='alembic_version'}=={k:v for k,v in after.items() if k!='alembic_version' and k not in added}
    assert set(after)-set(before)==added
    assert all(after[name]==[] for name in added)
    assert after['alembic_version']==[{'version_num':CURRENT}]
    assert readiness(flow_engine)
    accepted=attempt(flow_engine,case,version);assert accepted.status=='ACCEPTED'
    evidence(request.node.nodeid,before=before,after_upgrade=after,result=asdict(accepted),legacy_review=asdict(denied))


@pytest.mark.parametrize('mode',['old_stamp_new_check','new_stamp_old_check','partial','missing','unknown','multiple','extra_table','unvalidated',
    'literal_space','literal_parenthesis','literal_cast'])
def test_group02_corrupt_schema_fails_closed(flow_engine,identities,enabled,request,mode):
    case,version=ready_review(flow_engine,identities)
    with flow_engine.begin() as c:
        if mode=='old_stamp_new_check':c.execute(text("UPDATE alembic_version SET version_num='0007_lifecycle_guards'"))
        elif mode in {'new_stamp_old_check','unvalidated','literal_space','literal_parenthesis','literal_cast'}:
            c.execute(text('ALTER TABLE lifecycle_work DROP CONSTRAINT ck_lifecycle_work'))
            last={'literal_space':'RE VIEW','literal_parenthesis':'RE(VIEW)','literal_cast':'RE::textVIEW'}.get(mode,'REVIEW')
            expression="purpose IN ('PROPOSAL','REVISION','OUTCOME','NOTIFICATION','EFFECT'"+(", '"+last+"')" if mode!='new_stamp_old_check' else ')')+" AND state IN ('PENDING','RUNNING','DONE','SUPERSEDED','PAUSED') AND epoch >= 0"
            c.execute(text('ALTER TABLE lifecycle_work ADD CONSTRAINT ck_lifecycle_work CHECK ('+expression+')'+(' NOT VALID' if mode=='unvalidated' else '')))
        elif mode in {'partial','missing'}:
            c.execute(text('DROP TABLE lifecycle_authorities' if mode=='partial' else 'ALTER TABLE lifecycle_work DROP CONSTRAINT ck_lifecycle_work'))
        elif mode=='unknown':c.execute(text("UPDATE alembic_version SET version_num='unknown_revision'"))
        elif mode=='multiple':c.execute(text("INSERT INTO alembic_version VALUES ('unknown_revision')"))
        else:c.execute(text('CREATE TABLE unexpected_business_table (id integer)'))
    before=snapshot(flow_engine)
    assert not readiness(flow_engine)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError):installed(uow)
    result=attempt(flow_engine,case,version)
    assert result.status=='DENIED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))
