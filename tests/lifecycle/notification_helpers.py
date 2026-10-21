"""Cloud-only actual producer chains and explicit test-only notification grants."""
from dataclasses import asdict
from sqlalchemy import select
from returnops_api.private_notification import compose_private_notification
from returnops_domain import customer_tables as old, lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.notification_profile import COMPONENT
from returnops_domain.notification_intent import RETURN_PRODUCER
from returnops_domain.notification_tables import controls, facts
from manual_helpers import rows, snapshot, evidence
from label_artifact_helpers import customer, pdf_call_counts


def service(engine, identities, name='founder', **options):
    return compose_private_notification(engine,identities.auth_config,
        None if name is None else 'Bearer '+identities.tokens[name],**options)


def provision(engine, identities):
    with CustomerUnitOfWork(engine,write=True) as uow:
        store=identities.people['founder']['store_id']
        for component,purpose in ((COMPONENT,'NOTIFICATION'),(RETURN_PRODUCER,'OUTCOME')):
            if not uow.execute(select(life.authorities).where(life.authorities.c.store_id==store,
                life.authorities.c.component_id==component,life.authorities.c.purpose==purpose)).first():
                uow.execute(life.authorities.insert().values(store_id=store,component_id=component,
                    purpose=purpose,revision=1,enabled=True))
        uow.commit()


def _diagnostic_uow(observed):
    """Bounded code locations only; preserve the real UoW and every failure."""
    import sys
    safe_codes={'UNAUTHENTICATED','FORBIDDEN','NOT_FOUND','VALIDATION_ERROR','STALE_CASE_VERSION',
        'IDEMPOTENCY_CONFLICT','INVALID_STATE','REQUEST_TOO_LARGE','UNSUPPORTED_MEDIA_TYPE','INTERNAL_ERROR'}
    def capture(stage,error):
        if error is None:
            return
        if len(observed['events']) >= 8:
            observed['dropped'] += 1
            return
        frames=[]
        trace=error.__traceback__
        traversed=0
        while trace is not None and traversed < 64:
            frame=trace.tb_frame
            module=frame.f_globals.get('__name__','')
            if type(module) is str and module.startswith('returnops_domain.'):
                frames.append({'module':module,'function':frame.f_code.co_name,'line':trace.tb_lineno})
            trace=trace.tb_next
            traversed+=1
        from returnops_domain.errors import FlowError
        entry={'stage':stage,'type':type(error).__name__,'frames':frames[-12:],
               'frames_truncated':len(frames)>12 or trace is not None}
        if isinstance(error,FlowError) and error.code in safe_codes:
            entry['safe_code']=error.code
        observed['events'].append(entry)
    class DiagnosticUow(CustomerUnitOfWork):
        def poison(self):
            capture('poison',sys.exception())
            return super().poison()
        def __exit__(self,kind,value,trace):
            capture('exit',value)
            return super().__exit__(kind,value,trace)
    return DiagnosticUow


def ready(engine, identities, kind='reject', *, grants=True):
    """Return case_id/work_id and actual original producer result, never fake SENT."""
    artifact=None
    if kind=='return':
        from label_artifact_helpers import ready as prepare,complete,service as artifact_service
        args,_=prepare(engine,identities)
        artifact=complete(artifact_service(engine,identities),args)
        assert artifact.status=='COMMITTED',asdict(artifact)
        provision(engine,identities)
        head=next(row for row in rows(engine,old.case_heads) if row['case_id']==args['case_id'])
        observed={'events':[],'dropped':0}
        accepted=service(engine,identities,uow_factory=_diagnostic_uow(observed)).produce_return(
            args['case_id'],head['case_version'])
        assert accepted.status=='READY',{'result':asdict(accepted),'diagnostics':observed}
        case=args['case_id']
    elif kind=='reject':
        from reject_helpers import ready as prepare,attempt
        case,body=prepare(engine,identities)
        accepted=attempt(engine,identities,case,body)
        assert accepted.status=='ACCEPTED',asdict(accepted)
    elif kind in {'manual_pass','manual_escalated'}:
        from manual_helpers import service as manual_service
        if kind=='manual_pass':
            from pass_manual_helpers import ready as prepare,attempt
            case,body,_,at=prepare(engine,identities,preview_mode='none')
            accepted=attempt(engine,identities,case,body,at)
        else:
            from controlled_escalate_reviewer import ready_manual
            case,body=ready_manual(engine,identities)
            accepted=manual_service(engine,identities).accept(case,body,'notification-manual-key','notification_manual_corr')
        assert accepted.status=='ACCEPTED',asdict(accepted)
    else:
        from manual_helpers import ready as prepare,service as manual_service,provision_outcome
        if kind in {'manual_failure','manual_block'}:
            case,body=prepare(engine,identities,'failure' if kind=='manual_failure' else 'block')
        elif kind=='manual_intake':
            from returnops_domain.intake_processor import IntakeProcessor
            case=identities.flow().create({'original_message':'Synthetic intake source for notification.'},
                'notification-intake-create','notification_intake_corr').body['case_id']
            def broken(_):
                raise RuntimeError('Synthetic controlled intake failure')
            processor=IntakeProcessor(engine,evaluate=broken,retry_seconds=0)
            assert not processor.run_once() and processor.run_once()
            provision_outcome(engine,identities)
            head=next(row for row in rows(engine,old.case_heads) if row['case_id']==case)
            body=dict(expected_case_version=head['case_version'],decision='MANUAL_HANDLING',
                      reason='The operator will handle this request.',processing_failure_id=head['current_failure_id'])
        elif kind=='manual_assessment':
            from test_proposal_runtime_postgresql import ready as prepare_proposal,add_retained_clarifications
            from returnops_domain.proposal_processor import FixedProposalProcessor
            case=prepare_proposal(engine,identities)
            add_retained_clarifications(engine,identities,case,100)
            processor=FixedProposalProcessor(engine)
            assert processor.process(processor.prepare(case)).status=='FAILED'
            provision_outcome(engine,identities)
            head=next(row for row in rows(engine,old.case_heads) if row['case_id']==case)
            body=dict(expected_case_version=head['case_version'],decision='MANUAL_HANDLING',
                      reason='The operator will handle this request.',processing_failure_id=head['current_failure_id'])
        else:
            raise ValueError(kind)
        accepted=manual_service(engine,identities).accept(case,body,'notification-manual-key','notification_manual_corr')
        assert accepted.status=='ACCEPTED',asdict(accepted)
    if grants:provision(engine,identities)
    state=next(row for row in rows(engine,life.state) if row['case_id']==case)
    control=next(row for row in rows(engine,controls) if row['case_id']==case)
    assert control['notification_work_id']==state['notification_work_id'] and control['state']=='READY'
    return dict(case_id=case,work_id=control['notification_work_id'],control=control,
                producer=accepted,artifact=artifact)
