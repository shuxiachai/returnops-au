"""TEST ONLY real fixed proposal and accepted ESCALATE prerequisites."""
from sqlalchemy import select, update, delete
from returnops_api.private_revision import compose_private_revision
from returnops_domain import customer_tables as old, lifecycle_tables as t, investigation_tables as inv
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.revision_denial import COMPONENT
from controlled_escalate_reviewer import ready_review, receiver
from manual_helpers import rows, now


def provision(engine, identities):
    with CustomerUnitOfWork(engine, write=True) as uow:
        if not uow.execute(select(t.authorities).where(t.authorities.c.component_id == COMPONENT,
                t.authorities.c.purpose == 'REVISION')).first():
            uow.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],
                component_id=COMPONENT, purpose='REVISION', revision=1, enabled=True))
        uow.commit()


def ready(engine, identities, *, grant=True, evidence_ids=None):
    case, version = ready_review(engine, identities, evidence_ids=evidence_ids)
    assert receiver(engine).accept(case, version, 'original-review-key', 'review_correlation').status == 'ACCEPTED'
    proposal = next(r for r in rows(engine, old.history) if r['kind'] == 'PROPOSAL')
    if grant: provision(engine, identities)
    return case, dict(expected_case_version=version+1, decision='REQUEST_REVISION', reason='Please reassess this exact proposal.',
        proposal_id=proposal['object_id'], proposal_version=proposal['object_version'])


def service(engine, identities, name='founder', **options):
    return compose_private_revision(engine, identities.auth_config,
        None if name is None else 'Bearer '+identities.tokens[name], **options)


def attempt(engine, identities, case, body, **options):
    return service(engine, identities, **options).accept(case, body, 'original-revision-key', 'revision_correlation')


def assert_revised(engine, case, body, result):
    assert result.status == 'ACCEPTED', (result.status, result.safe_code, result.audit)
    head = next(r for r in rows(engine, old.case_heads) if r['case_id'] == case)
    state = next(r for r in rows(engine, t.state) if r['case_id'] == case)
    assert head['status'] == 'POLICY_ASSESSMENT' and head['case_version'] == body['expected_case_version']+1
    assert all(state[k] is None for k in ('proposal_record_id','review_record_id','preview_id','approval_record_id',
        'outcome_record_id','outcome','notification_record_id','notification_work_id'))
    work, = [r for r in rows(engine, t.work) if r['component_id'] == COMPONENT]
    assert work['purpose'] == 'REVISION' and work['state'] == 'DONE' and work['epoch'] == 1 and work['claim_id']
    assert state['generation'] == work['generation']+1 and head['input_version'] == work['input_version']
    assert not any(r['purpose'] in {'NOTIFICATION','EFFECT'} for r in rows(engine, t.work))
    assert not rows(engine, t.effects)
    assert not any(r['kind'] in {'APPROVAL','OPERATION','NOTIFICATION'} for r in rows(engine, old.history))


def mutate_authority(uow, identities, case, mode):
    if mode.startswith('human_') or mode == 'owner':
        from test_manual_postgresql import mutate_authority as human
        return human(uow, identities, case, mode)
    if mode == 'service_missing':
        uow.execute(delete(t.authorities).where(t.authorities.c.component_id == COMPONENT))
    elif mode in {'service_revoked','service_revision'}:
        uow.execute(update(t.authorities).where(t.authorities.c.component_id == COMPONENT).values(
            **({'enabled':False} if mode == 'service_revoked' else {'revision':2})))
    else:
        values = {'claim':{'claim_id':'replaced_claim'}, 'epoch':{'epoch':9},
            'lease':{'lease_expires_at':now()}, 'authority':{'authority_revision':2},
            'generation':{'generation':9}}[mode]
        uow.execute(update(t.work).where(t.work.c.component_id == COMPONENT).values(**values))


def mutate_source(uow, mode):
    state = uow.execute(select(t.state)).mappings().one()
    rid = state['review_record_id']
    if rid is None:
        rid = uow.execute(select(old.history.c.record_id).where(old.history.c.kind == 'REVIEW')).scalar_one()
    pid = uow.execute(select(old.history.c.record_id).where(old.history.c.kind == 'PROPOSAL')).scalar_one()
    if mode == 'review_event':uow.execute(delete(t.events).where(t.events.c.record_id == rid))
    elif mode == 'proposal_event':uow.execute(delete(t.events).where(t.events.c.record_id == pid))
    elif mode == 'review_binding':uow.execute(delete(t.sources).where(t.sources.c.record_id == rid))
    elif mode == 'review_claim':uow.execute(update(t.work).where(t.work.c.purpose == 'REVIEW').values(claim_id='bad_claim'))
    elif mode == 'review_generation':uow.execute(update(t.work).where(t.work.c.purpose == 'REVIEW').values(generation=77))
    elif mode == 'review_projection':uow.execute(update(t.sources).where(t.sources.c.record_id == rid).values(order_projection_id=None))
    elif mode == 'review_body':uow.execute(update(old.history_contents).where(old.history_contents.c.record_id == rid).values(body=b'{}'))
    elif mode == 'proposal_body':uow.execute(update(old.history_contents).where(old.history_contents.c.record_id == pid).values(body=b'{}'))
    elif mode == 'order_raw':uow.execute(update(inv.receipt_contents).values(body=b'{}'))
    elif mode == 'order_claim':uow.execute(update(inv.work).values(claim_id='bad_order_claim'))
    elif mode == 'order_available':uow.execute(update(inv.receipts).values(available=False))
    elif mode == 'raw_statement':
        from returnops_domain.storage import original_statement_contents
        uow.execute(update(original_statement_contents).values(raw_text=b'changed raw statement'))
    elif mode == 'input':uow.execute(update(old.case_heads).values(input_version=99))
    elif mode == 'generation':uow.execute(update(t.state).values(generation=99))
    elif mode == 'preview':uow.execute(update(t.state).values(preview_id='forbidden_preview'))
    elif mode == 'failure':uow.execute(update(old.case_heads).values(current_failure_id='unrelated_failure'))
    elif mode == 'block':uow.execute(update(inv.state).values(current_block_id='unrelated_block'))
    else:raise AssertionError(mode)
