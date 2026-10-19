"""Actual fenced SQL mock. Its only writes are to its independent return ledger."""
from dataclasses import dataclass
from sqlalchemy import select, update, literal, func, exists
from sqlalchemy.dialects.postgresql import insert
from . import customer_tables as old, lifecycle_tables as life
from .canonical import digest
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .manual_target import one
from .return_execution_tables import controls, ledger, permissions
from .return_execution_sources import (COMPONENT, CONFIG, authorize, database_now, continued_proof,
    control_identity, ledger_payload, stable, verify_fact)
from .lifecycle_state import reject


@dataclass(frozen=True, slots=True, repr=False)
class Ticket:
    preparation_id: str
    case_id: str
    original_key: str
    binding_hash: str
    kind: str
    claim_id: str
    epoch: int


@dataclass(frozen=True, slots=True, repr=False)
class MockReply:
    status: str
    fact: dict | None = None
    safe_code: str | None = None


def claim_current(uow, row, ticket, actor, grant, permission, *, require_create_authority=True):
    now = database_now(uow)
    if row['binding_hash'] != ticket.binding_hash or row['case_id'] != ticket.case_id or row['status'] != 'EXECUTING':
        reject(uow)
    if ticket.kind == 'DISPATCH':
        if (ticket.epoch != 0 or row['query_epoch'] != 0 or ticket.claim_id != row['dispatch_claim_id']
                or row['session_id'] != actor.session_id or not now < row['dispatch_deadline']
                or require_create_authority and (grant['revision'] != row['execution_authority_revision']
                    or permission['revision'] != row['provider_revision'])):
            reject(uow)
    elif ticket.kind == 'QUERY':
        if (row['query_epoch'] != ticket.epoch or row['query_claim_id'] != ticket.claim_id
                or row['query_lease_until'] is None or not now < row['query_lease_until']):
            reject(uow)
    else:
        reject(uow)


