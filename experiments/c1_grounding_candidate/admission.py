"""C1 exact-byte corpus admission, isolated from all application execution.

The trusted manifest SHA-256 is *external configuration*: A must check a genuine
non-author review against exact bytes before supplying that pin. A hash proves
integrity, not identity, approval authenticity, legal correctness or claim support.
Never derive the trusted pin automatically from an uploaded/caller-supplied file.

This module performs no network requests. Pending source-selection approval is
not exact-passage approval. Source text remains untrusted after admission; it
cannot grant authority, change review metadata or create a business decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Callable
from urllib.parse import urlsplit

from .grounding import (
    GroundingCandidate, GroundingError, _CATEGORIES, _LOAD_TIME, _MAX_BYTES,
    _categories, _encoded, _unique, _utc_now, _valid,
)


_MANIFEST_FILE = "admission-manifest.json"
_CORPUS_FILE = "corpus.json"
_HASH = re.compile(r"[a-f0-9]{64}")
_IDENTITY = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
_REVIEW_URL = re.compile(
    r"https://github\.com/shuxiachai/returnops-au/pull/[1-9][0-9]*"
    r"#pullrequestreview-[1-9][0-9]*"
)


def _require(condition):
    if not condition:
        raise ValueError("invalid admission data")


def _shape(value, fields):
    _require(type(value) is dict and set(value) == set(fields))


def _hash(value):
    return type(value) is str and _HASH.fullmatch(value) is not None


def _invalid_constant(_value):
    raise ValueError("nonfinite JSON")


def _parse(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                      parse_constant=_invalid_constant)


def _read_file(directory_fd, name):
    # Names are constants, not manifest paths. O_NOFOLLOW blocks a symlink leaf;
    # dir_fd anchors both reads to the same opened directory even if renamed.
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                 dir_fd=directory_fd)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        _require(stat.S_ISREG(info.st_mode) and 1 <= info.st_size <= _MAX_BYTES)
        raw = stream.read(_MAX_BYTES + 1)
    _require(1 <= len(raw) <= _MAX_BYTES)
    return raw


@dataclass(frozen=True, slots=True)
class AdmittedCorpus:
    """Immutable receipt from load_reviewed_corpus, not an approval authority."""

    corpus_version: str
    corpus_sha256: str
    manifest_sha256: str
    snapshot: bytes


def _validate_manifest(manifest):
    _shape(manifest, {"format_version", "corpus_file", "corpus_sha256",
                      "corpus_version", "review", "coverage", "passages"})
    _require(type(manifest["format_version"]) is int and manifest["format_version"] == 1)
    _require(manifest["corpus_file"] == _CORPUS_FILE and _hash(manifest["corpus_sha256"]))
    _require(type(manifest["corpus_version"]) is str
             and 1 <= len(manifest["corpus_version"]) <= 80)
    review = manifest["review"]
    _shape(review, {"status", "author", "reviewer", "reviewed_at", "evidence_uri"})
    if review["status"] != "APPROVED_EXACT_BYTES":
        raise GroundingError("UNREVIEWED_CORPUS")
    _require(all(type(review[key]) is str and _IDENTITY.fullmatch(review[key])
                 for key in ("author", "reviewer")))
    _require(review["author"].casefold() != review["reviewer"].casefold())
    _require(_valid("Timestamp", review["reviewed_at"]))
    _require(type(review["evidence_uri"]) is str
             and _REVIEW_URL.fullmatch(review["evidence_uri"]) is not None)
    coverage = manifest["coverage"]
    _shape(coverage, {"issue_categories", "conflicts_reviewed"})
    _require(_categories(coverage["issue_categories"])
             and set(coverage["issue_categories"]) == _CATEGORIES
             and coverage["conflicts_reviewed"] is True)
    _require(type(manifest["passages"]) is list and 1 <= len(manifest["passages"]) <= 100)
    expected = {}
    for item in manifest["passages"]:
        _shape(item, {"passage_id", "content_sha256"})
        _require(_valid("Id", item["passage_id"]) and _hash(item["content_sha256"])
                 and item["passage_id"] not in expected)
        expected[item["passage_id"]] = item["content_sha256"]
    return expected


def _validate_corpus(data, manifest, expected):
    _shape(data, {"format_version", "corpus_version", "is_synthetic", "review_status",
                  "passages", "conflicts"})
    _require(type(data["format_version"]) is int and data["format_version"] == 1
             and type(data["is_synthetic"]) is bool
             and data["corpus_version"] == manifest["corpus_version"]
             and data["review_status"] in ("PENDING_HUMAN_REVIEW", "APPROVED_EXACT_BYTES"))
    # Payload status is only descriptive. Admission derives exclusively from the
    # separately pinned manifest and verified review, never this string/content.
    _require(type(data["passages"]) is list and 1 <= len(data["passages"]) <= 100)
    entries, documents, actual = {}, {}, {}
    categories, types = set(), set()
    reviewed_on = datetime.fromisoformat(manifest["review"]["reviewed_at"].replace("Z", "+00:00")).date()
    for entry in data["passages"]:
        _shape(entry, {"issue_categories", "passage"})
        _require(_categories(entry["issue_categories"]))
        passage = entry["passage"]
        _require(type(passage) is dict and "retrieved_at" not in passage)
        _require(_valid("PolicyPassage", {**passage, "retrieved_at": _LOAD_TIME}))
        pid = passage["passage_id"]
        _require(pid not in entries and passage["corpus_version"] == data["corpus_version"]
                 and sha256(passage["content"].encode("utf-8")).hexdigest() == passage["content_sha256"]
                 and date.fromisoformat(passage["accessed_on"]) <= reviewed_on)
        if passage["is_synthetic"]:
            _require(passage["source_uri"].startswith("urn:returnops:synthetic:")
                     and "synthetic" in passage["title"].casefold())
        else:
            uri = urlsplit(passage["source_uri"])
            _require(uri.scheme == "https" and bool(uri.hostname)
                     and uri.username is None and uri.password is None)
        # A document cannot change from store policy to guidance (or from real
        # to synthetic) between passages while retaining its document identity.
        identity = (passage["source_type"], passage["is_synthetic"], passage["source_version"],
                    None if passage["is_synthetic"] else passage["source_uri"].split("#", 1)[0])
        previous = documents.setdefault(passage["document_id"], identity)
        _require(identity == previous)
        entries[pid], actual[pid] = entry, passage["content_sha256"]
        categories.update(entry["issue_categories"])
        types.add(passage["source_type"])
    _require(actual == expected and categories == _CATEGORIES
             and types == {"STORE_POLICY", "REVIEWED_CONSUMER_GUIDANCE"}
             and data["is_synthetic"] == all(e["passage"]["is_synthetic"] for e in entries.values()))
    _require(type(data["conflicts"]) is list and 1 <= len(data["conflicts"]) <= 100)
    conflicts = set()
    cross_source_conflict = False
    for conflict in data["conflicts"]:
        _shape(conflict, {"conflict_id", "passage_ids", "issue_categories", "message"})
        ids = conflict["passage_ids"]
        _require(_valid("Id", conflict["conflict_id"]) and conflict["conflict_id"] not in conflicts
                 and _categories(conflict["issue_categories"])
                 and type(ids) is list and 2 <= len(ids) <= 100
                 and all(type(pid) is str and pid in entries for pid in ids)
                 and len(set(ids)) == len(ids)
                 and type(conflict["message"]) is str and 1 <= len(conflict["message"]) <= 1000)
        _require(all(set(conflict["issue_categories"]).issubset(entries[pid]["issue_categories"])
                     for pid in ids))
        cross_source_conflict |= {entries[pid]["passage"]["source_type"] for pid in ids} == {
            "STORE_POLICY", "REVIEWED_CONSUMER_GUIDANCE"}
        conflicts.add(conflict["conflict_id"])
    _require(cross_source_conflict)
    # This proves registered coverage only, not semantic completeness. The
    # non-author review must decide which real source differences are material.


def load_reviewed_corpus(directory: Path | str, *, trusted_manifest_sha256: str) -> AdmittedCorpus:
    """Read a bounded two-file bundle and pin immutable, validated bytes.

    Caller configuration must come from genuine external review, not an upload,
    a model response or the bundle itself. No authentic review is claimed by
    merely passing tests using clearly synthetic fixture approvals.
    """
    try:
        if not _hash(trusted_manifest_sha256):
            raise GroundingError("UNTRUSTED_MANIFEST")
        if not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")):
            raise GroundingError("UNSUPPORTED_FILESYSTEM")
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            raw_manifest = _read_file(fd, _MANIFEST_FILE)
            if sha256(raw_manifest).hexdigest() != trusted_manifest_sha256:
                raise GroundingError("UNTRUSTED_MANIFEST")
            manifest = _parse(raw_manifest)
            expected = _validate_manifest(manifest)
            raw_corpus = _read_file(fd, _CORPUS_FILE)
        finally:
            os.close(fd)
        _require(sha256(raw_corpus).hexdigest() == manifest["corpus_sha256"])
        data = _parse(raw_corpus)
        _validate_corpus(data, manifest, expected)
        return AdmittedCorpus(data["corpus_version"], manifest["corpus_sha256"],
                              trusted_manifest_sha256, _encoded(data))
    except GroundingError as error:
        error_code = error.code
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        error_code = "INVALID_ADMISSION"
    # Raise after leaving the handler: from None alone hides traceback display
    # but still retains JSONDecodeError.doc / OSError paths in __context__.
    raise GroundingError(error_code) from None


class ReviewedGroundingCandidate(GroundingCandidate):
    """Existing C1 wire behavior behind exact-byte admission; still offline.

    Construct from_directory, never from untrusted bytes. This reuses ranking,
    conflict closure and citation checks without changing application imports.
    """

    def __init__(self, directory: Path | str, *, trusted_manifest_sha256: str,
                 top_k: int = 3, clock: Callable[[], str] = _utc_now):
        if type(top_k) is not int or not 1 <= top_k <= 100 or not callable(clock):
            raise GroundingError("INVALID_ADMISSION")
        admitted = load_reviewed_corpus(directory, trusted_manifest_sha256=trusted_manifest_sha256)
        self._version = admitted.corpus_version
        self._snapshot = admitted.snapshot
        self._raw_sha256 = admitted.corpus_sha256
        self._manifest_sha256 = admitted.manifest_sha256
        self._top_k, self._clock = top_k, clock

    @classmethod
    def from_directory(cls, directory: Path | str, *, trusted_manifest_sha256: str,
                       top_k: int = 3, clock: Callable[[], str] = _utc_now):
        return cls(directory, trusted_manifest_sha256=trusted_manifest_sha256,
                   top_k=top_k, clock=clock)

    @classmethod
    def from_bytes(cls, *args, **kwargs):
        raise GroundingError("UNTRUSTED_MANIFEST")

    @property
    def manifest_sha256(self):
        return self._manifest_sha256

    def verify_citations(self, request: dict) -> dict:
        result = super().verify_citations(request)
        for check in result["checks"]:
            if check["result"] == "VALID":
                check["message"] = (
                    "Citation matches the pinned admitted corpus; claim support, "
                    "case applicability and prior retrieval membership are not assessed."
                )
        return self._output("CitationVerificationResult", result)
