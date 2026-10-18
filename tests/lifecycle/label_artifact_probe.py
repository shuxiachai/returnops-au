"""Owned installed process; exact new database and no source checkout imports."""
from dataclasses import asdict
from functools import partial
from hashlib import sha256
import importlib,json,os,re,socket,sys,stat
from pathlib import Path
from time import monotonic_ns
sys.path.insert(0,sys.argv[1])
from sqlalchemy import create_engine,event,text
from sqlalchemy.engine import make_url
from returnops_api.private_label_artifact import compose_private_label_artifact
from returnops_api.security.authentication import AuthConfig
from returnops_domain import customer_uow
from returnops_domain.core_return_mock import CoreReturnMock
from returnops_domain.core_label_mock import CoreLabelMock
from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock

MODULES=['returnops_domain.'+n for n in ('label_artifact','label_artifact_sources','label_artifact_tables','label_artifact_schema',
    'label_artifact_history','label_artifact_retention','label_artifact_retention_sources','generated_evidence','core_label_artifact_mock','label_pdf','label_pdf_validation',
    'execution_artifact_chain_sources','lifecycle_schema','lifecycle_state','founder_integrity','history','customer_service',
    'label_execution_sources','return_execution_sources','return_label_sources','execution_preparation_sources')]+[
    'returnops_api.private_label_artifact','returnops_api.customer_authority','returnops_api.database']

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


