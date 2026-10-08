"""No-DB regression for the independent-process ready-file handshake."""
import json
from pathlib import Path
import threading

import pytest

import pass_review_process_probe as probe


def test_ready_json_is_invisible_until_complete_and_closed(tmp_path, monkeypatch):
    ready = tmp_path / 'ready.json'
    payload = dict(pid=101, case='synthetic-case', version=7,
                   key='original-review-key', application_name='synthetic-child')
    partial_written = threading.Event()
    finish_write = threading.Event()
    observed = {}
    failures = []
    original_dump = json.dump

    def paused_dump(value, stream):
        observed['stream'] = stream
        stream.write('{"pid":')
        stream.flush()
        partial_written.set()
        assert finish_write.wait(5), 'Observer did not release the staged write'
        stream.seek(0)
        stream.truncate()
        original_dump(value, stream)

    def publish():
        try:
            probe.publish_ready(ready, payload)
        except BaseException as error:
            failures.append(error)

    monkeypatch.setattr(probe.json, 'dump', paused_dump)
    writer = threading.Thread(target=publish, daemon=True)
    writer.start()
    try:
        assert partial_written.wait(5), 'Writer did not reach the partial-write window'
        staged = Path(observed['stream'].name)
        assert staged.parent == ready.parent and staged != ready
        assert staged.read_text(encoding='utf8') == '{"pid":'
        assert not ready.exists(), 'Incomplete JSON must not be published as ready'
    finally:
        finish_write.set()
        writer.join(5)
    assert not writer.is_alive(), 'Owned publication thread did not finish'
    assert failures == []
    assert observed['stream'].closed
    assert json.loads(ready.read_text(encoding='utf8')) == payload
    assert list(tmp_path.iterdir()) == [ready]


def test_ready_write_failure_propagates_without_publishing(tmp_path, monkeypatch):
    ready = tmp_path / 'ready.json'
    failure = OSError('Synthetic staged-write failure')
    observed = {}

    def fail_after_partial_write(value, stream):
        observed['stream'] = stream
        stream.write('{"pid":')
        stream.flush()
        raise failure

    monkeypatch.setattr(probe.json, 'dump', fail_after_partial_write)
    with pytest.raises(OSError) as raised:
        probe.publish_ready(ready, dict(pid=101))
    assert raised.value is failure
    assert observed['stream'].closed
    assert not ready.exists(), 'A failed staged write must not publish readiness'
