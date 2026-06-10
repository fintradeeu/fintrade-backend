"""Alembic environment configuration for async SQLAlchemy."""

import os
import sys
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

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

    if not has_alembic:
        if not has_users:
            # Fresh database: create all tables first!
            target_metadata.create_all(bind=connection)
        
        # Stamp the database to head to avoid re-running all migrations
        from alembic.script import ScriptDirectory
        import sqlalchemy as sa
        script = ScriptDirectory.from_config(context.config)
        head_rev = script.get_current_head()
        if head_rev:
            connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"))
            connection.execute(sa.text(f"INSERT INTO alembic_version (version_num) VALUES ('{head_rev}')"))
            connection.commit()
        return

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
