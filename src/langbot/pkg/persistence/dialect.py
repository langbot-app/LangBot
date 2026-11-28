"""Thin dialect-agnostic persistence primitives for SQLite and PostgreSQL.

Business and domain modules should call these helpers instead of importing
``sqlalchemy.dialects.*``, branching on ``dialect.name``, inspecting system
catalogs directly, or parsing database-driver error strings.
"""

from __future__ import annotations

import re
import typing

import sqlalchemy
from sqlalchemy.exc import IntegrityError

from .tenant_uow import TenantUnitOfWork

SUPPORTED_DIALECTS = frozenset({'sqlite', 'postgresql'})

_SQLITE_UNIQUE_ERROR_CODES = frozenset({1555, 2067})  # PRIMARYKEY, UNIQUE
_SQLITE_UNIQUE_ERROR_NAMES = frozenset(
    {
        'SQLITE_CONSTRAINT',
        'SQLITE_CONSTRAINT_PRIMARYKEY',
        'SQLITE_CONSTRAINT_UNIQUE',
    }
)
_SQLITE_UNIQUE_COLUMNS_RE = re.compile(r'unique constraint failed:\s*([^\n;]+)', re.IGNORECASE)
_POSTGRES_KEY_COLUMNS_RE = re.compile(r'key\s*\(([^)]+)\)\s*=', re.IGNORECASE)

_INFORMATION_SCHEMA_TABLES = sqlalchemy.table(
    'tables',
    sqlalchemy.column('table_schema'),
    sqlalchemy.column('table_name'),
    schema='information_schema',
)
_SQLITE_MASTER = sqlalchemy.table(
    'sqlite_master',
    sqlalchemy.column('type'),
    sqlalchemy.column('name'),
)


def resolve_dialect_name(target: typing.Any) -> str:
    """Resolve the database dialect name from an engine, manager, UoW, dialect, or string."""

    if isinstance(target, str):
        return target
    if isinstance(target, TenantUnitOfWork):
        target = target._engine
    else:
        get_engine = getattr(target, 'get_db_engine', None)
        if callable(get_engine):
            try:
                target = get_engine()
            except AttributeError:
                pass
    dialect = getattr(target, 'dialect', None)
    if dialect is not None and isinstance(getattr(dialect, 'name', None), str):
        return dialect.name
    db = getattr(target, 'db', None)
    if db is not None and isinstance(getattr(db, 'name', None), str):
        return db.name
    name = getattr(target, 'name', None)
    if isinstance(name, str):
        return name
    raise ValueError(f'Unsupported database dialect target: {target!r}')


def upsert_insert(target: typing.Any, table: typing.Any):
    """Return a SQLite or PostgreSQL INSERT statement supporting ON CONFLICT."""

    dialect_name = resolve_dialect_name(target)
    if dialect_name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert

        return insert(table)
    if dialect_name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert

        return insert(table)
    raise ValueError(f'Unsupported database dialect for upsert: {dialect_name}')


def _anchor_column(model: typing.Any, anchor_column: typing.Any = None):
    if anchor_column is not None:
        return anchor_column
    table = getattr(model, '__table__', model)
    primary_key_columns = list(getattr(getattr(table, 'primary_key', None), 'columns', ()))
    if not primary_key_columns:
        raise ValueError(f'Cannot lock {model!r} without a primary key or explicit anchor column')
    return primary_key_columns[0]


async def reserve_write_lock(
    executor: typing.Any,
    target: typing.Any,
    model: typing.Any,
    *where_clauses: typing.Any,
    anchor_column: typing.Any = None,
) -> None:
    """Reserve a SQLite writer lock before a read-then-write discovery query.

    On PostgreSQL this is a no-op because row-level locks serialize writers on
    the discovered rows without a read-snapshot upgrade race.
    """

    if not where_clauses:
        raise ValueError('reserve_write_lock requires at least one WHERE predicate')
    dialect_name = resolve_dialect_name(target)
    if dialect_name == 'postgresql':
        return
    if dialect_name != 'sqlite':
        raise ValueError(f'Unsupported database dialect for write lock reservation: {dialect_name}')
    await lock_rows_for_write(executor, model, *where_clauses, anchor_column=anchor_column)


