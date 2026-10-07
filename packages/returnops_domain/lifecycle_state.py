"""Current-reference invalidation shared by the actual input/retention callers."""
from sqlalchemy import select, text, update, delete
from . import customer_tables as old, lifecycle_tables as t
from .errors import FlowError

LEGACY_REVISIONS = {'0003_customer_flow', '0004_pre_case_audit', '0005_order_investigation', '0006_founder_reads'}
from .lifecycle_schema import CURRENT as REVISION, LEGACY, version as schema_version
MAX_VERSION = 9007199254740991


def reject(uow, code='INVALID_STATE'):
    uow.poison()
    raise FlowError(code)


def installed(uow):
    """Only explicitly old migration fixtures may use their old write behavior.

    At 0007, a missing table is corruption, never a reason to skip guards.
    The application readiness gate independently requires the exact head.
    """
    revisions = uow.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    names = set(uow.execute(text('SELECT tablename FROM pg_tables WHERE schemaname=current_schema()')).scalars())
    present = set(t.metadata.tables) & names
    if revisions in ([REVISION], [LEGACY]) and schema_version(uow.connection) in {REVISION, LEGACY}:
        return True
    if len(revisions) == 1 and revisions[0] in LEGACY_REVISIONS and not present:
        return False
    reject(uow)


def current(uow, head, *, initialize=False):
    row = uow.execute(select(t.state).where(t.state.c.case_id == head['case_id'])).mappings().one_or_none()
    if row is None and initialize:
        values = dict(case_id=head['case_id'], input_version=head['input_version'], generation=1,
            proposal_version=0, proposal_record_id=None, review_record_id=None, preview_id=None,
            approval_record_id=None, outcome_record_id=None, outcome=None, notification_id=None,
            notification_record_id=None, notification_hash=None, available=True)
        values.update(return_record_id=None, label_record_id=None, notification_work_id=None)
        uow.execute(t.state.insert().values(**values))
        return values
    if row is not None and row['input_version'] != head['input_version']:
        reject(uow)
    return row


def invalidate(uow, head, *, input_version=None, retention=False, accepting_event=None):
    if not installed(uow):
        return
    row = current(uow, head, initialize=True)
    preserve = None
    if accepting_event is not None:
        from .lifecycle_events import RevisionRequested
        if type(accepting_event) is not RevisionRequested or input_version is not None or retention:
            reject(uow)
        claim=accepting_event.claim
        if (claim.case_version!=head['case_version'] or claim.input_version!=head['input_version']
                or claim.generation!=row['generation']):
            reject(uow)
        work=uow.execute(select(t.work).where(t.work.c.work_id==claim.work_id)).mappings().one_or_none()
        source=uow.execute(select(t.sources).where(t.sources.c.record_id==accepting_event.record_id)).mappings().one_or_none()
        expected=dict(case_id=head['case_id'],work_id=claim.work_id,claim_id=claim.claim_id,epoch=claim.epoch,
            generation=row['generation'],input_version=head['input_version'],authority_revision=claim.authority_revision)
        if (work is None or source is None or work['purpose']!='REVISION' or work['state']!='RUNNING'
                or work['claimed_case_version']!=head['case_version'] or source['case_version']!=head['case_version']
                or source['slot']!='PRIMARY' or any(work[key]!=value or source[key]!=value for key,value in expected.items())):
            reject(uow)
        preserve=work['work_id']
    if row['generation'] >= MAX_VERSION:
        reject(uow)
    values = dict(generation=row['generation'] + 1, proposal_record_id=None,
                  review_record_id=None, preview_id=None, approval_record_id=None)
    if input_version is not None:
        if input_version != head['input_version'] + 1:
            reject(uow)
        values['input_version'] = input_version
    if retention:
        values['available'] = False
    uow.execute(update(t.state).where(t.state.c.case_id == head['case_id']).values(**values))
    # These are only lifecycle consumers, not the currently accepting intake or
    # order work. DONE/FAILED source receipts and historical effects survive.
    predicates=[t.work.c.case_id == head['case_id'],t.work.c.state.in_(['PENDING', 'RUNNING', 'PAUSED'])]
    if preserve is not None:
        predicates.append(t.work.c.work_id!=preserve)
    uow.execute(update(t.work).where(*predicates).values(
            state='PAUSED' if retention else 'SUPERSEDED', epoch=t.work.c.epoch + 1,
            claim_id=None, lease_expires_at=None))
    return {**row, **values}


def retain(uow, head, reason, redact):
    if not installed(uow):
        return
    invalidate(uow, head, retention=True)
    # Future bundles/notification text may copy the source being removed.
    # Delete derivative bytes atomically but retain identity, digest and facts.
    records = select(old.history.c.record_id).where(old.history.c.case_id == head['case_id'],
        old.history.c.kind.in_(['PROPOSAL','REVIEW','DECISION','APPROVAL','OPERATION','NOTIFICATION']))
    uow.execute(delete(old.history_contents).where(old.history_contents.c.record_id.in_(records)))
    uow.execute(update(old.history).where(old.history.c.record_id.in_(records),
        old.history.c.retention_state == 'AVAILABLE').values(
            retention_state='REDACTED' if redact else 'DELETED', removal_reason=reason))
