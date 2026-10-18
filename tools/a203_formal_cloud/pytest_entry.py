"""Exact parent/subtest reports only; no test/fixture wrapping or import-time execution."""
import math
import os
from pathlib import Path
import re
import sys

from runner import REPORT_RUNTIME, exact, load_inputs, require, safe_exception, selections, sha, write_new

EXCEPTION_TYPES = {'AssertionError', 'ValueError', 'TypeError', 'KeyError', 'OSError', 'PermissionError',
    'FileExistsError', 'RuntimeError', 'OperationalError', 'ProgrammingError', 'IntegrityError', 'DBAPIError',
    'SQLAlchemyError', 'TimeoutExpired', 'KeyboardInterrupt', 'Stop', 'OTHER'}


def verified_report_types():
    from importlib.metadata import distribution
    dependency = distribution('pytest')
    site = Path(dependency.locate_file('')).resolve()
    require(dependency.version == REPORT_RUNTIME['pytest_version'], 'pytest-version')
    for relative, expected in REPORT_RUNTIME['source_files'].items():
        require(sha(site / relative) == expected, 'pytest-source')
    from _pytest.reports import TestReport
    from _pytest.subtests import SubtestReport
    for kind, cls in (('parent', TestReport), ('subtest', SubtestReport)):
        require(cls.__module__ + '.' + cls.__qualname__ == REPORT_RUNTIME['classes'][kind], 'report-class')
        require(Path(sys.modules[cls.__module__].__file__).resolve() == site / (cls.__module__.replace('.', '/') + '.py'), 'report-origin')
    return TestReport, SubtestReport, site


def safe_outcome(value, suite):
    """Strict bounded projection also accepts failed/partial typed evidence for safe export."""
    keys = ('phase', 'suite', 'kind', 'collected', 'reports', 'collection_errors', 'skipped_collections',
            'unexpected_plugins', 'exit_code', 'testsfailed', 'report_counts', 'subtest_counts',
            'warning_count', 'report_runtime')
    exact(value, keys, 'outcome-fields')
    require(value['phase'] in {'primary', 'storage'} and value['suite'] in {'artifact', 'lifecycle', 'storage'}
            and value['kind'] in {'COLLECTION', 'EXECUTION'}, 'outcome-scope')
    require(type(value['collected']) is list and len(value['collected']) <= len(suite['expected_nodes'])
            and all(type(n) is str and n in suite['expected_nodes'] for n in value['collected']), 'outcome-collected')
    for key in ('collection_errors', 'skipped_collections', 'unexpected_plugins', 'testsfailed', 'warning_count'):
        require(type(value[key]) is int and value[key] >= 0, 'outcome-counter')
    require(type(value['exit_code']) is int, 'outcome-exit')
    require(value['report_runtime'] == REPORT_RUNTIME, 'outcome-runtime')
    reports = value['reports']
    require(type(reports) is list and len(reports) <= 100000, 'outcome-report-list')
    clean = []
    rowkeys = ('nodeid', 'when', 'outcome', 'wasxfail', 'duration', 'report_kind', 'report_sequence', 'subtest_index',
               'source_file', 'line', 'exception_type', 'sqlstate')
    for row in reports:
        exact(row, rowkeys, 'outcome-report-fields')
        require(row['nodeid'] is None or type(row['nodeid']) is str and row['nodeid'] in suite['expected_nodes'], 'report-node')
        require(row['when'] in {'setup', 'call', 'teardown', 'unknown'}
                and row['outcome'] in {'passed', 'failed', 'skipped', 'unknown'}
                and row['report_kind'] in {'parent', 'subtest', 'unknown'}, 'report-enum')
        require(type(row['wasxfail']) is bool and type(row['report_sequence']) is int and row['report_sequence'] > 0, 'report-identity')
        require(row['duration'] is None or type(row['duration']) in {int, float}
                and math.isfinite(row['duration']) and row['duration'] >= 0, 'report-duration')
        require(row['subtest_index'] is None or type(row['subtest_index']) is int and row['subtest_index'] > 0, 'subtest-index')
        require(row['source_file'] is None or type(row['source_file']) is str
                and re.fullmatch('[A-Za-z0-9_./-]+\\.py', row['source_file'])
                and not Path(row['source_file']).is_absolute() and '..' not in Path(row['source_file']).parts, 'report-source')
        require((row['source_file'] is None and row['line'] is None) or row['source_file'] is not None
                and type(row['line']) is int and row['line'] > 0, 'report-line')
        require(row['exception_type'] is None or row['exception_type'] in EXCEPTION_TYPES, 'report-exception')
        require(row['sqlstate'] is None or type(row['sqlstate']) is str and re.fullmatch('[A-Z0-9]{5}', row['sqlstate']), 'report-sqlstate')
        clean.append({key: row[key] for key in rowkeys})
    exact(value['report_counts'], ('parent', 'subtest', 'unknown'), 'report-count-fields')
    require(all(type(n) is int and n >= 0 for n in value['report_counts'].values()), 'report-counts')
    require(type(value['subtest_counts']) is dict and all(k in suite['expected_nodes'] and type(n) is int and n > 0
            for k, n in value['subtest_counts'].items()), 'subtest-counts')
    return dict(**{k: value[k] for k in keys if k != 'reports'}, reports=clean)


