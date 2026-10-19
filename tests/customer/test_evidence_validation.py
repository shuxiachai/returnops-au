"""Synthetic in-memory parser, contract/privacy and real process-limit checks."""
from dataclasses import FrozenInstanceError
import hashlib
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from types import SimpleNamespace
import zlib

from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
import pytest

from returnops_domain import evidence_validation as ev
from returnops_domain.errors import FlowError


def image_bytes(format="PNG", size=(8, 8)):
    output = io.BytesIO()
    with Image.new("RGB", size, (10, 20, 30)) as picture:
        picture.save(output, format=format)
    return output.getvalue()


def pdf_bytes(*, pages=1, content=b"q 0 0 12 12 re S Q", encrypted=False):
    output = io.BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=72, height=72)
        stream = DecodedStreamObject()
        stream.set_data(content)
        page[NameObject("/Contents")] = writer._add_object(stream.flate_encode())
    if encrypted:
        writer.encrypt("synthetic-fixture-password")
    writer.write(output)
    return output.getvalue()


def assert_error(call, code, status):
    with pytest.raises(FlowError) as result:
        call()
    assert result.value.code == code
    assert result.value.status == status
    assert result.value.__cause__ is None
    assert result.value.__context__ is None
    assert result.value.envelope("correlation_test")["error"]["details"] == []
    return result.value


@pytest.mark.parametrize("media,make", [
    ("image/jpeg", lambda: image_bytes("JPEG")),
    ("image/png", image_bytes),
    ("application/pdf", pdf_bytes),
], ids=["jpeg", "png", "pdf"])
def test_real_parser_accepts_valid_content_and_preserves_exact_bytes(media, make):
    content = make()
    result = ev.validate_evidence(content, "supplied-name.dat", media, "Customer description")
    assert result.content == content and type(result.content) is bytes
    assert result.size_bytes == len(content)
    assert result.sha256 == hashlib.sha256(content).hexdigest()
    assert result.filename == "supplied-name.dat"
    assert result.description == "Customer description"
    with pytest.raises(FrozenInstanceError):
        result.filename = "changed"


def test_unicode_nul_surrogates_and_path_like_metadata_are_preserved_and_hidden():
    filename = "../私人\\photo\x00\ud800.png"
    description = "客户 e\u0301 🙂\x00\udfff"
    content = image_bytes()
    result = ev.validate_evidence(content, filename, "image/png", description)
    assert result.filename == filename and result.description == description
    displayed = repr(result)
    assert "filename=" not in displayed and "description=" not in displayed and "content=" not in displayed
    assert "私人" not in displayed and "客户" not in displayed


def test_maximum_metadata_lengths_and_exact_ten_mib_are_supported():
    image = image_bytes()
    content = image + b"\0" * (ev.MAX_FILE_BYTES - len(image))
    result = ev.validate_evidence(content, "🙂" * 200, "image/png", "\ud800" * 2000)
    assert result.size_bytes == 10_485_760
    assert result.content == content


@pytest.mark.parametrize("filename,description", [
    ("", None), ("f" * 201, None), (None, None), (123, None),
    ("f", "d" * 2001), ("f", 123), ("f", b"description"),
], ids=["empty-name", "long-name", "none-name", "integer-name", "long-description", "integer-description", "bytes-description"])
def test_invalid_metadata_is_static_422(filename, description):
    assert_error(lambda: ev.validate_evidence(image_bytes(), filename, "image/png", description),
                 "VALIDATION_ERROR", 422)


def test_mutable_content_is_not_aliased_into_an_immutable_result():
    mutable = bytearray(image_bytes())
    assert_error(lambda: ev.validate_evidence(mutable, "f", "image/png"), "VALIDATION_ERROR", 422)
    assert_error(lambda: ev.ValidatedEvidence("f", "image/png", len(mutable), "a" * 64, None, mutable),
                 "VALIDATION_ERROR", 422)


def test_too_large_is_413_before_parsing(monkeypatch):
    monkeypatch.setattr(ev, "_run_parser", lambda *_: pytest.fail("oversize input reached parser"))
    assert_error(lambda: ev.validate_evidence(b"x" * (ev.MAX_FILE_BYTES + 1), "f", "image/png"),
                 "REQUEST_TOO_LARGE", 413)


