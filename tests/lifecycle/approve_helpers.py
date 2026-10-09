"""Test-only setup for the private preview then Founder-approve component.

These helpers deliberately provision PREVIEW and APPROVAL grants in the test
transaction.  Production composition must not create either grant, and these
helpers never provision EXECUTION.
"""
from sqlalchemy import select

from returnops_api.private_approve import compose_private_approve
from returnops_api.private_preview import compose_private_preview
from returnops_domain import customer_tables as old, lifecycle_tables as lifecycle
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.preview_profile import APPROVAL_COMPONENT, COMPONENT
from manual_helpers import rows
from pass_review_helpers import ControlledPassReviewer, ready_pass, receiver


def provision(engine, identities):
    """Explicit fixture-only grants; EXECUTION intentionally remains absent."""
    with CustomerUnitOfWork(engine, write=True) as uow:
        for component, purpose in ((COMPONENT, 'PREVIEW'), (APPROVAL_COMPONENT, 'APPROVAL')):
            exists = uow.execute(select(lifecycle.authorities).where(
                lifecycle.authorities.c.component_id == component,
                lifecycle.authorities.c.purpose == purpose,
            )).first()
            if exists is None:
                uow.execute(lifecycle.authorities.insert().values(
                    store_id=identities.people['founder']['store_id'], component_id=component,
                    purpose=purpose, revision=1, enabled=True))
        uow.commit()


def preview(engine, identities, **options):
    return compose_private_preview(engine, **options)


def approve(engine, identities, name='founder', **options):
    return compose_private_approve(engine, identities.auth_config,
        None if name is None else 'Bearer ' + identities.tokens[name], **options)


def ready(engine, identities, *, outcome='PASS'):
    """Create an actual retained PASS chain and then its server-owned preview."""
    case, version = ready_pass(engine, identities)
    review = receiver(engine, ControlledPassReviewer(outcome)).accept(
        case, version, 'approve-pass-key', 'approve-pass-correlation')
    assert review.status == 'ACCEPTED', review
    provision(engine, identities)
    preview_result = preview(engine, identities).accept(
        case, version + 1, 'approve-preview-key', 'approve-preview-correlation')
    assert preview_result.status == 'ACCEPTED', preview_result
    action_preview = preview_result.receipt['action_preview']
    proposal = next(row for row in rows(engine, old.history)
        if row['case_id'] == case and row['kind'] == 'PROPOSAL')
    request = dict(expected_case_version=version + 2, proposal_id=proposal['object_id'],
        proposal_version=proposal['object_version'], decision='APPROVE',
        reason='The Founder approves this retained simulated return.',
        preview_id=action_preview['preview_id'], scope_fingerprint=action_preview['scope_fingerprint'])
    return case, action_preview, request


def no_execution_grant(engine):
    return not any(row['purpose'] == 'EXECUTION' and row['enabled']
        for row in rows(engine, lifecycle.authorities))


def assert_approved_without_effects(engine, case, request, result):
    assert result.status == 'ACCEPTED', result
    head = next(row for row in rows(engine, old.case_heads) if row['case_id'] == case)
    state = next(row for row in rows(engine, lifecycle.state) if row['case_id'] == case)
    assert head['status'] == 'APPROVED'
    assert head['case_version'] == request['expected_case_version'] + 1
    assert state['approval_record_id'] and state['preview_id'] == request['preview_id']
    work = [row for row in rows(engine, lifecycle.work) if row['case_id'] == case and row['purpose'] == 'EXECUTION']
    assert len(work) == 1
    assert work[0]['state'] == 'PENDING' and work[0]['epoch'] == 0
    assert all(work[0][field] is None for field in ('claim_id', 'claimed_case_version',
        'lease_expires_at', 'authority_revision'))
    assert not rows(engine, lifecycle.effects)
    assert no_execution_grant(engine)
