"""stdlib-only mocks/AST/file checks. No real project import, DB, build or subprocess."""
import ast
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import sys
import tempfile
from time import monotonic_ns
import types
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]
sys.path.insert(0, str(HERE))
import runner as r
import export_safe as e
import pytest_entry as pe


class Fatal(BaseException):
    def __init__(self, code): self.code = code


def log_class(path, fake_os):
    tree = ast.parse(path.read_text(encoding='utf8'))
    selected = [node for node in tree.body if
                isinstance(node, ast.ClassDef) and node.name in {'DiagnosticWriteFailure', 'SafeDiagnosticLog'} or
                isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id.startswith('DIAGNOSTIC_')]
    env = dict(os=fake_os, stat=stat, Path=Path, re=re, json=json, monotonic_ns=monotonic_ns,
               __file__=str(path), diagnostic_exit=lambda code: (_ for _ in ()).throw(Fatal(code)))
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), env)
    return env['SafeDiagnosticLog']


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='offline-', dir=SOURCE.parent / 'offline-work')
        self.home = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def inputs(self): return r.load_inputs(SOURCE)

    def installed(self, source=None, home=None, data=None):
        source, home, data = source or SOURCE, home or self.home, data or self.inputs()
        installed = home / 'installed'
        installed.mkdir()
        for original, target in data['source_to_installed'].items():
            path = installed / target; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / original, path)
        for name in ('METADATA', 'WHEEL', 'top_level.txt', 'RECORD', 'INSTALLER', 'REQUESTED', 'direct_url.json'):
            path = installed / 'returnops_au-0.1.0.dist-info' / name
            path.parent.mkdir(exist_ok=True); path.write_text('{}', encoding='ascii')
        return installed


class LoggerTests(Files):
    def make(self, filename='tests/founder/conftest.py', **overrides):
        rows, opens = [], []
        fake = types.SimpleNamespace(name='posix', O_WRONLY=1, O_CREAT=64, O_EXCL=128,
            O_NOFOLLOW=131072, O_CLOEXEC=524288, getpid=lambda: 42,
            open=lambda *args: opens.append(args) or 7,
            write=lambda fd, raw: rows.append(raw) or len(raw), fsync=lambda fd: None, close=lambda fd: None)
        for k, v in overrides.items(): setattr(fake, k, v)
        cls = log_class(SOURCE / filename, fake)
        return cls, rows, opens, fake

    def test_posix_no_windows_attribute_and_secure_flags(self):
        for filename in ('tests/founder/conftest.py', 'tests/lifecycle/label_artifact_probe.py'):
            cls, rows, opens, fake = self.make(filename)
            log = cls(self.home / 'events.jsonl'); log.close()
            self.assertEqual(opens[0][1], 1 | 64 | 128 | 131072 | 524288)
            self.assertEqual(opens[0][2], 0o600)
            self.assertEqual(json.loads(rows[-1])['phase'], 'logger.close')

    def test_relative_escape_source_and_dotdot_rejected(self):
        cls, rows, opens, fake = self.make()
        for path in (Path('relative'), SOURCE / 'bad.jsonl', SOURCE.parent.parent / 'outside.jsonl', self.home / '..' / 'events'):
            with self.assertRaises(Fatal) as stopped: cls(path)
            self.assertEqual(stopped.exception.code, 125)
        self.assertEqual(opens, [])

    def test_symlink_including_dangling_is_rejected_before_exists(self):
        cls, rows, opens, fake = self.make()
        with patch.object(Path, 'is_symlink', return_value=True), patch.object(Path, 'exists', side_effect=AssertionError('must not follow')):
            with self.assertRaises(Fatal): cls(self.home / 'dangling.jsonl')
        self.assertEqual(opens, [])

    def test_windows_attribute_missing_fails_closed(self):
        cls, rows, opens, fake = self.make(name='nt')
        with patch.object(Path, 'lstat', return_value=types.SimpleNamespace(st_mode=stat.S_IFREG)), patch.object(Path, 'is_symlink', return_value=False):
            with self.assertRaises(Fatal): cls(self.home / 'file.jsonl')
        self.assertEqual(opens, [])

    def test_exclusive_open_rejection_terminates(self):
        cls, rows, opens, fake = self.make(open=lambda *args: (_ for _ in ()).throw(FileExistsError('secret')))
        with self.assertRaises(Fatal) as stopped: cls(self.home / 'existing')
        self.assertEqual(stopped.exception.code, 125); self.assertEqual(rows, [])

    def test_error_class_sqlstate_only_no_exception_text(self):
        cls, rows, opens, fake = self.make()
        log = cls(self.home / 'events.jsonl')
        error = RuntimeError('SECRET postgresql://password SQL select personal')
        error.orig = types.SimpleNamespace(sqlstate='55P03'); error.code = 'INTERNAL_ERROR'
        with self.assertRaises(Fatal) as stopped: log.stop('uow.enter', error)
        self.assertEqual(stopped.exception.code, 124)
        row = json.loads(rows[-2]); self.assertEqual(row['sqlstate'], '55P03')
        self.assertEqual(row['exception_type'], 'RuntimeError')
        self.assertNotIn(b'SECRET', b''.join(rows))

    def test_short_write_fsync_close_and_bound_fail_fatally(self):
        for mode in ('short', 'fsync', 'close', 'records', 'bytes'):
            cls, rows, opens, fake = self.make(); log = cls(self.home / 'events.jsonl')
            if mode == 'short': fake.write = lambda fd, data: len(data)-1
            if mode == 'fsync': fake.fsync = lambda fd: (_ for _ in ()).throw(OSError('secret'))
            if mode == 'close': fake.close = lambda fd: (_ for _ in ()).throw(OSError('secret'))
            if mode == 'records': log.sequence = log.MAX_RECORDS
            if mode == 'bytes': log.size = log.MAX_BYTES
            with self.assertRaises(Fatal) as stopped: log.close()
            self.assertEqual(stopped.exception.code, 125)


