"""Deterministic, synthetic-only preparation for the frozen C1 wire ports.

No network, model, database, provider, authority or workflow integration exists.
The corpus is untrusted data. A successful citation check is not a risk decision.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable

from jsonschema import Draft202012Validator, FormatChecker


class GroundingError(ValueError):
    """Safe component failure, distinct from a valid NO_MATCH result."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


_DEFS = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts/v1/schemas.json")
    .read_text(encoding="utf-8")
)["$defs"]
_VALIDATORS = {
    name: Draft202012Validator(
        {"$ref": f"#/$defs/{name}", "$defs": _DEFS},
        format_checker=FormatChecker(),
    )
    for name in (
        "Id", "Timestamp", "PolicyPassage", "RetrievalRequest", "RetrievalResult",
        "CitationVerificationRequest", "CitationVerificationResult",
    )
}
_CATEGORIES = frozenset({"FAULTY_OR_QUALITY_ISSUE", "WRONG_ITEM", "CHANGE_OF_MIND"})
_STOP = frozenset("a an and are as at be by for from in is it of on or that the this to with".split())
_LOAD_TIME = "2000-01-01T00:00:00Z"  # Shape check only; never returned as retrieval time.
_MAX_BYTES = 2 * 1024 * 1024
_MESSAGES = {
    "VALID": "Citation matches the pinned synthetic corpus; claim support is not assessed.",
    "NOT_FOUND": "Passage/document identity is absent from the pinned corpus.",
    "VERSION_MISMATCH": "Citation source or corpus version differs from the pinned passage.",
    "HASH_MISMATCH": "Citation hash differs from the exact stored UTF-8 content hash.",
    "LOCATION_MISMATCH": "Citation location differs from the pinned passage location.",
}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _encoded(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _copy(value):
    return json.loads(_encoded(value))


def _valid(name, value):
    return _VALIDATORS[name].is_valid(value)


def _tokens(value):
    return {token for token in re.findall(r"\w+", value.casefold())
            if len(token) >= 2 and token not in _STOP}


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _categories(value):
    return (type(value) is list and 1 <= len(value) <= 3
            and all(type(item) is str and item in _CATEGORIES for item in value)
            and len(set(value)) == len(value))


def _load(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= _MAX_BYTES:
        raise ValueError("corpus bytes")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    if type(data) is not dict or set(data) != {
        "format_version", "corpus_version", "is_synthetic", "review_status", "passages", "conflicts"
    }:
        raise ValueError("corpus shape")
    if (type(data["format_version"]) is not int or data["format_version"] != 1
            or data["is_synthetic"] is not True
            or data["review_status"] != "PENDING_HUMAN_REVIEW"
            or type(data["corpus_version"]) is not str
            or not 1 <= len(data["corpus_version"]) <= 80):
        raise ValueError("corpus metadata")
    if type(data["passages"]) is not list or not 1 <= len(data["passages"]) <= 100:
        raise ValueError("passage capacity")
    passages = {}
    for entry in data["passages"]:
        if (type(entry) is not dict or set(entry) != {"issue_categories", "passage"}
                or not _categories(entry["issue_categories"])):
            raise ValueError("entry shape")
        passage = entry["passage"]
        if type(passage) is not dict or "retrieved_at" in passage:
            raise ValueError("stored passage shape")
        if not _valid("PolicyPassage", {**passage, "retrieved_at": _LOAD_TIME}):
            raise ValueError("passage schema")
        if (passage["is_synthetic"] is not True
                or not passage["source_uri"].startswith("urn:returnops:")
                or passage["corpus_version"] != data["corpus_version"]
                or sha256(passage["content"].encode("utf-8")).hexdigest() != passage["content_sha256"]
                or passage["passage_id"] in passages):
            raise ValueError("passage integrity")
        passages[passage["passage_id"]] = entry
    if type(data["conflicts"]) is not list or len(data["conflicts"]) > 100:
        raise ValueError("conflict capacity")
    conflict_ids = set()
    for conflict in data["conflicts"]:
        if type(conflict) is not dict or set(conflict) != {
            "conflict_id", "passage_ids", "issue_categories", "message"
        }:
            raise ValueError("conflict shape")
        ids = conflict["passage_ids"]
        if (not _valid("Id", conflict["conflict_id"])
                or conflict["conflict_id"] in conflict_ids
                or not _categories(conflict["issue_categories"])
                or type(ids) is not list or not 2 <= len(ids) <= 100
                or any(type(pid) is not str or pid not in passages for pid in ids)
                or len(set(ids)) != len(ids)
                or type(conflict["message"]) is not str or not 1 <= len(conflict["message"]) <= 1000
                or any(not set(conflict["issue_categories"]).issubset(passages[pid]["issue_categories"])
                       for pid in ids)):
            raise ValueError("conflict integrity")
        conflict_ids.add(conflict["conflict_id"])
    # Keep serialized immutable snapshots: caller mutations cannot change provenance.
    return data["corpus_version"], _encoded(data)


class GroundingCandidate:
    """One pinned synthetic corpus generation; construct via from_bytes.

    top_k bounds the ranked seed set, not required conflict counterparts. Up to
    100 passages can be returned when preserving explicitly registered conflicts.
    This is a source-checkout experiment, not a packaged runtime service.
    """

    def __init__(self, raw: bytes, *, top_k: int = 3, clock: Callable[[], str] = _utc_now):
        failed = False
        try:
            if type(top_k) is not int or not 1 <= top_k <= 100 or not callable(clock):
                raise ValueError("configuration")
            version, snapshot = _load(raw)
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            failed = True
        if failed:
            raise GroundingError("INVALID_CORPUS") from None
        self._version = version
        self._snapshot = snapshot
        self._top_k = top_k
        self._clock = clock
        self._raw_sha256 = sha256(raw).hexdigest()

    @classmethod
    def from_bytes(cls, raw: bytes, *, top_k: int = 3, clock: Callable[[], str] = _utc_now):
        return cls(raw, top_k=top_k, clock=clock)

    @property
    def corpus_sha256(self):
        """Exact input-file bytes, not a claim of human approval or authenticity."""
        return self._raw_sha256

    def _request(self, name, request):
        failed = False
        try:
            if type(request) is not dict or not _valid(name, request):
                raise ValueError("request schema")
            result = _copy(request)
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            failed = True
        if failed:
            raise GroundingError("INVALID_REQUEST") from None
        if result["corpus_version"] != self._version:
            raise GroundingError("CORPUS_UNAVAILABLE")
        return result

    def _time(self):
        failed = False
        try:
            value = self._clock()
            if not _valid("Timestamp", value):
                failed = True
        except Exception:
            failed = True
        if failed:
            raise GroundingError("INVALID_CLOCK") from None
        return value

    @staticmethod
    def _output(name, value):
        if not _valid(name, value):
            raise GroundingError("INVALID_OUTPUT")
        return value

    def retrieve(self, request: dict) -> dict:
        request = self._request("RetrievalRequest", request)
        stamp = self._time()
        corpus = json.loads(self._snapshot)
        category = request["issue_category"]
        entries = {e["passage"]["passage_id"]: e for e in corpus["passages"]
                   if category == "UNCLEAR" or category in e["issue_categories"]}
        query_tokens = _tokens(request["query"])
        scores = {pid: len(query_tokens & _tokens(e["passage"]["content"]))
                  for pid, e in entries.items()}
        ranked = sorted((pid for pid, score in scores.items() if score > 0),
                        key=lambda pid: (-scores[pid], pid))
        selected = set(ranked[:self._top_k])
        # Register-triggered conflict closure, not semantic conflict detection.
        # Start from ALL positive hits so top-k cannot silently hide a known conflict.
        relevant = set(ranked)
        conflicts = sorted((c for c in corpus["conflicts"]
                            if category == "UNCLEAR" or category in c["issue_categories"]),
                           key=lambda c: c["conflict_id"])
        activated = set()
        changed = True
        while changed:
            changed = False
            for c in conflicts:
                if c["conflict_id"] not in activated and relevant.intersection(c["passage_ids"]):
                    activated.add(c["conflict_id"])
                    selected.update(c["passage_ids"])
                    relevant.update(c["passage_ids"])
                    changed = True
        ordered = sorted(selected, key=lambda pid: (-scores[pid], pid))
        result = {key: request[key] for key in ("case_id", "input_version", "corpus_version")}
        result.update({
            "status": "MATCHED" if ordered else "NO_MATCH",
            "passages": [{**entries[pid]["passage"], "retrieved_at": stamp} for pid in ordered],
            "conflicts": [c["message"] for c in conflicts if c["conflict_id"] in activated],
            "retrieved_at": stamp,
        })
        return self._output("RetrievalResult", result)

    def verify_citations(self, request: dict) -> dict:
        request = self._request("CitationVerificationRequest", request)
        ids = [c["citation_id"] for c in request["citations"]]
        if len(set(ids)) != len(ids):
            raise GroundingError("INVALID_REQUEST")
        stamp = self._time()
        passages = {e["passage"]["passage_id"]: e["passage"]
                    for e in json.loads(self._snapshot)["passages"]}
        checks = []
        for citation in request["citations"]:
            passage = passages.get(citation["passage_id"])
            if passage is None or citation["document_id"] != passage["document_id"]:
                outcome = "NOT_FOUND"
            elif any(citation[k] != passage[k] for k in ("source_version", "corpus_version")):
                outcome = "VERSION_MISMATCH"
            elif citation["content_sha256"] != passage["content_sha256"]:
                outcome = "HASH_MISMATCH"
            elif citation["location"] != passage["location"]:
                outcome = "LOCATION_MISMATCH"
            else:
                outcome = "VALID"
            checks.append({"citation_id": citation["citation_id"], "result": outcome,
                           "message": _MESSAGES[outcome]})
        result = {key: request[key] for key in (
            "case_id", "input_version", "proposal_id", "proposal_version", "corpus_version"
        )}
        result.update({"checks": checks, "checked_at": stamp})
        return self._output("CitationVerificationResult", result)
