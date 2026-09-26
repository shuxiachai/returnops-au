"""Migration entry point for the environment and initial-record groundwork."""
from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from returnops_api.settings import Settings, require_environment_database


def run_migrations() -> None:
    settings = Settings.from_environment()
    url = settings.database_url.get_secret_value()
    require_environment_database(url)
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=None, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    # Programmatic tests supply a transaction with an isolated generated schema.
    # It must still target the exact explicitly configured disposable database.
    supplied = context.config.attributes.get("connection")
    if supplied is not None:
        require_environment_database(supplied.engine.url.render_as_string(hide_password=False))
        if supplied.engine.url != make_url(url):
            raise RuntimeError("Supplied migration connection must match the explicit database configuration")
        context.configure(connection=supplied, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=5000"},
        hide_parameters=True,
        echo=False,
    )
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=None)
            with context.begin_transaction():
                context.run_migrations()
    except SQLAlchemyError:
        raise SystemExit("Database migration failed; check configuration and connectivity.") from None
    finally:
        engine.dispose()


run_migrations()
