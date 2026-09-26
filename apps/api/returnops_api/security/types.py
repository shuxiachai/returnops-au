"""Internal trusted records, deliberately separate from legacy domain models.

F.03; FR-009/012, NFR-002/003/009; docs/16 section 2, CS-D01.
Only a future trusted adapter constructs registry records. No wire DTO changes.
"""

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Protocol


def valid_id(value: object) -> bool:
    """The existing rc.5 Id boundary, including rejection of trailing newlines."""
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,79}", value) is not None


class Role(StrEnum):
    CUSTOMER = "CUSTOMER"
    FOUNDER = "FOUNDER"


@dataclass(frozen=True, slots=True)
class PrincipalRecord:
    principal_id: str
    role: Role
    store_id: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    principal_id: str
    issued_at: int
    not_before: int
    expires_at: int
    revoked: bool = False


@dataclass(frozen=True, slots=True)
class IdentitySnapshot:
    principal: PrincipalRecord
    session: SessionRecord


class IdentityStore(Protocol):
    def read_identity(self, principal_id: str, session_id: str) -> IdentitySnapshot | None:
        """Read both current records in one coherent snapshot, never a cached grant.

        Return None for missing records; raise SecurityStoreUnavailable on outage.
        A future adapter must not create default identities when storage is empty.
        """
        ...


@dataclass(frozen=True, slots=True)
class VerifiedPrincipal:
    """Internal result valid only for this check, not a reusable authorisation."""

    principal_id: str
    role: Role
    store_id: str
    session_id: str

    def session_view(self) -> dict[str, str]:
        """The exact rc.5 Principal projection; not an HTTP session endpoint."""
        return {"principal_id": self.principal_id, "role": self.role.value}
