"""Private durable first CREATE_RETURN preparation. No adapter is invoked."""
from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy import update
from . import customer_tables as old, founder_tables as founder, founder_codec as finite
from .audit import append_event, timestamp
from .canonical import encode_document
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .approval_admission_sources import (ProofReads, AdmissionUncertain, authorize, command_request,
    check_time, session_bounds, check_session_time)
from .execution_preparation_tables import preparations
from .execution_preparation_sources import (identities, request_fingerprint, source_closure, discover,
    fresh_proof, operation, audit_payload, retained_proof, current_staged, expected_closure)
from .lifecycle_schema import PREPARATION_VERSIONS, EXECUTION, version
from .lifecycle_state import reject
from .manual_target import one
from .preview_profile import APPROVAL_COMPONENT
from .wire import validate


@dataclass(frozen=True, slots=True, repr=False)
class PreparationResult:
    status: str
    preparation_id: str | None = None
    operation_id: str | None = None
    first_operation_record_id: str | None = None
    created_at: str | None = None
    state: str | None = None
    safe_code: str | None = None


def result(status, row):
    return PreparationResult(status, **{name:row[name] for name in
        ('preparation_id', 'operation_id', 'first_operation_record_id', 'state')},
        created_at=timestamp(row['created_at']))


class ExecutionPreparationService:
    def __init__(self, engine, authority, *, clock=lambda:datetime.now(timezone.utc),
                 uow_factory=CustomerUnitOfWork):
        self.engine, self.authority, self.clock, self.uow_factory = engine, authority, clock, uow_factory

    def prepare(self, case_id, expected_case_version, execution_work_id, original_approval_key,
                candidate_command, correlation_id):
        return self._run(case_id, expected_case_version, execution_work_id, original_approval_key,
                         candidate_command, correlation_id, recovery=False)

    def recover_preparation(self, case_id, expected_case_version, execution_work_id,
                            original_approval_key, candidate_command):
        """Independent confirmation only. Missing never invokes creation."""
        return self._run(case_id, expected_case_version, execution_work_id, original_approval_key,
                         candidate_command, 'preparation-recovery', recovery=True)

    @staticmethod
    def _stage(uow, head, proof, grant, work_id, candidate, correlation, now):
        stable = identities(work_id)
        body = operation(head, proof, stable, now); source_hash = finite.digest(body)
        row = dict(**stable, case_id=head['case_id'], approval_execution_work_id=work_id,
            original_approval_acceptance_id=proof['original_receipt']['fact']['acceptance_id'],
            command_type='CREATE_RETURN', request_fingerprint=request_fingerprint(candidate),
            profile_hash=proof['approval']['preview']['row']['profile_hash'],
            prepared_authority_revision=grant['revision'], created_at=now, state='PENDING')
        payload = audit_payload(row, body, source_hash)
        row['binding_hash'] = payload['binding_hash']
        ref = dict(record_id=row['first_operation_record_id'], kind='OPERATION',
                   object_id=row['operation_id'], object_version=1)
        history = dict(**ref, case_id=head['case_id'], case_version=head['case_version'],
            recorded_sequence=head['history_sequence']+1, recorded_at=now, content_sha256=source_hash,
            retention_state='AVAILABLE', removal_reason=None)
        content = dict(record_id=ref['record_id'], body=finite.encode_document(body))
        encoding = dict(record_id=ref['record_id'], profile=finite.PROFILE,
            source_content_sha256=source_hash, projected_content_sha256=source_hash, receipt_id=None)
        for table, values in ((old.history, history), (old.history_contents, content), (founder.encodings, encoding)):
            uow.execute(table.insert().values(**values))
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == head['case_id']).values(
            history_sequence=head['history_sequence']+1))
        event = append_event(uow, head['case_id'], actor={'kind':'SERVICE', 'component_id':APPROVAL_COMPONENT},
            event_type='OPERATION_REVISION_RECORDED', correlation_id=correlation, payload=payload,
            object_ids=[row['operation_id']], history_refs=[ref], now=now)
        row['origin_audit_event_id'] = event['event_id']
        uow.execute(preparations.insert().values(**row))
        audit = dict(event_id=event['event_id'], case_id=head['case_id'], sequence=head['audit_sequence']+1,
                     event_hash=event['event_hash'], body=encode_document(event))
        post_head = {**head, 'history_sequence':head['history_sequence']+1,
                     'audit_sequence':head['audit_sequence']+1, 'audit_head':event['event_hash']}
        return row, post_head, [(old.history, history), (old.history_contents, content),
            (founder.encodings, encoding), (old.audit, audit), (preparations, row)]

    def _run(self, case_id, expected, work_id, original_key, candidate_command, correlation, *, recovery):
        uow = None; committed = False; uncertain = False
        try:
            with self.uow_factory(self.engine, write=True) as uow:
                reads = ProofReads(uow)
                validate('Id', case_id)
                actor, head, grant = authorize(reads, self.authority, case_id)
                if version(reads.connection) not in PREPARATION_VERSIONS:
                    reject(reads)
                bounds = session_bounds(reads, actor)
                if type(expected) is not int:
                    reject(reads, 'VALIDATION_ERROR')
                validate('Version', expected); validate('Id', work_id)
                validate('IdempotencyKey', original_key); validate('Id', correlation)
                candidate = command_request(candidate_command)
                before = source_closure(reads, case_id)

                def guarded(call, *args):
                    try:
                        return call(reads, *args)
                    except FlowError as error:
                        if error.code == 'INTERNAL_ERROR' and not uow.failed:
                            reject(reads)
                        raise

                def retained(reads, *args):
                    if version(reads.connection) == EXECUTION:
                        from .return_execution_sources import preparation_replay
                        return preparation_replay(reads, *args)
                    return retained_proof(reads, *args)

                saved = discover(reads, work_id)
                initial = self.clock(); check_session_time(initial, bounds)
                fresh = saved is None and not recovery
                proof = None
                if fresh:
                    proof = guarded(fresh_proof, actor, head, expected, work_id, original_key, candidate)
                    check_time(initial, proof)
                    saved, post_head, additions = self._stage(uow, head, proof, grant, work_id, candidate, correlation, initial)
                    expected_rows = expected_closure(before, additions, post_head)
                    status = 'PREPARED'
                else:
                    post_head = head; expected_rows = before; status = 'REPLAYED'
                seal = None if saved is None else guarded(retained, actor, post_head, expected,
                    work_id, original_key, candidate, saved)
                if fresh:
                    guarded(current_staged, post_head, proof, seal)
                if source_closure(reads, case_id) != expected_rows:
                    reject(reads)

                def final_check():
                    nonlocal uncertain
                    try:
                        h = one(reads, old.case_heads, case_id=case_id)
                        latest = discover(reads, work_id)
                        if h != post_head or (None if latest is None else dict(latest)) != (None if saved is None else dict(saved)):
                            reject(reads)
                        if latest is not None:
                            checked = guarded(retained, actor, h, expected, work_id, original_key, candidate, latest)
                            if checked != seal:
                                reject(reads)
                            if fresh:
                                guarded(current_staged, h, proof, checked)
                        a, current_head, g = authorize(reads, self.authority, case_id)
                        if a != actor or current_head != post_head or g != grant or version(reads.connection) not in PREPARATION_VERSIONS:
                            reject(reads)
                        if source_closure(reads, case_id) != expected_rows:
                            reject(reads)
                        if session_bounds(reads, a) != bounds:
                            reject(reads, 'UNAUTHENTICATED')
                        # LAST I/O. No query, callback or reconstruction follows.
                        if self.authority(reads.connection, 'getSession') != actor:
                            reject(reads, 'UNAUTHENTICATED')
                        now = self.clock()
                        check_session_time(now, bounds)
                        if now < initial:
                            reject(reads)
                        if fresh:
                            check_time(now, proof, initial=initial)
                    except (AdmissionUncertain, AcceptanceOutcomeUnknown):
                        uncertain = True
                        raise
                    except FlowError as error:
                        uncertain = error.code == 'INTERNAL_ERROR' and uow.failed
                        raise
                    except Exception:
                        uncertain = True
                        raise

                uow.before_commit(final_check); uow.commit(); committed = True
            return PreparationResult('UNKNOWN') if saved is None else result(status, saved)
        except (AdmissionUncertain, AcceptanceOutcomeUnknown):
            return PreparationResult('UNKNOWN')
        except FlowError as error:
            if (committed or uncertain or error.code == 'INTERNAL_ERROR'
                    or uow is not None and uow.connection is not None and not uow.connection.closed):
                return PreparationResult('UNKNOWN')
            return PreparationResult('UNKNOWN' if recovery else 'DENIED', safe_code=error.code)
        except Exception:
            return PreparationResult('UNKNOWN')
