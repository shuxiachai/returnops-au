"""Exercise the actual Compose probe against owned HTTP servers, without Docker/DB.

F.02 / NFR-006/007/008; docs/10 and the C independent-reproduction guide.
An injected proxy must neither break a healthy local API nor mask its 503.
"""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from typing import Iterator

import pytest


ROOT = Path(__file__).resolve().parents[2]
PROBE_URL = "http://127.0.0.1:8000/health/ready"


@contextmanager
def owned_http_server(status: int) -> Iterator[tuple[str, list[str]]]:
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            requests.append(self.path)
            body = b'{"status":"ready"}' if status == 200 else b'{"status":"not_ready"}'
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def compose_probe_code() -> str:
    # This intentionally parses the existing JSON-array YAML scalar, rather
    # than duplicating the health implementation or adding a YAML dependency.
    source = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    lines = re.findall(r'^\s+test: (\["CMD", "python", "-c", .+\])$', source, re.MULTILINE)
    assert len(lines) == 1, "Locate exactly one Python Compose healthcheck"
    command = json.loads(lines[0])
    assert command[:3] == ["CMD", "python", "-c"] and len(command) == 4
    code = command[3]
    assert code.count(PROBE_URL) == 1, "Keep the production probe on its fixed local readiness URL"
    return code


@pytest.mark.parametrize("api_status", [200, 503], ids=["healthy", "unready"])
def test_compose_probe_ignores_proxy_and_preserves_real_api_status(api_status: int) -> None:
    with owned_http_server(api_status) as (api_url, api_requests), owned_http_server(200) as (proxy_url, proxy_requests):
        # Only the port changes for this test; execute the command extracted
        # from Compose itself. Never bind 8000 or contact an existing service.
        code = compose_probe_code().replace(PROBE_URL, api_url + "/health/ready")
        environment = {key: value for key, value in os.environ.items()
                       if not key.lower().endswith("_proxy") and key != "REQUEST_METHOD"}
        environment.update(HTTP_PROXY=proxy_url, http_proxy=proxy_url,
                           HTTPS_PROXY=proxy_url, https_proxy=proxy_url,
                           NO_PROXY="", no_proxy="", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], env=environment,
            capture_output=True, text=True, timeout=10, check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        assert (result.returncode == 0) == (api_status == 200), result.stderr
        assert api_requests == ["/health/ready"]
        assert proxy_requests == [], "A proxy response must not decide local API health"
