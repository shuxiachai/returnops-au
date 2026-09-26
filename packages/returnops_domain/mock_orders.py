"""Explicitly loaded immutable synthetic catalogue and scoped A1.04 provider.

Importing this module does not load catalogue/schema files or create state.
Neither lookup nor catalogue replacement writes files, a DB, orders or cases.
"""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import resources
import json
import re
from .canonical import decode_document, digest, encode_document
from .order_ports import (
    CatalogueMetadata, CatalogueRecord, CurrentOrderContext, OrderLookupError,
    OrderReadContext, OrderSource, valid_id,
)

_MESSAGES = {
    "MATCHED": "A synthetic order snapshot matched the authorized scope.",
    "NOT_FOUND": "No matching order was found in the authorized scope.",
    "CONFLICT": "The authorized order reference is ambiguous.",
    "AUTHORITY_DENIED": "The current service is not permitted to read this provider.",
    "PROVIDER_FAILURE": "The synthetic order source is unavailable.",
}
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")


def _metadata_valid(value):
    return (type(value) is CatalogueMetadata and type(value.format_version) is int
        and value.format_version == 1 and valid_id(value.provider_id)
        and all(type(v) is str and _VERSION.fullmatch(v) for v in (value.dataset_version, value.provider_version))
        and type(value.dataset_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", value.dataset_sha256) is not None)


def _snapshot(value):
    from .wire import validate
    result = validate("OrderSnapshot", value, internal=True)
    ids = [line["line_item_id"] for line in result["line_items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Invalid synthetic line identity")
    return result


def _document(value):
    """Trusted configuration validation; callers sanitize any thrown detail."""
    if type(value) is not dict or set(value) != {"is_synthetic", "format_version", "dataset_version", "provider_id", "provider_version", "orders"}:
        raise ValueError("Invalid synthetic catalogue shape")
    if value["is_synthetic"] is not True or type(value["format_version"]) is not int or value["format_version"] != 1:
        raise ValueError("Invalid synthetic catalogue format")
    if not valid_id(value["provider_id"]) or any(type(value[k]) is not str or not _VERSION.fullmatch(value[k]) for k in ("dataset_version", "provider_version")):
        raise ValueError("Invalid synthetic catalogue identity")
    if type(value["orders"]) is not list or not 1 <= len(value["orders"]) <= 1000:
        raise ValueError("Invalid synthetic catalogue size")
    records = []; normalized = []; snapshot_ids = set(); order_ids = set()
    for row in value["orders"]:
        if type(row) is not dict or set(row) != {"store_id", "owner_principal_id", "order_reference", "snapshot"}:
            raise ValueError("Invalid synthetic record shape")
        if not valid_id(row["store_id"]) or not valid_id(row["owner_principal_id"]):
            raise ValueError("Invalid synthetic scope")
        if type(row["order_reference"]) is not str or not 1 <= len(row["order_reference"]) <= 120:
            raise ValueError("Invalid synthetic reference")
        snapshot = _snapshot(row["snapshot"])
        if (snapshot["provider_id"] != value["provider_id"] or snapshot["snapshot_id"] in snapshot_ids
                or snapshot["order_id"] in order_ids):
            raise ValueError("Duplicate or mismatched synthetic snapshot identity")
        snapshot_ids.add(snapshot["snapshot_id"]); order_ids.add(snapshot["order_id"])
        normalized.append({**row, "snapshot": snapshot})
        records.append(CatalogueRecord(row["store_id"], row["owner_principal_id"], row["order_reference"], encode_document(snapshot)))
    content = {**value, "orders": normalized}
    metadata = CatalogueMetadata(value["format_version"], value["dataset_version"], value["provider_id"], value["provider_version"], digest(content, "synthetic-orders/v1"))
    return metadata, tuple(records)

@dataclass(frozen=True, slots=True, repr=False)
class SyntheticCatalogue:
    metadata: CatalogueMetadata
    _records: tuple[CatalogueRecord, ...] = field(repr=False)

    def __post_init__(self):
        failed = False
        try:
            if not _metadata_valid(self.metadata) or type(self._records) is not tuple:
                raise ValueError("Invalid immutable catalogue")
            if any(type(row) is not CatalogueRecord or type(row.snapshot_bytes) is not bytes for row in self._records):
                raise ValueError("Invalid immutable catalogue records")
            document = {"is_synthetic": True, "format_version": self.metadata.format_version,
                "dataset_version": self.metadata.dataset_version, "provider_id": self.metadata.provider_id,
                "provider_version": self.metadata.provider_version, "orders": [
                    {"store_id": row.store_id, "owner_principal_id": row.owner_principal_id,
                     "order_reference": row.order_reference, "snapshot": decode_document(row.snapshot_bytes)}
                    for row in self._records]}
            metadata, records = _document(document)
            if metadata != self.metadata or records != self._records:
                raise ValueError("Synthetic catalogue metadata does not match its content")
        except Exception:
            failed = True
        if failed:
            raise OrderLookupError("INVALID_CONFIGURATION") from None

    @classmethod
    def from_document(cls, value: Mapping) -> SyntheticCatalogue:
        """Explicit trusted load; no partial/empty fallback on malformed input."""
        failed = False
        try:
            metadata, records = _document(value)
        except Exception:
            failed = True
        if failed:
            raise OrderLookupError("INVALID_CONFIGURATION") from None
        return cls(metadata, records)

    def read_matches(self, context, order_reference):
        return tuple(row for row in self._records if row.store_id == context.store_id
            and row.owner_principal_id == context.owner_principal_id and row.order_reference == order_reference)

    def replacement(self, value: Mapping) -> SyntheticCatalogue:
        """Create a separate generation; the old instance remains unchanged.

        Known snapshot identity/version cannot silently acquire new content or
        ownership. Cross-process unseen histories still require Domain checks.
        """
        new = self.from_document(value)
        failed = False
        try:
            if (new.metadata.provider_id != self.metadata.provider_id
                    or new.metadata.dataset_version == self.metadata.dataset_version):
                raise ValueError("Replacement must identify a new dataset generation")
            old_by_id = {decode_document(row.snapshot_bytes)["snapshot_id"]: row for row in self._records}
            old_by_order = {decode_document(row.snapshot_bytes)["order_id"]: row for row in self._records}
            for row in new._records:
                snapshot = decode_document(row.snapshot_bytes)
                old = old_by_id.get(snapshot["snapshot_id"])
                existing_order = old_by_order.get(snapshot["order_id"])
                if existing_order is not None and old != existing_order:
                    raise ValueError("An order cannot silently change snapshot identity")
                if old is None:
                    continue
                previous = decode_document(old.snapshot_bytes)
                if (previous["order_id"] != snapshot["order_id"] or old.store_id != row.store_id
                        or old.owner_principal_id != row.owner_principal_id or old.order_reference != row.order_reference
                        or snapshot["snapshot_version"] < previous["snapshot_version"]
                        or (snapshot["snapshot_version"] == previous["snapshot_version"] and old.snapshot_bytes != row.snapshot_bytes)):
                    raise ValueError("Conflicting synthetic snapshot generation")
        except Exception:
            failed = True
        if failed:
            raise OrderLookupError("INVALID_CONFIGURATION") from None
        return new


def load_builtin_catalogue() -> SyntheticCatalogue:
    """Explicit package-resource read, independent of cwd and repository paths."""
    failed = False
    try:
        raw = resources.files("returnops_domain").joinpath("order_data", "synthetic_orders_v1.json").read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("Synthetic catalogue is too large")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result: raise ValueError("Duplicate catalogue member")
                result[key] = value
            return result
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        result = SyntheticCatalogue.from_document(document)
    except Exception:
        failed = True
    if failed:
        raise OrderLookupError("INVALID_CONFIGURATION") from None
    return result


class MockOrderProvider:
    """One trusted resolver/source binding; every query resolves current access."""
    def __init__(self, resolver: CurrentOrderContext, source: OrderSource, *, service_id: str):
        failed = False
        try:
            metadata = source.metadata
            if (not valid_id(service_id) or not _metadata_valid(metadata)
                    or not callable(resolver.resolve) or not callable(source.read_matches)):
                raise ValueError("Invalid order composition")
        except Exception:
            failed = True
        if failed:
            raise OrderLookupError("INVALID_CONFIGURATION") from None
        self._resolver, self._source = resolver, source
        self._service_id, self._metadata = service_id, metadata

    @property
    def metadata(self):
        return self._metadata

    def lookup(self, request: Mapping) -> dict:
        from .wire import validate
        failed = False
        try:
            if not isinstance(request, Mapping): raise ValueError("Invalid query")
            query = validate("OrderLookupRequest", dict(request))
        except Exception:
            failed = True
        if failed:
            raise OrderLookupError("INVALID_REQUEST") from None
        code = None
        try:
            context = self._resolver.resolve(query["case_id"], query["input_version"])
        except OrderLookupError as error:
            code = error.code if error.code in {"CASE_ACCESS_DENIED", "STALE_INPUT"} else "CONTEXT_UNAVAILABLE"
        except Exception:
            code = "CONTEXT_UNAVAILABLE"
        if code is not None:
            raise OrderLookupError(code) from None
        invalid_context = False
        try:
            if type(context) is not OrderReadContext: raise ValueError("Invalid context type")
            context.__post_init__()
        except Exception:
            invalid_context = True
        if invalid_context:
            raise OrderLookupError("CONTEXT_UNAVAILABLE") from None
        if context.case_id != query["case_id"] or context.service_id != self._service_id:
            raise OrderLookupError("CONTEXT_MISMATCH")
        if context.input_version != query["input_version"]:
            raise OrderLookupError("STALE_INPUT")
        if not context.can_read_orders or context.provider_id != self._metadata.provider_id:
            return self._result(query, "AUTHORITY_DENIED")
        if "order_reference" not in query:
            return self._result(query, "NOT_FOUND")
        failed = False
        try:
            if self._source.metadata != self._metadata:
                raise ValueError("Source generation changed inside provider instance")
            candidates = self._source.read_matches(context, query["order_reference"])
            if type(candidates) is not tuple or len(candidates) > 1000:
                raise ValueError("Invalid source observations")
            snapshots = []
            for row in candidates:
                if (type(row) is not CatalogueRecord or row.store_id != context.store_id
                        or row.owner_principal_id != context.owner_principal_id
                        or row.order_reference != query["order_reference"] or type(row.snapshot_bytes) is not bytes):
                    raise ValueError("Source returned observations outside current scope")
                snapshot = _snapshot(decode_document(row.snapshot_bytes))
                if snapshot["provider_id"] != self._metadata.provider_id:
                    raise ValueError("Source returned a different provider")
                snapshots.append(snapshot)
            if self._source.metadata != self._metadata:
                raise ValueError("Source changed during lookup")
            if len({s["snapshot_id"] for s in snapshots}) != len(snapshots) or len({s["order_id"] for s in snapshots}) != len(snapshots):
                raise ValueError("Duplicate source identity")
        except Exception:
            failed = True
        if failed:
            return self._result(query, "PROVIDER_FAILURE")
        if not snapshots:
            return self._result(query, "NOT_FOUND")
        if len(snapshots) != 1:
            return self._result(query, "CONFLICT")
        return self._result(query, "MATCHED", snapshots[0])

    @staticmethod
    def _result(query, status, snapshot=None):
        from .wire import validate
        value = {"case_id": query["case_id"], "input_version": query["input_version"], "status": status, "message": _MESSAGES[status]}
        if snapshot is not None: value["snapshot"] = snapshot
        return validate("OrderLookupResult", value, internal=True)