@pytest.mark.parametrize("media,content", [
    ("image/png", b""), ("text/plain", b"hello"),
    ("IMAGE/PNG", b"hello"), ("image/png", b"\x89PNG\r\n\x1a\nforged"),
    ("image/jpeg", b"\xff\xd8\xff\xe0forged\xff\xd9"),
    ("application/pdf", b"%PDF-1.7\nforged\n%%EOF\n"),
], ids=["empty", "unsupported", "wrong-case", "forged-png", "forged-jpeg", "forged-pdf"])
def test_unsupported_and_forged_content_is_415(media, content):
    assert_error(lambda: ev.validate_evidence(content, "f", media), "UNSUPPORTED_MEDIA_TYPE", 415)


@pytest.mark.parametrize("declared,content", [
    ("image/jpeg", image_bytes()), ("image/png", image_bytes("JPEG")),
    ("application/pdf", image_bytes()), ("image/png", pdf_bytes()),
], ids=["png-as-jpeg", "jpeg-as-png", "png-as-pdf", "pdf-as-png"])
def test_declared_mime_must_match_actual_parser(declared, content):
    assert_error(lambda: ev.validate_evidence(content, "f", declared), "UNSUPPORTED_MEDIA_TYPE", 415)


@pytest.mark.parametrize("media,content", [
    ("image/jpeg", image_bytes("JPEG")[:-20]),
    ("image/png", image_bytes()[:-20]),
    ("application/pdf", pdf_bytes()[:-20]),
    ("application/pdf", pdf_bytes(content=b"(")),
], ids=["truncated-jpeg", "truncated-png", "truncated-pdf", "bad-pdf-content-stream"])
def test_structurally_malformed_files_are_actually_decoded(media, content):
    assert_error(lambda: ev.validate_evidence(content, "f", media), "UNSUPPORTED_MEDIA_TYPE", 415)


def png_chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def test_png_decompression_bomb_dimensions_fail_in_worker():
    content = (b"\x89PNG\r\n\x1a\n"
               + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 6000, 6000, 8, 2, 0, 0, 0))
               + png_chunk(b"IDAT", zlib.compress(b"\0")) + png_chunk(b"IEND", b""))
    assert_error(lambda: ev.validate_evidence(content, "f", "image/png"), "UNSUPPORTED_MEDIA_TYPE", 415)


def test_pdf_stream_expansion_bound_and_encryption_fail_closed():
    content = pdf_bytes(content=b" " * (ev.MAX_STREAM_BYTES + 1))
    assert len(content) < ev.MAX_FILE_BYTES
    assert_error(lambda: ev.validate_evidence(content, "f", "application/pdf"), "UNSUPPORTED_MEDIA_TYPE", 415)
    assert_error(lambda: ev.validate_evidence(pdf_bytes(encrypted=True), "f", "application/pdf"),
                 "UNSUPPORTED_MEDIA_TYPE", 415)


def test_pdf_page_processing_bound():
    content = pdf_bytes(pages=ev.MAX_PDF_PAGES + 1)
    assert_error(lambda: ev.validate_evidence(content, "f", "application/pdf"), "UNSUPPORTED_MEDIA_TYPE", 415)