class GateTests(Files):
    def context(self):
        return dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted', GITHUB_EVENT_NAME='push',
            GITHUB_REPOSITORY='shuxiachai/returnops-au', GITHUB_REF=r.BRANCH, GITHUB_RUN_ATTEMPT='1',
            GITHUB_RUN_ID='123', GITHUB_SHA='a'*40, DIAGNOSTIC_SERVICE_ID='b'*64,
            DIAGNOSTIC_SERVICE_IMAGE=r.IMAGE, DIAGNOSTIC_SERVICE_PORT='55433', DIAGNOSTIC_PASSWORD='synthetic_password')

    def test_context_rejects_attempt_branch_service_and_local(self):
        env = self.context(); self.assertNotIn('DIAGNOSTIC_PASSWORD', r.cloud_context(env, 'linux'))
        for key, value in [('GITHUB_RUN_ATTEMPT','2'), ('GITHUB_REF','refs/heads/main'), ('GITHUB_EVENT_NAME','pull_request'),
                           ('DIAGNOSTIC_SERVICE_ID',''), ('DIAGNOSTIC_SERVICE_PORT','5432'), ('DIAGNOSTIC_SERVICE_IMAGE','postgres:latest'),
                           ('DATABASE_URL','postgresql://local'), ('PGHOST','127.0.0.1'), ('RUNNER_ENVIRONMENT','self-hosted')]:
            with self.assertRaises(r.Stop): r.cloud_context(dict(env, **{key:value}), 'linux')
        with self.assertRaises(r.Stop): r.cloud_context(env, 'win32')

    def test_identity_rejects_wrong_oid_version_name_or_nonfresh(self):
        good = dict(database=r.DATABASE, user='returnops_ci', oid=42, version=170011, server_port=5432, tables=0, user_schemas=['public'])
        r.check_identity(good, fresh=True)
        for key, value in [('oid',0),('version',170012),('database','returnops_f02_ci'),('user','postgres'),('server_port',55433),('tables',1),('user_schemas',['public','old'])]:
            with self.assertRaises(r.Stop): r.check_identity(dict(good, **{key:value}), fresh=True)
        with self.assertRaises(r.Stop): r.check_identity(good, expected_oid=43)

    def test_readonly_service_inspect_matches_actual_container_digest_and_port(self):
        env=self.context();private=self.home/'private';private.mkdir();calls=[]
        container=dict(id=env['DIAGNOSTIC_SERVICE_ID'],image_id='sha256:'+'c'*64,configured_image=r.IMAGE,running=True,ports={'5432/tcp':[{'HostIp':'0.0.0.0','HostPort':'55433'}]})
        def execute(args,cwd,env,private,label):
            calls.append(args)
            value=container if label=='service-inspect' else dict(id=container['image_id'],digests=['postgres@'+r.IMAGE.split('@')[1]])
            (private/(label+'.stdout')).write_text(json.dumps(value))
            return 0
        result=r.service_proof(self.home,env,private,execute)
        self.assertEqual(result['published_port'],55433);self.assertEqual(len(calls),2)
        self.assertTrue(all('inspect' in args for args in calls));self.assertNotIn('.Env',repr(calls))
        for key,value in [('id','d'*64),('running',False),('configured_image','postgres:latest'),('ports',{'5432/tcp':[{'HostIp':'0.0.0.0','HostPort':'5432'}]})]:
            old=container[key];container[key]=value
            with self.assertRaises(r.Stop):r.service_proof(self.home,env,private,execute)
            container[key]=old

    def test_input_manifest_copy_and_hash_drift(self):
        dest = self.home / 'staged'
        source, data = r.stage(SOURCE, dest)
        self.assertEqual(len(data['intentional_absences']), 106)
        self.assertFalse(any((source / p).exists() for p in data['intentional_absences']))
        target = source / next(iter(data['runtime137']))
        target.write_bytes(target.read_bytes()+b'# drift')
        with self.assertRaises(r.Stop): r.load_inputs(source)

    def test_installed_144_source_137_pair_and_extra_rejected(self):
        data=self.inputs(); installed=self.installed(data=data)
        proof=r.verify_installed(SOURCE, installed, data)
        self.assertEqual(proof['runtime_pairs'],137); self.assertEqual(proof['installed_count'],144)
        (installed / 'foreign.py').write_text('bad')
        with self.assertRaises(r.Stop): r.verify_installed(SOURCE, installed, data)

    def test_package_build_commands_and_simulated_wheel_provenance(self):
        data=self.inputs(); private=self.home/'private'; private.mkdir(); calls=[]
        def execute(args,cwd,env,folder,label):
            calls.append(args); self.assertEqual(env['PIP_NO_INDEX'],'1'); self.assertNotIn('PYTHONPATH',env)
            if label=='wheel':
                with zipfile.ZipFile(self.home/'wheels/returnops_au-0.1.0-py3-none-any.whl','w') as z:
                    for original,target in data['source_to_installed'].items(): z.writestr(target,(SOURCE/original).read_bytes())
                    for name in ('METADATA','WHEEL','top_level.txt','RECORD'): z.writestr('returnops_au-0.1.0.dist-info/'+name,b'{}')
            else:
                installed=self.installed(data=data);meta=installed/'returnops_au-0.1.0.dist-info'
                (meta/'INSTALLER').write_bytes(b'pip\n');(meta/'REQUESTED').write_bytes(b'')
                wheel=self.home/'wheels/returnops_au-0.1.0-py3-none-any.whl'
                (meta/'direct_url.json').write_text(json.dumps({'url':wheel.as_uri(),'archive_info':{'hashes':{'sha256':r.sha(wheel)}}}))
            return 0
        result=r.package(SOURCE,self.home,data,{'PYTHONPATH':'foreign'},private,execute)
        self.assertEqual(result['installed_count'],144)
        self.assertEqual(len(calls),2); self.assertIn('--no-build-isolation',calls[0]); self.assertIn('--no-compile',calls[1])

    def test_fixed_collection_and_typed_outcomes(self):
        for phase in ('COLLECTION','EXECUTION'):
            path=self.home/(phase+'.json')
            value=dict(node=r.NODE,phase=phase,collected=[r.NODE],reports=[] if phase=='COLLECTION' else [['setup','passed'],['call','passed'],['teardown','passed']],collection_errors=0,exit_code=0)
            path.write_text(json.dumps(value));r.accept_outcome(path,0,phase)
            for change in ({'collected':[r.NODE,'other']},{'reports':[['call','passed']]},{'exit_code':1},{'collection_errors':1}):
                path.write_text(json.dumps(dict(value,**change)))
                with self.assertRaises(r.Stop):r.accept_outcome(path,0,phase)
            self.assertEqual(r.fixed_command(SOURCE,self.home,phase)[-1],r.NODE)
        with self.assertRaises(r.Stop):r.fixed_command(SOURCE,self.home,'environment')

    def test_failed_collection_stops_before_run_and_repeat_refuses(self):
        source,data=r.stage(SOURCE,self.home/'job');home=source.parent;self.installed(source,home,data)
        private=home/'private';private.mkdir();calls=[]
        def execute(args,cwd,env,private,label):
            calls.append(label)
            r.write_new(cwd/'outcome.json',dict(node=r.NODE,phase='COLLECTION',collected=[r.NODE],reports=[],collection_errors=0,exit_code=1))
            return 1
        for attempt in range(2):
            with self.assertRaises((r.Stop,FileExistsError)):r.run_case(source,home,{'oid':42},'FAKE_NO_CONNECTION',private,execute)
        self.assertEqual(calls,['collect-diagnostic'])
        self.assertFalse((home/'runtime/artifacts/test-diagnostic').exists())

    def test_observer_rejects_different_and_multiple_nodes(self):
        observer=pe.Observer('COLLECTION')
        for nodes in ([],['other'],[r.NODE,r.NODE]):
            with self.assertRaises(r.Stop):observer.pytest_collection_modifyitems(None,None,[types.SimpleNamespace(nodeid=n) for n in nodes])
        observer.pytest_collection_modifyitems(None,None,[types.SimpleNamespace(nodeid=r.NODE)])
        self.assertEqual(observer.collected,[r.NODE])

    def test_success_requires_complete_parent_and_child_logs(self):
        source,data=r.stage(SOURCE,self.home/'job');home=source.parent;self.installed(source,home,data)
        private=home/'private';private.mkdir();calls=[]
        def log(path,phases):
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(''.join(json.dumps(dict(sequence=i,process=42,elapsed_ms=i,phase=p,event='return',exception_type=None,flow_code=None,sqlstate=None))+'\n' for i,p in enumerate(phases,1)))
        def execute(args,cwd,env,private,label):
            calls.append(label);phase=env['ARTIFACT_DIAGNOSTIC_PHASE']
            reports=[] if phase=='COLLECTION' else [['setup','passed'],['call','passed'],['teardown','passed']]
            r.write_new(cwd/'outcome.json',dict(node=r.NODE,phase=phase,collected=[r.NODE],reports=reports,collection_errors=0,exit_code=0))
            if phase=='EXECUTION':
                log(cwd/'diagnostic-logs/parent-diagnostic.jsonl',['logger.init','parent.complete','fixture.complete','logger.close'])
                for name in ('0','1','restart'):log(cwd/'pytest-temp'/('artifact-diagnostic-'+name+'.jsonl'),['logger.init','probe.complete','logger.close'])
            return 0
        result=r.run_case(source,home,{'oid':42},'FAKE_NO_CONNECTION',private,execute)
        self.assertEqual(calls,['collect-diagnostic','test-diagnostic']);self.assertEqual(result['EXECUTION']['exit_code'],0)
        with self.assertRaises(FileExistsError):r.run_case(source,home,{'oid':42},'FAKE_NO_CONNECTION',private,execute)

    def test_exit_without_typed_completion_stays_failed(self):
        source,data=r.stage(SOURCE,self.home/'job');home=source.parent;self.installed(source,home,data)
        private=home/'private';private.mkdir();calls=[]
        def execute(args,cwd,env,private,label):
            calls.append(label)
            if label=='collect-diagnostic':
                r.write_new(cwd/'outcome.json',dict(node=r.NODE,phase='COLLECTION',collected=[r.NODE],reports=[],collection_errors=0,exit_code=0));return 0
            return 124
        with self.assertRaises(r.Stop):r.run_case(source,home,{'oid':42},'FAKE_NO_CONNECTION',private,execute)
        self.assertEqual(calls,['collect-diagnostic','test-diagnostic'])
        self.assertEqual(json.loads((home/'runtime/artifacts/test-diagnostic/process-exit.json').read_bytes()),{'actual_exit':124})

    def test_export_rejects_payload_and_projects_safe_child_fields(self):
        allowed=e.enums(SOURCE)
        path=self.home/'artifact-0.stdout.bin'
        counts={k:0 for k in ('return_provider','label_provider','artifact_read','outbound','notification_send','LLM','pdf_render','pdf_text_line','pdf_assembly','pdf_expected','pdf_validation')}
        value=dict(result=dict(status='UNKNOWN',safe_code='INTERNAL_ERROR',token='SECRET'),counts=counts,process=42,announced=[],installed_hashes={})
        path.write_text(json.dumps(value)); output=e.child_output(path,allowed)
        self.assertNotIn('SECRET',json.dumps(output));self.assertEqual(output['result']['status'],'UNKNOWN')
        path=self.home/'artifact-0.stderr.bin';path.write_text('SQL PASSWORD SECRET')
        with self.assertRaises((r.Stop,json.JSONDecodeError)):e.child_output(path,allowed)

    def export_outcome(self, reports):
        job = self.home / 'diagnostic'
        safe = job / 'safe-artifacts'; safe.mkdir(parents=True)
        fixture = job / 'source/tests/founder/conftest.py'; fixture.parent.mkdir(parents=True)
        shutil.copyfile(SOURCE / 'tests/founder/conftest.py', fixture)
        action = job / 'runtime/artifacts/test-diagnostic'; action.mkdir(parents=True)
        value = dict(node=r.NODE, phase='EXECUTION', collected=[r.NODE], reports=reports,
                     collection_errors=0, exit_code=1)
        (action / 'outcome.json').write_text(json.dumps(value), encoding='utf8')
        checkout_entry = self.home / 'checkout/tools/a203_t2_cloud/export_safe.py'
        with patch.object(e, '__file__', str(checkout_entry)), patch.object(sys, 'argv', [str(checkout_entry)]):
            e.main()
        return safe / 'test-diagnostic-outcome.json', value

    def test_export_outcome_normal_exact_safe_projection(self):
        path, expected = self.export_outcome([['setup', 'passed'], ['call', 'failed'], ['teardown', 'passed']])
        self.assertEqual(json.loads(path.read_bytes()), expected)
        self.assertEqual(set(json.loads(path.read_bytes())), {'node', 'phase', 'collected', 'reports', 'collection_errors', 'exit_code'})

    def test_export_outcome_extra_tail_is_rejected_without_artifact(self):
        with self.assertRaises(r.Stop):
            self.export_outcome([['call', 'failed', 'SQL_OR_TOKEN_TEXT']])
        safe = self.home / 'diagnostic/safe-artifacts'
        self.assertFalse((safe / 'test-diagnostic-outcome.json').exists())
        self.assertFalse(any(b'SQL_OR_TOKEN_TEXT' in path.read_bytes() for path in safe.iterdir() if path.is_file()))

    def test_export_outcome_non_list_is_rejected_without_artifact(self):
        with self.assertRaises(r.Stop):
            self.export_outcome({'call': 'failed'})
        self.assertFalse((self.home / 'diagnostic/safe-artifacts/test-diagnostic-outcome.json').exists())

    def test_imports_inert_without_db_build_or_pytest(self):
        self.assertNotIn('sqlalchemy',sys.modules);self.assertNotIn('alembic',sys.modules);self.assertNotIn('pytest',sys.modules)
        for filename in ('runner.py','pytest_entry.py','export_safe.py'):
            spec=importlib.util.spec_from_file_location('inert_'+filename.replace('.','_'),HERE/filename)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertNotIn('sqlalchemy',sys.modules);self.assertNotIn('alembic',sys.modules);self.assertNotIn('pytest',sys.modules)