class CoreReturnMock:
    def __init__(self, engine, *, uow_factory=CustomerUnitOfWork):
        self.engine, self.uow_factory = engine, uow_factory

    def _outcome(self, control, command):
        """Private deterministic core behavior; no caller-selected backend."""
        return 'SUCCEEDED'

    def _insert(self, uow, row, actor, permission, bounds, outcome):
        if outcome not in {'SUCCEEDED', 'FAILED'}:
            reject(uow)
        values = dict(effect_key=row['effect_key'], store_id=row['store_id'], provider_id=row['provider_id'],
            config_id=row['config_id'], config_hash=row['config_hash'], operation_id=row['operation_id'],
            dispatch_record_id=row['dispatch_record_id'], dispatch_binding_hash=row['binding_hash'],
            operation_fingerprint=row['operation_fingerprint'], provider_operation_id=stable('mock_return', row['preparation_id']),
            parcel_id=row['parcel_id'], status=outcome,
            provider_return_id=stable('return', row['preparation_id']) if outcome == 'SUCCEEDED' else None,
            error_code='INTERNAL_ERROR' if outcome == 'FAILED' else None, fact_hash='0' * 64)
        # One DB wall-clock sample in this INSERT statement is the acceptance
        # point. No Domain FK and no second fenced connection are involved.
        wall = select(func.clock_timestamp().label('now')).cte('return_effect_time').prefix_with('MATERIALIZED')
        session_live = exists(select(old.sessions.c.session_id).where(old.sessions.c.session_id == actor.session_id,
            old.sessions.c.principal_id == actor.principal_id, old.sessions.c.revoked.is_(False),
            old.sessions.c.issued_at == bounds[2], old.sessions.c.not_before == bounds[3], old.sessions.c.expires_at == bounds[4]))
        founder_live = exists(select(old.principals.c.principal_id).where(old.principals.c.principal_id == actor.principal_id,
            old.principals.c.enabled.is_(True), old.principals.c.role == 'FOUNDER', old.principals.c.store_id == row['store_id']))
        owner_live = exists(select(old.principals.c.principal_id).where(old.principals.c.principal_id == row['owner_id'],
            old.principals.c.enabled.is_(True), old.principals.c.role == 'CUSTOMER', old.principals.c.store_id == row['store_id']))
        grant_live = exists(select(life.authorities.c.component_id).where(life.authorities.c.store_id == row['store_id'],
            life.authorities.c.component_id == COMPONENT, life.authorities.c.purpose == 'EXECUTION',
            life.authorities.c.enabled.is_(True), life.authorities.c.revision == row['execution_authority_revision']))
        provider_live = exists(select(permissions.c.store_id).where(permissions.c.store_id == row['store_id'],
            permissions.c.component_id == COMPONENT, permissions.c.provider_id == row['provider_id'],
            permissions.c.config_id == row['config_id'], permissions.c.command_type == 'CREATE_RETURN',
            permissions.c.config_hash == row['config_hash'], permissions.c.revision == permission['revision'], permissions.c.create_enabled.is_(True)))
        original_claim = exists(select(controls.c.preparation_id).where(controls.c.preparation_id == row['preparation_id'],
            controls.c.binding_hash == row['binding_hash'], controls.c.status == 'EXECUTING',
            controls.c.query_epoch == 0, controls.c.source_available.is_(True)))
        current_head = exists(select(old.case_heads.c.case_id).where(old.case_heads.c.case_id == row['case_id'],
            old.case_heads.c.case_version == row['dispatch_case_version'], old.case_heads.c.input_version == row['input_version'],
            old.case_heads.c.status == 'ACTION_IN_PROGRESS', old.case_heads.c.available.is_(True),
            old.case_heads.c.owner_principal_id == row['owner_id'], old.case_heads.c.store_id == row['store_id']))
        current_state = exists(select(life.state.c.case_id).where(life.state.c.case_id == row['case_id'],
            life.state.c.available.is_(True), life.state.c.generation == row['generation'],
            life.state.c.input_version == row['input_version'], life.state.c.approval_record_id == row['approval_record_id']))
        names = list(values) + ['accepted_at']
        selection = select(*(literal(value, type_=ledger.c[name].type) for name, value in values.items()), wall.c.now).select_from(wall).where(
            wall.c.now >= row['dispatch_at'], wall.c.now < row['dispatch_deadline'],
            func.extract('epoch', wall.c.now) >= bounds[3], func.extract('epoch', wall.c.now) < bounds[4],
            session_live, founder_live, owner_live, grant_live, provider_live, original_claim, current_head, current_state)
        inserted = uow.execute(insert(ledger).from_select(names, selection).on_conflict_do_nothing(
            index_elements=[ledger.c.effect_key]).returning(ledger)).mappings().one_or_none()
        if inserted is None:
            # Missing, an expired guard, or conflict is never a second attempt.
            return None
        saved = dict(inserted)
        saved['fact_hash'] = digest(ledger_payload(saved), 'core-return-fact/v1')
        if uow.execute(update(ledger).where(ledger.c.effect_key == saved['effect_key'], ledger.c.fact_hash == '0' * 64)
                .values(fact_hash=saved['fact_hash'])).rowcount != 1:
            reject(uow)
        return saved

    def perform(self, ticket, callback):
        """T2 starts only after the caller has confirmed T1 commit and close."""
        committing = False
        try:
            with self.uow_factory(self.engine, write=True) as uow:
                create = ticket.kind == 'DISPATCH'
                actor, head, grant, permission, bounds = authorize(uow, callback, ticket.case_id, create=create)
                row = one(uow, controls, preparation_id=ticket.preparation_id)
                control_identity(uow, actor, head, row, ticket.original_key)
                claim_current(uow, row, ticket, actor, grant, permission)
                root = continued_proof(uow, actor, head, row, ticket.original_key, creating=create)
                saved = uow.execute(select(ledger).where(ledger.c.effect_key == row['effect_key'])).mappings().one_or_none()
                if saved is not None:
                    verify_fact(uow, row, saved)
                    fact = dict(saved)
                elif create:
                    outcome = self._outcome(row, root['command'])
                    # The real F.03 service is rechecked immediately before the
                    # guarded INSERT; SQL independently checks its live dates.
                    if callback(uow.connection, 'getSession') != actor:
                        reject(uow, 'UNAUTHENTICATED')
                    fact = self._insert(uow, row, actor, permission, bounds, outcome)
                    if fact is not None:
                        verify_fact(uow, row, fact)
                else:
                    fact = None
                committing = True
                uow.commit()
            return MockReply('FOUND' if fact is not None else 'NOT_FOUND', fact)
        except FlowError as error:
            return MockReply('UNKNOWN' if committing or error.code == 'INTERNAL_ERROR' else 'DENIED', safe_code=error.code)
        except Exception:
            return MockReply('UNKNOWN')