def main():
    installed=Path(sys.argv[1]).resolve();config=json.loads(sys.stdin.buffer.read())
    assert config['diagnostic_name'] in {'artifact-diagnostic-0.jsonl','artifact-diagnostic-1.jsonl','artifact-diagnostic-restart.jsonl'}
    assert Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[2].parent/'runtime/artifacts/test-diagnostic')
    log=SafeDiagnosticLog(Path.cwd()/config['diagnostic_name'])
    state={'phase':'probe.init'}
    log.emit('probe.init','enter')
    assert os.environ['ARTIFACT_DIAGNOSTIC_PHASE']=='EXECUTION'
    assert installed==Path(os.environ['MANUAL_INSTALLED_DIR']).resolve()==Path(__file__).resolve().parents[2].parent/'installed'
    assert re.fullmatch(r'customer_test_[a-f0-9]{32}',config['schema'])
    assert not Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[2])
    hashes={}
    for name in MODULES:
        path=Path(importlib.import_module(name).__file__).resolve();assert path.is_relative_to(installed)
        hashes[name]=sha256(path.read_bytes()).hexdigest()
    url=make_url(os.environ['DATABASE_URL'])
    assert url.host=='127.0.0.1' and url.port==55433
    assert url.database==os.environ['ARTIFACT_DATABASE_NAME']
    assert url.database in ('returnops_f02_a203_artifact_20261016','returnops_f02_a203_artifact_v02_20261016','returnops_f02_a203_artifact_v04_20261018','returnops_f02_a203_artifact_diag_v05_20261018')
    expected_oid=int(os.environ['ARTIFACT_DATABASE_OID']);assert expected_oid>0
    engine=create_engine(url,hide_parameters=True,echo=False,connect_args={
        'connect_timeout':3,'options':'-c search_path='+config['schema']+' -c statement_timeout=15000'})

    def instrument(phase,function):
        # Each invocation captures its own original, never a loop's final alias.
        def wrapped(*args,**kwargs):
            previous=state['phase'];state['phase']=phase
            log.emit(phase,'enter')
            try:
                value=function(*args,**kwargs)
            except DiagnosticWriteFailure:
                raise
            except BaseException as error:
                log.emit(phase,'error',error)
                raise
            else:
                log.emit(phase,'return')
                return value
            finally:
                state['phase']=previous
        return wrapped

    def observe_database_error(context):
        # Observe this engine only, before UoW/security conversion hides the SQLSTATE.
        # Do not inspect statement/parameters/connection/exception text or replace errors.
        log.emit(state['phase'],'db_error',context.sqlalchemy_exception)
        log.emit(state['phase'],'driver_error',context.original_exception)
        return None

    event.listen(engine,'handle_error',observe_database_error)
    def exact_database(connection,record):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),oid,current_setting('server_version_num') FROM pg_database WHERE datname=current_database()")
            name,oid,version=cursor.fetchone()
        connection.rollback();assert (name,oid,int(version))==(url.database,expected_oid,170011)
    event.listen(engine,'connect',instrument('probe.identity',exact_database))
    auth=AuthConfig(config['issuer'],config['audience'],bytes.fromhex(config['signing_key']),leeway_seconds=0)
    caller=compose_private_label_artifact(engine,auth,'Bearer '+config['token'],
        uow_factory=partial(customer_uow.CustomerUnitOfWork,lock_timeout_ms=10000))
    caller._claim=instrument('T1',caller._claim)
    caller._complete=instrument('T3',caller._complete)
    caller._release=instrument('RELEASE',caller._release)
    caller.recover_label_artifact=instrument('RECOVER',caller.recover_label_artifact)
    # Patch the class's methods, not the default argument of CoreLabelArtifactMock.
    # Its original 5000ms default and the service's original 10000ms remain unchanged.
    for name,phase in (('__enter__','uow.enter'),('commit','uow.commit'),('_close','uow.close'),('__exit__','uow.exit')):
        setattr(customer_uow.CustomerUnitOfWork,name,instrument(phase,getattr(customer_uow.CustomerUnitOfWork,name)))
    from returnops_domain import core_label_artifact_mock as mock_module
    for name,phase in (('authorize','T2.authorize'),('current_claim','T2.current-claim'),
                       ('verify_original_label_source_0013','T2.source')):
        setattr(mock_module,name,instrument(phase,getattr(mock_module,name)))
    counts=dict(return_provider=0,label_provider=0,artifact_read=0,outbound=0,notification_send=0,LLM=0)
    def forbidden_return(*a,**k):counts['return_provider']+=1;raise AssertionError('No provider creation or query')
    def forbidden_label(*a,**k):counts['label_provider']+=1;raise AssertionError('No provider creation or query')
    CoreReturnMock.perform=forbidden_return;CoreLabelMock.perform=forbidden_label
    original=CoreLabelArtifactMock.retrieve_original_label
    observed_original=instrument('T2',original)
    def observed(self,*a,**k):counts['artifact_read']+=1;return observed_original(self,*a,**k)
    CoreLabelArtifactMock.retrieve_original_label=observed
    def outbound(*a,**k):counts['outbound']+=1;raise AssertionError('No outbound connection')
    socket.create_connection=outbound
    from returnops_domain import label_pdf as pdf,label_pdf_validation as validation,label_artifact_sources as sources
    # Code identity observes preexisting import aliases. Only ordinary T2 may render.
    pdf_codes={function.__code__:name for name,function in dict(pdf_render=pdf.render_label_pdf,
        pdf_text_line=pdf._text_line,pdf_assembly=pdf._assemble_pdf,pdf_expected=sources.expected_pdf,
        pdf_validation=validation.verify_label_pdf).items()}
    counts.update({name:0 for name in pdf_codes.values()})
    def profile(frame,event,arg):
        if event=='call' and frame.f_code in pdf_codes:
            name=pdf_codes[frame.f_code];counts[name]+=1
            if config['mode']=='recover' and name!='pdf_validation':raise AssertionError('Recovery executed renderer code')
        if event=='call' and frame.f_code.co_name in {'send_notification','invoke_model','generate_completion'}:
            counts['notification_send' if frame.f_code.co_name=='send_notification' else 'LLM']+=1
    fence=customer_uow.acquire_fence;announced=[]
    observed_original_fence=instrument('fence',fence)
    def observed_fence(connection,*,write):
        if config.get('signal') and not announced:
            pid=connection.execute(text('SELECT pg_backend_pid()')).scalar_one();target=Path(config['signal']);pending=target.with_suffix('.writing')
            with pending.open('x',encoding='utf8') as stream:json.dump(dict(pid=pid,process=os.getpid()),stream)
            pending.replace(target);announced.append(pid)
        return observed_original_fence(connection,write=write)
    customer_uow.acquire_fence=observed_fence;sys.setprofile(profile)
    try:
        if config['mode']=='complete':result=caller.complete_label_artifact(**config['arguments'])
        else:assert config['mode']=='recover';result=caller.recover_label_artifact(**config['arguments'])
    finally:sys.setprofile(None)
    instrument('probe.dispose',engine.dispose)()
    log.emit('probe.complete','return',flow_code=result.safe_code)
    log.close()
    print(json.dumps(dict(result=asdict(result),counts=counts,process=os.getpid(),announced=announced,installed_hashes=hashes)))

if __name__=='__main__':
    try:main()
    except DiagnosticWriteFailure:
        diagnostic_exit(125)
    except Exception as error:
        error_type=type(error).__name__
        print(json.dumps(dict(probe_error_type=error_type if error_type in DIAGNOSTIC_TYPES else 'OTHER')),file=sys.stderr)
        raise SystemExit(1) from None
    except BaseException:
        diagnostic_exit(124)
