"""Independent fenced SQL mock transaction; its sole write is the label ledger."""
from dataclasses import dataclass
from sqlalchemy import select, update, literal, func, exists
from sqlalchemy.dialects.postgresql import insert
from . import customer_tables as old, lifecycle_tables as life
from .canonical import digest
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .manual_target import one
from .lifecycle_state import reject
from .label_execution_tables import controls, ledger, permissions
from .label_execution_sources import (COMPONENT, CONFIG, authorize, creation_authority, database_now,
    control_identity, create_source, full_chain, ledger_payload, stable, verify_fact, closure)
from .label_execution_history import expected_delta


@dataclass(frozen=True, slots=True, repr=False)
class Ticket:
    control_id: str
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


def claim_current(uow, row, ticket, actor, grant, permission, *, create=False):
    if (row['control_id'] != ticket.control_id or row['case_id'] != ticket.case_id
            or row['binding_hash'] != ticket.binding_hash or row['status'] != 'EXECUTING'
            or row['confirmed_effect_status'] is not None):
        reject(uow)
    now = database_now(uow)
    if ticket.kind == 'DISPATCH':
        if (ticket.epoch != 0 or row['query_epoch'] != 0 or ticket.claim_id != row['dispatch_claim_id']
                or row['session_id'] != actor.session_id or now >= row['dispatch_deadline']
                or create and (grant['revision'] != row['execution_authority_revision'] or permission['revision'] != row['provider_revision'])):
            reject(uow)
    elif ticket.kind == 'QUERY':
        if (create or row['query_epoch'] != ticket.epoch or row['query_claim_id'] != ticket.claim_id
                or row['query_lease_until'] is None or now >= row['query_lease_until']):
            reject(uow)
    else:
        reject(uow)


