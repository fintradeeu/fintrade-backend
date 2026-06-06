"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.database import Base
from app.db.base import import_all_models

# Import all models so metadata is populated
import_all_models()

config = context.config
config.set_main_option("sqlalchemy.url", settings.async_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.async_database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    from sqlalchemy import inspect
    insp = inspect(connection)
    has_alembic = insp.has_table('alembic_version')
    has_users = insp.has_table('users')

    if not has_alembic and not has_users:
        # Fresh database: create all tables first!
        target_metadata.create_all(bind=connection)

    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    from app.db.database import get_engine_args
    args = get_engine_args()
    args["poolclass"] = pool.NullPool
    # Remove pool-related args not compatible with NullPool if any
    args.pop("pool_size", None)
    args.pop("max_overflow", None)
    
    connectable = create_async_engine(**args)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations online."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
