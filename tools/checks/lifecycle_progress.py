"""Passive lifecycle progress for F.02 / NFR-006/007 and the M-A/M-S models.

Only pytest node identities and public report metadata are emitted. This plugin
does not select, reorder, execute, retry, stop, or change the result of a test.
It has no database, network, filesystem, fixture, or business-module access.
An incomplete journal is incomplete evidence, never a successful test result.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time


PREFIX = "RETURNOPS_LIFECYCLE_PROGRESS "
_started = 0


def _identity(nodeid: str) -> dict[str, object]:
    """Retain the source/function locator, replacing every parameter ID."""
    locator, separator, parameters = nodeid.partition("[")
    parameter_hash = None
    if separator:
        parameter_hash = hashlib.sha256(parameters.encode("utf-8")).hexdigest()
        locator += "[param_sha256=" + parameter_hash + "]"
    return {
        "nodeid": locator,
        "nodeid_sha256": hashlib.sha256(nodeid.encode("utf-8")).hexdigest(),
        "parameter_id_sha256": parameter_hash,
    }


def _emit(event: str, **fields: object) -> None:
    """Flush from reporting hooks intended to run with phase capture suspended.

    sys.__stdout__ does not itself bypass file-descriptor capture. Actual
    visibility before test completion must be verified by the dummy harness.

    Observation must not turn a test result into an observer failure if the
    output stream disappears. Consumers must check journal completeness.
    KeyboardInterrupt and SystemExit are deliberately not intercepted.
    """
    try:
        stream = sys.__stdout__
        if stream is None:
            return
        record = {
            "format": 1,
            "event": event,
            "pid": os.getpid(),
            "monotonic_seconds": time.monotonic(),
            **fields,
        }
        stream.write("\n" + PREFIX + json.dumps(record, ensure_ascii=True) + "\n")
        stream.flush()
    except Exception:
        # No exception text, report repr, local variables, or environment data.
        return


def pytest_sessionstart(session) -> None:
    global _started
    _started = 0


def pytest_collection_finish(session) -> None:
    """Observe pytest's final item order without changing its item list."""
    _emit("collection_start", count=len(session.items))
    for ordinal, item in enumerate(session.items, start=1):
        _emit("collection_node", ordinal=ordinal, **_identity(item.nodeid))
    _emit("collection_end", count=len(session.items))


def pytest_runtest_logstart(nodeid, location) -> None:
    global _started
    _started += 1
    _emit("node_start", ordinal=_started, **_identity(nodeid))


def pytest_runtest_logreport(report) -> None:
    _emit(
        "phase_end",
        **_identity(report.nodeid),
        phase=report.when,
        outcome=report.outcome,
        duration_seconds=report.duration,
    )


def pytest_runtest_logfinish(nodeid, location) -> None:
    _emit("node_finish", **_identity(nodeid))
