"""Finite private report proof; report text, arguments and exceptions stay private."""
import json
import os
from pathlib import Path

NODES = json.loads(Path(__file__).with_name('selection.json').read_text())['nodes']
_descriptor = None
_records = 0


def _close():
    global _descriptor
    descriptor, _descriptor = _descriptor, None
    if descriptor is not None:
        try: os.close(descriptor)
        except Exception: pass


def _write(value):
    global _records
    if _descriptor is None: return
    try:
        assert _records < 2 + 3 * len(NODES)
        raw = (json.dumps(value, separators=(',', ':')) + '\n').encode('ascii')
        assert len(raw) <= 256
        assert os.write(_descriptor, raw) == len(raw)
        _records += 1
    except Exception:
        # Proof I/O cannot change test execution, failure codes or fixture teardown.
        _close()


def pytest_sessionstart(session):
    global _descriptor, _records
    try:
        path = Path(os.environ['A82_REPORT_PATH'])
        assert path.is_absolute() and path.parent.is_dir() and not path.parent.is_symlink()
        assert not path.exists() and not path.is_symlink()
        _descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                              getattr(os, 'O_NOFOLLOW', 0), 0o600)
        _records = 0
    except Exception: _close()


def pytest_collection_finish(session):
    _write(dict(event='collection', count=len(session.items),
                exact_nodes=[item.nodeid for item in session.items] == NODES))


def pytest_runtest_logreport(report):
    _write(dict(event='report', node_index=NODES.index(report.nodeid) if report.nodeid in NODES else -1,
        phase=report.when if report.when in ('setup','call','teardown') else 'unknown',
        outcome=report.outcome if report.outcome in ('passed','failed','skipped') else 'unknown',
        xfail=hasattr(report, 'wasxfail')))


def pytest_sessionfinish(session, exitstatus):
    _write(dict(event='session', exitstatus=int(exitstatus)))
    _close()
