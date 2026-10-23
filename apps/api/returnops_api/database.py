"""Read-only infrastructure diagnostics, not CaseRepository or business state.

F.02 / NFR-006/007/008; docs/02 modular-monolith and PostgreSQL boundary.
"""
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .settings import Settings


EXPECTED_SCHEMA_REVISION = "0014_notification_delivery"


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=2,
        pool_timeout=3,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=10000"},
        hide_parameters=True,
        echo=False,
    )


def readiness(engine: Engine) -> bool:
    """Only the exact expected single revision is ready. Never migrate/stamp."""
    try:
        with engine.connect() as connection:
            if connection.execute(text("SELECT 1")).scalar_one() != 1:
                return False
            revisions = connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num")
            ).scalars().all()
            from returnops_domain.lifecycle_schema import version
            return revisions == [EXPECTED_SCHEMA_REVISION] and version(connection) == EXPECTED_SCHEMA_REVISION
    except SQLAlchemyError:
        # Driver errors may include host/user/DSN fragments; expose no details.
        return False
