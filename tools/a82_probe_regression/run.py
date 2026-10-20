"""Issue81/KAN-15: finite12 regression, no local execution or implicit retries."""
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import threading

SELECTION = json.loads(Path(__file__).with_name('selection.json').read_text())
NODES = SELECTION['nodes']
BASE = '7b2dd209a628e58f84d136e933fd345745799a77'
BRANCH = 'refs/heads/diag/81-a82-remaining-20261020'
LIMIT = 1024 * 1024
STAGES = set()
HARNESSES = {'.github/workflows/a82-probe-regression.yml',
             'tools/a82_probe_regression/run.py', 'tools/a82_probe_regression/phase_report.py',
             'tools/a82_probe_regression/selection.json'}
REASONS = {'artifact signal timeout or early exit', 'artifact actual waiter timeout',
    'artifact owned process timeout', 'parent assertion or observation failed with an owned child still running',
    'label signal timeout', 'label child exited before wait observation', 'label actual waiter timeout',
    'label owned process timeout', 'owned process timeout', 'fence signal timeout',
    'owned child exited before observed fence wait', 'actual advisory waiter timeout'}


def read_sample(path, base):
    """A failed/racing evidence read is data, never a replacement test exit."""
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or path.is_symlink():
            return None, dict(file=path.name, collection_error='nonregular-or-symlink')
        if not path.resolve(strict=True).is_relative_to(base.resolve(strict=True)):
            return None, dict(file=path.name, collection_error='outside-evidence-base')
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(descriptor, 'rb') as source:
            opened = os.fstat(source.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                return None, dict(file=path.name, collection_error='file-changed-before-read')
            raw = source.read(LIMIT + 1)
    except (OSError, ValueError) as error:
        return None, dict(file=path.name, collection_error=type(error).__name__)
    return raw, dict(file=path.name, size=opened.st_size,
                  sampled_bytes=min(len(raw), LIMIT), truncated=len(raw) > LIMIT,
                  sample_sha256=sha256(raw[:LIMIT]).hexdigest())


def stream_summary(path, base):
    """Do not export arbitrary text, tokens, config payloads, SQL or tracebacks."""
    raw, result = read_sample(path, base)
    if raw is None:
        return result
    if len(raw) > LIMIT:
        return result
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        result['text_omitted'] = True
        return result
    if isinstance(value, dict):
        kind = value.get('probe_error_type')
        if isinstance(kind, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', kind):
            result['probe_error_type'] = kind
        if isinstance(value.get('diagnostic_stage'), str) and value['diagnostic_stage'] in STAGES:
            result['diagnostic_stage'] = value['diagnostic_stage']
        if type(value.get('process')) is int:
            result['process'] = value['process']
    return result


def collect(base):
    emergencies, streams = [], []
    prefixes = ('test_LE_G6_G11', 'test_LE_G8_G11', 'test_RB_G7_G11', 'test_RB_G9_G11', 'test_LA_P07_P13')
    folders = sorted({folder for prefix in prefixes for folder in base.glob(prefix + '*')
                      if not folder.is_symlink() and folder.is_dir()})
    assert len(folders) <= 12
    for folder in folders:
        assert folder.resolve().is_relative_to(base.resolve())
        for name in ('bridge-emergency.json', 'bridge-emergency-samples.json'):
            path = folder / name
            if not path.exists(): continue
            raw, metadata = read_sample(path, base)
            if raw is None or metadata['truncated']:
                emergencies.append(metadata); continue
            try:
                value = json.loads(raw)
                assert type(value) is dict and type(value.get('owned_children', [])) is list
                assert all(type(child) is dict for child in value.get('owned_children', []))
                row = {key:value[key] for key in ('stopped','pytest_process','streams_final','no_kill','no_retry','schema_retained')
                       if type(value.get(key)) in (bool,int)}
                row['file'] = name
                row['reason'] = value.get('reason') if value.get('reason') in REASONS else 'unrecognized-reason-omitted'
                row['owned_children'] = [{key:child[key] for key in ('pid','poll')
                    if key in child and (child[key] is None or type(child[key]) is int)}
                    for child in value.get('owned_children', [])[:3]]
                emergencies.append(row)
            except (ValueError,UnicodeError,AssertionError,TypeError,RecursionError) as error:
                emergencies.append({**metadata,'collection_error':type(error).__name__})
        for prefix in ('label','bridge','artifact'):
            for index in ('0','1','first','accept','restart'):
                for kind in ('stdout','stderr'):
                    path = folder / (prefix+'-'+index+'.'+kind+'.bin')
                    if path.exists(): streams.append(stream_summary(path,base))
    return dict(emergencies=emergencies,child_streams=streams)


def phase_proof(path, private, code, poll):
    raw, metadata = read_sample(path, private)
    result = dict(selected_nodes_passed=False, report=metadata)
    if raw is None: return result
    expected = [dict(event='collection',count=len(NODES),exact_nodes=True)]
    expected += [dict(event='report',node_index=index,phase=phase,outcome='passed',xfail=False)
                 for index in range(len(NODES)) for phase in ('setup','call','teardown')]
    expected += [dict(event='session',exitstatus=0)]
    try:
        assert len(raw) <= 16384 and not metadata['truncated'] and raw.endswith(b'\n')
        records = [json.loads(line) for line in raw.splitlines()]
        assert len(records) == len(expected)
        for actual,wanted in zip(records,expected):
            assert type(actual) is dict and set(actual) == set(wanted)
            assert all(type(actual[key]) is type(value) and actual[key] == value for key,value in wanted.items())
        assert type(code) is int and code == 0 and type(poll) is int and poll == 0
    except (AssertionError,ValueError,UnicodeError,RecursionError):
        result['proof_error'] = 'incomplete-or-nonpassing-phase-proof'; return result
    result.update(selected_nodes_passed=True,collected=len(NODES),report_count=len(expected),
        exact_order=True,setup_passed=len(NODES),call_passed=len(NODES),teardown_passed=len(NODES),
        skipped=0,xfail=0,session_exitstatus=0)
    return result


def regression_exit(code, proof):
    return code if code != 0 else (0 if proof['selected_nodes_passed'] else 126)


def listing(raw):
    entries = {}
    for item in raw.split(b'\0'):
        if not item: continue
        meta,name = item.split(b'\t',1)
        mode,kind,blob = meta.decode().split()
        entries[name.decode()] = dict(mode=mode,kind=kind,blob=blob)
    return entries


def main():
    root = Path(__file__).resolve().parents[2]
    # Reject before subprocess, artifacts, tests or DB access outside this one job.
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    assert os.environ.get('GITHUB_REPOSITORY') == 'shuxiachai/returnops-au'
    assert os.environ.get('GITHUB_REF') == BRANCH and os.environ.get('GITHUB_EVENT_NAME') == 'push'
    assert os.environ.get('GITHUB_RUN_ATTEMPT') == '1'
    assert os.environ.get('DATABASE_URL') == 'postgresql+psycopg://returnops_ci:ci_synthetic_only@localhost:5432/returnops_f02_ci'
    assert not any(key in os.environ for key in ('ARTIFACT_DATABASE_NAME','ARTIFACT_DATABASE_OID',
        'LABEL_DATABASE_NAME','LABEL_DATABASE_OID','BRIDGE_DATABASE_NAME','BRIDGE_DATABASE_OID',
        'MANUAL_INSTALLED_DIR','MANUAL_EVIDENCE_DIR','PYTEST_ADDOPTS'))
    assert os.environ.get('A82_SERVICE_ID') and len(NODES) == len(set(NODES)) == 12
    temp = Path(os.environ['RUNNER_TEMP']).resolve(); assert not temp.is_relative_to(root)
    def git(*args): return subprocess.check_output(['git','-C',str(root),*args])
    def git_text(*args): return git(*args).decode().strip()
    commit = git_text('rev-parse','HEAD'); formal = SELECTION['formal_commit']
    assert commit == os.environ['GITHUB_SHA']
    assert git_text('rev-list','--parents','-n','1',commit).split() == [commit,formal]
    assert git_text('rev-list','--parents','-n','1',formal).split() == [formal,BASE]
    actual, expected, original = (listing(git('ls-tree','-rz',ref)) for ref in (commit,formal,BASE))
    assert set(actual)-set(expected) == HARNESSES and not set(expected)-set(actual)
    assert {name:entry for name,entry in actual.items() if name not in HARNESSES} == expected
    changed = {name for name in set(expected)|set(original) if expected.get(name) != original.get(name)}
    assert changed == set(SELECTION['formal_paths']) and len(changed) == 9
    assert not set(original)-set(expected)
    for name,entry in actual.items():
        assert entry['mode'] == '100644' and entry['kind'] == 'blob'
        path = root/name; assert path.is_file() and not path.is_symlink()
        data = path.read_bytes()
        assert sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == entry['blob']
    output = root/'a82-safe-artifact'; output.mkdir(exist_ok=False)
    private = Path(tempfile.mkdtemp(prefix='a82-finite-probes-',dir=temp)); base=private/'pytest'
    from sqlalchemy import create_engine,text
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,
        connect_args={'connect_timeout':3,'options':'-c statement_timeout=5000'})
    with engine.connect() as connection:
        identity=dict(connection.execute(text("SELECT current_database() AS name,current_user AS role,oid AS oid,current_setting('server_version_num') AS version,inet_server_port() AS port FROM pg_database WHERE datname=current_database()")).mappings().one())
        revisions=list(connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars())
    engine.dispose()
    assert identity['name']=='returnops_f02_ci' and identity['role']=='returnops_ci'
    assert int(identity['version'])==170011 and identity['port']==5432 and identity['oid']>0
    assert revisions==['0013_label_artifact_result']
    provenance=dict(nodes=NODES,selected_count=12,formal_commit=formal,formal_tree=git_text('rev-parse',formal+'^{tree}'),
        formal_parent=BASE,validation_commit=commit,validation_tree=git_text('rev-parse','HEAD^{tree}'),
        validation_parent=formal,projected_tree_equal=True,formal_paths=sorted(changed),harness_paths=sorted(HARNESSES),
        tracked_working_bytes_equal=True,run=os.environ['GITHUB_RUN_ID'],attempt=1,
        service_id=os.environ['A82_SERVICE_ID'],actual_database_identity=identity,migration=revisions,
        installed_fixture_scope='module',maximum_wheel_builds=3,outer_timeout_seconds=1800,retry=False)
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');print(json.dumps(provenance),flush=True)
    report_path=private/'phase-report.jsonl'
    command=[sys.executable,'-B','-m','pytest',*NODES,'-vv','-s','--tb=short','-x',
        '--basetemp',str(base),'-p','tools.a82_probe_regression.phase_report']
    environment={**os.environ,'PYTHONUNBUFFERED':'1','A82_REPORT_PATH':str(report_path)}
    captured=bytearray();totals=[0]
    process=subprocess.Popen(command,cwd=root,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    def drain():
        while chunk:=process.stdout.read(65536):
            totals[0]+=len(chunk);captured.extend(chunk[:max(0,LIMIT-len(captured))])
    reader=threading.Thread(target=drain,daemon=True);reader.start();timed_out=False
    try:code=process.wait(timeout=1800)
    except subprocess.TimeoutExpired:timed_out=True;code=125
    reader.join(timeout=2);data=bytes(captured)
    (private/'pytest-output.bin').write_bytes(data);poll=process.poll()
    try:proof=phase_proof(report_path,private,code,poll)
    except Exception as error:proof=dict(selected_nodes_passed=False,proof_error=type(error).__name__)
    driver_code=regression_exit(code,proof)
    try:evidence=collect(base)
    except Exception as error:evidence=dict(collection_error=type(error).__name__)
    result=dict(**evidence,nodes=NODES,selected_count=12,exit_code=code,driver_exit_code=driver_code,
        outer_deadline_reached=timed_out,pytest_pid=process.pid,pytest_poll=poll,
        pytest_output_bytes=totals[0],pytest_sample_sha256=sha256(data).hexdigest(),
        pytest_output_truncated=totals[0]>len(data),full_suite=False,acceptance=False,case_proof=proof)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    return driver_code


if __name__=='__main__':sys.exit(main())
