"""Private point-in-time approval check; no claim, dispatch, receipt or audit."""
from dataclasses import dataclass
from datetime import datetime, timezone
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .lifecycle_state import reject
from .wire import validate
from .approval_admission_sources import (AdmissionUncertain, ProofReads, authorize,
    command_request, source_closure, read_proof, check_time, session_bounds, check_session_time)


@dataclass(frozen=True, slots=True, repr=False)
class AdmissionResult:
    """CHECKED describes the completed check only, never future permission."""
    status: str
    safe_code: str | None = None


class ApprovalAdmissionService:
    def __init__(self, engine, authority, *, clock=lambda:datetime.now(timezone.utc),
                 uow_factory=CustomerUnitOfWork):
        self.engine, self.authority, self.clock = engine, authority, clock
        self.uow_factory = uow_factory

    def check(self, case_id, expected_case_version, execution_work_id, original_approval_key, candidate_command):
        uow = None
        committed = False
        uncertain = False
        try:
            with self.uow_factory(self.engine, write=True) as uow:
                # write=True is only the existing exclusive global fence and
                # final-check mechanism. ProofReads disallows helper mutations.
                reads = ProofReads(uow)
                validate('Id', case_id)
                actor, head, grant = authorize(reads, self.authority, case_id)
                original_session = session_bounds(reads, actor)
                if type(expected_case_version) is not int:
                    reject(reads, 'VALIDATION_ERROR')
                validate('Version', expected_case_version)
                validate('Id', execution_work_id)
                validate('IdempotencyKey', original_approval_key)
                candidate = command_request(candidate_command)
                original_rows = source_closure(reads, case_id)

                def current_proof():
                    try:
                        return read_proof(reads, actor, head, expected_case_version,
                                          execution_work_id, original_approval_key, candidate)
                    except FlowError as error:
                        # Existing integrity readers use INTERNAL_ERROR for
                        # inconsistent retained bytes. A failed DB execute has
                        # already poisoned the UoW and remains uncertain.
                        if error.code == 'INTERNAL_ERROR' and not uow.failed:
                            reject(reads)
                        raise

                proof = current_proof()
                initial_time = self.clock()
                check_time(initial_time, proof)
                check_session_time(initial_time, original_session)

                def final_check():
                    nonlocal uncertain
                    # Complete all expensive reads before the last F.03 session
                    # check. No DB/callback work follows its final time sample.
                    try:
                        latest = current_proof()
                        if latest != proof or source_closure(reads, case_id) != original_rows:
                            reject(reads)
                        a, h, g = authorize(reads, self.authority, case_id)
                        if a != actor or h != head or g != grant:
                            reject(reads)
                        if session_bounds(reads, a) != original_session:
                            reject(reads, 'UNAUTHENTICATED')
                        # LAST I/O: F.03 verifies the token and current registry,
                        # including its own post-lookup wall-time check. It also
                        # binds the unchanged registry dates to signed claims.
                        if self.authority(reads.connection, 'getSession') != actor:
                            reject(reads, 'UNAUTHENTICATED')
                        final_time = self.clock()
                        check_time(final_time, proof, initial=initial_time)
                        check_session_time(final_time, original_session)
                    except (AdmissionUncertain, AcceptanceOutcomeUnknown):
                        uncertain = True
                        raise
                    except FlowError as error:
                        uncertain = error.code == 'INTERNAL_ERROR' and uow.failed
                        raise
                    except Exception:
                        uncertain = True
                        raise

                uow.before_commit(final_check)
                uow.commit()
                committed = True
            return AdmissionResult('CHECKED')
        except (AdmissionUncertain, AcceptanceOutcomeUnknown):
            return AdmissionResult('UNKNOWN')
        except FlowError as error:
            if (committed or uncertain or error.code == 'INTERNAL_ERROR'
                    or uow is not None and uow.connection is not None and not uow.connection.closed):
                return AdmissionResult('UNKNOWN')
            return AdmissionResult('DENIED', error.code)
        except Exception:
            # No inferred rollback, follow-up read, new key, retry, or audit.
            return AdmissionResult('UNKNOWN')
