"""Formal original tests on one fresh hosted PostgreSQL service; inert at import.

FR-009/010; NFR-002/003/004/006/009; governed execution / exact-scope UML.
Only the new primary234 and separately released Storage74 are claimed.
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

BRANCHES = {'primary': 'refs/heads/test/81-a203-formal-20261018',
            'storage': 'refs/heads/test/81-a203-storage-20261018'}
DATABASES = {'primary': 'returnops_f02_a203_artifact_v04_20261018',
             'storage': 'returnops_f02_a203_artifact_storage_v04_20261018'}
VERSION = 170011
HEAD = '0013_label_artifact_result'
IMAGE = 'postgres:17-bookworm@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0'
MANIFEST = 'tools/a203_formal_cloud/inputs.json'
CORE_FREEZE = 'f772bf58edbd37b21c3c1d497334b140e30e8810c9d4dc157caf0183d0db123f'
RELEASE = 'tools/a203_formal_cloud/storage-release.json'
REPORT_RUNTIME = {'pytest_version': '9.1.1',
 'classes': {'parent': '_pytest.reports.TestReport', 'subtest': '_pytest.subtests.SubtestReport'},
 'source_files': {
  '_pytest/reports.py': '2e9272a67cde38b925eba24a288b2ef77f741c0daa22da6fbce53ee6e58fa41d',
  '_pytest/subtests.py': 'f514883bad06a84cec0d7ddc1dd8ce8c16e5680597f9fc5a9bd8836b878f92a4',
  '_pytest/unittest.py': '24657b6c497eacbf50a978713598b3baed4c05c29f1c01891563cfefed119224'}}

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


def exact(value, keys, code):
    require(type(value) is dict and set(value) == set(keys), code)


def cloud_context(env, platform=None):
    require((platform or sys.platform) == 'linux', 'linux-only')
    phases = [key for key, value in BRANCHES.items() if env.get('GITHUB_REF') == value]
    require(len(phases) == 1, 'branch')
    phase = phases[0]
    expected = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted',
                'GITHUB_EVENT_NAME': 'push', 'GITHUB_REPOSITORY': 'shuxiachai/returnops-au',
                'GITHUB_REF': BRANCHES[phase], 'GITHUB_RUN_ATTEMPT': '1'}
    require(all(env.get(k) == v for k, v in expected.items()), 'cloud-context')
    require(bool(re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ID', ''))), 'run-id')
    require(bool(re.fullmatch('[a-f0-9]{40}', env.get('GITHUB_SHA', ''))), 'commit')
    require(bool(re.fullmatch('[a-f0-9]{64}', env.get('FORMAL_SERVICE_ID', ''))), 'service-id')
    require(env.get('FORMAL_SERVICE_IMAGE') == IMAGE, 'service-image')
    require(env.get('FORMAL_SERVICE_PORT') == '55433', 'service-port')
    require(not any(k in env for k in ('DATABASE_URL', 'PGHOST', 'PGSERVICE', 'PGPASSFILE')), 'inherited-database')
    require(bool(re.fullmatch('[a-zA-Z0-9_]{16,80}', env.get('FORMAL_PASSWORD', ''))), 'service-credential')
    return dict(phase=phase, **{key: env[key] for key in (*expected, 'GITHUB_RUN_ID', 'GITHUB_SHA', 'FORMAL_SERVICE_ID')})


def load_inputs(source):
    data = json.loads(safe_file(source / MANIFEST).read_bytes())
    exact(data, ('format', 'core_freeze_sha256', 'core444', 'files', 'runtime137',
                 'source_to_installed', 'migrations13', 'intentional_absences',
                 'origin_primary_selection_sha256', 'offline_collection_map_sha256'), 'input-fields')
    require(data['format'] == 1 and data['core_freeze_sha256'] == CORE_FREEZE, 'input-format')
    require(data['origin_primary_selection_sha256'] == '96664f9d8cef01813e0097f8dea4b4e9348a09db1da777f3a35e5913e2347d6f'
            and data['offline_collection_map_sha256'] == '9edecf669ec186b83e1b082a76184ecb50747c74bd2cb96725a47cd0ea02f5d3', 'selection-origin')
    require(len(data['core444']) == 444 and len(data['runtime137']) == len(data['source_to_installed']) == 137,
            'source-count')
    require(len(data['migrations13']) == 13 and len(data['intentional_absences']) == 106, 'baseline-count')
    require(set(data['runtime137']) == set(data['source_to_installed']), 'runtime-mapping')
    require(MANIFEST not in data['files'], 'manifest-self-reference')
    require(len(data['files']) == (452 if RELEASE in data['files'] else 451), 'file-count')
    for relative, expected in data['files'].items():
        require(type(relative) is str and not Path(relative).is_absolute() and '\\' not in relative
                and '..' not in Path(relative).parts, 'input-path')
        require(type(expected) is str and re.fullmatch('[a-f0-9]{64}', expected), 'input-hash')
        require(sha(safe_file(source / relative)) == expected, 'source-hash')
    for mapping in ('core444', 'runtime137', 'migrations13'):
        require(all(data['files'].get(k) == v for k, v in data[mapping].items()), 'source-map-pair')
    require(not set(data['intentional_absences']) & set(data['files']), 'absence-overlap')
    return data


def source_inventory(source, data):
    require(not any(p.is_symlink() for p in source.rglob('*')), 'source-symlink')
    actual = {p.relative_to(source).as_posix(): sha(safe_file(p))
              for p in source.rglob('*') if p.is_file() and '.git' not in p.relative_to(source).parts}
    require(actual == dict(data['files'], **{MANIFEST: sha(source / MANIFEST)}), 'source-inventory')
    require(not any((source / name).exists() or (source / name).is_symlink()
                    for name in data['intentional_absences']), 'staged-historical-path')
    return actual


def stage(checkout, home):
    data = load_inputs(checkout)
    home.mkdir(exist_ok=False)
    source = home / 'source'
    source.mkdir()
    # Checkout may contain the 106 retained historical Git objects and .git.
    for relative in (*data['files'], MANIFEST):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe_file(checkout / relative), target)
    load_inputs(source)
    source_inventory(source, data)
    return source, data


def selections(source, phase):
    require(phase in BRANCHES, 'phase')
    path = source / ('tools/a203_formal_cloud/' + phase + '-selection.json')
    value = json.loads(safe_file(path).read_bytes())
    exact(value, ('format', 'core_freeze_sha256', 'origin_selection_sha256',
                  'expected_public_tables', 'suites'), 'selection-fields')
    require(value['format'] == 1 and value['core_freeze_sha256'] == CORE_FREEZE, 'selection-core')
    names = ['artifact', 'lifecycle'] if phase == 'primary' else ['storage']
    require(list(value['suites']) == names, 'suite-order')
    require(len(value['expected_public_tables']) == 61
            and value['expected_public_tables'] == sorted(set(value['expected_public_tables']))
            and all(re.fullmatch('[a-z_]+', n) for n in value['expected_public_tables']), 'table-selection')
    for name, suite in value['suites'].items():
        exact(suite, ('selectors', 'expected_nodes', 'expected_count', 'max_seconds'), 'suite-fields')
        count = {'artifact': 1, 'lifecycle': 233, 'storage': 74}[name]
        require(suite['expected_count'] == count and len(suite['expected_nodes']) == count
                and len(set(suite['expected_nodes'])) == count, 'node-count')
        require(suite['max_seconds'] == (3600 if name == 'storage' else 14400), 'outer-budget')
        require(type(suite['selectors']) is list and all(type(s) is str and s.startswith('tests/')
                and '\\' not in s and '..' not in s.split('::')[0].split('/') for s in suite['selectors']), 'selectors')
        if name == 'storage':
            require(suite['selectors'] == ['tests/storage/test_postgresql.py', 'tests/storage/test_records.py'], 'storage-selectors')
        else:
            require(suite['selectors'] == suite['expected_nodes'], 'primary-selectors')
        selected_files = {s.split('::')[0] for s in suite['selectors']}
        require(all(type(n) is str and '::' in n and n.split('::')[0] in selected_files for n in suite['expected_nodes']), 'node-files')
    return value


def command(args, cwd, env, private, label, timeout=300):
    # Each owned process and its normal descendants share an isolated Linux group.
    with (private / (label + '.stdout')).open('xb') as out, (private / (label + '.stderr')).open('xb') as err:
        child = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err, start_new_session=True)
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Stop('process-timeout-outcome-unknown') from None
    empty = None
    if code == 0:
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            empty = True
        else:
            empty = False
    write_new(private / (label + '.process.json'), dict(actual_exit=code, owned_process_group_empty=empty))
    if code == 0:
        require(empty is True, 'owned-process-group-not-empty')
    return code




def service_proof(home, env, private, execute=command):
    """Future hosted-run read-only Docker inspection; never full inspect/Env output."""
    identifier = env['FORMAL_SERVICE_ID']
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


def safe_exception(error):
    allowed = {'AssertionError', 'ValueError', 'TypeError', 'KeyError', 'OSError', 'PermissionError',
               'FileExistsError', 'RuntimeError', 'OperationalError', 'ProgrammingError', 'IntegrityError',
               'DBAPIError', 'SQLAlchemyError', 'TimeoutExpired', 'KeyboardInterrupt', 'Stop'}
    name = type(error).__name__
    state = getattr(getattr(error, 'orig', error), 'sqlstate', None)
    return dict(exception_type=name if name in allowed else 'OTHER',
                sqlstate=state if type(state) is str and re.fullmatch('[A-Z0-9]{5}', state) else None)


def github_json(kind, identity):
    # Exactly two fixed public endpoints are used by the Storage gate. No retry/redirect/token.
    require(kind in {'runs', 'artifacts'} and type(identity) is int and identity > 0, 'github-target')
    from urllib.request import Request, build_opener, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, message, headers, newurl):
            raise Stop('github-redirect')
    url = f'https://api.github.com/repos/shuxiachai/returnops-au/actions/{kind}/{identity}'
    request = Request(url, headers={'Accept': 'application/vnd.github+json',
                                   'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'a203-formal-validation'})
    with build_opener(NoRedirect).open(request, timeout=15) as response:
        require(response.status == 200 and response.geturl() == url, 'github-response')
        raw = response.read(2_000_001)
    require(len(raw) <= 2_000_000, 'github-size')
    value = json.loads(raw)
    require(type(value) is dict, 'github-shape')
    return value


def storage_release(source, data, fetch=github_json):
    require(RELEASE in data['files'], 'storage-not-released')
    value = json.loads(safe_file(source / RELEASE).read_bytes())
    exact(value, ('format', 'status', 'repository', 'primary_branch', 'primary_head', 'primary_run_id',
                  'primary_run_attempt', 'artifact_id', 'artifact_name', 'artifact_digest',
                  'core_freeze_sha256', 'primary_selection_sha256', 'primary_inputs_sha256',
                  'final_seal_sha256', 'review'), 'release-fields')
    require(value['format'] == 1 and value['status'] == 'PRIMARY_234_INDEPENDENT_PASS'
            and value['repository'] == 'shuxiachai/returnops-au'
            and value['primary_branch'] == BRANCHES['primary'].removeprefix('refs/heads/')
            and type(value['primary_run_attempt']) is int and value['primary_run_attempt'] == 1, 'release-scope')
    require(type(value['primary_head']) is str and re.fullmatch('[a-f0-9]{40}', value['primary_head']), 'release-head')
    require(all(type(value[k]) is int and value[k] > 0 for k in ('primary_run_id', 'artifact_id')), 'release-ids')
    require(value['artifact_name'] == f"a203-formal-primary-{value['primary_run_id']}-1", 'release-artifact-name')
    require(type(value['artifact_digest']) is str and re.fullmatch('sha256:[a-f0-9]{64}', value['artifact_digest']), 'release-digest')
    require(value['core_freeze_sha256'] == CORE_FREEZE
            and value['primary_selection_sha256'] == sha(source / 'tools/a203_formal_cloud/primary-selection.json'), 'release-source')
    require(all(type(value[k]) is str and re.fullmatch('[a-f0-9]{64}', value[k])
                for k in ('primary_inputs_sha256', 'final_seal_sha256')), 'release-pins')
    review = value['review']
    exact(review, ('status', 'reviewer', 'authors', 'review_record_sha256'), 'release-review-fields')
    require(review['status'] == 'PASS' and type(review['reviewer']) is str
            and re.fullmatch('[A-Za-z0-9_/-]{1,100}', review['reviewer'])
            and type(review['authors']) is list and review['authors']
            and all(type(a) is str and re.fullmatch('[A-Za-z0-9_/-]{1,100}', a) for a in review['authors'])
            and review['reviewer'] not in review['authors']
            and type(review['review_record_sha256']) is str
            and re.fullmatch('[a-f0-9]{64}', review['review_record_sha256']), 'release-independent-review')
    run = fetch('runs', value['primary_run_id'])
    require(run.get('id') == value['primary_run_id'] and run.get('run_attempt') == 1
            and run.get('event') == 'push' and run.get('status') == 'completed' and run.get('conclusion') == 'success'
            and run.get('head_sha') == value['primary_head'] and run.get('head_branch') == value['primary_branch']
            and run.get('path') == '.github/workflows/a203-formal-validation.yml'
            and run.get('repository', {}).get('full_name') == value['repository'], 'release-run')
    artifact = fetch('artifacts', value['artifact_id'])
    require(artifact.get('id') == value['artifact_id'] and artifact.get('name') == value['artifact_name']
            and artifact.get('expired') is False and artifact.get('digest') == value['artifact_digest']
            and artifact.get('workflow_run', {}).get('id') == value['primary_run_id']
            and artifact.get('workflow_run', {}).get('head_sha') == value['primary_head']
            and artifact.get('workflow_run', {}).get('head_branch') == value['primary_branch'], 'release-artifact')
    return dict(status='PRIMARY_RELEASE_VERIFIED', release_sha256=sha(source / RELEASE),
                primary_head=value['primary_head'], primary_run_id=value['primary_run_id'],
                artifact_id=value['artifact_id'], artifact_digest=value['artifact_digest'],
                final_seal_sha256=value['final_seal_sha256'],
                assurance='ROOT_ATTESTED_INTERNAL_REVIEW_NOT_HOSTILE_SAME_PRIVILEGE_ATTESTATION')


def check_identity(row, database, expected_oid=None, *, fresh=False):
    require(row['database'] == database and row['user'] == 'returnops_ci', 'database-identity')
    require(type(row['oid']) is int and row['oid'] > 0, 'database-oid')
    require(row['version'] == VERSION and row['server_port'] == 5432, 'database-version-port')
    if expected_oid is not None:
        require(row['oid'] == expected_oid, 'database-oid-drift')
    if fresh:
        require(row['tables'] == 0 and row['user_schemas'] == ['public'], 'database-not-fresh')


def identity(connection):
    from sqlalchemy import text
    return dict(connection.execute(text('SELECT current_database() AS database, current_user AS "user", '
        "oid::integer AS oid, current_setting('server_version_num')::integer AS version, "
        'inet_server_port() AS server_port FROM pg_database WHERE datname=current_database()')).mappings().one())


def bootstrap(source, raw_url, database, expected_tables):
    from sqlalchemy import create_engine, text, inspect
    from alembic.config import Config
    from alembic import command as alembic
    engine = create_engine(raw_url, echo=False, hide_parameters=True,
                           connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=10000'})
    connection = engine.connect()
    row = identity(connection)
    row['tables'] = connection.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar_one()
    row['user_schemas'] = list(connection.execute(text("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema' ORDER BY nspname")).scalars())
    check_identity(row, database, fresh=True)
    connection.commit()
    config = Config(str(source / 'alembic.ini'))
    config.set_main_option('script_location', str(source / 'alembic'))
    config.attributes['connection'] = connection
    alembic.upgrade(config, 'head')
    connection.commit()
    require(list(connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars()) == [HEAD], 'migration-head')
    require(sorted(inspect(connection).get_table_names(schema='public')) == expected_tables, 'migration-table-set')
    final = identity(connection)
    check_identity(final, database, row['oid'])
    connection.commit()
    connection.close()
    engine.dispose()
    return dict(**final, migration_head=HEAD, tables=len(expected_tables), initial_tables=0)


def success_audit(raw_url, database, oid, expected_tables, *, storage=False):
    # Called only after exact pytest PASS and empty owned process group. No failure diagnostics/cleanup SQL.
    from sqlalchemy import create_engine, text, inspect, pool
    from returnops_domain.fence import acquire_fence
    from returnops_domain import lifecycle_schema
    engine = create_engine(raw_url, echo=False, hide_parameters=True, poolclass=pool.NullPool,
        connect_args={'connect_timeout': 3, 'options': '-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=10000'})
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        require(connection.execute(text('SHOW transaction_read_only')).scalar_one() == 'on', 'audit-readonly')
        acquire_fence(connection, write=False)
        current = identity(connection)
        check_identity(current, database, oid)
        require(connection.execute(text('SELECT current_schema()')).scalar_one() == 'public', 'audit-schema')
        require(list(connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars()) == [HEAD]
                and lifecycle_schema.version(connection) == HEAD, 'audit-head')
        tables = sorted(inspect(connection).get_table_names(schema='public'))
        require(tables == expected_tables, 'audit-tables')
        counts = {name: connection.execute(text('SELECT count(*) FROM public."' + name + '"')).scalar_one() for name in tables}
        schemas = list(connection.execute(text("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema' ORDER BY nspname")).scalars())
        require(schemas == ['public'], 'audit-extra-schema')
        peers = connection.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datid=:oid AND pid<>pg_backend_pid() AND backend_type='client backend'"), {'oid': oid}).scalar_one()
        require(peers == 0, 'audit-other-client')
        snapshot = dict(database=database, database_oid=oid, server_version=VERSION, revision=HEAD,
            table_counts=counts, business_rows=sum(n for k, n in counts.items() if k != 'alembic_version'),
            customer_test_schemas=[], read_only_shared_fence=True, other_client_sessions=0)
        if storage:
            from storage_audit import audit
            oracle = audit(connection, snapshot)
            snapshot['storage_oracle_sha256'] = hashlib.sha256(json.dumps(oracle, sort_keys=True, ensure_ascii=True).encode('ascii')).hexdigest()
            snapshot['storage_oracle_status'] = oracle['status']
            snapshot['attribution'] = 'PAYLOAD_MULTISET_ONLY_NO_INDIVIDUAL_NODE_TO_UUID_ATTRIBUTION'
        else:
            require(counts['alembic_version'] == 1 and snapshot['business_rows'] == 0, 'audit-business-rows')
    engine.dispose()
    return snapshot


def case_environment(home, oid, database, raw_url):
    require(type(oid) is int and oid > 0 and database in DATABASES.values(), 'case-identity')
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'LANG', 'LC_ALL', 'SYSTEMROOT'}}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=os.pathsep.join([str(home / 'source/packages'), str(home / 'source/apps/api')]),
               MANUAL_INSTALLED_DIR=str(home / 'installed'), DATABASE_URL=raw_url)
    for prefix in ('ARTIFACT', 'LABEL', 'BRIDGE'):
        env[prefix + '_DATABASE_NAME'] = database
        env[prefix + '_DATABASE_OID'] = str(oid)
    return env


def run_suite(source, home, proof, raw_url, phase, name, suite, private, execute=command):
    from pytest_entry import validate_outcome
    outcomes = {}
    for kind, prefix in (('COLLECTION', 'collect'), ('EXECUTION', 'test')):
        data = load_inputs(source)
        source_inventory(source, data)
        verify_installed(source, home / 'installed', data)
        label = prefix + '-' + name
        action = home / 'runtime/artifacts' / label
        action.mkdir(parents=True, exist_ok=False)
        (action / 'evidence').mkdir()
        write_new(action / 'attempt-started.json', dict(phase=phase, suite=name, kind=kind))
        env = case_environment(home, proof['oid'], proof['database'], raw_url)
        env['MANUAL_EVIDENCE_DIR'] = str(action / 'evidence')
        args = [sys.executable, '-B', str(source / 'tools/a203_formal_cloud/pytest_entry.py'),
                str(source), str(action), phase, name, kind]
        code = execute(args, action, env, private, label, timeout=suite['max_seconds'])
        write_new(action / 'process-exit.json', dict(actual_exit=code))
        outcomes[kind] = validate_outcome(json.loads(safe_file(action / 'outcome.json').read_bytes()), suite, kind)
        require(outcomes[kind]['phase'] == phase and outcomes[kind]['suite'] == name, 'outcome-phase-suite')
        require(all(r['source_file'] is None or r['source_file'] in data['files'] for r in outcomes[kind]['reports']), 'outcome-source-file')
        require(type(code) is int and code == outcomes[kind]['exit_code'] == 0, 'pytest-exit')
    return outcomes


def main():
    context = cloud_context(os.environ)
    require(len(sys.argv) == 1, 'arguments-forbidden')
    phase = context['phase']
    checkout = Path(__file__).resolve().parents[2]
    home = checkout.parent / 'formal'
    source, data = stage(checkout, home)
    private = home / 'private'
    private.mkdir()
    safe = home / 'safe-artifacts'
    safe.mkdir()
    write_new(safe / 'provenance.json', dict(**context, inputs_sha256=sha(source / MANIFEST), core_freeze_sha256=CORE_FREEZE))
    stage_name = 'release'
    try:
        selection = selections(source, phase)
        if phase == 'storage':
            write_new(safe / 'primary-release-proof.json', storage_release(source, data))
        else:
            require(RELEASE not in data['files'], 'primary-release-unexpected')
        stage_name = 'service-container'
        write_new(safe / 'container-proof.json', service_proof(home, os.environ.copy(), private))
        stage_name = 'build'
        write_new(safe / 'package-proof.json', package(source, home, data, os.environ.copy(), private))
        write_new(safe / 'source-before.json', source_inventory(source, data))
        sys.path.insert(0, str(home / 'installed'))
        stage_name = 'service-bootstrap'
        database = DATABASES[phase]
        raw = 'postgresql+psycopg://returnops_ci:' + os.environ['FORMAL_PASSWORD'] + '@127.0.0.1:55433/' + database
        os.environ['DATABASE_URL'] = raw
        proof = bootstrap(source, raw, database, selection['expected_public_tables'])
        write_new(safe / 'service-proof.json', proof)
        outcomes = {}
        last = None
        for name, suite in selection['suites'].items():
            stage_name = name
            outcomes[name] = run_suite(source, home, proof, raw, phase, name, suite, private)
            last = success_audit(raw, database, proof['oid'], selection['expected_public_tables'], storage=phase == 'storage')
            write_new(safe / (name + '-seal.json'), last)
        stage_name = 'final-seal'
        write_new(safe / 'source-after.json', source_inventory(source, load_inputs(source)))
        write_new(safe / 'installed-after.json', verify_installed(source, home / 'installed', data))
        final = success_audit(raw, database, proof['oid'], selection['expected_public_tables'], storage=phase == 'storage')
        require(final == last, 'final-seal-drift')
        write_new(safe / 'final-seal.json', final)
        write_new(safe / 'result.json', dict(status='FORMAL_PRIMARY_234_PASS' if phase == 'primary' else 'FORMAL_STORAGE_74_PASS',
            phase=phase, suites={k: len(v['EXECUTION']['collected']) for k, v in outcomes.items()},
            source_manifest_sha256=sha(source / MANIFEST), core_freeze_sha256=CORE_FREEZE,
            selection_sha256=sha(source / ('tools/a203_formal_cloud/' + phase + '-selection.json')),
            final_seal_sha256=sha(safe / 'final-seal.json'), database_retained=False,
            old_2906_transferred=False, full_3140_acceptance_claimed=False))
        return 0
    except BaseException as error:
        write_new(safe / 'stop.json', dict(status='STOP_UNKNOWN_OR_FAILED', stage=stage_name,
            **safe_exception(error), database_retained=False, retry_permitted=False))
        return 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('A203_FORMAL_CLOUD_PRECONDITION_STOP', file=sys.stderr)
        raise SystemExit(1) from None