def validate_outcome(value, suite, kind):
    data = safe_outcome(value, suite)
    nodes = data['collected']
    require(data['kind'] == kind and nodes == suite['expected_nodes'] and len(nodes) == len(set(nodes)), 'collection-exact')
    require(data['exit_code'] == 0 and data['collection_errors'] == data['skipped_collections'] == data['unexpected_plugins'] == 0,
            'outcome-incomplete')
    reports = data['reports']
    require([r['report_sequence'] for r in reports] == list(range(1, len(reports) + 1)), 'report-sequence')
    for row in reports:
        require(row['report_kind'] in {'parent', 'subtest'} and row['nodeid'] in nodes
                and row['when'] in {'setup', 'call', 'teardown'} and row['outcome'] == 'passed'
                and row['wasxfail'] is False and row['duration'] is not None, 'report-pass')
    parents = [r for r in reports if r['report_kind'] == 'parent']
    subtests = [r for r in reports if r['report_kind'] == 'subtest']
    require(data['report_counts'] == dict(parent=len(parents), subtest=len(subtests), unknown=0), 'report-count-match')
    require(all(r['subtest_index'] is None for r in parents), 'parent-subtest-identity')
    counts = {}
    for row in subtests:
        require(row['when'] == 'call', 'subtest-phase')
        node = row['nodeid']
        counts[node] = counts.get(node, 0) + 1
        require(row['subtest_index'] == counts[node], 'subtest-order')
    require(data['subtest_counts'] == counts, 'subtest-count-match')
    if kind == 'EXECUTION':
        require(data['testsfailed'] == 0 and len(parents) == 3 * len(nodes), 'parent-count')
        for when in ('setup', 'call', 'teardown'):
            phase = [r['nodeid'] for r in parents if r['when'] == when]
            require(len(phase) == len(nodes) and set(phase) == set(nodes), 'parent-phases')
    else:
        require(reports == [] and data['testsfailed'] == 0, 'collection-not-execution')
    return data


