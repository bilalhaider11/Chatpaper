from logging.config import fileConfig

from sqlalchemy import create_engine, inspect, pool, text

from alembic import context

# import your models here
from core.database import Base
from core.config import settings
from models.auth import User
from models.file_model import FileRecord  # noqa: F401
from models.ingestion import DocumentParent, IngestionJob  # noqa: F401
from models.conversation import ConversationList, Conversation  # noqa: F401
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url from .env so alembic.ini value is ignored.
config.set_main_option("sqlalchemy.url", settings.database)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata
# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Use settings.database — engine_from_config would read alembic.ini (often localhost).
    connectable = create_engine(settings.database, poolclass=pool.NullPool)

    # engine.begin() commits on success; connect() alone can roll back migrations on exit.
    with connectable.begin() as connection:
        if connection.dialect.name == "postgresql" and inspect(connection).has_table(
            "alembic_version"
        ):
            connection.execute(
                text(
                    "ALTER TABLE alembic_version "
                    "ALTER COLUMN version_num TYPE VARCHAR(64)"
                )
            )

        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
