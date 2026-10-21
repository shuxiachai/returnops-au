"""TEST ONLY actual retained PASS and HUMAN REJECT prerequisites."""
from datetime import timedelta
from sqlalchemy import delete, select, update
from returnops_api.private_reject import compose_private_reject
from returnops_domain import customer_tables as old, lifecycle_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.reject_denial import COMPONENT
from pass_review_helpers import ready_pass, receiver, ControlledPassReviewer
from manual_helpers import rows, now
from revision_helpers import mutate_source as mutate_retained_source


def provision(engine, identities):
    """Explicit test provisioning; private composition never creates grants."""
    with CustomerUnitOfWork(engine, write=True) as uow:
        if not uow.execute(select(t.authorities).where(t.authorities.c.component_id == COMPONENT,
                t.authorities.c.purpose == 'OUTCOME')).first():
            uow.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],
                component_id=COMPONENT, purpose='OUTCOME', revision=1, enabled=True))
        uow.commit()


def ready(engine, identities, *, grant=True, outcome='PASS'):
    case, version = ready_pass(engine, identities)
    accepted = receiver(engine, ControlledPassReviewer(outcome)).accept(
        case, version, 'original-pass-key', 'pass_correlation')
    assert accepted.status == 'ACCEPTED', (accepted.status, accepted.safe_code, accepted.audit)
    proposal = next(r for r in rows(engine, old.history) if r['case_id'] == case and r['kind'] == 'PROPOSAL')
    if grant: provision(engine, identities)
    return case, dict(expected_case_version=version+1, decision='REJECT', reason='The Founder rejects this exact proposal.',
        proposal_id=proposal['object_id'], proposal_version=proposal['object_version'])


def service(engine, identities, name='founder', **options):
    return compose_private_reject(engine, identities.auth_config,
        None if name is None else 'Bearer '+identities.tokens[name], **options)


def attempt(engine, identities, case, body, **options):
    return service(engine, identities, **options).accept(case, body, 'original-reject-key', 'reject_correlation')


def provision_notification(engine, identities):
    """Only a future test caller owns this grant and notification progression."""
    with CustomerUnitOfWork(engine, write=True) as uow:
        uow.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],
            component_id=COMPONENT, purpose='NOTIFICATION', revision=1, enabled=True))
        uow.commit()


def assert_rejected(engine, case, body, result):
    assert result.status == 'ACCEPTED', (result.status, result.safe_code, result.audit)
    head = next(r for r in rows(engine, old.case_heads) if r['case_id'] == case)
    state = next(r for r in rows(engine, t.state) if r['case_id'] == case)
    assert head['status'] == 'NOTIFICATION_PENDING' and head['case_version'] == body['expected_case_version']+1
    assert state['outcome'] == 'REJECTED' and state['proposal_record_id'] and state['review_record_id']
    assert all(state[k] is None for k in ('preview_id', 'approval_record_id', 'return_record_id', 'label_record_id'))
    from returnops_domain.lifecycle_schema import NOTIFICATION,version
    from returnops_domain.notification_profile import COMPONENT as delivery_component
    with engine.connect() as connection:
        modern=version(connection)==NOTIFICATION
    expected_notification_component=delivery_component if modern else COMPONENT
    works = [r for r in rows(engine,t.work) if r['case_id']==case
             and r['component_id'] in {COMPONENT,expected_notification_component}]
    assert len(works) == 2
    outcome = next(r for r in works if r['purpose'] == 'OUTCOME')
    notification = next(r for r in works if r['purpose'] == 'NOTIFICATION')
    assert outcome['component_id']==COMPONENT and notification['component_id']==expected_notification_component
    if modern:
        from returnops_domain.notification_tables import controls,facts
        saved,=[row for row in rows(engine,controls) if row['case_id']==case]
        assert saved['notification_work_id']==notification['work_id'] and saved['state']=='READY'
        assert saved['attempt_count']==0 and saved['producer_id']==COMPONENT
        assert not [row for row in rows(engine,facts) if row['case_id']==case]
    assert outcome['state'] == 'DONE' and outcome['epoch'] == 1 and outcome['claim_id']
    assert state['generation'] == outcome['generation'] and head['input_version'] == outcome['input_version']
    assert notification['state'] == 'PENDING' and notification['epoch'] == 0
    assert all(notification[k] is None for k in ('claim_id', 'lease_expires_at', 'authority_revision'))
    assert notification['idempotency_key'] and notification['work_id'] == state['notification_work_id']
    assert not rows(engine, t.effects)
    assert not any(r['kind'] in {'APPROVAL', 'OPERATION'} for r in rows(engine, old.history))
    assert result.receipt['decision'] == 'REJECT' and result.receipt['case_version'] == head['case_version']


def mutate_authority(uow, identities, case, mode):
    if mode.startswith('human_') or mode == 'owner':
        from test_manual_postgresql import mutate_authority as human
        return human(uow, identities, case, mode)
    if mode == 'service_missing':
        uow.execute(delete(t.authorities).where(t.authorities.c.component_id == COMPONENT))
    elif mode in {'service_revoked', 'service_revision'}:
        uow.execute(update(t.authorities).where(t.authorities.c.component_id == COMPONENT).values(
            **({'enabled':False} if mode == 'service_revoked' else {'revision':2})))
    else:
        values = {'claim':{'claim_id':'replaced_claim'}, 'epoch':{'epoch':9},
            'lease':{'lease_expires_at':now()}, 'authority':{'authority_revision':2},
            'generation':{'generation':9}, 'lease_renewal':{'lease_expires_at':now()+timedelta(seconds=3600)}}[mode]
        uow.execute(update(t.work).where(t.work.c.component_id == COMPONENT, t.work.c.purpose == 'OUTCOME').values(**values))


def mutate_source(uow, mode):
    state = uow.execute(select(t.state)).mappings().one()
    rid = state['review_record_id']
    if mode == 'missing_review':
        uow.execute(update(t.state).values(review_record_id=None))
    elif mode in {'review_fingerprint', 'review_ESC', 'review_version'}:
        values = {'review_fingerprint':{'fingerprint':'0'*64}, 'review_ESC':{'event_kind':'REVIEW_ESCALATE'},
            'review_version':{'pre_case_version':999}}[mode]
        uow.execute(update(t.events).where(t.events.c.record_id == rid).values(**values))
    elif mode == 'review_audit':
        from returnops_domain.canonical import decode_document
        for row in uow.execute(select(old.audit)).mappings():
            if any(ref['record_id'] == rid for ref in decode_document(row['body'])['history_refs']):
                uow.execute(delete(old.audit).where(old.audit.c.event_id == row['event_id']))
    elif mode in {'approval', 'outcome', 'notification', 'return', 'label'}:
        field = {'approval':'approval_record_id', 'outcome':'outcome_record_id',
            'notification':'notification_record_id', 'return':'return_record_id', 'label':'label_record_id'}[mode]
        uow.execute(update(t.state).values(**{field:'forbidden_existing_source'}))
    else:
        mutate_retained_source(uow, mode)