class BootstrapTests(Files):
    def fake_modules(self, fail=False):
        calls=[]; identity=dict(database=r.DATABASE,user='returnops_ci',oid=42,version=170011,server_port=5432)
        class Result:
            def __init__(self,value):self.value=value
            def mappings(self):return self
            def one(self):return self.value
            def scalar_one(self):return self.value
            def scalars(self):return self.value
        class Connection:
            def execute(self,sql):
                calls.append(sql)
                if 'current_database' in sql:return Result(identity)
                if 'pg_namespace' in sql:return Result(['public'])
                if 'version_num FROM alembic' in sql:return Result([r.HEAD])
                if 'BASE TABLE' in sql:return Result(61)
                return Result(0)
            def commit(self):calls.append('commit')
            def close(self):calls.append('close')
        class Engine:
            def connect(self):calls.append('connect');return Connection()
            def dispose(self):calls.append('dispose')
        class Config:
            def __init__(self,path):self.attributes={}
            def set_main_option(self,key,value):pass
        def upgrade(config,head):
            calls.append('upgrade:'+head)
            if fail:raise RuntimeError('SECRET SQL failure')
        modules={'sqlalchemy':types.SimpleNamespace(create_engine=lambda *a,**k:Engine(),text=lambda x:x),
                 'alembic':types.SimpleNamespace(command=types.SimpleNamespace(upgrade=upgrade)),
                 'alembic.config':types.SimpleNamespace(Config=Config)}
        return calls,modules

    def test_fake_bootstrap_full_head_oid_and_close_success(self):
        calls,modules=self.fake_modules()
        with patch.dict(sys.modules,modules):result=r.bootstrap(SOURCE,'FAKE_NO_CONNECTION')
        self.assertEqual(result['oid'],42);self.assertEqual(result['migration_head'],r.HEAD)
        self.assertEqual(calls[-2:],['close','dispose'])

    def test_fake_bootstrap_first_error_has_no_later_sql_or_cleanup(self):
        calls,modules=self.fake_modules(fail=True)
        with patch.dict(sys.modules,modules),self.assertRaises(RuntimeError) as error:r.bootstrap(SOURCE,'FAKE_NO_CONNECTION')
        self.assertEqual(calls[-1],'upgrade:head');self.assertNotIn('close',calls);self.assertNotIn('dispose',calls)
        self.assertNotIn('SECRET',json.dumps(r.safe_exception(error.exception)))


