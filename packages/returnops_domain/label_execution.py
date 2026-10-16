"""Private one-shot label reservation, independent SQL effect and confirmation.

This component stops at a durable fact plus EXECUTING and artifact-only intent.
There is no artifact reader, PDF store, completed result, outcome or sender.
"""
from dataclasses import dataclass
from datetime import timedelta
from secrets import token_hex
from sqlalchemy import select, update
from . import customer_tables as old, founder_codec as finite
from .audit import append_event
from .canonical import digest
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .approval_admission_sources import check_time, check_session_time, session_bounds
from .lifecycle_state import reject, MAX_VERSION
from .lifecycle_sources import Sources
from .manual_target import one
from .label_execution_tables import controls, ledger, artifact_work
from .label_execution_sources import (COMPONENT, CONFIG, config_hash, database_now, key_hash, identities, stable,
    authorize, creation_authority, create_source, full_chain, eligible, command_hash, bridge_hash, operation,
    control_payload, dispatch_payload, accepted_payload, verify_fact, closure, artifact_values, confirmation_body)
from .label_execution_history import append_operation, expected_delta, audit_row
from .core_label_mock import CoreLabelMock, Ticket, claim_current
from .wire import validate


@dataclass(frozen=True, slots=True, repr=False)
class LabelExecutionResult:
    status: str
    operation_id: str | None = None
    operation_state: str | None = None
    provider_operation_id: str | None = None
    confirmation_record_id: str | None = None
    provider_fact_status: str | None = None
    artifact_work_id: str | None = None
    safe_code: str | None = None


def observed(status, row):
    return LabelExecutionResult(status,row['operation_id'],row['status'],row['confirmed_provider_operation_id'],
        row['confirmation_record_id'],row['confirmed_effect_status'],
        stable('artifact',row['execution_work_id']) if row['confirmation_record_id'] is not None and row['confirmed_effect_status'] == 'SUCCEEDED' else None)


