"""Validate untrusted upload bytes without giving parsers application secrets.

The 10 MiB/filename/description limits are frozen v1 contract limits. Internal
processing bounds are 8 seconds wall time, 4 seconds CPU, 384 MiB per worker,
25 million decoded image pixels over at most 100 frames, and PDF limits of 200
pages, 20,000 visited objects, 16 MiB per decoded stream / 32 MiB in total and
100,000 page-content operations. More complex input is rejected with 415.

Pillow verifies and fully decodes JPEG/PNG. pypdf strictly reads PDF structure,
walks referenced objects, decodes streams and parses page-content operations;
encrypted documents and unavailable stream decoders are rejected. This is not
PDF rendering, malware scanning, sanitisation, or a filesystem/network sandbox.
The original bytes and Unicode metadata are retained exactly. Metadata never
becomes a path, process argument or HTTP header. Only trusted module paths and a
fixed MIME enum reach the worker command. Its environment contains no inherited
application variables; Windows SystemRoot is the sole OS bootstrap exception.

The disposable worker applies OS limits before importing either parser or
reading input. Windows uses a job object (memory, CPU and one-process limits),
Linux uses RLIMIT_AS/RLIMIT_CPU. Missing isolation/dependencies fail closed as
503. Resource exhaustion/malformed input is 415. Parser output is discarded;
only fixed exit codes cross the process boundary. The caller must also bound
request concurrency and streamed body size before collecting these bytes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGE_FRAMES = 100
MAX_PDF_PAGES = 200
MAX_PDF_OBJECTS = 20_000
MAX_STREAM_BYTES = 16 * 1024 * 1024
MAX_TOTAL_STREAM_BYTES = 32 * 1024 * 1024
MAX_CONTENT_OPERATIONS = 100_000
WORKER_MEMORY_BYTES = 384 * 1024 * 1024
WORKER_CPU_SECONDS = 4
WORKER_TIMEOUT_SECONDS = 8
_MEDIA = {"image/jpeg": "JPEG", "image/png": "PNG", "application/pdf": "PDF"}
_OK, _INVALID, _UNAVAILABLE = 0, 11, 12
_WINDOWS_JOB = None  # Keep the worker's job handle alive until process exit.


@dataclass(frozen=True, slots=True)
class ValidatedEvidence:
    filename: str = field(repr=False)
    media_type: str
    size_bytes: int
    sha256: str
    description: str | None = field(repr=False)
    content: bytes = field(repr=False)

    def __post_init__(self) -> None:
        # Frozen fields cannot hide an aliased mutable bytearray/string subclass.
        if (type(self.content) is not bytes or type(self.filename) is not str
                or type(self.media_type) is not str or type(self.size_bytes) is not int
                or type(self.sha256) is not str
                or (self.description is not None and type(self.description) is not str)):
            from .errors import FlowError
            raise FlowError("VALIDATION_ERROR")


def _worker_environment() -> dict[str, str]:
    if os.name == "nt":
        system_root = os.environ.get("SystemRoot")
        return {"SystemRoot": system_root} if system_root else {}
    return {}


def _run_parser(content: bytes, media_type: str) -> int:
    result = _UNAVAILABLE
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(Path(__file__).resolve()), media_type],
            input=content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=_worker_environment(), cwd=Path(sys.executable).resolve().parent,
            timeout=WORKER_TIMEOUT_SECONDS, check=False, close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        result = completed.returncode
    except subprocess.TimeoutExpired:
        # subprocess.run kills and reaps its worker before raising.
        result = _INVALID
    except (OSError, ValueError, subprocess.SubprocessError):
        result = _UNAVAILABLE
    return result


def validate_evidence(content: bytes, filename: str, media_type: str,
                      description: str | None = None) -> ValidatedEvidence:
    from .errors import FlowError

    if (type(content) is not bytes or type(filename) is not str
            or not 1 <= len(filename) <= 200
            or type(media_type) is not str
            or (description is not None
                and (type(description) is not str or len(description) > 2000))):
        raise FlowError("VALIDATION_ERROR")
    if len(content) > MAX_FILE_BYTES:
        raise FlowError("REQUEST_TOO_LARGE")
    if not content or media_type not in _MEDIA:
        raise FlowError("UNSUPPORTED_MEDIA_TYPE")
    outcome = _run_parser(content, media_type)
    # Raise outside exception handlers: no parser/subprocess cause or context.
    if outcome == _UNAVAILABLE:
        raise FlowError("INTERNAL_ERROR")
    if outcome != _OK:
        raise FlowError("UNSUPPORTED_MEDIA_TYPE")
    return ValidatedEvidence(filename, media_type, len(content),
                             hashlib.sha256(content).hexdigest(), description, content)


def _apply_windows_limits() -> None:
    import ctypes
    from ctypes import wintypes

    class BasicLimit(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class ExtendedLimit(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                               ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError("Worker limits unavailable")
    limits = ExtendedLimit()
    limits.BasicLimitInformation.LimitFlags = 0x2 | 0x8 | 0x100
    limits.BasicLimitInformation.PerProcessUserTimeLimit = WORKER_CPU_SECONDS * 10_000_000
    limits.BasicLimitInformation.ActiveProcessLimit = 1
    limits.ProcessMemoryLimit = WORKER_MEMORY_BYTES
    if (not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
            or not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess())):
        kernel.CloseHandle(job)
        raise OSError("Worker limits unavailable")
    global _WINDOWS_JOB
    _WINDOWS_JOB = job


def _apply_limits() -> None:
    if os.name == "nt":
        _apply_windows_limits()
    elif sys.platform.startswith("linux"):
        import resource
        for name, requested in ((resource.RLIMIT_AS, WORKER_MEMORY_BYTES),
                                (resource.RLIMIT_CPU, WORKER_CPU_SECONDS),
                                (resource.RLIMIT_CORE, 0)):
            _, hard = resource.getrlimit(name)
            limit = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
            resource.setrlimit(name, (limit, limit))
    else:
        raise OSError("Worker limits unavailable")


def _parse_image(content: bytes, declared: str) -> None:
    import warnings
    from PIL import Image, ImageFile

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    with Image.open(io.BytesIO(content), formats=[declared]) as image:
        if image.format != declared:
            raise ValueError("Invalid format")
        image.verify()
    total_pixels = 0
    with Image.open(io.BytesIO(content), formats=[declared]) as image:
        frames = getattr(image, "n_frames", 1)
        if not 1 <= frames <= MAX_IMAGE_FRAMES:
            raise ValueError("Image processing bound")
        for index in range(frames):
            image.seek(index)
            width, height = image.size
            total_pixels += width * height
            if width <= 0 or height <= 0 or total_pixels > MAX_IMAGE_PIXELS:
                raise ValueError("Image processing bound")
            image.load()


def _parse_pdf(content: bytes) -> None:
    from pypdf import PdfReader, Configuration, apply_configuration

    configuration = Configuration(
        maximum_declared_stream_length=MAX_FILE_BYTES,
        array_based_stream_maximum_output_length=MAX_STREAM_BYTES,
        jbig2_maximum_output_length=MAX_STREAM_BYTES,
        lzw_maximum_output_length=MAX_STREAM_BYTES,
        run_length_maximum_output_length=MAX_STREAM_BYTES,
        zlib_maximum_output_length=MAX_STREAM_BYTES,
        image_maximum_buffer_size=MAX_STREAM_BYTES,
        page_tree_maximum_entries=MAX_PDF_OBJECTS,
        page_tree_maximum_depth=50,
        jbig2dec_binary=None,
    )
    with apply_configuration(configuration):
        reader = PdfReader(io.BytesIO(content), strict=True)
        _walk_pdf(reader)


def _walk_pdf(reader) -> None:
    from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, StreamObject

    if reader.is_encrypted or reader.trailer["/Root"].get("/Type") != "/Catalog":
        raise ValueError("Unsupported PDF structure")
    if not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
        raise ValueError("PDF processing bound")
    pending = [reader.trailer]
    seen_references: set[tuple[int, int]] = set()
    seen_objects: set[int] = set()
    decoded_bytes = 0
    visited = 0
    while pending:
        obj = pending.pop()
        visited += 1
        if visited > MAX_PDF_OBJECTS:
            raise ValueError("PDF processing bound")
        if isinstance(obj, IndirectObject):
            key = (obj.idnum, obj.generation)
            if key in seen_references:
                continue
            seen_references.add(key)
            obj = obj.get_object()
        if isinstance(obj, (DictionaryObject, ArrayObject)):
            if id(obj) in seen_objects:
                continue
            seen_objects.add(id(obj))
        if isinstance(obj, StreamObject):
            data = obj.get_data()
            decoded_bytes += len(data)
            if len(data) > MAX_STREAM_BYTES or decoded_bytes > MAX_TOTAL_STREAM_BYTES:
                raise ValueError("PDF processing bound")
        if isinstance(obj, DictionaryObject):
            pending.extend(obj.values())
        elif isinstance(obj, ArrayObject):
            pending.extend(obj)
    operation_count = 0
    for page in reader.pages:
        if page.get("/Type") != "/Page":
            raise ValueError("Invalid PDF page")
        contents = page.get_contents()
        if contents is not None:
            operation_count += len(contents.operations)
            if operation_count > MAX_CONTENT_OPERATIONS:
                raise ValueError("PDF processing bound")


def _worker() -> int:
    try:
        _apply_limits()
    except Exception:
        return _UNAVAILABLE
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in _MEDIA:
            return _INVALID
        content = sys.stdin.buffer.read(MAX_FILE_BYTES + 1)
        if not 1 <= len(content) <= MAX_FILE_BYTES:
            return _INVALID
        if sys.argv[1] == "application/pdf":
            _parse_pdf(content)
        else:
            _parse_image(content, _MEDIA[sys.argv[1]])
    except (ImportError, ModuleNotFoundError):
        return _UNAVAILABLE
    except Exception:
        return _INVALID
    return _OK


if __name__ == "__main__":
    # No traceback, parser warning or personal bytes are emitted to the parent.
    sys.exit(_worker())
