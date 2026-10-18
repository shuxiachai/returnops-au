"""One disposable GitHub service, one fixed diagnostic node; no import side effects.

FR-008/009; NFR-003/006/009; docs/02 and member-a approval/execution models.
This instrumented observation cannot establish an uninstrumented T2 fix.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

NODE = 'tests/lifecycle/test_label_artifact_process_postgresql.py::test_LA_P07_P13_two_actual_installed_processes_one_claim_and_completion'
BRANCH = 'refs/heads/diag/81-a203-t2-cloud-20261018'
DATABASE = 'returnops_f02_a203_artifact_diag_v05_20261018'
VERSION = 170011
HEAD = '0013_label_artifact_result'
IMAGE = 'postgres:17-bookworm@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0'
MANIFEST = 'tools/a203_t2_cloud/inputs.json'


class Stop(RuntimeError):
    """Its fixed code is safe; arbitrary exception messages are never exported."""


def require(condition, code):
    if not condition:
        raise Stop(code)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=True) + '\n').encode('ascii')
    with Path(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def safe_file(path):
    path = Path(path)
    for item in (path, *path.parents):
        require(not item.is_symlink(), 'symlink')
        if os.name == 'nt' and item.exists():
            import stat
            require(not item.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT, 'reparse')
    require(path.is_file(), 'missing-file')
    return path


def cloud_context(env, platform=None):
    require((platform or sys.platform) == 'linux', 'linux-only')
    expected = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted',
                'GITHUB_EVENT_NAME': 'push', 'GITHUB_REPOSITORY': 'shuxiachai/returnops-au',
                'GITHUB_REF': BRANCH, 'GITHUB_RUN_ATTEMPT': '1'}
    require(all(env.get(k) == v for k, v in expected.items()), 'cloud-context')
    require(bool(re.fullmatch('[0-9]+', env.get('GITHUB_RUN_ID', ''))), 'run-id')
    require(bool(re.fullmatch('[a-f0-9]{40}', env.get('GITHUB_SHA', ''))), 'commit')
    require(bool(re.fullmatch('[a-f0-9]{64}', env.get('DIAGNOSTIC_SERVICE_ID', ''))), 'service-id')
    require(env.get('DIAGNOSTIC_SERVICE_IMAGE') == IMAGE, 'service-image')
    require(env.get('DIAGNOSTIC_SERVICE_PORT') == '55433', 'service-port')
    # Never inherit a local/user DSN. Workflow supplies only this job's disposable credential.
    require('DATABASE_URL' not in env and 'PGHOST' not in env and 'PGSERVICE' not in env, 'inherited-database')
    password = env.get('DIAGNOSTIC_PASSWORD', '')
    require(bool(re.fullmatch('[a-zA-Z0-9_]{16,80}', password)), 'service-credential')
    return {key: env[key] for key in (*expected, 'GITHUB_RUN_ID', 'GITHUB_SHA', 'DIAGNOSTIC_SERVICE_ID')}


def load_inputs(source):
    data = json.loads(safe_file(source / MANIFEST).read_bytes())
    require(data['format'] == 1 and data['node'] == NODE, 'input-format')
    require(len(data['source_to_installed']) == len(data['runtime137']) == 137, 'runtime-count')
    require(len(data['migrations13']) == 13 and len(data['intentional_absences']) == 106, 'baseline-count')
    require(set(data['runtime137']) == set(data['source_to_installed']), 'runtime-mapping')
    for relative, expected in data['files'].items():
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'input-path')
        require(sha(safe_file(source / relative)) == expected, 'source-hash')
    return data


def stage(checkout, home):
    data = load_inputs(checkout)
    home.mkdir(exist_ok=False)
    source = home / 'source'
    source.mkdir()
    # 106 intentionally absent historical docs remain only in Git, never materialized here.
    for relative in (*data['files'], MANIFEST):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe_file(checkout / relative), target)
    load_inputs(source)
    require(not any((source / relative).exists() or (source / relative).is_symlink()
                    for relative in data['intentional_absences']), 'staged-historical-path')
    return source, data


def command(args, cwd, env, private, label, timeout=300):
    # Raw streams are retained privately in the job, never printed or uploaded.
    with (private / (label + '.stdout')).open('xb') as out, (private / (label + '.stderr')).open('xb') as err:
        child = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
        try:
            return child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Do not kill/retry or issue SQL. Hosted-job teardown owns the disposable service.
            raise Stop('process-timeout-outcome-unknown') from None


def service_proof(home, env, private, execute=command):
    """Future hosted-run read-only Docker inspection; never full inspect/Env output."""
    identifier = env['DIAGNOSTIC_SERVICE_ID']
    template = '{"id":{{json .Id}},"image_id":{{json .Image}},"configured_image":{{json .Config.Image}},"running":{{json .State.Running}},"ports":{{json .NetworkSettings.Ports}}}'
    require(execute(['docker', 'inspect', '--format', template, identifier], home, env, private, 'service-inspect') == 0, 'service-inspect-exit')
    raw = safe_file(private / 'service-inspect.stdout').read_bytes()
    require(len(raw) <= 8192, 'service-inspect-bound')
    value = json.loads(raw)
    require(set(value) == {'id', 'image_id', 'configured_image', 'running', 'ports'}, 'service-inspect-fields')
    require(value['id'] == identifier and value['running'] is True and value['configured_image'] == IMAGE, 'service-inspect-identity')
    require(bool(re.fullmatch('sha256:[a-f0-9]{64}', value['image_id'])), 'service-image-id')
    require(set(value['ports']) == {'5432/tcp'}, 'service-ports')
    bindings = value['ports']['5432/tcp']
    require(type(bindings) is list and 1 <= len(bindings) <= 2, 'service-bindings')
    require(all(set(row) == {'HostIp', 'HostPort'} and row['HostPort'] == '55433'
                and row['HostIp'] in {'127.0.0.1', '0.0.0.0', '::'} for row in bindings), 'service-binding')
    template = '{"id":{{json .Id}},"digests":{{json .RepoDigests}}}'
    require(execute(['docker', 'image', 'inspect', '--format', template, value['image_id']], home, env, private, 'image-inspect') == 0, 'image-inspect-exit')
    raw = safe_file(private / 'image-inspect.stdout').read_bytes()
    require(len(raw) <= 8192, 'image-inspect-bound')
    actual = json.loads(raw)
    require(set(actual) == {'id', 'digests'} and actual['id'] == value['image_id'], 'image-inspect-identity')
    require(type(actual['digests']) is list and 'postgres@' + IMAGE.split('@')[1] in actual['digests'], 'image-digest')
    # Record only fixed/restricted fields; arbitrary image labels/digests never enter an artifact.
    return dict(container_id=identifier, image_id=value['image_id'], verified_digest=IMAGE.split('@')[1],
                running=True, published_port=55433, container_port=5432,
                assurance='HOSTED_JOB_SERVICE_MAPPING_NOT_HOSTILE_SAME_PRIVILEGE_ATTESTATION')


def package(source, home, data, env, private, execute=command):
    build = home / 'build-input'
    shutil.copytree(source, build)
    wheels = home / 'wheels'
    wheels.mkdir()
    installed = home / 'installed'
    clean = dict(env, PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1', PYTHONDONTWRITEBYTECODE='1')
    clean.pop('PYTHONPATH', None)
    require(execute([sys.executable, '-B', '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                     '--wheel-dir', str(wheels), str(build)], home, clean, private, 'wheel') == 0, 'wheel-exit')
    candidates = list(wheels.glob('returnops_au-0.1.0-py3-none-any.whl'))
    require(len(candidates) == 1 and len(list(wheels.iterdir())) == 1, 'wheel-count')
    wheel = candidates[0]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'duplicate-wheel-entry')
        runtime = {name for name in names if name.startswith(('returnops_api/', 'returnops_domain/'))}
        require(runtime == set(data['source_to_installed'].values()), 'wheel-runtime-set')
        require(len(names) == 141 and all(name in runtime or name.startswith('returnops_au-0.1.0.dist-info/') for name in names), 'wheel-file-set')
        for source_name, target in data['source_to_installed'].items():
            require(hashlib.sha256(archive.read(target)).hexdigest() == data['files'][source_name], 'wheel-source-pair')
    require(execute([sys.executable, '-B', '-m', 'pip', 'install', '--no-deps', '--no-compile',
                     '--target', str(installed), str(wheel)], home, clean, private, 'install') == 0, 'install-exit')
    proof = verify_installed(source, installed, data)
    with zipfile.ZipFile(wheel) as archive:
        for name in ('METADATA', 'WHEEL', 'top_level.txt'):
            relative = 'returnops_au-0.1.0.dist-info/' + name
            require(archive.read(relative) == (installed / relative).read_bytes(), 'installed-wheel-metadata')
    metadata = installed / 'returnops_au-0.1.0.dist-info'
    require((metadata / 'INSTALLER').read_bytes() == b'pip\n' and (metadata / 'REQUESTED').read_bytes() == b'', 'installer-metadata')
    origin = json.loads((metadata / 'direct_url.json').read_bytes())
    require(origin.get('url') == wheel.as_uri() and origin.get('archive_info', {}).get('hashes') == {'sha256': sha(wheel)}, 'installed-wheel-origin')
    load_inputs(source)
    return dict(wheel_sha256=sha(wheel), source_manifest_sha256=sha(source / MANIFEST),
                metadata_note='Three immutable wheel metadata files matched; pip rewrites RECORD and creates INSTALLER/REQUESTED/direct_url.', **proof)


def verify_installed(source, installed, data):
    actual = {p.relative_to(installed).as_posix(): sha(safe_file(p)) for p in installed.rglob('*') if p.is_file()}
    runtime = set(data['source_to_installed'].values())
    meta = {'returnops_au-0.1.0.dist-info/' + name for name in
            ('METADATA', 'WHEEL', 'top_level.txt', 'RECORD', 'INSTALLER', 'REQUESTED', 'direct_url.json')}
    require(set(actual) == runtime | meta and len(actual) == 144, 'installed-set')
    for original, target in data['source_to_installed'].items():
        require(actual[target] == data['files'][original] == sha(source / original), 'installed-source-pair')
    return dict(installed_files=actual, runtime_pairs=137, installed_count=144)


def check_identity(row, expected_oid=None, *, fresh=False):
    require(row['database'] == DATABASE and row['user'] == 'returnops_ci', 'database-identity')
    require(type(row['oid']) is int and row['oid'] > 0, 'database-oid')
    require(row['version'] == VERSION and row['server_port'] == 5432, 'database-version-port')
    if expected_oid is not None:
        require(row['oid'] == expected_oid, 'database-oid-drift')
    if fresh:
        require(row['tables'] == 0 and row['user_schemas'] == ['public'], 'database-not-fresh')


def bootstrap(source, raw_url):
    # This function is called only after cloud + source + build gates. Imports do not connect.
    from sqlalchemy import create_engine, text
    from alembic.config import Config
    from alembic import command as alembic
    engine = create_engine(raw_url, echo=False, hide_parameters=True,
                           connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=10000'})
    connection = engine.connect()
    row = dict(connection.execute(text("SELECT current_database() AS database, current_user AS \"user\", oid::integer AS oid, current_setting('server_version_num')::integer AS version, inet_server_port() AS server_port FROM pg_database WHERE datname=current_database()")).mappings().one())
    row['tables'] = connection.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar_one()
    row['user_schemas'] = list(connection.execute(text("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema' ORDER BY nspname")).scalars())
    check_identity(row, fresh=True)
    connection.commit()
    config = Config(str(source / 'alembic.ini'))
    config.set_main_option('script_location', str(source / 'alembic'))
    config.attributes['connection'] = connection
    alembic.upgrade(config, 'head')
    connection.commit()
    require(list(connection.execute(text('SELECT version_num FROM alembic_version')).scalars()) == [HEAD], 'migration-head')
    tables = connection.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")).scalar_one()
    require(tables == 61, 'migration-tables')
    final = dict(connection.execute(text("SELECT current_database() AS database, current_user AS \"user\", oid::integer AS oid, current_setting('server_version_num')::integer AS version, inet_server_port() AS server_port FROM pg_database WHERE datname=current_database()")).mappings().one())
    check_identity(final, row['oid'])
    connection.commit()
    connection.close()
    engine.dispose()
    return dict(**final, migration_head=HEAD, tables=tables, initial_tables=row['tables'])


def case_environment(source, home, oid, raw_url):
    require(type(oid) is int and oid > 0, 'case-oid')
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'LANG', 'LC_ALL', 'SYSTEMROOT'}}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=str(home / 'installed'), MANUAL_INSTALLED_DIR=str(home / 'installed'),
               ARTIFACT_DATABASE_NAME=DATABASE, ARTIFACT_DATABASE_OID=str(oid), DATABASE_URL=raw_url)
    return env


def fixed_command(source, action, phase):
    require(phase in {'COLLECTION', 'EXECUTION'}, 'case-phase')
    args = [sys.executable, '-B', str(source / 'tools/a203_t2_cloud/pytest_entry.py'),
            str(source), str(action), phase, NODE]
    return args


def accept_outcome(path, exit_code, phase):
    value = json.loads(safe_file(path).read_bytes())
    require(value['node'] == NODE and value['phase'] == phase and value['collected'] == [NODE], 'collection-exact')
    require(exit_code == value['exit_code'] == 0, 'pytest-exit')
    require(value['collection_errors'] == 0, 'collection-error')
    expected = [] if phase == 'COLLECTION' else [['setup', 'passed'], ['call', 'passed'], ['teardown', 'passed']]
    require(value['reports'] == expected, 'typed-outcome')
    return value


def run_case(source, home, identity, raw_url, private, execute=command):
    env = case_environment(source, home, identity['oid'], raw_url)
    results = {}
    for phase, label in (('COLLECTION', 'collect-diagnostic'), ('EXECUTION', 'test-diagnostic')):
        data = load_inputs(source)
        verify_installed(source, home / 'installed', data)
        action = home / 'runtime/artifacts' / label
        action.mkdir(parents=True, exist_ok=False)  # attempt cannot be reused
        (action / 'diagnostic-logs').mkdir()
        (action / 'evidence').mkdir()
        once = action / 'attempt-started.json'
        write_new(once, dict(node=NODE, phase=phase))
        current = dict(env, ARTIFACT_DIAGNOSTIC_PHASE=phase,
                       ARTIFACT_DIAGNOSTIC_ROOT=str(action / 'diagnostic-logs'),
                       MANUAL_EVIDENCE_DIR=str(action / 'evidence'))
        code = execute(fixed_command(source, action, phase), action, current, private, label)
        write_new(action / 'process-exit.json', dict(actual_exit=code))
        results[phase] = accept_outcome(action / 'outcome.json', code, phase)
    from export_safe import enums, validated_log
    allowed = enums(source)
    action = home / 'runtime/artifacts/test-diagnostic'
    parent = validated_log(action / 'diagnostic-logs/parent-diagnostic.jsonl', allowed)
    require(parent[-1]['phase'] == 'logger.close' and parent[-1]['event'] == 'return', 'parent-close')
    for marker in ('parent.complete', 'fixture.complete'):
        require(any(row['phase'] == marker and row['event'] == 'return' for row in parent), 'parent-success-marker')
    for name in ('artifact-diagnostic-0.jsonl', 'artifact-diagnostic-1.jsonl', 'artifact-diagnostic-restart.jsonl'):
        paths = list(action.rglob(name))
        require(len(paths) == 1, 'child-log-count')
        rows = validated_log(paths[0], allowed)
        require(rows[-1]['phase'] == 'logger.close' and rows[-1]['event'] == 'return', 'child-close')
        require(any(row['phase'] == 'probe.complete' and row['event'] == 'return' for row in rows), 'child-success-marker')
    return results


def safe_exception(error):
    allowed = {'AssertionError', 'ValueError', 'TypeError', 'KeyError', 'OSError', 'PermissionError',
               'FileExistsError', 'RuntimeError', 'OperationalError', 'ProgrammingError', 'IntegrityError',
               'DBAPIError', 'SQLAlchemyError', 'TimeoutExpired', 'KeyboardInterrupt', 'Stop'}
    name = type(error).__name__
    state = getattr(getattr(error, 'orig', error), 'sqlstate', None)
    return dict(exception_type=name if name in allowed else 'OTHER',
                sqlstate=state if type(state) is str and re.fullmatch('[A-Z0-9]{5}', state) else None)


def main():
    # All prerequisites before opening a database. No CLI-controlled node/URL or local mode.
    cloud_context(os.environ)
    require(len(sys.argv) == 1, 'arguments-forbidden')
    checkout = Path(__file__).resolve().parents[2]
    home = checkout.parent / 'diagnostic'
    source, data = stage(checkout, home)
    private = home / 'private'
    private.mkdir()
    safe = home / 'safe-artifacts'
    safe.mkdir()
    write_new(safe / 'provenance.json', cloud_context(os.environ))
    stage_name = 'service-container'
    try:
        write_new(safe / 'container-proof.json', service_proof(home, os.environ.copy(), private))
        stage_name = 'build'
        proof = package(source, home, data, os.environ.copy(), private)
        write_new(safe / 'package-proof.json', proof)
        # source imports needed by Alembic, after exact wheel/install provenance is established.
        sys.path.insert(0, str(home / 'installed'))
        stage_name = 'service-bootstrap'
        raw = 'postgresql+psycopg://returnops_ci:' + os.environ['DIAGNOSTIC_PASSWORD'] + '@127.0.0.1:55433/' + DATABASE
        os.environ['DATABASE_URL'] = raw  # Alembic verifies the same in-memory URL.
        identity = bootstrap(source, raw)
        write_new(safe / 'service-proof.json', identity)
        stage_name = 'singleton'
        result = run_case(source, home, identity, raw, private)
        load_inputs(source)
        verify_installed(source, home / 'installed', data)
        write_new(safe / 'result.json', dict(status='INSTRUMENTED_SINGLETON_PASS', outcomes=result,
                  database_retained=False, uninstrumented_fix_proven=False))
        return 0
    except BaseException as error:
        write_new(safe / 'stop.json', dict(status='STOP_UNKNOWN_OR_FAILED', stage=stage_name,
                  **safe_exception(error), database_retained=False, retry_permitted=False))
        return 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # Never print a traceback, URL, SQL, parameters or a secret-bearing exception.
        print('A203_T2_CLOUD_PRECONDITION_STOP', file=sys.stderr)
        raise SystemExit(1) from None
