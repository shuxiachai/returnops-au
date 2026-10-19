"""One private connection and fenced transaction for a customer operation."""
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from .errors import FlowError, AcceptanceOutcomeUnknown
from .fence import acquire_fence

class CustomerUnitOfWork:
    def __init__(self, engine, *, write: bool, lock_timeout_ms: int = 5000) -> None:
        self.engine, self.write = engine, write
        if type(lock_timeout_ms) is not int or not 1 <= lock_timeout_ms <= 10000: raise FlowError("INTERNAL_ERROR")
        self.lock_timeout_ms = lock_timeout_ms
        self.connection = None; self.transaction = None; self.failed = False; self.finished = False
        self._commit_checks = []

    def poison(self): self.failed = True

    def before_commit(self, check):
        """Private guard checks run under this transaction's original fence."""
        if not self.write or self.failed or self.finished or self.transaction is None or not callable(check):
            self.poison(); raise FlowError('INTERNAL_ERROR')
        self._commit_checks.append(check)

    def __enter__(self):
        if self.connection is not None or self.engine.echo or self.engine.pool.echo or not self.engine.hide_parameters:
            raise FlowError("INTERNAL_ERROR")
        failed = False
        try:
            self.connection = self.engine.connect()
            self.connection = self.connection.execution_options(isolation_level="READ COMMITTED")
            self.transaction = self.connection.begin()
            self.connection.execute(text("SELECT set_config('lock_timeout', :timeout, true)"), {"timeout": str(self.lock_timeout_ms)+"ms"})
            acquire_fence(self.connection, write=self.write)
        except SQLAlchemyError:
            failed = True
        if failed:
            self._close(); raise FlowError("INTERNAL_ERROR") from None
        return self

    def execute(self, statement, parameters=None):
        if self.failed or self.finished or self.connection is None: raise FlowError("INTERNAL_ERROR")
        if not self.write and not getattr(statement, "is_select", False):
            self.failed = True
            raise FlowError("INTERNAL_ERROR")
        failed = False
        try:
            result = self.connection.execute(statement, parameters or {})
        except SQLAlchemyError:
            self.failed = True; failed = True
        if failed: raise FlowError("INTERNAL_ERROR") from None
        return result

    def commit(self):
        if self.failed or self.finished or self.transaction is None: raise FlowError("INTERNAL_ERROR")
        check_failed = False
        try:
            for check in self._commit_checks: check()
        except Exception:
            self.poison(); check_failed = True
        if check_failed:
            raise FlowError('INVALID_STATE') from None
        failed = False
        try: self.transaction.commit()
        except SQLAlchemyError: failed = True
        self.finished = True
        if failed:
            self.failed = True; raise AcceptanceOutcomeUnknown() from None

    def _close(self):
        closed = True
        try:
            if self.connection is not None: self.connection.close()
        except SQLAlchemyError:
            self.failed = True; closed = False
        self.finished = True
        return closed

    def __exit__(self, kind, value, trace):
        closed = self._close()
        if not closed and kind is None:
            raise FlowError("INTERNAL_ERROR") from None
        return False
