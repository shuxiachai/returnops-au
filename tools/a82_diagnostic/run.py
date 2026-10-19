"""Issue81/KAN-15: one diagnostic node; only safe bounded summaries leave tmp."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import threading

NODE = ('tests/lifecycle/test_label_artifact_process_postgresql.py::'
        'test_LA_P07_P13_two_actual_installed_processes_one_claim_and_completion')
SOURCE = '7b2dd209a628e58f84d136e933fd345745799a77'
BRANCH = 'refs/heads/diag/81-a82-process-20261020'
LIMIT = 1024 * 1024
REASONS = {'artifact signal timeout or early exit', 'artifact actual waiter timeout',
           'artifact owned process timeout', 'parent assertion or observation failed with an owned child still running'}
STAGES = {'startup', 'installed-modules', 'parse-database-url', 'host-port-binding',
          'database-name-binding', 'database-allowlist-binding', 'database-oid-binding',
          'engine-and-operation'}


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
    emergencies = []
    streams = []
    try:
        folders = sorted(base.glob('test_LA_P07_P13*'))[:2]
    except OSError as error:
        return dict(emergencies=[], child_streams=[], collection_error=type(error).__name__)
    for folder in folders:
        if folder.is_symlink() or not folder.is_dir() or not folder.resolve().is_relative_to(base.resolve()):
            emergencies.append(dict(file=folder.name, collection_error='invalid-evidence-directory'))
            continue
        for name in ('bridge-emergency.json', 'bridge-emergency-samples.json'):
            path = folder / name
            raw, metadata = read_sample(path, base)
            if raw is None or metadata['truncated']:
                emergencies.append(metadata)
                continue
            try:
                value = json.loads(raw)
                assert isinstance(value, dict)
                assert isinstance(value.get('owned_children', []), list)
                assert all(isinstance(child, dict) for child in value.get('owned_children', []))
            except (ValueError, UnicodeError, AssertionError, RecursionError) as error:
                emergencies.append({**metadata, 'collection_error': type(error).__name__})
                continue
            row = {key: value.get(key) for key in
                   ('stopped', 'pytest_process', 'streams_final', 'no_kill', 'no_retry', 'schema_retained')
                   if type(value.get(key)) in (bool, int)}
            row['file'] = name
            row['reason'] = value.get('reason') if isinstance(value.get('reason'), str) and value['reason'] in REASONS else 'unrecognized-reason-omitted'
            row['owned_children'] = [
                {key: child[key] for key in ('pid', 'poll')
                 if key in child and (child[key] is None or type(child[key]) is int)}
                for child in value.get('owned_children', [])[:3]]
            emergencies.append(row)
        for index in ('0', '1', 'restart'):
            for kind in ('stdout', 'stderr'):
                path = folder / ('artifact-' + index + '.' + kind + '.bin')
                streams.append(stream_summary(path, base))
    return dict(emergencies=emergencies, child_streams=streams)


def diagnostic_result(code, base, **values):
    try:
        evidence = collect(base)
    except Exception as error:
        evidence = dict(collection_error=type(error).__name__)
    return dict(**values, **evidence, exit_code=code)


def main():
    root = Path(__file__).resolve().parents[2]
    # Fail before any subprocess/test/DB access outside the single authorized job.
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    assert os.environ.get('GITHUB_REPOSITORY') == 'shuxiachai/returnops-au'
    assert os.environ.get('GITHUB_REF') == BRANCH
    assert os.environ.get('GITHUB_RUN_ATTEMPT') == '1'
    assert os.environ.get('GITHUB_EVENT_NAME') == 'push'
    assert os.environ.get('DATABASE_URL') == 'postgresql+psycopg://returnops_ci:ci_synthetic_only@localhost:5432/returnops_f02_ci'
    assert not any(os.environ.get(key) for key in ('ARTIFACT_DATABASE_NAME', 'ARTIFACT_DATABASE_OID', 'MANUAL_INSTALLED_DIR', 'MANUAL_EVIDENCE_DIR', 'PYTEST_ADDOPTS'))
    assert os.environ.get('A82_SERVICE_ID')
    temp = Path(os.environ['RUNNER_TEMP']).resolve()
    assert not temp.is_relative_to(root)
    output = root / 'a82-safe-artifact'
    output.mkdir(exist_ok=False)
    private = Path(tempfile.mkdtemp(prefix='a82-single-node-', dir=temp))
    base = private / 'pytest'
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    commit = git('rev-parse', 'HEAD')
    assert commit == os.environ['GITHUB_SHA']
    assert git('rev-parse', 'HEAD^') == SOURCE
    assert git('rev-list', '--parents', '-n', '1', 'HEAD').split() == [commit, SOURCE]
    from sqlalchemy import create_engine, text
    engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True, echo=False,
                           connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=5000'})
    with engine.connect() as connection:
        identity = dict(connection.execute(text(
            "SELECT current_database() AS name, current_user AS role, "
            "oid AS oid, current_setting('server_version_num') AS version, "
            "inet_server_port() AS port FROM pg_database WHERE datname=current_database()"
        )).mappings().one())
        revisions = list(connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars())
    engine.dispose()
    assert identity['name'] == 'returnops_f02_ci' and identity['role'] == 'returnops_ci'
    assert int(identity['version']) == 170011 and identity['port'] == 5432 and identity['oid'] > 0
    assert revisions == ['0013_label_artifact_result']
    provenance = dict(node=NODE, commit=commit, tree=git('rev-parse', 'HEAD^{tree}'),
                      source=SOURCE, run=os.environ['GITHUB_RUN_ID'], attempt=1,
                      service_id=os.environ['A82_SERVICE_ID'],
                      database=dict(host='localhost', port=5432, name='returnops_f02_ci'),
                      actual_database_identity=identity, migration=revisions,
                      old_probe_bindings_supplied=False, retry=False)
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps(provenance), flush=True)
    command = [sys.executable, '-B', '-m', 'pytest', NODE, '-vv', '-s', '--tb=short', '-x', '--basetemp', str(base)]
    environment = {**os.environ, 'PYTHONUNBUFFERED': '1'}
    captured = bytearray()
    totals = [0]
    process = subprocess.Popen(command, cwd=root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    def drain():
        while chunk := process.stdout.read(65536):
            totals[0] += len(chunk)
            captured.extend(chunk[:max(0, LIMIT - len(captured))])
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    # This is an outer diagnostic bound, not a change to any test timeout.
    # No kill/retry/schema cleanup: the disposable Actions service owns cleanup.
    timed_out = False
    try:
        code = process.wait(timeout=600)
    except subprocess.TimeoutExpired:
        timed_out = True
        code = 125
    reader.join(timeout=2)
    data = bytes(captured)
    # Raw pytest output stays in the temporary job directory, never the artifact.
    (private / 'pytest-output.bin').write_bytes(data)
    result = diagnostic_result(code, base, node=NODE, outer_deadline_reached=timed_out,
                  pytest_pid=process.pid, pytest_poll=process.poll(),
                  pytest_output_bytes=totals[0], pytest_sample_sha256=sha256(data).hexdigest(),
                  pytest_output_truncated=totals[0] > len(data),
                  full_suite=False, acceptance=False)
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
