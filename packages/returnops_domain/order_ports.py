"""Neutral A1.04 ports. Query fields never supply authority or select a source."""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import Protocol

_MESSAGES = {
    "INVALID_REQUEST": "Order lookup request fields are invalid.",
    "CASE_ACCESS_DENIED": "Current case access was not granted.",
    "STALE_INPUT": "The case input version is no longer current.",
    "CONTEXT_MISMATCH": "The trusted order context does not match this lookup.",
    "CONTEXT_UNAVAILABLE": "Current order access could not be established.",
    "INVALID_CONFIGURATION": "The synthetic order component configuration is invalid.",
}

class OrderLookupError(Exception):
    """Allowlisted internal error; never a provider business outcome."""
    def __init__(self, code: str):
        if code not in _MESSAGES:
            raise ValueError("Unsupported order lookup error code.")
        self.code = code
        super().__init__(_MESSAGES[code])

class OrderSourceUnavailable(Exception):
    """Trusted source failure; the provider discards its exception context."""
    def __init__(self):
        super().__init__("The synthetic order source is unavailable.")


def valid_id(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,79}", value) is not None

@dataclass(frozen=True, slots=True, repr=False)
class OrderReadContext:
    """An authorized, current case binding supplied only by trusted composition.

    The resolver must check case access and the current input before returning.
    This value is an observation, not a reusable grant for later persistence.
    """
    case_id: str
    input_version: int
    store_id: str
    owner_principal_id: str
    service_id: str
    provider_id: str
    can_read_orders: bool

    def __post_init__(self):
        if (not all(valid_id(value) for value in (self.case_id, self.store_id,
                self.owner_principal_id, self.service_id, self.provider_id))
                or type(self.input_version) is not int
                or not 1 <= self.input_version <= 9007199254740991
                or type(self.can_read_orders) is not bool):
            raise OrderLookupError("CONTEXT_UNAVAILABLE")

class CurrentOrderContext(Protocol):
    def resolve(self, case_id: str, input_version: int) -> OrderReadContext:
        """Freshly authorize this case and version, or raise a safe typed error."""
        ...

class OrderLookupPort(Protocol):
    def lookup(self, request: Mapping) -> dict:
        ...

@dataclass(frozen=True, slots=True, repr=False)
class CatalogueMetadata:
    format_version: int
    dataset_version: str
    provider_id: str
    provider_version: str
    dataset_sha256: str

@dataclass(frozen=True, slots=True, repr=False)
class CatalogueRecord:
    store_id: str
    owner_principal_id: str
    order_reference: str = field(repr=False)
    snapshot_bytes: bytes = field(repr=False)

class OrderSource(Protocol):
    @property
    def metadata(self) -> CatalogueMetadata: ...

    def read_matches(self, context: OrderReadContext, order_reference: str) -> tuple[CatalogueRecord, ...]:
        """Trusted read-only source; called only after current context checks."""
        ...
