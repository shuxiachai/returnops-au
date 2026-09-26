"""Neutral domain ports; no API import or token model crosses this boundary."""
from dataclasses import dataclass, field
from typing import Protocol
from sqlalchemy.engine import Connection

@dataclass(frozen=True, slots=True)
class Actor:
    principal_id: str = field(repr=False)
    role: str
    store_id: str = field(repr=False)
    session_id: str = field(repr=False)

class CurrentAuthority(Protocol):
    def __call__(self, connection: Connection, operation: str, resource_id: str | None = None) -> Actor:
        """Authenticate and authorize from current records on this connection."""
        ...
