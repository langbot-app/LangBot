"""Programmatic Alembic runner for LangBot.

Usage from async code:
    from langbot.pkg.persistence.alembic_runner import run_alembic_upgrade
    await run_alembic_upgrade(async_engine)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine
    from sqlalchemy.engine import Connection


_ALEMBIC_DIR = os.path.join(os.path.dirname(__file__), 'alembic')


def _build_config(connection: Connection) -> Config:
    """Build an Alembic Config with sync connection attached."""
    cfg = Config()
    cfg.set_main_option('script_location', _ALEMBIC_DIR)
    cfg.attributes['connection'] = connection
    return cfg


def _do_upgrade(connection: Connection, revision: str = 'head') -> None:
    """Synchronous upgrade — runs inside run_sync."""
    cfg = _build_config(connection)
    command.upgrade(cfg, revision)


def _do_stamp(connection: Connection, revision: str = 'head') -> None:
    """Synchronous stamp — runs inside run_sync."""
    cfg = _build_config(connection)
    command.stamp(cfg, revision)


def _do_get_current(connection: Connection) -> str | None:
    """Get current alembic revision synchronously."""
    ctx = MigrationContext.configure(connection)
    return ctx.get_current_revision()


async def run_alembic_upgrade(async_engine: AsyncEngine, revision: str = 'head') -> None:
    """Run Alembic upgrade to the given revision."""
    async with async_engine.connect() as conn:
        await conn.run_sync(_do_upgrade, revision)
        await conn.commit()


async def run_alembic_stamp(async_engine: AsyncEngine, revision: str = 'head') -> None:
    """Stamp the database with a revision without running migrations."""
    async with async_engine.connect() as conn:
        await conn.run_sync(_do_stamp, revision)
        await conn.commit()


async def get_alembic_current(async_engine: AsyncEngine) -> str | None:
    """Get current alembic revision, or None if not stamped."""
    async with async_engine.connect() as conn:
        return await conn.run_sync(_do_get_current)
