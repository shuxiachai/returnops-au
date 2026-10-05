"""A1.05 offline synthetic preparation; no persistence or execution authority.

FR-001/004/006/007/008, NFR-001/003/006/009; UC-02 and the A1 fixed-packet
handoff. Existing frozen DTOs remain the single schema/capacity oracle.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

from returnops_domain.errors import FlowError
from returnops_domain.founder_codec import digest, validate
from returnops_domain.founder_history_types import proposal_bindings


OFFLINE_LABEL = "OFFLINE_SYNTHETIC_NON_EXECUTABLE"
INVENTORY_LABEL = "OFFLINE_SYNTHETIC_SOURCE_INVENTORY"
_IDENTITIES = (
    "case_id", "input_version", "proposal_id", "proposal_version",
    "corpus_version", "original_statement_id",
)
_CITATION_BINDINGS = (
    "passage_id", "document_id", "source_version", "corpus_version",
    "content_sha256", "location",
)


class OfflinePreparationError(ValueError):
    """Static diagnostic only: do not include customer/source payloads."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OfflinePreparationError(message)


def _keys(value: object, required: set[str], optional: set[str] = frozenset()) -> None:
    _require(type(value) is dict and required <= value.keys()
             and value.keys() <= required | optional, "Incomplete or unknown inventory fields.")


def _material(entry: dict, *, attachment: bool = False) -> dict:
    fields = {"value", "fingerprint"} | ({"content"} if attachment else set())
    _keys(entry, fields)
    value = entry["value"]
    _require(type(value) is dict and entry["fingerprint"] == digest(value),
             "Source fingerprint does not match the complete DTO.")
    if attachment:
        content = entry["content"]
        _require(type(content) is bytes, "Retained synthetic attachment bytes are required.")
        _require(len(content) == value["size_bytes"]
                 and sha256(content).hexdigest() == value["sha256"],
                 "Attachment bytes do not match their retained metadata.")
    return value


def _complete_collection(candidate: list, entries: list, identity: str,
                         *, attachment: bool = False) -> None:
    _require(type(entries) is list, "Source inventory must retain complete collections.")
    values = [_material(entry, attachment=attachment) for entry in entries]
    ids = [value[identity] for value in values]
    _require(len(ids) == len(set(ids)), "Duplicate source inventory identities.")
    # Equality deliberately preserves the complete ordered DTOs, not previews or
    # only the subset referenced by the candidate's evidence matrix. The shared
    # finite codec distinguishes booleans from numbers and normalizes 1.0 to 1.
    _require(digest(candidate) == digest(values),
             "Candidate omits or alters retained source material.")


def assemble_offline_proposal(candidate_bundle: dict, source_inventory: dict) -> dict:
    """Return a labelled deep copy of one fully sourced synthetic proposal.

    The inventory must be captured independently of the candidate. Its complete
    DTO fingerprints use founder_codec.digest (history/finite-v2); they prove
    internal fixture consistency only, never retention, authorization, currency,
    accepted order projection or corpus review. Attachment content is checked
    but is not copied into the unchanged HistoricalProposalBundle wire shape.

    Missing/altered retained source material and exceeded DTO capacity reject
    the entire draft. Complete business MISSING/CONFLICTING/NO_MATCH material is
    preserved for future independent Risk review, without creating a review.
    """
    invalid = False
    try:
        bundle = validate("HistoricalProposalBundle", candidate_bundle)
        proposal_bindings(bundle)
        _keys(source_inventory, set(_IDENTITIES) | {
            "label", "statements", "attachments", "order_lookup", "retrieval_result",
        }, {"image_observations"})
        _require(source_inventory["label"] == INVENTORY_LABEL,
                 "An explicitly synthetic offline inventory is required.")
        packet = bundle["packet"]
        _require(digest({key: packet[key] for key in _IDENTITIES})
                 == digest({key: source_inventory[key] for key in _IDENTITIES}),
                 "Candidate identity differs from the independent inventory.")
        run = packet["model_run"]
        _require(run["provider_id"] == "provider-fixture"
                 and run["model_id"] == "fixture-no-live-model"
                 and run["input_tokens"] == run["output_tokens"] == 0,
                 "Only explicit zero-token model fixtures are supported.")
        _complete_collection(bundle["statements"], source_inventory["statements"], "statement_id")
        _complete_collection(bundle["attachments"], source_inventory["attachments"],
                             "evidence_id", attachment=True)
        for name in ("order_lookup", "retrieval_result", "image_observations"):
            _require((name in bundle) == (name in source_inventory),
                     "Candidate omits or invents an optional source DTO.")
            if name in bundle:
                _require(digest(bundle[name]) == digest(_material(source_inventory[name])),
                         "Candidate omits or alters a complete source DTO.")

        passages = bundle["retrieval_result"]["passages"]
        by_id = {passage["passage_id"]: passage for passage in passages}
        _require(len(by_id) == len(passages), "Duplicate retained passage identities.")
        for passage in passages:
            _require(passage["is_synthetic"] is True,
                     "Only explicitly synthetic passage fixtures are supported.")
            _require(sha256(passage["content"].encode("utf-8")).hexdigest()
                     == passage["content_sha256"], "Passage content hash does not match retained text.")
        checks = {check["citation_id"]: check for check in bundle["citation_verification"]["checks"]}
        for citation in packet["citations"]:
            passage = by_id.get(citation["passage_id"])
            _require(passage is not None and all(
                citation[key] == passage[key] for key in _CITATION_BINDINGS),
                "Citation does not bind to the exact retained passage.")
            _require(checks[citation["citation_id"]]["result"] == "VALID",
                     "Each cited passage requires an explicit VALID fixture check.")
    except (FlowError, KeyError, TypeError, UnicodeError, RecursionError):
        invalid = True
    # Leave the handler before constructing the rejection: even a suppressed
    # UnicodeError context can retain the complete source text in .object.
    if invalid:
        raise OfflinePreparationError("Invalid or incomplete offline preparation material.") from None
    # A separate wrapper carries the label; the frozen bundle gains no fields,
    # trusted capability, current pointer, approval, command or synthetic event.
    return {"label": OFFLINE_LABEL, "bundle": deepcopy(bundle)}
