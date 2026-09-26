"""Cross-process transaction fence for every supported trusted registry/domain write.

The dedicated single-store prototype serializes trusted writes. DBA SQL outside
these adapters is outside this coordination boundary, not claimed prevented.
"""
from sqlalchemy import text
from sqlalchemy.engine import Connection

FENCE_KEY = 0x52455455524E5331

def acquire_fence(connection: Connection, *, write: bool) -> None:
    function = "pg_advisory_xact_lock" if write else "pg_advisory_xact_lock_shared"
    connection.execute(text(f"SELECT {function}(:key)"), {"key": FENCE_KEY})