async def lock_rows_for_write(
    executor: typing.Any,
    model: typing.Any,
    *where_clauses: typing.Any,
    anchor_column: typing.Any = None,
) -> None:
    """Serialize concurrent writers on matching rows across SQLite and PostgreSQL.

    SQLite ignores ``SELECT ... FOR UPDATE``; a self-update on the anchor column
    acquires SQLite's write reservation and PostgreSQL's row lock through the
    same structured statement.
    """

    if not where_clauses:
        raise ValueError('lock_rows_for_write requires at least one WHERE predicate')
    column = _anchor_column(model, anchor_column)
    await executor.execute(sqlalchemy.update(model).where(*where_clauses).values({column.key: column}))


def table_exists_query(target: typing.Any, table_name: str) -> sqlalchemy.sql.Select:
    """Build a scoped structured SELECT checking whether ``table_name`` exists."""

    dialect_name = resolve_dialect_name(target)
    if dialect_name == 'postgresql':
        return (
            sqlalchemy.select(_INFORMATION_SCHEMA_TABLES.c.table_name)
            .where(_INFORMATION_SCHEMA_TABLES.c.table_schema == 'public')
            .where(_INFORMATION_SCHEMA_TABLES.c.table_name == table_name)
            .limit(1)
        )
    if dialect_name == 'sqlite':
        return (
            sqlalchemy.select(_SQLITE_MASTER.c.name)
            .where(_SQLITE_MASTER.c.type == 'table')
            .where(_SQLITE_MASTER.c.name == table_name)
            .limit(1)
        )
    raise ValueError(f'Unsupported database dialect for table inspection: {dialect_name}')


def time_bucket(
    target: typing.Any,
    column: typing.Any,
    *,
    bucket: str,
    iso_format: bool = False,
):
    """Build a server-side UTC ``hour`` or ``day`` bucket expression."""

    if bucket not in {'hour', 'day'}:
        raise ValueError(f'Unsupported time bucket: {bucket!r}')
    dialect_name = resolve_dialect_name(target)
    if dialect_name == 'postgresql':
        return sqlalchemy.func.date_trunc(bucket, column)
    if dialect_name == 'sqlite':
        if iso_format:
            pattern = '%Y-%m-%dT%H:00:00' if bucket == 'hour' else '%Y-%m-%dT00:00:00'
        else:
            pattern = '%Y-%m-%d %H:00' if bucket == 'hour' else '%Y-%m-%d'
        return sqlalchemy.func.strftime(pattern, column)
    raise ValueError(f'Unsupported database dialect for time bucketing: {dialect_name}')


def json_text(target: typing.Any, column: typing.Any, key: str):
    """Extract a top-level string field from a text-backed JSON column."""

    dialect_name = resolve_dialect_name(target)
    if dialect_name == 'sqlite':
        expression = sqlalchemy.type_coerce(column, sqlalchemy.JSON)
    elif dialect_name == 'postgresql':
        expression = sqlalchemy.cast(column, sqlalchemy.JSON)
    else:
        raise ValueError(f'Unsupported database dialect for JSON extraction: {dialect_name}')
    return expression[key].as_string()


def json_path_text(target: typing.Any, column: typing.Any, *path: str):
    """Extract a nested string field from a text-backed JSON column."""

    if not path:
        raise ValueError('json_path_text requires at least one path component')
    expression = (
        sqlalchemy.type_coerce(column, sqlalchemy.JSON)
        if resolve_dialect_name(target) == 'sqlite'
        else sqlalchemy.cast(column, sqlalchemy.JSON)
    )
    for key in path:
        expression = expression[key]
    return expression.as_string()


def _iter_exception_chain(exc: BaseException) -> typing.Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        orig = getattr(current, 'orig', None)
        if isinstance(orig, BaseException) and id(orig) not in seen:
            current = orig
            continue
        cause = getattr(current, '__cause__', None)
        if isinstance(cause, BaseException) and id(cause) not in seen:
            current = cause
            continue
        break


def _parse_column_list(raw: str) -> set[str]:
    columns: set[str] = set()
    for part in raw.split(','):
        token = part.strip().strip('"`[]')
        if not token:
            continue
        if '.' in token:
            token = token.rsplit('.', 1)[-1].strip('"`[]')
        if token:
            columns.add(token.lower())
    return columns


def _extract_sqlite_conflict_columns(driver_text: str) -> set[str]:
    match = _SQLITE_UNIQUE_COLUMNS_RE.search(driver_text)
    if not match:
        return set()
    return _parse_column_list(match.group(1))