class CoreLabelMock:
    def __init__(self, engine, *, uow_factory=CustomerUnitOfWork):
        self.engine, self.uow_factory = engine, uow_factory

    def _outcome(self, control, command):
        return 'SUCCEEDED'

    def _insert(self, uow, row, actor, permission, bounds, source, outcome):
        from .return_execution_sources import COMPONENT as RETURN_COMPONENT
        from .return_execution_tables import permissions as return_permissions
        if outcome not in {'SUCCEEDED','FAILED'}:
            reject(uow)
        values = {name:row[name] for name in ('effect_key','case_id','store_id','provider_id','config_id','config_hash',
            'operation_id','dispatch_record_id','operation_fingerprint','command_hash','return_ledger_hash','provider_return_id','parcel_id')}
        values.update(dispatch_binding_hash=row['binding_hash'], provider_operation_id=stable('mock_label',row['execution_work_id']),
            status=outcome, provider_label_id=stable('label',row['execution_work_id']) if outcome == 'SUCCEEDED' else None,
            error_code='INTERNAL_ERROR' if outcome == 'FAILED' else None, fact_hash='0'*64)
        wall = select(func.clock_timestamp().label('now')).cte('label_effect_time').prefix_with('MATERIALIZED')
        session_live = exists(select(old.sessions.c.session_id).where(old.sessions.c.session_id == actor.session_id,
            old.sessions.c.principal_id == actor.principal_id, old.sessions.c.revoked.is_(False),
            old.sessions.c.issued_at == bounds[2], old.sessions.c.not_before == bounds[3], old.sessions.c.expires_at == bounds[4]))
        founder_live = exists(select(old.principals.c.principal_id).where(old.principals.c.principal_id == actor.principal_id,
            old.principals.c.enabled.is_(True), old.principals.c.role == 'FOUNDER', old.principals.c.store_id == row['store_id']))
        owner_live = exists(select(old.principals.c.principal_id).where(old.principals.c.principal_id == row['owner_id'],
            old.principals.c.enabled.is_(True), old.principals.c.role == 'CUSTOMER', old.principals.c.store_id == row['store_id']))
        grants = [exists(select(life.authorities.c.component_id).where(life.authorities.c.store_id == row['store_id'],
            life.authorities.c.component_id == component, life.authorities.c.purpose == purpose,
            life.authorities.c.enabled.is_(True), life.authorities.c.revision == row[revision])) for component,purpose,revision in (
                (COMPONENT,'EXECUTION','execution_authority_revision'), (COMPONENT,'EFFECT','effect_authority_revision'),
                (RETURN_COMPONENT,'EFFECT','return_authority_revision'))]
        provider_live = exists(select(permissions.c.store_id).where(permissions.c.store_id == row['store_id'],
            permissions.c.component_id == COMPONENT, permissions.c.provider_id == row['provider_id'],
            permissions.c.config_id == row['config_id'], permissions.c.command_type == 'GENERATE_LABEL',
            permissions.c.config_hash == row['config_hash'], permissions.c.revision == row['provider_revision'],
            permissions.c.create_enabled.is_(True), permissions.c.query_enabled.is_(True)))
        returned, root, bridge = source
        return_provider_live = exists(select(return_permissions.c.store_id).where(return_permissions.c.store_id == row['store_id'],
            return_permissions.c.component_id == RETURN_COMPONENT, return_permissions.c.provider_id == returned['provider_id'],
            return_permissions.c.config_id == returned['config_id'], return_permissions.c.command_type == 'CREATE_RETURN',
            return_permissions.c.config_hash == returned['config_hash'], return_permissions.c.revision == row['return_provider_revision'],
            return_permissions.c.query_enabled.is_(True)))
        original_claim = exists(select(controls.c.control_id).where(controls.c.control_id == row['control_id'],
            controls.c.binding_hash == row['binding_hash'], controls.c.dispatch_claim_id == row['dispatch_claim_id'],
            controls.c.status == 'EXECUTING', controls.c.confirmed_effect_status.is_(None), controls.c.query_epoch == 0,
            controls.c.source_available.is_(True), controls.c.session_id == actor.session_id))
        current_head = exists(select(old.case_heads.c.case_id).where(old.case_heads.c.case_id == row['case_id'],
            old.case_heads.c.case_version == row['dispatch_case_version'], old.case_heads.c.input_version == row['input_version'],
            old.case_heads.c.status == 'ACTION_IN_PROGRESS', old.case_heads.c.available.is_(True),
            old.case_heads.c.current_failure_id.is_(None), old.case_heads.c.owner_principal_id == row['owner_id'], old.case_heads.c.store_id == row['store_id']))
        preview = root['approval']['preview']['row']
        current_state = exists(select(life.state.c.case_id).where(life.state.c.case_id == row['case_id'],
            life.state.c.available.is_(True), life.state.c.generation == row['generation'],
            life.state.c.input_version == row['input_version'], life.state.c.approval_record_id == row['approval_record_id'],
            life.state.c.proposal_record_id == preview['proposal_record_id'], life.state.c.review_record_id == preview['review_record_id'],
            life.state.c.preview_id == preview['preview_id'],
            *(life.state.c[name].is_(None) for name in ('outcome','outcome_record_id','notification_id','notification_record_id',
                'notification_hash','notification_work_id','return_record_id','label_record_id'))))
        names = list(values) + ['accepted_at']
        selection = select(*(literal(value,type_=ledger.c[name].type) for name,value in values.items()),wall.c.now).select_from(wall).where(
            wall.c.now >= row['dispatch_at'], wall.c.now < row['dispatch_deadline'], wall.c.now < preview['expires_at'],
            func.extract('epoch',wall.c.now) >= bounds[3], func.extract('epoch',wall.c.now) < bounds[4],
            session_live, founder_live, owner_live, *grants, provider_live, return_provider_live, original_claim, current_head, current_state)
        found = uow.execute(insert(ledger).from_select(names,selection).on_conflict_do_nothing(
            index_elements=[ledger.c.effect_key]).returning(ledger)).mappings().one_or_none()
        if found is None:
            return None
        fact = dict(found); fact['fact_hash'] = digest(ledger_payload(fact),'core-label-fact/v1')
        if uow.execute(update(ledger).where(ledger.c.effect_key == fact['effect_key'],ledger.c.fact_hash == '0'*64)
                .values(fact_hash=fact['fact_hash'])).rowcount != 1:
            reject(uow)
        return fact

    def perform(self, ticket, callback):
        phase = {'commit_possible':False}
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                create = ticket.kind == 'DISPATCH'
                authorization = authorize(uow,callback,ticket.case_id,create=create)
                actor,head,grant,permission,bounds = authorization
                extra = creation_authority(uow,callback,authorization) if create else None
                before = closure(uow,ticket.case_id)
                row = one(uow,controls,control_id=ticket.control_id)
                control_identity(uow,actor,head,row,ticket.original_key)
                claim_current(uow,row,ticket,actor,grant,permission,create=create)
                source = (create_source if create else full_chain)(uow,actor,head,row['execution_work_id'],ticket.original_key)
                if create and (head['case_version'] != row['dispatch_case_version']
                        or tuple(item['revision'] for item in extra) != (row['effect_authority_revision'],row['return_authority_revision'],row['return_provider_revision'])):
                    reject(uow)
                saved = uow.execute(select(ledger).where(ledger.c.effect_key == row['effect_key'])).mappings().one_or_none()
                added = False
                if saved is not None:
                    verify_fact(uow,row,saved); fact = dict(saved)
                elif create:
                    outcome = self._outcome(row,source[2]['source']['label_command'])
                    if callback(uow.connection,'getSession') != actor:
                        reject(uow,'UNAUTHENTICATED')
                    fact = self._insert(uow,row,actor,permission,bounds,source,outcome)
                    added = fact is not None
                    if added:
                        verify_fact(uow,row,fact)
                else:
                    fact = None
                expected = expected_delta(before,[(ledger,fact)] if added else [],[],head)
                def final_check():
                    fresh = authorize(uow,callback,ticket.case_id,create=create)
                    if fresh != authorization or (create and creation_authority(uow,callback,fresh) != extra):
                        reject(uow)
                    full_chain(uow,actor,head,row['execution_work_id'],ticket.original_key)
                    if closure(uow,ticket.case_id) != expected or callback(uow.connection,'getSession') != actor:
                        reject(uow)
                    from .approval_admission_sources import check_session_time
                    check_session_time(database_now(uow),bounds)
                uow.before_commit(final_check)
                uow.before_commit(lambda:phase.update(commit_possible=True))
                uow.commit()
            return MockReply('FOUND' if fact is not None else 'NOT_FOUND',fact)
        except FlowError as error:
            return MockReply('UNKNOWN' if phase['commit_possible'] or error.code == 'INTERNAL_ERROR' else 'DENIED',safe_code=error.code)
        except Exception:
            return MockReply('UNKNOWN')