class Observer:
    def __init__(self, source, phase, name, kind, suite):
        self.source = source
        self.suite = suite
        self.source_files = set(load_inputs(source)['files'])
        self.parent_type, self.subtest_type, self.site = verified_report_types()
        self.data = dict(phase=phase, suite=name, kind=kind, collected=[], reports=[],
            collection_errors=0, skipped_collections=0, unexpected_plugins=0, exit_code=-1,
            testsfailed=0, warning_count=0, report_counts=dict(parent=0, subtest=0, unknown=0),
            subtest_counts={}, report_runtime=REPORT_RUNTIME)

    def pytest_collection_finish(self, session):
        self.data['collected'] = [item.nodeid for item in session.items]
        for name, plugin in session.config.pluginmanager.list_name_plugin():
            if plugin is None:
                continue
            module = plugin if hasattr(plugin, '__file__') else sys.modules.get(type(plugin).__module__)
            filename = getattr(module, '__file__', None)
            if filename is None:
                continue
            path = Path(filename).resolve()
            if not (path.is_relative_to(self.source) or path.is_relative_to(self.site / '_pytest')):
                self.data['unexpected_plugins'] += 1
        require(self.data['collected'] == self.suite['expected_nodes'], 'collection-exact')

    def pytest_collectreport(self, report):
        self.data['collection_errors'] += int(report.failed)
        self.data['skipped_collections'] += int(report.skipped)

    def pytest_runtest_makereport(self, item, call):
        # Registered as a report hook wrapper only in main. No user repr/locals/text.
        outcome = yield
        report = outcome.get_result()
        metadata = dict(source_file=None, line=None, exception_type=None, sqlstate=None)
        candidate = Path(item.path).resolve()
        line = item.location[1] + 1
        if call.excinfo is not None:
            metadata.update(safe_exception(call.excinfo.value))
            for entry in call.excinfo.traceback:
                path = Path(entry.path).resolve()
                if path.is_relative_to(self.source) and path.relative_to(self.source).as_posix() in self.source_files:
                    candidate, line = path, entry.lineno + 1
        if candidate.is_relative_to(self.source):
            relative = candidate.relative_to(self.source).as_posix()
            if relative in self.source_files and type(line) is int and line > 0:
                metadata.update(source_file=relative, line=line)
        report._a203_safe_location = metadata

    def pytest_runtest_logreport(self, report):
        kind = ('parent' if type(report) is self.parent_type else
                'subtest' if type(report) is self.subtest_type else 'unknown')
        self.data['report_counts'][kind] += 1
        if kind == 'unknown':
            node, when, outcome, xfail, duration = None, 'unknown', 'unknown', False, None
        else:
            node = report.nodeid if type(report.nodeid) is str and report.nodeid in self.data['collected'] else None
            when = report.when if report.when in {'setup', 'call', 'teardown'} else 'unknown'
            outcome = report.outcome if report.outcome in {'passed', 'failed', 'skipped'} else 'unknown'
            xfail = hasattr(report, 'wasxfail')
            duration = report.duration if type(report.duration) in {int, float} and math.isfinite(report.duration) and report.duration >= 0 else None
        index = None
        if kind == 'subtest' and node is not None:
            counts = self.data['subtest_counts']
            counts[node] = counts.get(node, 0) + 1
            index = counts[node]
        metadata = getattr(report, '_a203_safe_location', dict(source_file=None, line=None, exception_type=None, sqlstate=None))
        self.data['reports'].append(dict(nodeid=node, when=when, outcome=outcome, wasxfail=xfail,
            duration=duration, report_kind=kind, report_sequence=len(self.data['reports']) + 1,
            subtest_index=index, **metadata))
        require(kind != 'unknown', 'report-class-unknown')

    def pytest_warning_recorded(self, warning_message, when, nodeid, location):
        self.data['warning_count'] += 1

    def pytest_sessionfinish(self, session, exitstatus):
        self.data['exit_code'] = int(exitstatus)
        self.data['testsfailed'] = int(session.testsfailed)


def main():
    require(len(sys.argv) == 6, 'entry-arguments')
    source, action = (Path(arg).resolve() for arg in sys.argv[1:3])
    phase, name, kind = sys.argv[3:]
    require(kind in {'COLLECTION', 'EXECUTION'}, 'entry-kind')
    selection = selections(source, phase)
    require(name in selection['suites'], 'entry-suite')
    suite = selection['suites'][name]
    label = ('collect-' if kind == 'COLLECTION' else 'test-') + name
    require(action == source.parent / 'runtime/artifacts' / label and Path.cwd() == action, 'entry-layout')
    require(os.environ['MANUAL_INSTALLED_DIR'] == str(source.parent / 'installed')
            and os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
            and os.environ['PYTHONPATH'] == os.pathsep.join([str(source / 'packages'), str(source / 'apps/api')]), 'entry-environment')
    test_directory = source / ('tests/storage' if name == 'storage' else 'tests/lifecycle')
    sys.path[:0] = [str(source), str(source / 'packages'), str(source / 'apps/api'), str(test_directory)]
    import pytest
    Observer.pytest_runtest_makereport = pytest.hookimpl(hookwrapper=True)(Observer.pytest_runtest_makereport)
    observer = Observer(source, phase, name, kind, suite)
    args = [str(source / s.split('::', 1)[0]) + ('::' + s.split('::', 1)[1] if '::' in s else '')
            for s in suite['selectors']]
    args += ['-q', '-x', '--strict-markers', '-c', str(source / 'pyproject.toml'),
             '--tb=no', '--no-header', '-p', 'no:cacheprovider', '-o', 'addopts=',
             '--rootdir', str(source), '--confcutdir', str(source), '--basetemp', str(action / 'pytest-temp')]
    if kind == 'COLLECTION':
        args.append('--collect-only')
    code = int(pytest.main(args, plugins=[observer]))
    observer.data['exit_code'] = code
    write_new(action / 'outcome.json', observer.data)
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('A203_FORMAL_PYTEST_ENTRY_STOP', file=sys.stderr)
        raise SystemExit(1) from None