class StructureTests(unittest.TestCase):
    def test_workflow_yaml_exact_trigger_service_and_safe_upload(self):
        import yaml
        workflow=yaml.load((SOURCE/'.github/workflows/a203-t2-diagnostic.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(workflow['on'],{'push':{'branches':['diag/a203-t2-cloud-20261018']}})
        self.assertEqual(workflow['concurrency']['cancel-in-progress'],'false')
        job=workflow['jobs']['diagnostic'];self.assertEqual(job['if'],'github.run_attempt == 1')
        service=job['services']['postgres'];self.assertEqual(service['ports'],['55433:5432']);self.assertEqual(service['image'],r.IMAGE)
        self.assertEqual(service['env']['POSTGRES_DB'],r.DATABASE)
        steps=job['steps'];self.assertEqual(steps[-1]['if'],'always()');self.assertEqual(steps[-2]['if'],'always()')
        self.assertEqual(steps[0]['env'],{'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'core.autocrlf','GIT_CONFIG_VALUE_0':'false'})
        self.assertEqual(steps[-1]['with']['path'],'diagnostic/safe-artifacts/*.json')
        self.assertEqual(steps[-1]['with']['overwrite'],'false')
        self.assertNotIn('tools/checks/run.py environment',json.dumps(workflow))
        self.assertEqual(len([s for s in steps if 'runner.py' in s.get('run','')]),1)

    def test_original_case_and_production_migrations_unchanged(self):
        baseline=json.loads((SOURCE.parent/'records/copy-receipt.json').read_bytes())['files']
        data=r.load_inputs(SOURCE)
        for name in [*data['runtime137'],*data['migrations13'],'tests/lifecycle/test_label_artifact_process_postgresql.py','.github/workflows/ci.yml']:
            self.assertEqual(r.sha(SOURCE/name),baseline[name]['sha256'],name)
        changed=[name for name,value in baseline.items() if r.sha(SOURCE/name)!=value['sha256']]
        self.assertEqual(sorted(changed),['tests/founder/conftest.py','tests/lifecycle/label_artifact_probe.py'])

    def test_logger_only_ast_delta(self):
        baseline_root=SOURCE.parent.parent/'diagnostic-v05/source'
        for name in ('tests/founder/conftest.py','tests/lifecycle/label_artifact_probe.py'):
            def stripped(path):
                tree=ast.parse(path.read_bytes())
                for cls in tree.body:
                    if isinstance(cls,ast.ClassDef) and cls.name=='SafeDiagnosticLog':
                        cls.body=[node for node in cls.body if not isinstance(node,ast.FunctionDef) or node.name!='_initialize']
                return ast.dump(tree)
            self.assertEqual(stripped(SOURCE/name),stripped(baseline_root/name))


if __name__ == '__main__':
    (SOURCE.parent/'offline-work').mkdir(exist_ok=True)
    # Hard mocks: any accidentally introduced real subprocess/network launch fails immediately.
    with ExitStack() as guard:
        guard.enter_context(patch('subprocess.Popen',side_effect=AssertionError('offline subprocess forbidden')))
        guard.enter_context(patch('socket.create_connection',side_effect=AssertionError('offline network forbidden')))
        guard.enter_context(patch('socket.socket',side_effect=AssertionError('offline network forbidden')))
        unittest.main(verbosity=2)
