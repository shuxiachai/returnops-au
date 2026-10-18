"""File-only strict projections after success, failure or cancellation. Never SQL."""
import json
from pathlib import Path
import re
import sys

from runner import (BRANCHES, CORE_FREEZE, DATABASES, HEAD, IMAGE, MANIFEST, VERSION,
                    exact, load_inputs, require, safe_file, selections, sha, write_new)
from pytest_entry import safe_outcome


def digest(value):
    require(type(value) is str and re.fullmatch('[a-f0-9]{64}', value), 'export-digest')
    return value


def file_map(value, names):
    exact(value, names, 'export-file-map')
    return {name: digest(value[name]) for name in names}


def installed(value, data):
    exact(value, ('installed_files', 'runtime_pairs', 'installed_count'), 'export-installed-fields')
    require(value['runtime_pairs'] == 137 and value['installed_count'] == 144, 'export-installed-count')
    names = list(data['source_to_installed'].values()) + ['returnops_au-0.1.0.dist-info/' + n for n in
        ('METADATA', 'WHEEL', 'top_level.txt', 'RECORD', 'INSTALLER', 'REQUESTED', 'direct_url.json')]
    return dict(installed_files=file_map(value['installed_files'], names), runtime_pairs=137, installed_count=144)


def record(name, value, data, phase, tables):
    if name in {'source-before.json', 'source-after.json'}:
        return file_map(value, (*data['files'], MANIFEST))
    if name == 'installed-after.json':
        return installed(value, data)
    if name == 'package-proof.json':
        exact(value, ('wheel_sha256', 'source_manifest_sha256', 'metadata_note', 'installed_files',
                     'runtime_pairs', 'installed_count'), 'export-package-fields')
        projection = installed({k: value[k] for k in ('installed_files', 'runtime_pairs', 'installed_count')}, data)
        return dict(**projection, wheel_sha256=digest(value['wheel_sha256']),
            source_manifest_sha256=digest(value['source_manifest_sha256']), metadata_note='WHEEL_AND_SOURCE_BYTE_PAIRS_VERIFIED')
    if name == 'provenance.json':
        keys = ('phase', 'GITHUB_ACTIONS', 'RUNNER_ENVIRONMENT', 'GITHUB_EVENT_NAME', 'GITHUB_REPOSITORY',
                'GITHUB_REF', 'GITHUB_RUN_ATTEMPT', 'GITHUB_RUN_ID', 'GITHUB_SHA', 'FORMAL_SERVICE_ID',
                'inputs_sha256', 'core_freeze_sha256')
        exact(value, keys, 'export-provenance-fields')
        fixed = dict(phase=phase, GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
            GITHUB_EVENT_NAME='push', GITHUB_REPOSITORY='shuxiachai/returnops-au', GITHUB_REF=BRANCHES[phase],
            GITHUB_RUN_ATTEMPT='1', core_freeze_sha256=CORE_FREEZE)
        require(all(value[k] == v for k, v in fixed.items()), 'export-provenance')
        require(type(value['GITHUB_RUN_ID']) is str and re.fullmatch('[1-9][0-9]*', value['GITHUB_RUN_ID'])
                and type(value['GITHUB_SHA']) is str and re.fullmatch('[a-f0-9]{40}', value['GITHUB_SHA']), 'export-run')
        return dict(**fixed, GITHUB_RUN_ID=value['GITHUB_RUN_ID'], GITHUB_SHA=value['GITHUB_SHA'],
            FORMAL_SERVICE_ID=digest(value['FORMAL_SERVICE_ID']), inputs_sha256=digest(value['inputs_sha256']))
    if name == 'container-proof.json':
        exact(value, ('container_id', 'image_id', 'verified_digest', 'running', 'published_port', 'container_port', 'assurance'), 'export-container-fields')
        require(type(value['image_id']) is str and re.fullmatch('sha256:[a-f0-9]{64}', value['image_id'])
                and value['verified_digest'] == IMAGE.split('@')[1] and value['running'] is True
                and value['published_port'] == 55433 and value['container_port'] == 5432, 'export-container')
        return dict(container_id=digest(value['container_id']), image_id=value['image_id'],
            verified_digest=IMAGE.split('@')[1], running=True, published_port=55433, container_port=5432,
            assurance='HOSTED_JOB_SERVICE_MAPPING_NOT_HOSTILE_SAME_PRIVILEGE_ATTESTATION')
    if name == 'service-proof.json':
        exact(value, ('database', 'user', 'oid', 'version', 'server_port', 'migration_head', 'tables', 'initial_tables'), 'export-service-fields')
        require(value['database'] == DATABASES[phase] and value['user'] == 'returnops_ci'
                and type(value['oid']) is int and value['oid'] > 0 and value['version'] == VERSION
                and value['server_port'] == 5432 and value['migration_head'] == HEAD
                and value['tables'] == 61 and value['initial_tables'] == 0, 'export-service')
        return {k: value[k] for k in value}
    if name.endswith('-seal.json'):
        keys = ('database', 'database_oid', 'server_version', 'revision', 'table_counts', 'business_rows',
                'customer_test_schemas', 'read_only_shared_fence', 'other_client_sessions')
        extra = ('storage_oracle_sha256', 'storage_oracle_status', 'attribution') if phase == 'storage' else ()
        exact(value, (*keys, *extra), 'export-seal-fields')
        require(value['database'] == DATABASES[phase] and type(value['database_oid']) is int and value['database_oid'] > 0
                and value['server_version'] == VERSION and value['revision'] == HEAD
                and value['customer_test_schemas'] == [] and value['read_only_shared_fence'] is True
                and value['other_client_sessions'] == 0, 'export-seal')
        exact(value['table_counts'], tables, 'export-seal-tables')
        expected = {name: (1 if name == 'alembic_version' else
            5 if phase == 'storage' and name in {'case_records', 'original_statement_records', 'original_statement_contents'} else 0) for name in tables}
        require(value['table_counts'] == expected and value['business_rows'] == (15 if phase == 'storage' else 0), 'export-seal-counts')
        result = {k: value[k] for k in keys}
        if phase == 'storage':
            require(value['storage_oracle_status'] == 'EXACT_FIVE_RETAINED_BUNDLES_FIFTEEN_BUSINESS_ROWS'
                    and value['attribution'] == 'PAYLOAD_MULTISET_ONLY_NO_INDIVIDUAL_NODE_TO_UUID_ATTRIBUTION', 'export-storage-oracle')
            result.update(storage_oracle_sha256=digest(value['storage_oracle_sha256']),
                storage_oracle_status=value['storage_oracle_status'], attribution=value['attribution'])
        return result
    if name == 'stop.json':
        exact(value, ('status', 'stage', 'exception_type', 'sqlstate', 'database_retained', 'retry_permitted'), 'export-stop-fields')
        require(value['status'] == 'STOP_UNKNOWN_OR_FAILED' and value['stage'] in
            {'release', 'service-container', 'build', 'service-bootstrap', 'artifact', 'lifecycle', 'storage', 'final-seal'}
            and value['exception_type'] in {'AssertionError', 'ValueError', 'TypeError', 'KeyError', 'OSError', 'PermissionError',
                'FileExistsError', 'RuntimeError', 'OperationalError', 'ProgrammingError', 'IntegrityError', 'DBAPIError',
                'SQLAlchemyError', 'TimeoutExpired', 'KeyboardInterrupt', 'Stop', 'OTHER'}
            and (value['sqlstate'] is None or type(value['sqlstate']) is str and re.fullmatch('[A-Z0-9]{5}', value['sqlstate']))
            and value['database_retained'] is False and value['retry_permitted'] is False, 'export-stop')
        return {k: value[k] for k in value}
    if name == 'result.json':
        exact(value, ('status', 'phase', 'suites', 'source_manifest_sha256', 'core_freeze_sha256',
            'selection_sha256', 'final_seal_sha256', 'database_retained', 'old_2906_transferred', 'full_3140_acceptance_claimed'), 'export-result-fields')
        require(value['phase'] == phase and value['status'] == ('FORMAL_PRIMARY_234_PASS' if phase == 'primary' else 'FORMAL_STORAGE_74_PASS')
                and value['suites'] == ({'artifact': 1, 'lifecycle': 233} if phase == 'primary' else {'storage': 74})
                and value['core_freeze_sha256'] == CORE_FREEZE and all(value[k] is False for k in
                    ('database_retained', 'old_2906_transferred', 'full_3140_acceptance_claimed')), 'export-result')
        for key in ('source_manifest_sha256', 'selection_sha256', 'final_seal_sha256'):
            digest(value[key])
        return {k: value[k] for k in value}
    if name == 'primary-release-proof.json':
        exact(value, ('status', 'release_sha256', 'primary_head', 'primary_run_id', 'artifact_id', 'artifact_digest',
                     'final_seal_sha256', 'assurance'), 'export-release-fields')
        require(phase == 'storage' and value['status'] == 'PRIMARY_RELEASE_VERIFIED'
                and type(value['primary_head']) is str and re.fullmatch('[a-f0-9]{40}', value['primary_head'])
                and all(type(value[k]) is int and value[k] > 0 for k in ('primary_run_id', 'artifact_id'))
                and type(value['artifact_digest']) is str and re.fullmatch('sha256:[a-f0-9]{64}', value['artifact_digest']), 'export-release')
        return dict(status='PRIMARY_RELEASE_VERIFIED', release_sha256=digest(value['release_sha256']),
            primary_head=value['primary_head'], primary_run_id=value['primary_run_id'], artifact_id=value['artifact_id'],
            artifact_digest=value['artifact_digest'], final_seal_sha256=digest(value['final_seal_sha256']),
            assurance='ROOT_ATTESTED_INTERNAL_REVIEW_NOT_HOSTILE_SAME_PRIVILEGE_ATTESTATION')
    raise ValueError('unknown-safe-record')


