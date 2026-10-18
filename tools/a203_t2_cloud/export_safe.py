"""File-only bounded export, including after failure/cancellation; never imports DB code."""
import ast
import json
from pathlib import Path
import re
import sys

from runner import NODE, require, safe_file, sha, write_new


def enums(source):
    tree = ast.parse((source / 'tests/founder/conftest.py').read_text(encoding='utf8'))
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.startswith('DIAGNOSTIC_'):
                require(isinstance(node.value, ast.Call) and node.value.func.id == 'frozenset', 'enum-shape')
                result[name] = frozenset(ast.literal_eval(node.value.args[0]))
    return result


def validated_log(path, allowed):
    raw = safe_file(path).read_bytes()
    require(len(raw) <= 65536 and raw.endswith(b'\n'), 'log-boundary')
    rows = [json.loads(line) for line in raw.splitlines()]
    require(0 < len(rows) <= 256, 'log-count')
    keys = {'sequence', 'process', 'elapsed_ms', 'phase', 'event', 'exception_type', 'flow_code', 'sqlstate'}
    for sequence, row in enumerate(rows, 1):
        require(set(row) == keys and row['sequence'] == sequence, 'log-fields')
        require(type(row['process']) is int and row['process'] > 0 and type(row['elapsed_ms']) is int and row['elapsed_ms'] >= 0, 'log-numbers')
        for key, choices in [('phase', 'PHASES'), ('event', 'EVENTS'), ('exception_type', 'TYPES'), ('flow_code', 'FLOW_CODES')]:
            require(row[key] in allowed['DIAGNOSTIC_' + choices] or (key in {'exception_type', 'flow_code'} and row[key] is None), 'log-enum')
        require(row['sqlstate'] is None or type(row['sqlstate']) is str and re.fullmatch('[A-Z0-9]{5}', row['sqlstate']), 'log-sqlstate')
    return rows


def child_output(path, allowed):
    raw = safe_file(path).read_bytes()
    require(len(raw) <= 65536, 'child-size')
    record = dict(bytes=len(raw), sha256=sha(path))
    if path.name.endswith('.stderr.bin'):
        if raw in {b'', b'ARTIFACT_DIAGNOSTIC_STOP\n', b'ARTIFACT_DIAGNOSTIC_LOG_FAILURE\n'}:
            record['fixed_marker'] = raw.decode('ascii').strip()
        else:
            value = json.loads(raw)
            require(set(value) == {'probe_error_type'} and value['probe_error_type'] in allowed['DIAGNOSTIC_TYPES'], 'child-stderr')
            record.update(value)
        return record
    value = json.loads(raw)
    require(set(value) == {'result', 'counts', 'process', 'announced', 'installed_hashes'}, 'child-fields')
    result = value['result']
    require(result['status'] in {'COMMITTED', 'REPLAYED', 'IN_PROGRESS', 'RETAINED', 'DENIED', 'UNKNOWN'}, 'child-status')
    require(result['safe_code'] is None or result['safe_code'] in allowed['DIAGNOSTIC_FLOW_CODES'], 'child-code')
    counts = value['counts']
    require(set(counts) == {'return_provider', 'label_provider', 'artifact_read', 'outbound', 'notification_send', 'LLM',
                           'pdf_render', 'pdf_text_line', 'pdf_assembly', 'pdf_expected', 'pdf_validation'}, 'child-counts')
    require(all(type(n) is int and n >= 0 for n in counts.values()), 'child-count-values')
    require(type(value['process']) is int and value['process'] > 0, 'child-pid')
    # IDs, payloads, tokens and arbitrary extra result text never leave the private job area.
    record.update(result={'status': result['status'], 'safe_code': result['safe_code']}, counts=counts,
                  process=value['process'], output_kind='SAFE_PROJECTION_NOT_RAW_STREAM')
    return record


def main():
    require(len(sys.argv) == 1, 'arguments-forbidden')
    checkout = Path(__file__).resolve().parents[2]
    home = checkout.parent / 'diagnostic'
    if not (home / 'safe-artifacts').is_dir():
        return 0
    source = home / 'source'
    allowed = enums(source)
    safe = home / 'safe-artifacts'
    exported, rejected = [], []
    action = home / 'runtime/artifacts/test-diagnostic'
    if action.is_dir():
        paths = sorted(action.rglob('*.jsonl')) + sorted(action.rglob('artifact-*.stdout.bin')) + sorted(action.rglob('artifact-*.stderr.bin'))
        require(len(paths) <= 10, 'export-count')
        for index, path in enumerate(paths):
            relative = path.relative_to(action).as_posix()
            try:
                if path.suffix == '.jsonl':
                    require(path.name in {'parent-diagnostic.jsonl', 'artifact-diagnostic-0.jsonl', 'artifact-diagnostic-1.jsonl', 'artifact-diagnostic-restart.jsonl'}, 'log-name')
                    value = dict(kind='SAFE_DIAGNOSTIC_ROWS', rows=validated_log(path, allowed))
                else:
                    require(re.fullmatch(r'artifact-(?:0|1|restart)\.(?:stdout|stderr)\.bin', path.name), 'child-name')
                    value = child_output(path, allowed)
                # Store safe source-relative path, never external absolute paths or raw bytes.
                output = f'observation-{index:02d}.json'
                write_new(safe / output, dict(source=relative, **value))
                exported.append(output)
            except Exception:
                rejected.append(dict(index=index, status='UNSAFE_PARTIAL_OR_UNREADABLE_NOT_EXPORTED'))
    for label in ('collect-diagnostic', 'test-diagnostic'):
        directory = home / 'runtime/artifacts' / label
        for filename in ('process-exit.json', 'outcome.json'):
            path = directory / filename
            if not path.exists():
                continue
            value = json.loads(safe_file(path).read_bytes())
            if filename == 'process-exit.json':
                require(set(value) == {'actual_exit'} and type(value['actual_exit']) is int, 'exit-shape')
            else:
                require(set(value) == {'node', 'phase', 'collected', 'reports', 'collection_errors', 'exit_code'}, 'outcome-fields')
                require(value['node'] == NODE and value['phase'] in {'COLLECTION', 'EXECUTION'}, 'outcome-node')
                require(value['collected'] in ([], [NODE]), 'outcome-collected')
                reports = value['reports']
                require(type(reports) is list, 'outcome-reports-list')
                require(all(type(row) is list and len(row) == 2
                            and type(row[0]) is str and row[0] in {'setup', 'call', 'teardown'}
                            and type(row[1]) is str and row[1] in {'passed', 'failed', 'skipped'}
                            for row in reports), 'outcome-reports')
                require(type(value['collection_errors']) is int and type(value['exit_code']) is int, 'outcome-codes')
                value = dict(node=NODE, phase=value['phase'], collected=[NODE] if value['collected'] else [],
                             reports=[[when, outcome] for when, outcome in reports],
                             collection_errors=value['collection_errors'], exit_code=value['exit_code'])
            write_new(safe / (label + '-' + filename), value)
    write_new(safe / 'export.json', dict(exported=exported, rejected=rejected,
              database_queries=0, raw_streams_uploaded=False, database_retained=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('A203_T2_FILE_EXPORT_STOP', file=sys.stderr)
        raise SystemExit(1) from None
