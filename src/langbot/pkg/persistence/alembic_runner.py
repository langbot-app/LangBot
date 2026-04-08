"""Programmatic Alembic runner for LangBot.

Usage from async code:
    from langbot.pkg.persistence.alembic_runner import run_alembic_upgrade
    await run_alembic_upgrade(async_engine)

CLI usage (autogenerate):
    python -m langbot.pkg.persistence.alembic_runner autogenerate "add description column"
    python -m langbot.pkg.persistence.alembic_runner upgrade
    python -m langbot.pkg.persistence.alembic_runner current
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


def _do_autogenerate(connection: Connection, message: str = 'auto migration') -> None:
    """Synchronous autogenerate — runs inside run_sync."""
    cfg = _build_config(connection)
    command.revision(cfg, message=message, autogenerate=True)


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


async def run_alembic_autogenerate(async_engine: AsyncEngine, message: str = 'auto migration') -> None:
    """Compare ORM models against DB schema and generate a migration script."""
    async with async_engine.connect() as conn:
        await conn.run_sync(_do_autogenerate, message)


# CLI entrypoint: python -m langbot.pkg.persistence.alembic_runner <command> [args]
if __name__ == '__main__':
    import sys
    import asyncio

    def _get_engine():
        """Create engine from data/config.yaml or default SQLite."""
        from sqlalchemy.ext.asyncio import create_async_engine

        try:
            import yaml

            with open('data/config.yaml') as f:
                config = yaml.safe_load(f)
            db_cfg = config.get('database', {})
            db_type = db_cfg.get('use', 'sqlite')
            if db_type == 'postgresql':
                pg = db_cfg.get('postgresql', {})
                url = (
                    f'postgresql+asyncpg://{pg.get("user", "postgres")}:{pg.get("password", "postgres")}'
                    f'@{pg.get("host", "127.0.0.1")}:{pg.get("port", 5432)}/{pg.get("database", "postgres")}'
                )
            else:
                path = db_cfg.get('sqlite', {}).get('path', 'data/langbot.db')
                url = f'sqlite+aiosqlite:///{path}'
        except Exception:
            url = 'sqlite+aiosqlite:///data/langbot.db'

        return create_async_engine(url)

    def main():
        if len(sys.argv) < 2:
            print('Usage: python -m langbot.pkg.persistence.alembic_runner <command> [args]')
            print('Commands:')
            print('  autogenerate "message"  — Generate migration from ORM model diff')
            print('  upgrade [revision]      — Upgrade database (default: head)')
            print('  stamp [revision]        — Stamp revision without running (default: head)')
            print('  current                 — Show current revision')
            sys.exit(1)

        cmd = sys.argv[1]
        engine = _get_engine()

        if cmd == 'autogenerate':
            msg = sys.argv[2] if len(sys.argv) > 2 else 'auto migration'
            asyncio.run(run_alembic_autogenerate(engine, msg))
            print(f'Migration generated: {msg}')
        elif cmd == 'upgrade':
            rev = sys.argv[2] if len(sys.argv) > 2 else 'head'
            asyncio.run(run_alembic_upgrade(engine, rev))
            print(f'Upgraded to: {rev}')
        elif cmd == 'stamp':
            rev = sys.argv[2] if len(sys.argv) > 2 else 'head'
            asyncio.run(run_alembic_stamp(engine, rev))
            print(f'Stamped: {rev}')
        elif cmd == 'current':
            rev = asyncio.run(get_alembic_current(engine))
            print(f'Current revision: {rev}')
        else:
            print(f'Unknown command: {cmd}')
            sys.exit(1)

    main()