def main():
    require(len(sys.argv) == 1, 'arguments-forbidden')
    checkout = Path(__file__).resolve().parents[2]
    home = checkout.parent / 'formal'
    if not (home / 'safe-artifacts').is_dir():
        return 0
    source = home / 'source'
    # Tests only use staged source. Read the pristine checkout so a staged-source
    # hash drift cannot discard the already-written safe STOP/outcome evidence.
    data = load_inputs(checkout)
    provenance = json.loads(safe_file(home / 'safe-artifacts/provenance.json').read_bytes())
    phase = provenance['phase']
    selection = selections(checkout, phase)
    output = home / 'upload'
    output.mkdir(exist_ok=False)
    names = ['provenance.json', 'container-proof.json', 'package-proof.json', 'source-before.json', 'service-proof.json',
             'source-after.json', 'installed-after.json', 'final-seal.json', 'result.json', 'stop.json']
    names += [name + '-seal.json' for name in selection['suites']]
    if phase == 'storage':
        names.append('primary-release-proof.json')
    exported, rejected = [], []
    def export(path, name, project):
        if not path.exists():
            return
        try:
            raw = safe_file(path).read_bytes()
            require(len(raw) <= 8_000_000, 'export-bound')
            value = project(json.loads(raw))
            write_new(output / name, value)
            exported.append(name)
        except Exception:
            rejected.append(dict(file=name, status='UNSAFE_PARTIAL_OR_UNREADABLE_NOT_EXPORTED'))
    for name in names:
        export(home / 'safe-artifacts' / name, name, lambda value, name=name: record(name, value, data, phase, selection['expected_public_tables']))
    for name, suite in selection['suites'].items():
        for prefix, kind in (('collect', 'COLLECTION'), ('test', 'EXECUTION')):
            label = prefix + '-' + name
            def outcome(value):
                require(value['phase'] == phase and value['suite'] == name and value['kind'] == kind, 'export-outcome-scope')
                safe = safe_outcome(value, suite)
                require(all(row['source_file'] is None or row['source_file'] in data['files'] for row in safe['reports']), 'export-outcome-source')
                return safe
            export(home / 'runtime/artifacts' / label / 'outcome.json', label + '-outcome.json', outcome)
    for label in ['service-inspect', 'image-inspect', 'wheel', 'install'] + [p + '-' + n for n in selection['suites'] for p in ('collect', 'test')]:
        def process(value):
            exact(value, ('actual_exit', 'owned_process_group_empty'), 'export-process-fields')
            require(type(value['actual_exit']) is int and (value['owned_process_group_empty'] is None
                    or type(value['owned_process_group_empty']) is bool), 'export-process')
            return dict(actual_exit=value['actual_exit'], owned_process_group_empty=value['owned_process_group_empty'])
        export(home / 'private' / (label + '.process.json'), label + '-process.json', process)
    write_new(output / 'export.json', dict(exported=exported, rejected=rejected, database_queries=0,
        raw_streams_uploaded=False, database_retained=False))
    return 1 if rejected else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('A203_FORMAL_FILE_EXPORT_STOP', file=sys.stderr)
        raise SystemExit(1) from None
