"""Explicit secret configuration. F.02; NFR-003/006/007/009, docs/02 architecture."""
import os
import re

from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class ConfigurationError(ValueError):
    """Safe configuration error that never echoes a DSN or secret."""


def require_environment_database(raw: str) -> None:
    """F.02 migrations target only explicit disposable environment databases."""
    try:
        url = make_url(raw)
        name = url.database or ""
        if (
            url.drivername != "postgresql+psycopg"
            or not url.host
            or "?" in raw
            or "#" in raw
            or len(name) > 63
            or re.fullmatch(r"returnops_f02(?:_[a-z0-9_]+)?", name) is None
        ):
            raise ValueError
    except (ValueError, TypeError, ArgumentError):
        raise ConfigurationError(
            "F.02 migration requires a dedicated returnops_f02 database (optional suffix), without query parameters or fragments."
        ) from None


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    database_url: SecretStr

    @classmethod
    def from_environment(cls) -> "Settings":
        raw = os.environ.get("DATABASE_URL", "")
        try:
            url = make_url(raw)
            if (
                url.drivername != "postgresql+psycopg"
                or not url.host
                or not url.database
                or not url.username
            ):
                raise ValueError
            # Validate malformed port before SQLAlchemy/driver construction.
            if url.port is not None and not 1 <= url.port <= 65535:
                raise ValueError
        except (ValueError, TypeError, ArgumentError):
            raise ConfigurationError(
                "Set DATABASE_URL to a valid postgresql+psycopg URL with host, user and database."
            ) from None
        return cls(database_url=SecretStr(raw))
