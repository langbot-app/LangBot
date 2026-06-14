"""Alembic environment for LangBot.

This env.py is designed to be called programmatically (not via CLI).
It supports both SQLite and PostgreSQL.

The sync connection is passed via config attributes by the runner.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy.engine import Connection

from langbot.pkg.entity.persistence.base import Base

# Import all ORM models so they are registered with Base.metadata
# This is required for autogenerate to detect model changes
from langbot.pkg.entity.persistence import (
    agent_runner_state,  # noqa: F401
    apikey,  # noqa: F401
    artifact,  # noqa: F401
    bot,  # noqa: F401
    bstorage,  # noqa: F401
    event_log,  # noqa: F401
    mcp,  # noqa: F401
    metadata,  # noqa: F401
    model,  # noqa: F401
    monitoring,  # noqa: F401
    pipeline,  # noqa: F401
    plugin,  # noqa: F401
    rag,  # noqa: F401
    transcript,  # noqa: F401
    user,  # noqa: F401
    vector,  # noqa: F401
    webhook,  # noqa: F401
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL without a live connection."""
    url = context.config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live sync connection passed via config attributes."""
    connection: Connection = context.config.attributes.get('connection')
    if connection is None:
        raise RuntimeError('connection not provided in alembic config attributes')

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # render_as_batch=True is critical for SQLite ALTER TABLE support
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