def _extract_postgres_detail_columns(detail_text: str) -> set[str]:
    match = _POSTGRES_KEY_COLUMNS_RE.search(detail_text)
    if not match:
        return set()
    return _parse_column_list(match.group(1))


def is_unique_violation(
    exc: BaseException,
    *,
    constraints: typing.Sequence[str] = (),
    columns: typing.Sequence[str] = (),
) -> bool:
    """Return True when ``exc`` is a unique/primary-key constraint violation.

    Matches exclusively against the underlying DBAPI driver error metadata and
    message (never SQLAlchemy's formatted ``[SQL: ...]`` or ``[parameters: ...]``)
    so unrelated primary-key collisions or user-supplied parameter text cannot
    masquerade as a target constraint conflict.
    """

    if not isinstance(exc, IntegrityError):
        return False

    driver_items = [item for item in _iter_exception_chain(exc) if item is not exc]
    sqlstate: str | None = None
    constraint_name: str | None = None
    detail_text: str | None = None
    sqlite_code: int | None = None
    sqlite_name: str | None = None
    driver_messages: list[str] = []

    for item in driver_items:
        driver_messages.append(str(item))
        if sqlstate is None:
            candidate = getattr(item, 'sqlstate', None) or getattr(item, 'pgcode', None)
            if isinstance(candidate, str) and candidate:
                sqlstate = candidate
        if constraint_name is None:
            candidate = getattr(item, 'constraint_name', None)
            if not candidate:
                diag = getattr(item, 'diag', None)
                candidate = getattr(diag, 'constraint_name', None)
            if isinstance(candidate, str) and candidate:
                constraint_name = candidate
        if detail_text is None:
            candidate = getattr(item, 'detail', None)
            if not candidate:
                diag = getattr(item, 'diag', None)
                candidate = getattr(diag, 'message_detail', None)
            if isinstance(candidate, str) and candidate:
                detail_text = candidate
        if sqlite_code is None:
            candidate = getattr(item, 'sqlite_errorcode', None)
            if isinstance(candidate, int):
                sqlite_code = candidate
        if sqlite_name is None:
            candidate = getattr(item, 'sqlite_errorname', None)
            if isinstance(candidate, str) and candidate:
                sqlite_name = candidate

    if not driver_messages:
        message_fn = getattr(exc, '_message', None)
        if callable(message_fn):
            driver_messages.append(str(message_fn()))

    driver_lower = ' '.join(driver_messages).lower()
    expected_constraints = {name.lower() for name in constraints}
    expected_columns = {column.lower() for column in columns}

    if sqlstate is not None:
        if sqlstate != '23505':
            return False
        if not expected_constraints and not expected_columns:
            return True
        if expected_constraints:
            if constraint_name is not None:
                return constraint_name.lower() in expected_constraints
            if any(name in driver_lower for name in expected_constraints):
                return True
        if expected_columns:
            pg_columns = _extract_postgres_detail_columns(detail_text or driver_lower)
            if pg_columns and pg_columns == expected_columns:
                return True
        return False

    if sqlite_code is not None:
        if sqlite_code in _SQLITE_UNIQUE_ERROR_CODES:
            is_unique = True
        elif sqlite_code == 19:
            if sqlite_name is not None and sqlite_name not in _SQLITE_UNIQUE_ERROR_NAMES:
                return False
            is_unique = 'unique constraint failed:' in driver_lower
        else:
            return False
        if not is_unique:
            return False
        if not expected_constraints and not expected_columns:
            return True
        if expected_columns:
            sqlite_columns = _extract_sqlite_conflict_columns(driver_lower)
            if sqlite_columns and sqlite_columns == expected_columns:
                return True
        if expected_constraints and any(name in driver_lower for name in expected_constraints):
            return True
        return False

    if 'duplicate key value violates unique constraint' in driver_lower:
        if not expected_constraints and not expected_columns:
            return True
        if expected_constraints and any(name in driver_lower for name in expected_constraints):
            return True
        if expected_columns:
            pg_columns = _extract_postgres_detail_columns(detail_text or driver_lower)
            if pg_columns and pg_columns == expected_columns:
                return True
        return False

    if 'unique constraint failed:' in driver_lower:
        if not expected_constraints and not expected_columns:
            return True
        if expected_columns:
            sqlite_columns = _extract_sqlite_conflict_columns(driver_lower)
            if sqlite_columns and sqlite_columns == expected_columns:
                return True
        if expected_constraints and any(name in driver_lower for name in expected_constraints):
            return True
        return False

    return False
