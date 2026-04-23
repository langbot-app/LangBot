"""Alembic environment for LangBot.

This env.py is designed to be called programmatically (not via CLI).
It supports both SQLite and PostgreSQL.

The sync connection is passed via config attributes by the runner.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy.engine import Connection

from langbot.pkg.entity.persistence.base import Base

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
