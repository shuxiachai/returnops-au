"""Real schema-isolated PG17 and private test identities, shared with investigation."""
import importlib.util
import os
import json
import re
import stat
import sys
from time import monotonic_ns
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from returnops_api.settings import require_environment_database

spec = importlib.util.spec_from_file_location('founder_investigation_fixture', Path(__file__).parents[1] / 'investigation/conftest.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
identities = shared.identities
enabled = shared.enabled


class DiagnosticWriteFailure(BaseException):
    """Never become a production UNKNOWN through an except Exception handler."""


DIAGNOSTIC_PHASES = frozenset({
    'logger.init', 'logger.close', 'fixture.admission', 'fixture.create-schema',
    'fixture.migrate', 'fixture.await-call', 'fixture.cleanup', 'fixture.complete',
    'fixture.create-commit', 'fixture.create-close', 'fixture.migrate-commit',
    'fixture.migrate-close', 'fixture.cleanup-commit', 'fixture.cleanup-close',
    'parent.ready', 'parent.snapshot', 'parent.holder', 'parent.launch', 'parent.signals',
    'parent.waiters', 'parent.release-holder', 'parent.wait-child', 'parent.child-exit', 'parent.child-log-failure',
    'parent.child-json', 'parent.zero-effects', 'parent.pdf-counts', 'parent.installed-hashes',
    'parent.distinct-processes', 'parent.one-completion', 'parent.result-statuses',
    'parent.one-read', 'parent.one-claim-artifact-content', 'parent.before-restart',
    'parent.restart', 'parent.restart-result', 'parent.restart-validation',
    'parent.evidence', 'parent.complete', 'probe.init', 'probe.identity', 'probe.dispose',
    'probe.complete', 'T1', 'T2', 'T3', 'RELEASE', 'RECOVER', 'T2.authorize', 'T2.current-claim',
    'T2.source', 'uow.enter', 'uow.commit', 'uow.close', 'uow.exit', 'fence',
})
DIAGNOSTIC_EVENTS = frozenset({'enter', 'return', 'error', 'db_error', 'driver_error', 'checkpoint'})
DIAGNOSTIC_TYPES = frozenset({
    'AssertionError', 'RuntimeError', 'ValueError', 'TypeError', 'KeyError', 'AttributeError', 'JSONDecodeError',
    'OSError', 'PermissionError', 'FileExistsError', 'TimeoutError', 'TimeoutExpired',
    'SQLAlchemyError', 'DBAPIError', 'OperationalError', 'DatabaseError', 'InterfaceError',
    'DataError', 'IntegrityError', 'ProgrammingError', 'InternalError', 'InvalidRequestError',
    'PendingRollbackError', 'DisconnectionError', 'FlowError', 'AcceptanceOutcomeUnknown',
    'SecurityStoreUnavailable', 'SecurityDependencyError', 'LockNotAvailable', 'QueryCanceled',
    'DeadlockDetected', 'SerializationFailure', 'UndefinedTable', 'UndefinedColumn',
    'InsufficientPrivilege', 'ConnectionFailure', 'AdminShutdown', 'KeyboardInterrupt',
    'SystemExit', 'OTHER',
})
DIAGNOSTIC_FLOW_CODES = frozenset({'INTERNAL_ERROR', 'INVALID_STATE', 'VALIDATION_ERROR',
    'UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND', 'CONFLICT', 'REQUEST_TOO_LARGE',
    'UNSUPPORTED_MEDIA_TYPE'})


def diagnostic_exit(code):
    # Fixed bytes only. No exception object, text, traceback, flush of other buffers or SQL.
    try:
        os.write(2, b'ARTIFACT_DIAGNOSTIC_LOG_FAILURE\n' if code == 125 else b'ARTIFACT_DIAGNOSTIC_STOP\n')
    except BaseException:
        pass
    os._exit(code)


class SafeDiagnosticLog:
    MAX_RECORDS = 256
    MAX_BYTES = 65536

    def __init__(self, path):
        self._fatal_boundary(self._initialize, path)

    @staticmethod
    def _fatal_boundary(operation, *args, **kwargs):
        # Convert locally and terminate at the logger call boundary. Raising a
        # logger failure through a DB callback would run its caller's finally.
        try:
            try:
                return operation(*args, **kwargs)
            except DiagnosticWriteFailure:
                raise
            except BaseException:
                raise DiagnosticWriteFailure() from None
        except DiagnosticWriteFailure:
            diagnostic_exit(125)

    def _initialize(self, path):
        self.fd = None
        self.failed = False
        self.closed = False
        self.sequence = 0
        self.size = 0
        self.started = monotonic_ns()
        self.phase = 'logger.init'
        try:
            source = Path(__file__).resolve().parents[2]
            home = source.parent
            path = Path(path)
            if not path.is_absolute() or '..' in path.parts:
                raise ValueError()
            for item in (path, *path.parents):
                if item.is_symlink():
                    raise ValueError()
                if os.name == 'nt' and item.exists() and item.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise ValueError()
            resolved = path.resolve()
            if not resolved.is_relative_to(home) or resolved.is_relative_to(source) or not resolved.parent.is_dir():
                raise ValueError()
            self.fd = os.open(resolved, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0), 0o600)
            self.emit('logger.init', 'return')
        except BaseException:
            self.failed = True
            raise DiagnosticWriteFailure() from None

    def emit(self, phase, event, error=None, *, flow_code=None):
        return self._fatal_boundary(self._emit, phase, event, error, flow_code=flow_code)

    def _emit(self, phase, event, error=None, *, flow_code=None):
        if self.failed or self.closed:
            raise DiagnosticWriteFailure() from None
        try:
            if phase not in DIAGNOSTIC_PHASES or event not in DIAGNOSTIC_EVENTS:
                raise ValueError()
            error_type = None if error is None else type(error).__name__
            if error_type is not None and error_type not in DIAGNOSTIC_TYPES:
                error_type = 'OTHER'
            code = flow_code if error is None else getattr(error, 'code', None)
            code = code if type(code) is str and code in DIAGNOSTIC_FLOW_CODES else None
            driver = getattr(error, 'orig', error) if error is not None else None
            state = getattr(driver, 'sqlstate', None) if driver is not None else None
            state = state if type(state) is str and re.fullmatch('[A-Z0-9]{5}', state) else None
            row = dict(sequence=self.sequence + 1, process=os.getpid(),
                elapsed_ms=(monotonic_ns() - self.started) // 1000000, phase=phase, event=event,
                exception_type=error_type, flow_code=code, sqlstate=state)
            raw = (json.dumps(row, ensure_ascii=True, separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')
            if self.sequence >= self.MAX_RECORDS or self.size + len(raw) > self.MAX_BYTES:
                raise ValueError()
            if os.write(self.fd, raw) != len(raw):
                raise OSError()
            os.fsync(self.fd)
            self.sequence += 1
            self.size += len(raw)
            self.phase = phase
        except BaseException:
            self.failed = True
            raise DiagnosticWriteFailure() from None

    def close(self):
        return self._fatal_boundary(self._close_log)

    def _close_log(self):
        if self.failed or self.closed:
            raise DiagnosticWriteFailure() from None
        try:
            self.emit('logger.close', 'return')
            os.close(self.fd)
            self.closed = True
        except BaseException:
            self.failed = True
            raise DiagnosticWriteFailure() from None

    def stop(self, phase, error=None):
        try:
            self.emit(phase, 'error', error)
            self.close()
        except DiagnosticWriteFailure:
            diagnostic_exit(125)
        diagnostic_exit(124)


@pytest.fixture
def flow_engine(request):
    log = None
    phase = 'fixture.admission'
    try:
        source = Path(__file__).resolve().parents[2]
        if Path(os.environ['ARTIFACT_DIAGNOSTIC_ROOT']).resolve() != source.parent / 'runtime/artifacts/test-diagnostic/diagnostic-logs':
            diagnostic_exit(125)
        log = SafeDiagnosticLog(Path(os.environ['ARTIFACT_DIAGNOSTIC_ROOT']) / 'parent-diagnostic.jsonl')
        log.emit(phase, 'enter')
        from sqlalchemy.engine import make_url
        assert os.environ['ARTIFACT_DIAGNOSTIC_PHASE'] == 'EXECUTION'
        assert Path(os.environ['MANUAL_INSTALLED_DIR']).resolve() == source.parent / 'installed'
        assert Path(os.environ['MANUAL_INSTALLED_DIR']).is_dir()
        raw = os.environ.get('DATABASE_URL', '')
        require_environment_database(raw)
        url = make_url(raw)
        assert (url.host, url.port, url.database) == ('127.0.0.1', 55433, 'returnops_f02_a203_artifact_diag_v05_20261018')
        assert url.database == os.environ['ARTIFACT_DATABASE_NAME']
        expected_oid = int(os.environ['ARTIFACT_DATABASE_OID'])
        assert expected_oid > 0
        schema = 'customer_test_' + uuid4().hex
        control = create_engine(raw, hide_parameters=True, echo=False)
        phase = 'fixture.create-schema'; log.emit(phase, 'enter')
        # No transaction context manager: failures must reach the stop boundary
        # before this fixture issues rollback, close, disposal or DROP.
        connection = control.connect()
        transaction = connection.begin()
        assert 170000 <= int(connection.execute(text('SHOW server_version_num')).scalar_one()) < 180000
        assert tuple(connection.execute(text("SELECT current_database(),oid FROM pg_database WHERE datname=current_database()")).one()) == (url.database, expected_oid)
        assert connection.execute(text('SELECT count(*) FROM pg_namespace WHERE nspname=:name'), {'name': schema}).scalar_one() == 0
        connection.execute(text('CREATE SCHEMA ' + schema))
        phase = 'fixture.create-commit'; log.emit(phase, 'enter')
        transaction.commit()
        log.emit(phase, 'return')
        phase = 'fixture.create-close'; log.emit(phase, 'enter')
        connection.close()
        log.emit(phase, 'return')
        engine = create_engine(raw, hide_parameters=True, echo=False, pool_size=8, max_overflow=4,
            connect_args={'connect_timeout': 3, 'options': '-c search_path=' + schema + ' -c statement_timeout=10000'})
        engine._customer_test_schema = schema
        engine._artifact_diagnostic = log
        engine._artifact_diagnostic_call_succeeded = False
        phase = 'fixture.migrate'; log.emit(phase, 'enter')
        # Same migration Config/connection/revision inputs as migrate(), with
        # explicit commit so no fixture context-manager rollback can run.
        config = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))
        connection = engine.connect()
        transaction = connection.begin()
        config.attributes['connection'] = connection
        command.upgrade(config, getattr(request, 'param', 'head'))
        phase = 'fixture.migrate-commit'; log.emit(phase, 'enter')
        transaction.commit()
        log.emit(phase, 'return')
        phase = 'fixture.migrate-close'; log.emit(phase, 'enter')
        connection.close()
        log.emit(phase, 'return')
        phase = 'fixture.await-call'; log.emit(phase, 'enter')
        yield engine
        # pytest does not throw a failed test call back through the fixture yield.
        # Only the exact test's post-assertion marker admits normal owned-schema teardown.
        if engine._artifact_diagnostic_call_succeeded is not True:
            log.stop(phase)
        phase = 'fixture.cleanup'; log.emit(phase, 'enter')
        engine.dispose()
        connection = control.connect()
        transaction = connection.begin()
        connection.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        phase = 'fixture.cleanup-commit'; log.emit(phase, 'enter')
        transaction.commit()
        log.emit(phase, 'return')
        phase = 'fixture.cleanup-close'; log.emit(phase, 'enter')
        connection.close()
        control.dispose()
        log.emit(phase, 'return')
        log.emit('fixture.complete', 'return')
        log.close()
    except DiagnosticWriteFailure:
        diagnostic_exit(125)
    except BaseException as error:
        if log is None:
            diagnostic_exit(125)
        log.stop(phase, error)


def migrate(engine, revision='head'):
    config = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, revision)
