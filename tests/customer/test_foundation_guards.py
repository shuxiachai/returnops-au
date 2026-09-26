from types import SimpleNamespace
import traceback
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain import customer_tables as tables

class BrokenTransaction:
    def __init__(self, commit_error=False): self.commit_error = commit_error
    def commit(self):
        if self.commit_error: raise SQLAlchemyError("private-commit-driver-detail")

class FakeConnection:
    def __init__(self, *, close_error=False, commit_error=False):
        self.close_error = close_error; self.transaction = BrokenTransaction(commit_error)
    def execution_options(self, **options):
        assert options == {"isolation_level": "READ COMMITTED"}
        return self
    def begin(self): return self.transaction
    def execute(self, *args): return None
    def close(self):
        if self.close_error: raise SQLAlchemyError("private-cleanup-driver-detail")

class FakeEngine:
    echo = False; hide_parameters = True; pool = SimpleNamespace(echo=False)
    def __init__(self, **kwargs): self.connection = FakeConnection(**kwargs)
    def connect(self): return self.connection

def test_cleanup_failure_is_not_reported_as_success_and_has_no_raw_context():
    try:
        with CustomerUnitOfWork(FakeEngine(close_error=True), write=True): pass
    except FlowError as error:
        output = str(error) + "".join(traceback.format_exception(error))
        assert "private-cleanup-driver-detail" not in output
        assert error.__cause__ is None and error.__context__ is None
    else: pytest.fail("Cleanup failure was swallowed")

def test_cleanup_does_not_replace_unknown_commit_or_existing_safe_error():
    with pytest.raises(AcceptanceOutcomeUnknown):
        with CustomerUnitOfWork(FakeEngine(close_error=True, commit_error=True), write=True) as uow:
            uow.commit()
    with pytest.raises(FlowError) as error:
        with CustomerUnitOfWork(FakeEngine(close_error=True), write=True):
            raise FlowError("INVALID_STATE")
    assert error.value.code == "INVALID_STATE"

def test_read_only_customer_uow_refuses_a_later_write_and_poisoned_commit():
    with CustomerUnitOfWork(FakeEngine(), write=False) as uow:
        uow.execute(select(tables.principals))
        with pytest.raises(FlowError): uow.execute(tables.principals.insert())
        with pytest.raises(FlowError): uow.commit()
