"""Exact typed pytest observer; import is inert and never runs fixtures."""
import json
import os
from pathlib import Path
import sys

from runner import NODE, require, write_new


class Observer:
    def __init__(self, phase):
        self.phase = phase
        self.collected = []
        self.errors = 0
        self.reports = []

    def pytest_collection_modifyitems(self, session, config, items):
        self.collected = [item.nodeid for item in items]
        require(self.collected == [NODE], 'collection-exact')

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors += 1

    def pytest_runtest_logreport(self, report):
        from _pytest.reports import TestReport
        require(type(report) is TestReport and report.nodeid == NODE, 'report-type-node')
        require(report.when in {'setup', 'call', 'teardown'}, 'report-phase')
        self.reports.append([report.when, report.outcome])


def main():
    require(len(sys.argv) == 5, 'entry-arguments')
    source, action = (Path(arg).resolve() for arg in sys.argv[1:3])
    phase, node = sys.argv[3:]
    require(node == NODE and phase in {'COLLECTION', 'EXECUTION'}, 'entry-node')
    label = 'collect-diagnostic' if phase == 'COLLECTION' else 'test-diagnostic'
    require(action == source.parent / 'runtime/artifacts' / label and Path.cwd() == action, 'entry-layout')
    require(os.environ['ARTIFACT_DIAGNOSTIC_PHASE'] == phase, 'entry-phase')
    require(os.environ['MANUAL_INSTALLED_DIR'] == str(source.parent / 'installed'), 'entry-installed')
    import pytest
    observer = Observer(phase)
    args = [str(source / node.split('::')[0]) + '::' + node.split('::')[1],
            '-q', '--tb=no', '--no-header', '-p', 'no:cacheprovider', '-o', 'addopts=',
            '--rootdir', str(source), '--basetemp', str(action / 'pytest-temp')]
    if phase == 'COLLECTION':
        args.append('--collect-only')
    code = int(pytest.main(args, plugins=[observer]))
    write_new(action / 'outcome.json', dict(node=NODE, phase=phase, collected=observer.collected,
              reports=observer.reports, collection_errors=observer.errors, exit_code=code))
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('A203_T2_PYTEST_ENTRY_STOP', file=sys.stderr)
        raise SystemExit(1) from None