class LabelExecutionService:
    def __init__(self, engine, authority, *, uow_factory=CustomerUnitOfWork, mock_factory=CoreLabelMock):
        self.engine,self.authority,self.uow_factory,self.mock_factory = engine,authority,uow_factory,mock_factory

    def execute_accepted_label(self,case_id,expected_case_version,execution_work_id,original_approval_key,correlation_id):
        value = self._reserve(case_id,expected_case_version,execution_work_id,original_approval_key,correlation_id)
        return value if type(value) is LabelExecutionResult else self._perform(value,correlation_id)

    def reconcile_label(self,case_id,execution_work_id,original_approval_key,correlation_id):
        value = self._query_claim(case_id,execution_work_id,original_approval_key,correlation_id)
        return value if type(value) is LabelExecutionResult else self._perform(value,correlation_id)

    @staticmethod
    def _request(case_id,work_id,key,correlation,expected=None,*,creating=False):
        for value in (case_id,work_id,correlation):validate('Id',value)
        validate('IdempotencyKey',key)
        if creating:
            if type(expected) is not int:raise FlowError('VALIDATION_ERROR')
            validate('Version',expected)

    @staticmethod
    def _error(error,phase):
        return LabelExecutionResult('UNKNOWN' if phase['commit_possible'] or error.code == 'INTERNAL_ERROR' else 'DENIED',safe_code=error.code)

    def _final(self,uow,authorization,expected_head,expected_seal,work_id,key,row,phase,*,create=False,extra=None,ticket_row=None,ticket=None):
        actor,_,grant,permission,bounds = authorization
        def check():
            fresh = authorize(uow,self.authority,expected_head['case_id'],create=create)
            a,h,g,p,b = fresh
            if (a != actor or h != expected_head or g != grant or p != permission or b != bounds
                    or create and creation_authority(uow,self.authority,fresh) != extra):
                reject(uow)
            found = uow.execute(select(controls).where(controls.c.execution_work_id == work_id)).mappings().one_or_none()
            if (None if found is None else dict(found)) != row:
                reject(uow)
            source = None
            if row is not None:
                source = full_chain(uow,actor,expected_head,work_id,key)
                if create and not eligible(uow,expected_head,source[1],source[0]):
                    reject(uow)
            if closure(uow,expected_head['case_id']) != expected_seal:
                reject(uow)
            if self.authority(uow.connection,'getSession') != actor or session_bounds(uow,actor) != bounds:
                reject(uow,'UNAUTHENTICATED')
            # Check live authority again after all potentially slow source reads.
            fresh = authorize(uow,self.authority,expected_head['case_id'],create=create)
            if fresh != (actor,expected_head,grant,permission,bounds):reject(uow)
            if create and creation_authority(uow,self.authority,fresh) != extra:reject(uow)
            if closure(uow,expected_head['case_id']) != expected_seal:reject(uow)
            now = database_now(uow)
            check_session_time(now,bounds)
            if create:check_time(now,source[1])
            if ticket is not None:
                deadline = ticket_row['dispatch_deadline'] if ticket.kind == 'DISPATCH' else ticket_row['query_lease_until']
                if deadline is None or now >= deadline:reject(uow)
        uow.before_commit(check)
        uow.before_commit(lambda:phase.update(commit_possible=True))

    def _observation(self,uow,authorization,work_id,key,row,phase):
        head = authorization[1]; before = closure(uow,head['case_id'])
        self._final(uow,authorization,head,before,work_id,key,row,phase)
        uow.commit()
        if row is None:return LabelExecutionResult('UNKNOWN')
        if row['confirmed_effect_status'] is not None:
            return observed('REPLAYED' if row['confirmation_record_id'] is not None else 'FACT_REPLAYED',row)
        return observed('UNKNOWN',row)

    def _reserve(self,case_id,expected,work_id,key,correlation):
        phase = {'commit_possible':False}
        try:
            self._request(case_id,work_id,key,correlation,expected,creating=True)
            with self.uow_factory(self.engine,write=True) as uow:
                query = authorize(uow,self.authority,case_id,create=False)
                actor,head,_,_,bounds = query
                found = uow.execute(select(controls).where(controls.c.execution_work_id == work_id)).mappings().one_or_none()
                if found is not None:
                    row = dict(found)
                    from .label_execution_sources import control_identity
                    control_identity(uow,actor,head,row,key)
                    if expected != row['pre_dispatch_case_version']:reject(uow,'IDEMPOTENCY_CONFLICT')
                    value = self._observation(uow,query,work_id,key,row,phase)
                else:
                    authorization = authorize(uow,self.authority,case_id,create=True)
                    if authorization[0] != actor or authorization[1] != head or authorization[4] != bounds:reject(uow)
                    extra = creation_authority(uow,self.authority,authorization)
                    before = closure(uow,case_id)
                    returned,root,bridge = create_source(uow,actor,head,work_id,key)
                    if head['case_version'] != expected:reject(uow,'STALE_CASE_VERSION')
                    if max(head['history_sequence'],head['audit_sequence']) > MAX_VERSION - 2 or expected >= MAX_VERSION:reject(uow)
                    now = database_now(uow);check_time(now,root);check_session_time(now,bounds)
                    ids = identities(work_id);command = bridge['source']['label_command']
                    first = operation(head,root,command,ids,now)
                    dispatched = {**first,'status':'EXECUTING','case_version':expected+1}
                    grant,permission = authorization[2:4]; effect,return_grant,return_permission = extra
                    row = dict(**ids,case_id=case_id,store_id=head['store_id'],owner_id=head['owner_principal_id'],
                        principal_id=actor.principal_id,session_id=actor.session_id,execution_work_id=work_id,
                        approval_record_id=returned['approval_record_id'],approval_acceptance_id=returned['approval_acceptance_id'],
                        bridge_event_id=bridge['ids']['event_id'],bridge_work_id=bridge['ids']['work_id'],
                        bridge_target_hash=bridge['ids']['target_hash'],bridge_receipt_hash=bridge_hash(bridge['accepted']['receipt']),
                        return_preparation_id=returned['preparation_id'],return_operation_id=returned['operation_id'],
                        return_record_id=returned['result_record_id'],return_result_hash=bridge['source']['record']['content_sha256'],
                        return_ledger_hash=bridge['source']['fact']['fact_hash'],provider_return_id=bridge['source']['fact']['provider_return_id'],
                        command_id=command['command_id'],return_command_id=returned['command_id'],approval_id=first['approval_id'],
                        proposal_id=first['proposal_id'],provider_id=command['provider_id'],config_id=CONFIG['config_id'],parcel_id=returned['parcel_id'],
                        first_body_hash=finite.digest(first),dispatch_body_hash=finite.digest(dispatched),command_hash=command_hash(command),
                        operation_fingerprint=first['operation_fingerprint'],original_key_hash=key_hash(actor,key),
                        profile_hash=returned['profile_hash'],config_hash=config_hash(),input_version=returned['input_version'],
                        generation=returned['generation'],proposal_version=first['proposal_version'],pre_dispatch_case_version=expected,
                        dispatch_case_version=expected+1,execution_authority_revision=grant['revision'],effect_authority_revision=effect['revision'],
                        provider_revision=permission['revision'],return_authority_revision=return_grant['revision'],return_provider_revision=return_permission['revision'],
                        dispatch_at=now,dispatch_deadline=min(now+timedelta(seconds=30),root['approval']['preview']['row']['expires_at']),
                        status='EXECUTING',query_epoch=0,query_claim_id=None,query_lease_until=None,
                        confirmation_record_id=None,confirmation_audit_id=None,confirmation_case_version=None,confirmed_ledger_hash=None,
                        confirmed_provider_operation_id=None,confirmed_provider_label_id=None,confirmed_effect_status=None,
                        confirmation_retained=False,source_available=True)
                    row['binding_hash'] = digest(control_payload(row),'label-reservation/v1')
                    _,event,post,additions = append_operation(uow,head,row['first_record_id'],first,1,dispatch_payload(row,1),correlation,now)
                    row['first_audit_id'] = event['event_id']
                    if uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == case_id,
                            old.case_heads.c.case_version == expected,old.case_heads.c.status == 'ACTION_IN_PROGRESS')
                            .values(case_version=expected+1,updated_at=now)).rowcount != 1:reject(uow)
                    post = {**post,'case_version':expected+1,'updated_at':now}
                    _,event,post,rows = append_operation(uow,post,row['dispatch_record_id'],dispatched,2,dispatch_payload(row,2),correlation,now)
                    row['dispatch_audit_id'] = event['event_id']; additions += rows
                    uow.execute(controls.insert().values(**row));additions.append((controls,row))
                    expected_seal = expected_delta(before,additions,[],post)
                    ticket = Ticket(row['control_id'],case_id,key,row['binding_hash'],'DISPATCH',row['dispatch_claim_id'],0)
                    self._final(uow,authorization,post,expected_seal,work_id,key,row,phase,create=True,extra=extra,ticket_row=row,ticket=ticket)
                    uow.commit();value = ticket
            # A dispatch ticket leaves this function only after commit AND close.
            return value
        except FlowError as error:return self._error(error,phase)
        except Exception:return LabelExecutionResult('UNKNOWN')

    def _query_claim(self,case_id,work_id,key,correlation):
        phase = {'commit_possible':False}
        try:
            self._request(case_id,work_id,key,correlation)
            with self.uow_factory(self.engine,write=True) as uow:
                authorization = authorize(uow,self.authority,case_id,create=False)
                actor,head,grant,permission,bounds = authorization
                found = uow.execute(select(controls).where(controls.c.execution_work_id == work_id)).mappings().one_or_none()
                row = None if found is None else dict(found)
                if row is None:
                    value = self._observation(uow,authorization,work_id,key,None,phase)
                else:
                    full_chain(uow,actor,head,work_id,key)
                    if row['confirmed_effect_status'] is not None or row['query_claim_id'] is not None and database_now(uow) < row['query_lease_until']:
                        value = self._observation(uow,authorization,work_id,key,row,phase)
                    else:
                        if row['query_epoch'] >= MAX_VERSION:reject(uow)
                        before = closure(uow,case_id);now = database_now(uow)
                        changes = dict(query_epoch=row['query_epoch']+1,query_claim_id='lquery_'+token_hex(16),query_lease_until=now+timedelta(seconds=30))
                        if uow.execute(update(controls).where(controls.c.control_id == row['control_id'],
                                controls.c.query_epoch == row['query_epoch'],controls.c.confirmed_effect_status.is_(None)).values(**changes)).rowcount != 1:reject(uow)
                        final = {**row,**changes}
                        value = Ticket(row['control_id'],case_id,key,row['binding_hash'],'QUERY',changes['query_claim_id'],changes['query_epoch'])
                        expected = expected_delta(before,[],[(controls,row,final)],head)
                        self._final(uow,authorization,head,expected,work_id,key,final,phase,ticket_row=final,ticket=value)
                        uow.commit()
            return value
        except FlowError as error:return self._error(error,phase)
        except Exception:return LabelExecutionResult('UNKNOWN')

    def _perform(self,ticket,correlation):
        try:reply = self.mock_factory(self.engine).perform(ticket,self.authority)
        except Exception:return LabelExecutionResult('UNKNOWN')
        if reply.status != 'FOUND' or reply.fact is None:
            return LabelExecutionResult('DENIED' if reply.status == 'DENIED' else 'UNKNOWN',safe_code=reply.safe_code)
        return self._accept(ticket,reply.fact,correlation)

    def _accept(self,ticket,returned_fact,correlation):
        phase = {'commit_possible':False}
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                authorization = authorize(uow,self.authority,ticket.case_id,create=False)
                actor,head,grant,permission,bounds = authorization
                row = one(uow,controls,control_id=ticket.control_id)
                source = full_chain(uow,actor,head,row['execution_work_id'],ticket.original_key)
                if row['confirmed_effect_status'] is not None:
                    value = self._observation(uow,authorization,row['execution_work_id'],ticket.original_key,row,phase)
                else:
                    claim_current(uow,row,ticket,actor,grant,permission)
                    fact = one(uow,ledger,effect_key=row['effect_key'])
                    if fact != returned_fact:reject(uow)
                    verify_fact(uow,row,fact)
                    if max(head['history_sequence'],head['audit_sequence']) >= MAX_VERSION:reject(uow)
                    before = closure(uow,ticket.case_id);now = database_now(uow)
                    changes = dict(confirmed_ledger_hash=fact['fact_hash'],confirmed_effect_status=fact['status'],
                        confirmed_provider_operation_id=fact['provider_operation_id'],confirmed_provider_label_id=fact['provider_label_id'],
                        confirmation_case_version=head['case_version'],query_claim_id=None,query_lease_until=None)
                    additions = []
                    if row['source_available']:
                        _,dispatched = Sources(uow,head,COMPONENT).read(row['dispatch_record_id'],{'OPERATION'})
                        body = confirmation_body(dispatched,fact,now,correlation)
                        record_id = stable('lconfirm',row['execution_work_id'])
                        record,event,post,additions = append_operation(uow,head,record_id,body,3,
                            accepted_payload(row,fact,finite.digest(body)),correlation,now)
                        changes.update(status=body['status'],confirmation_record_id=record_id,
                            confirmation_audit_id=event['event_id'],confirmation_retained=True)
                        if fact['status'] == 'SUCCEEDED':
                            state = 'PENDING' if eligible(uow,post,source[1],source[0]) else 'PAUSED'
                            work = artifact_values(row,fact,record,state)
                            uow.execute(artifact_work.insert().values(**work));additions.append((artifact_work,work))
                    else:
                        dispatch = one(uow,old.history,record_id=row['dispatch_record_id'])
                        ref = {name:dispatch[name] for name in ('record_id','kind','object_id','object_version')}
                        event = append_event(uow,head['case_id'],actor={'kind':'SERVICE','component_id':COMPONENT},
                            event_type='LABEL_EFFECT_CONFIRMED_RETAINED',correlation_id=correlation,
                            payload=accepted_payload(row,fact),object_ids=[row['operation_id']],history_refs=[ref],now=now)
                        changes.update(confirmation_audit_id=event['event_id'],confirmation_retained=False)
                        additions.append((old.audit,audit_row(head,event)))
                        post = {**head,'audit_sequence':head['audit_sequence']+1,'audit_head':event['event_hash']}
                    if uow.execute(update(controls).where(controls.c.control_id == row['control_id'],
                            controls.c.query_epoch == row['query_epoch'],controls.c.confirmed_effect_status.is_(None))
                            .values(**changes)).rowcount != 1:reject(uow)
                    final = {**row,**changes}
                    expected = expected_delta(before,additions,[(controls,row,final)],post)
                    self._final(uow,authorization,post,expected,row['execution_work_id'],ticket.original_key,final,phase,ticket_row=row,ticket=ticket)
                    uow.commit();value = observed('COMMITTED' if row['source_available'] else 'FACT_RECORDED',final)
            return value
        except FlowError as error:return self._error(error,phase)
        except Exception:return LabelExecutionResult('UNKNOWN')