def test_parser_process_receives_no_filename_description_or_application_environment(monkeypatch):
    for name in ("DATABASE_URL", "JWT_SECRET", "OPENAI_API_KEY", "PYTHONPATH", "PATH"):
        monkeypatch.setenv(name, "synthetic-private-test-value")
    calls = []
    def capture(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(ev.subprocess, "run", capture)
    ev.validate_evidence(image_bytes(), "private-filename", "image/png", "private-description")
    args, kwargs = calls[0]
    assert set(kwargs["env"]) <= {"SystemRoot"}
    assert "private-filename" not in args and "private-description" not in args
    assert args[1:3] == ["-I", "-B"]
    assert kwargs["stdout"] == subprocess.DEVNULL and kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["close_fds"] is True
    assert kwargs["timeout"] == 8


def test_actual_worker_timeout_is_bounded_and_context_free(monkeypatch):
    monkeypatch.setattr(ev, "WORKER_TIMEOUT_SECONDS", 0.0001)
    start = time.monotonic()
    assert_error(lambda: ev.validate_evidence(image_bytes(), "private", "image/png"),
                 "UNSUPPORTED_MEDIA_TYPE", 415)
    assert time.monotonic() - start < 3


@pytest.mark.parametrize("failure", [OSError("private-parser-detail"), ValueError("private-parser-detail")],
                         ids=["launch-oserror", "launch-valueerror"])
def test_worker_launch_failure_is_static_503_without_context(monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(ev.subprocess, "run", fail)
    error = assert_error(lambda: ev.validate_evidence(image_bytes(), "private", "image/png"),
                         "INTERNAL_ERROR", 503)
    assert "private" not in str(error) and "private" not in repr(error)


def test_missing_parser_dependency_and_limit_setup_fail_closed(monkeypatch, capsys):
    monkeypatch.setattr(ev.sys, "argv", ["worker", "image/png"])
    monkeypatch.setattr(ev.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(image_bytes())))
    monkeypatch.setattr(ev, "_apply_limits", lambda: None)
    def unavailable(*args):
        raise ImportError("private-dependency-detail")
    monkeypatch.setattr(ev, "_parse_image", unavailable)
    assert ev._worker() == ev._UNAVAILABLE
    monkeypatch.setattr(ev, "_apply_limits", unavailable)
    assert ev._worker() == ev._UNAVAILABLE
    assert capsys.readouterr() == ("", "")


def run_limit_probe(body, timeout=7):
    # Real child, same OS limit setup; no DB, token, user media or network access.
    code = ("import runpy\n"
            f"scope = runpy.run_path({str(Path(ev.__file__).resolve())!r})\n"
            "scope['_apply_limits']()\n" + body)
    return subprocess.run([sys.executable, "-I", "-B", "-c", code],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          env=ev._worker_environment(), timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def test_actual_worker_memory_limit_prevents_over_limit_allocation():
    completed = run_limit_probe(
        "try:\n    value = bytearray(scope['WORKER_MEMORY_BYTES'])\n"
        "except MemoryError:\n    raise SystemExit(0)\n"
        "raise SystemExit(91)\n")
    assert completed.returncode == 0


def test_actual_worker_cpu_limit_terminates_busy_loop():
    # Four CPU seconds need not fit seven wall seconds on a contended runner.
    # The actual parser's independent wall deadline is covered above.
    completed = run_limit_probe("while True:\n    pass\n", timeout=30)
    if os.name == "nt":
        assert completed.returncode == 0xC0000044  # STATUS_QUOTA_EXCEEDED
    else:
        import signal
        assert completed.returncode in (-signal.SIGKILL, -signal.SIGXCPU)


def test_png_valid_checksums_with_incomplete_pixel_data_still_fails_decode():
    content = (b"\x89PNG\r\n\x1a\n"
               + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
               + png_chunk(b"IDAT", zlib.compress(b"\0")) + png_chunk(b"IEND", b""))
    assert_error(lambda: ev.validate_evidence(content, "f", "image/png"), "UNSUPPORTED_MEDIA_TYPE", 415)


def test_animated_png_frames_are_decoded():
    output = io.BytesIO()
    with Image.new("RGB", (4, 4), "red") as first, Image.new("RGB", (4, 4), "blue") as second:
        first.save(output, format="PNG", save_all=True, append_images=[second], duration=50)
    content = output.getvalue()
    assert ev.validate_evidence(content, "animation.png", "image/png").content == content


def test_production_eight_second_wall_watchdog_kills_a_stalled_worker(tmp_path, monkeypatch):
    # Synthetic stalled child isolates the wall watchdog from the CPU quota.
    script = tmp_path / "stalled_worker.py"
    script.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    monkeypatch.setattr(ev, "__file__", str(script))
    assert ev.WORKER_TIMEOUT_SECONDS == 8
    start = time.monotonic()
    assert_error(lambda: ev.validate_evidence(image_bytes(), "private", "image/png"),
                 "UNSUPPORTED_MEDIA_TYPE", 415)
    elapsed = time.monotonic() - start
    assert 7.5 <= elapsed < 15  # Allow OS process creation/reaping overhead.
