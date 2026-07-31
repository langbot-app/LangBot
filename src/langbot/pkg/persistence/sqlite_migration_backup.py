"""Durable SQLite backups for destructive Alembic migration boundaries."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import json
import os
import pathlib
import re
import secrets
import sqlite3
import tempfile
import typing

from sqlalchemy.ext.asyncio import AsyncEngine


class SQLiteMigrationBackupError(RuntimeError):
    """A verified migration backup could not be created or restored."""


@dataclasses.dataclass(frozen=True, slots=True)
class SQLiteMigrationBackup:
    database_path: pathlib.Path
    backup_path: pathlib.Path
    manifest_path: pathlib.Path
    source_revision: str
    target_revision: str
    created_at: str


def _safe_label(value: str) -> str:
    label = re.sub(r'[^A-Za-z0-9_.-]+', '-', value).strip('-')
    return label or 'unknown'


def _database_path(engine: AsyncEngine) -> pathlib.Path:
    if engine.dialect.name != 'sqlite':
        raise SQLiteMigrationBackupError('SQLite migration backups require a SQLite engine')
    database = engine.url.database
    if not database or database == ':memory:' or engine.url.query.get('mode') == 'memory':
        raise SQLiteMigrationBackupError('Tenant schema migrations require a file-backed SQLite database for recovery')
    database_path = pathlib.Path(database).expanduser()
    if not database_path.is_absolute():
        database_path = pathlib.Path.cwd() / database_path
    database_path = database_path.resolve()
    if not database_path.is_file():
        raise SQLiteMigrationBackupError(f'SQLite database does not exist: {database_path}')
    return database_path


def _open_read_only(path: pathlib.Path) -> sqlite3.Connection:
    return sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True, timeout=30)


def _read_revision(connection: sqlite3.Connection) -> str | None:
    has_version_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
    ).fetchone()
    if has_version_table is None:
        return None
    rows = connection.execute('SELECT version_num FROM alembic_version').fetchall()
    if not rows:
        return None
    if len(rows) != 1 or not isinstance(rows[0][0], str):
        raise SQLiteMigrationBackupError('SQLite backup has an invalid Alembic revision table')
    return rows[0][0]


def _verify_connection(connection: sqlite3.Connection, expected_revision: str) -> None:
    quick_check = connection.execute('PRAGMA quick_check').fetchall()
    if quick_check != [('ok',)]:
        raise SQLiteMigrationBackupError(f'SQLite quick_check failed: {quick_check[:5]!r}')
    actual_revision = _read_revision(connection)
    if actual_revision != expected_revision:
        raise SQLiteMigrationBackupError(
            f'SQLite backup revision mismatch: {actual_revision!r} != {expected_revision!r}'
        )


def _verify_file(path: pathlib.Path, expected_revision: str) -> None:
    with _open_read_only(path) as connection:
        _verify_connection(connection, expected_revision)


def _write_manifest(backup: SQLiteMigrationBackup, status: str, **extra: typing.Any) -> None:
    payload: dict[str, typing.Any] = {
        'version': 1,
        'status': status,
        'created_at': backup.created_at,
        'database_path': str(backup.database_path),
        'backup_path': str(backup.backup_path),
        'source_revision': backup.source_revision,
        'target_revision': backup.target_revision,
        'quick_check': 'ok',
        **extra,
    }
    backup.manifest_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{backup.manifest_path.name}.',
        suffix='.tmp',
        dir=backup.manifest_path.parent,
    )
    temporary_path = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, backup.manifest_path)
        _fsync_directory(backup.manifest_path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _fsync_file(path: pathlib.Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: pathlib.Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _create_backup(
    database_path: pathlib.Path,
    source_revision: str,
    target_revision: str,
) -> SQLiteMigrationBackup:
    backup_directory = database_path.parent / 'migration-backups'
    backup_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(backup_directory, 0o700)
    created_at = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H-%M-%S.%fZ')
    stem = (
        f'{database_path.stem}-pre-{_safe_label(target_revision)}-'
        f'from-{_safe_label(source_revision)}-{created_at}-{secrets.token_hex(4)}'
    )
    backup_path = backup_directory / f'{stem}.sqlite3'
    manifest_path = backup_directory / f'{stem}.json'
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{stem}.',
        suffix='.creating',
        dir=backup_directory,
    )
    os.close(descriptor)
    temporary_path = pathlib.Path(temporary_name)
    try:
        with (
            _open_read_only(database_path) as source,
            sqlite3.connect(
                temporary_path,
                timeout=30,
            ) as destination,
        ):
            source.execute('PRAGMA busy_timeout = 30000')
            source.backup(destination)
            destination.commit()
            _verify_connection(destination, source_revision)
        os.chmod(temporary_path, 0o600)
        _fsync_file(temporary_path)
        os.replace(temporary_path, backup_path)
        _fsync_file(backup_path)
        _fsync_directory(backup_directory)
        backup = SQLiteMigrationBackup(
            database_path=database_path,
            backup_path=backup_path,
            manifest_path=manifest_path,
            source_revision=source_revision,
            target_revision=target_revision,
            created_at=created_at,
        )
        _write_manifest(backup, 'verified')
        return backup
    except Exception:
        backup_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    finally:
        temporary_path.unlink(missing_ok=True)


async def create_verified_backup(
    engine: AsyncEngine,
    *,
    source_revision: str,
    target_revision: str,
) -> SQLiteMigrationBackup:
    """Create and verify an online-consistent backup next to instance data."""

    database_path = _database_path(engine)
    return await asyncio.to_thread(
        _create_backup,
        database_path,
        source_revision,
        target_revision,
    )


def _restore_backup(backup: SQLiteMigrationBackup) -> None:
    _verify_file(backup.backup_path, backup.source_revision)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f'.{backup.database_path.name}.',
        suffix='.restoring',
        dir=backup.database_path.parent,
    )
    os.close(descriptor)
    temporary_path = pathlib.Path(temporary_name)
    try:
        with (
            _open_read_only(backup.backup_path) as source,
            sqlite3.connect(
                temporary_path,
                timeout=30,
            ) as destination,
        ):
            source.backup(destination)
            destination.commit()
            _verify_connection(destination, backup.source_revision)
        os.chmod(temporary_path, 0o600)
        _fsync_file(temporary_path)

        # A stale WAL could replay pages from the failed migration after the
        # main database file is replaced. The engine is disposed before this
        # function runs, so these exact sidecars are safe to remove.
        for suffix in ('-wal', '-shm', '-journal'):
            pathlib.Path(f'{backup.database_path}{suffix}').unlink(missing_ok=True)
        os.replace(temporary_path, backup.database_path)
        _fsync_file(backup.database_path)
        _fsync_directory(backup.database_path.parent)
        _verify_file(backup.database_path, backup.source_revision)
    finally:
        temporary_path.unlink(missing_ok=True)


async def restore_verified_backup(engine: AsyncEngine, backup: SQLiteMigrationBackup) -> None:
    """Atomically restore a verified backup after a migration failure."""

    await engine.dispose()
    await asyncio.to_thread(_restore_backup, backup)
    await asyncio.to_thread(
        _write_manifest,
        backup,
        'restored_after_failure',
        restored_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )


async def mark_migration_succeeded(
    backup: SQLiteMigrationBackup,
    *,
    completed_revision: str,
) -> None:
    """Mark a retained verified backup after its migration boundary succeeds."""

    await asyncio.to_thread(
        _write_manifest,
        backup,
        'migration_succeeded',
        completed_at=datetime.datetime.now(datetime.UTC).isoformat(),
        completed_revision=completed_revision,
    )
