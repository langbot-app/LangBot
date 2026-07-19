from __future__ import annotations

import asyncio
import collections.abc
import contextlib
import contextvars
import dataclasses
import enum
import functools
import types
import typing

import sqlalchemy
import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
import sqlalchemy.orm as sqlalchemy_orm
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql.dml import OnConflictDoUpdate as PostgreSQLOnConflictDoUpdate
from sqlalchemy.dialects.sqlite.dml import OnConflictDoUpdate as SQLiteOnConflictDoUpdate


TENANT_SETTING = 'langbot.workspace_uuid'
ACCOUNT_SETTING = 'langbot.account_uuid'
API_KEY_HASH_SETTING = 'langbot.api_key_hash'
INVITATION_HASH_SETTING = 'langbot.invitation_hash'
INSTANCE_SETTING = 'langbot.instance_uuid'
IDENTITY_DIGEST_SETTING = 'langbot.identity_digest'

TENANT_POLICY_NAME = 'langbot_workspace_isolation'
ACCOUNT_DISCOVERY_POLICY_NAME = 'langbot_account_discovery'
API_KEY_DISCOVERY_POLICY_NAME = 'langbot_api_key_discovery'
INVITATION_DISCOVERY_POLICY_NAME = 'langbot_invitation_discovery'
INSTANCE_DISCOVERY_POLICY_NAME = 'langbot_instance_discovery'

# Keep this contract explicit. A new tenant-owned table must be added to both
# this runtime list and the corresponding Alembic migration before release.
TENANT_TABLE_COLUMNS: dict[str, str] = {
    'workspaces': 'uuid',
    'workspace_memberships': 'workspace_uuid',
    'workspace_invitations': 'workspace_uuid',
    'workspace_execution_states': 'workspace_uuid',
    'workspace_metadata': 'workspace_uuid',
    'api_keys': 'workspace_uuid',
    'bots': 'workspace_uuid',
    'bot_admins': 'workspace_uuid',
    'binary_storages': 'workspace_uuid',
    'mcp_servers': 'workspace_uuid',
    'model_providers': 'workspace_uuid',
    'llm_models': 'workspace_uuid',
    'embedding_models': 'workspace_uuid',
    'rerank_models': 'workspace_uuid',
    'legacy_pipelines': 'workspace_uuid',
    'pipeline_run_records': 'workspace_uuid',
    'plugin_settings': 'workspace_uuid',
    'knowledge_bases': 'workspace_uuid',
    'knowledge_base_files': 'workspace_uuid',
    'knowledge_base_chunks': 'workspace_uuid',
    'webhooks': 'workspace_uuid',
    'monitoring_messages': 'workspace_uuid',
    'monitoring_llm_calls': 'workspace_uuid',
    'monitoring_tool_calls': 'workspace_uuid',
    'monitoring_sessions': 'workspace_uuid',
    'monitoring_errors': 'workspace_uuid',
    'monitoring_embedding_calls': 'workspace_uuid',
    'monitoring_feedback': 'workspace_uuid',
    # Created by 0013 rather than ORM metadata; it is still part of the same
    # business-database RLS contract and permits no discovery policies.
    'langbot_vectors': 'workspace_uuid',
}


class PersistenceScopeKind(enum.StrEnum):
    WORKSPACE = 'workspace'
    ACCOUNT_DISCOVERY = 'account_discovery'
    API_KEY_DISCOVERY = 'api_key_discovery'
    INVITATION_DISCOVERY = 'invitation_discovery'
    INSTANCE_DISCOVERY = 'instance_discovery'
    IDENTITY_DISCOVERY = 'identity_discovery'


@dataclasses.dataclass(frozen=True, slots=True)
class PersistenceScope:
    """A trusted, transaction-local database visibility scope."""

    kind: PersistenceScopeKind
    settings: tuple[tuple[str, str], ...]

    @classmethod
    def workspace(cls, workspace_uuid: str) -> PersistenceScope:
        return cls._one(PersistenceScopeKind.WORKSPACE, TENANT_SETTING, workspace_uuid)

    @classmethod
    def account(cls, account_uuid: str) -> PersistenceScope:
        return cls._one(PersistenceScopeKind.ACCOUNT_DISCOVERY, ACCOUNT_SETTING, account_uuid)

    @classmethod
    def api_key(cls, key_hash: str) -> PersistenceScope:
        return cls._one(PersistenceScopeKind.API_KEY_DISCOVERY, API_KEY_HASH_SETTING, key_hash)

    @classmethod
    def invitation(cls, token_hash: str) -> PersistenceScope:
        return cls._one(PersistenceScopeKind.INVITATION_DISCOVERY, INVITATION_HASH_SETTING, token_hash)

    @classmethod
    def instance(cls, instance_uuid: str) -> PersistenceScope:
        return cls._one(PersistenceScopeKind.INSTANCE_DISCOVERY, INSTANCE_SETTING, instance_uuid)

    @classmethod
    def identity(cls, identity_digest: str) -> PersistenceScope:
        return cls._one(PersistenceScopeKind.IDENTITY_DISCOVERY, IDENTITY_DIGEST_SETTING, identity_digest)

    @classmethod
    def _one(cls, kind: PersistenceScopeKind, setting: str, value: str) -> PersistenceScope:
        return cls(kind, ((setting, cls._normalize(value, kind.value)),))

    @staticmethod
    def _normalize(value: str, label: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f'{label} must be a string')
        normalized = value.strip()
        if not normalized:
            raise ValueError(f'{label} must not be empty')
        if len(normalized) > 512:
            raise ValueError(f'{label} exceeds the database scope limit')
        return normalized


class TenantScopeRequiredError(RuntimeError):
    """Raised when Cloud business data is accessed without a trusted scope."""


class CrossScopeTransactionError(RuntimeError):
    """Raised when code tries to change scope inside an active transaction."""


class TransactionRollbackOnlyError(RuntimeError):
    """Raised when a caught failure made the outer transaction unsafe to commit."""


class ScopedSessionTransactionError(RuntimeError):
    """Raised when callers try to escape a UoW-owned transaction boundary."""


@dataclasses.dataclass(slots=True)
class ActiveScopedTransaction:
    scope: PersistenceScope
    session: sqlalchemy_asyncio.AsyncSession
    engine: sqlalchemy_asyncio.AsyncEngine
    owner_task: asyncio.Task[typing.Any] | None
    depth: int = 1
    rollback_only: bool = False
    rollback_only_cause: BaseException | None = None
    after_commit_waiters: list[asyncio.Future[None]] = dataclasses.field(default_factory=list)

    def mark_rollback_only(self, cause: BaseException | None = None) -> None:
        """Remember that this transaction must never release commit-gated work."""

        self.rollback_only = True
        if self.rollback_only_cause is None:
            self.rollback_only_cause = cause


_UOW_SESSION_CONTROL_CAPABILITY = object()


@dataclasses.dataclass(slots=True)
class _ScopedSessionGuardState:
    owner_task: asyncio.Task[typing.Any] | None
    transaction_state: ActiveScopedTransaction | None = None
    active: bool = True
    session_events_blocked: bool = False


_SYNC_PROXY_CAPABILITY: contextvars.ContextVar[_ScopedSessionGuardState | None] = contextvars.ContextVar(
    'langbot_sync_session_proxy_capability',
    default=None,
)

_ALLOWED_SCOPED_BUILTIN_FUNCTION_TYPES = {
    'coalesce': sqlalchemy.sql.functions.coalesce,
    'count': sqlalchemy.sql.functions.count,
    'now': sqlalchemy.sql.functions.now,
    'sum': sqlalchemy.sql.functions.sum,
}
_ALLOWED_SCOPED_GENERIC_FUNCTIONS = frozenset({'length', 'nullif'})
_ALLOWED_SCOPED_CUSTOM_OPERATORS = frozenset({'<=>'})
_ALLOWED_SCOPED_STATEMENT_TYPES = (
    sqlalchemy.sql.dml.UpdateBase,
    sqlalchemy.sql.selectable.SelectBase,
)
_ALLOWED_SCOPED_POST_VALUES_TYPES = (
    PostgreSQLOnConflictDoUpdate,
    SQLiteOnConflictDoUpdate,
)


def _collect_embedded_clause_elements(value: typing.Any) -> list[sqlalchemy.sql.elements.ClauseElement]:
    """Find executable expressions in SQLAlchemy containers omitted by visitors."""

    if isinstance(value, sqlalchemy.sql.elements.ClauseElement):
        return [value]
    if isinstance(value, collections.abc.Mapping):
        elements: list[sqlalchemy.sql.elements.ClauseElement] = []
        for key, item in value.items():
            elements.extend(_collect_embedded_clause_elements(key))
            elements.extend(_collect_embedded_clause_elements(item))
        return elements
    if isinstance(value, (list, tuple)):
        elements = []
        for item in value:
            elements.extend(_collect_embedded_clause_elements(item))
        return elements
    clause_factory = getattr(value, '__clause_element__', None)
    if callable(clause_factory):
        clause_element = clause_factory()
        if isinstance(clause_element, sqlalchemy.sql.elements.ClauseElement):
            return [clause_element]
    return []


def _validate_opaque_identifier(
    value: typing.Any,
    *,
    label: str,
) -> list[sqlalchemy.sql.elements.ClauseElement]:
    """Validate identifiers stored outside SQLAlchemy's normal AST traversal."""

    if isinstance(value, sqlalchemy.sql.elements.ClauseElement):
        return [value]
    if not isinstance(value, str):
        raise ScopedSessionTransactionError(f'TenantUnitOfWork does not allow an unknown {label}')
    if isinstance(value, sqlalchemy.sql.elements.quoted_name) and value.quote is False:
        raise ScopedSessionTransactionError('TenantUnitOfWork does not allow forced-unquoted SQL identifiers')
    if not value or value[0].isdigit() or any(not (character.isalnum() or character == '_') for character in value):
        raise ScopedSessionTransactionError(f'TenantUnitOfWork does not allow an unsafe {label}')
    return []


def _validate_scoped_sql_type(
    sql_type: typing.Any,
    *,
    seen: set[int] | None = None,
) -> None:
    """Reject caller-defined SQL compilers hidden behind otherwise safe nodes."""

    if not isinstance(sql_type, sqlalchemy.types.TypeEngine):
        return
    if seen is None:
        seen = set()
    identity = id(sql_type)
    if identity in seen:
        return
    seen.add(identity)

    if type(sql_type) is Vector:
        return
    if not type(sql_type).__module__.startswith('sqlalchemy.'):
        raise ScopedSessionTransactionError('TenantUnitOfWork does not allow custom SQL types in public statements')

    for identifier_attribute in ('name', 'schema', 'collation'):
        identifier = getattr(sql_type, identifier_attribute, None)
        if isinstance(identifier, sqlalchemy.sql.elements.quoted_name) and identifier.quote is False:
            raise ScopedSessionTransactionError('TenantUnitOfWork does not allow forced-unquoted SQL type identifiers')

    nested_types: list[typing.Any] = [
        getattr(sql_type, 'item_type', None),
        getattr(sql_type, 'impl', None),
    ]
    nested_types.extend(getattr(sql_type, 'types', ()) or ())
    for nested_type in nested_types:
        if nested_type is not sql_type:
            _validate_scoped_sql_type(nested_type, seen=seen)


def _collect_multi_value_elements(
    multi_values: typing.Any,
) -> list[sqlalchemy.sql.elements.ClauseElement]:
    """Validate batch INSERT rows which SQLAlchemy omits from AST visitors."""

    children: list[sqlalchemy.sql.elements.ClauseElement] = []
    for value_group in multi_values or ():
        if not isinstance(value_group, (list, tuple)):
            raise ScopedSessionTransactionError('TenantUnitOfWork does not allow an unknown batch INSERT shape')
        for row in value_group:
            if isinstance(row, collections.abc.Mapping):
                for key, value in row.items():
                    children.extend(_validate_opaque_identifier(key, label='batch INSERT column'))
                    children.extend(_collect_embedded_clause_elements(value))
            elif isinstance(row, (list, tuple)):
                children.extend(_collect_embedded_clause_elements(row))
            else:
                raise ScopedSessionTransactionError('TenantUnitOfWork does not allow an unknown batch INSERT row')
    return children


def _iter_scoped_statement_elements(
    statement: sqlalchemy.sql.elements.ClauseElement,
) -> typing.Iterator[sqlalchemy.sql.elements.ClauseElement]:
    """Walk the SQL AST, including dialect clauses SQLAlchemy omits from visitors.

    PostgreSQL and SQLite ``ON CONFLICT`` clauses currently expose no children
    through ``get_children()``.  Their conflict targets and update expressions
    still form executable SQL, so this walker adds those containers explicitly
    and rejects any future, unknown post-values clause by default.
    """

    pending: list[sqlalchemy.sql.elements.ClauseElement] = [statement]
    seen: set[int] = set()
    while pending:
        element = pending.pop()
        identity = id(element)
        if identity in seen:
            continue
        seen.add(identity)
        yield element

        children = [
            child for child in element.get_children() if isinstance(child, sqlalchemy.sql.elements.ClauseElement)
        ]
        post_values_clause = getattr(element, '_post_values_clause', None)
        if post_values_clause is not None:
            if not isinstance(post_values_clause, _ALLOWED_SCOPED_POST_VALUES_TYPES):
                raise ScopedSessionTransactionError(
                    'TenantUnitOfWork does not allow an unknown dialect post-values SQL clause'
                )
            children.append(post_values_clause)

        children.extend(_collect_multi_value_elements(getattr(element, '_multi_values', ())))

        if isinstance(element, _ALLOWED_SCOPED_POST_VALUES_TYPES):
            if getattr(element, 'constraint_target', None) is not None:
                raise ScopedSessionTransactionError('TenantUnitOfWork does not allow named ON CONFLICT constraints')
            for target in getattr(element, 'inferred_target_elements', ()) or ():
                children.extend(_validate_opaque_identifier(target, label='ON CONFLICT target'))
            children.extend(_collect_embedded_clause_elements(getattr(element, 'inferred_target_whereclause', None)))
            children.extend(_collect_embedded_clause_elements(getattr(element, 'update_whereclause', None)))
            for update_pair in getattr(element, 'update_values_to_set', ()):
                if not isinstance(update_pair, (list, tuple)) or len(update_pair) != 2:
                    raise ScopedSessionTransactionError(
                        'TenantUnitOfWork does not allow an unknown ON CONFLICT update shape'
                    )
                key, value = update_pair
                children.extend(_validate_opaque_identifier(key, label='ON CONFLICT update column'))
                children.extend(_collect_embedded_clause_elements(value))

        pending.extend(children)


def _validate_scoped_statement_call(args: tuple[typing.Any, ...], kwargs: dict[str, typing.Any]) -> None:
    """Admit only structured SQLAlchemy statements with a small safe vocabulary.

    A textual denylist cannot be complete on PostgreSQL: ordinary built-in
    functions can execute SQL supplied in string arguments, while statement
    prefixes, suffixes, hints, and custom operators can inject syntax without
    appearing as a top-level ``TextClause``.  Tenant code therefore uses
    SQLAlchemy's structured query/DML AST exclusively.  Raw fragments and
    unknown functions/operators fail closed before compilation.
    """

    statement = args[0] if args else kwargs.get('statement')
    if statement is None:
        return
    if kwargs.get('execution_options'):
        raise ScopedSessionTransactionError('TenantUnitOfWork does not allow public SQL execution options')
    if kwargs.get('bind_arguments'):
        raise ScopedSessionTransactionError('TenantUnitOfWork does not allow foreign database bind arguments')
    if not isinstance(statement, _ALLOWED_SCOPED_STATEMENT_TYPES):
        raise ScopedSessionTransactionError(
            'TenantUnitOfWork public SQL must use a structured SQLAlchemy query, values, or DML statement'
        )

    for element in _iter_scoped_statement_elements(statement):
        if not type(element).__module__.startswith('sqlalchemy.'):
            raise ScopedSessionTransactionError(
                'TenantUnitOfWork does not allow custom SQL AST nodes in public statements'
            )

        _validate_scoped_sql_type(getattr(element, 'type', None))

        if isinstance(element, sqlalchemy.sql.selectable.Values):
            raise ScopedSessionTransactionError(
                'TenantUnitOfWork does not allow SQL VALUES constructs in public statements'
            )

        if isinstance(element, sqlalchemy.sql.dml.Insert) and getattr(element, 'select', None) is not None:
            raise ScopedSessionTransactionError(
                'TenantUnitOfWork does not allow INSERT FROM SELECT in public statements'
            )

        for identifier_attribute in ('name', 'schema', 'collation'):
            identifier = getattr(element, identifier_attribute, None)
            if isinstance(identifier, sqlalchemy.sql.elements.quoted_name) and identifier.quote is False:
                raise ScopedSessionTransactionError('TenantUnitOfWork does not allow forced-unquoted SQL identifiers')

        if any(
            getattr(element, attribute_name, None)
            for attribute_name in (
                '_prefixes',
                '_suffixes',
                '_hints',
                '_statement_hints',
                '_execution_options',
                '_with_options',
            )
        ):
            raise ScopedSessionTransactionError(
                'TenantUnitOfWork does not allow textual statement modifiers or execution options'
            )

        if (
            isinstance(element, sqlalchemy.sql.elements.TextClause)
            or getattr(
                element,
                '__visit_name__',
                None,
            )
            == 'textual_label_reference'
        ):
            raise ScopedSessionTransactionError(
                'TenantUnitOfWork does not allow raw or textual SQL fragments in public statements'
            )

        if isinstance(element, sqlalchemy.sql.elements.ColumnClause) and element.is_literal and element.name != '*':
            raise ScopedSessionTransactionError(
                'TenantUnitOfWork does not allow literal SQL columns in public statements'
            )

        if isinstance(element, sqlalchemy.sql.elements.Extract):
            raise ScopedSessionTransactionError(
                'TenantUnitOfWork does not allow SQL EXTRACT fields in public statements'
            )

        if isinstance(element, sqlalchemy.sql.elements.BindParameter) and element.literal_execute:
            raise ScopedSessionTransactionError('TenantUnitOfWork does not allow literal-execute SQL parameters')

        if isinstance(element, sqlalchemy.sql.elements.Cast) and type(element.type) is not Vector:
            raise ScopedSessionTransactionError(
                'TenantUnitOfWork only allows the trusted pgvector cast used by tenant vector search'
            )

        if isinstance(element, sqlalchemy.sql.functions.FunctionElement):
            function_name = str(getattr(element, 'name', '')).casefold()
            package_names = tuple(getattr(element, 'packagenames', ()))
            generic_function_allowed = (
                type(element) is sqlalchemy.sql.functions.Function
                and function_name in _ALLOWED_SCOPED_GENERIC_FUNCTIONS
            )
            builtin_function_allowed = _ALLOWED_SCOPED_BUILTIN_FUNCTION_TYPES.get(function_name) is type(element)
            if package_names or not (generic_function_allowed or builtin_function_allowed):
                raise ScopedSessionTransactionError(
                    f'TenantUnitOfWork does not allow SQL function {function_name or "<unknown>"!r}'
                )

        for operator_attribute in ('operator', 'modifier'):
            operator = getattr(element, operator_attribute, None)
            if not isinstance(operator, sqlalchemy.sql.operators.custom_op):
                continue
            operator_name = str(operator.opstring)
            if not (
                isinstance(element, sqlalchemy.sql.elements.BinaryExpression)
                and operator_attribute == 'operator'
                and operator_name in _ALLOWED_SCOPED_CUSTOM_OPERATORS
            ):
                raise ScopedSessionTransactionError(
                    f'TenantUnitOfWork does not allow custom SQL operator {operator_name!r}'
                )


class _NoopSessionEventCollection:
    """Empty SQLAlchemy SessionEvents collection used after fail-closed detection."""

    def __bool__(self) -> bool:
        return False

    def __iter__(self) -> typing.Iterator[typing.Any]:
        return iter(())

    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        del args, kwargs


class _NoopSessionEventsDispatch:
    """Prevent a rejected SessionEvents listener from firing during rollback cleanup."""

    _event_names: tuple[str, ...] = ()

    def __getattr__(self, name: str) -> _NoopSessionEventCollection:
        del name
        return _NOOP_SESSION_EVENT_COLLECTION


_NOOP_SESSION_EVENT_COLLECTION = _NoopSessionEventCollection()
_NOOP_SESSION_EVENTS_DISPATCH = _NoopSessionEventsDispatch()


class TenantScopedSyncSession(sqlalchemy_orm.Session):
    """Synchronous proxy usable only from its owning AsyncSession operation."""

    def __init__(
        self,
        bind: sqlalchemy.engine.Engine | sqlalchemy.engine.Connection | None = None,
        *,
        binds: dict[typing.Any, typing.Any] | None = None,
        langbot_guard_state: _ScopedSessionGuardState,
        **kwargs: typing.Any,
    ) -> None:
        if binds:
            raise ScopedSessionTransactionError('Tenant-scoped Sessions cannot use multiple database binds')
        object.__setattr__(self, '_langbot_guard_state', langbot_guard_state)
        object.__setattr__(self, '_langbot_expected_bind', bind)
        object.__setattr__(self, '_langbot_initializing', True)
        try:
            super().__init__(bind=bind, binds=None, **kwargs)
        finally:
            object.__setattr__(self, '_langbot_initializing', False)

    def __getattribute__(self, name: str) -> typing.Any:
        if name.startswith('_'):
            return super().__getattribute__(name)
        self._require_proxy_capability()
        guard = object.__getattribute__(self, '_langbot_guard_state')
        if name == 'dispatch' and guard.session_events_blocked:
            return _NOOP_SESSION_EVENTS_DISPATCH
        attribute = super().__getattribute__(name)
        if name == 'dispatch' and not object.__getattribute__(self, '_langbot_initializing'):
            event_name = next(
                (candidate for candidate in attribute._event_names if bool(getattr(attribute, candidate))),
                None,
            )
            if event_name is not None:
                guard.session_events_blocked = True
                self._reject_proxy_escape(f'ORM Session event listener {event_name}')
        if isinstance(attribute, types.MethodType):
            return self._guard_method_call(attribute)
        return attribute

    def __setattr__(self, name: str, value: typing.Any) -> None:
        if name.startswith('_') or object.__getattribute__(self, '_langbot_initializing'):
            super().__setattr__(name, value)
            return
        self._require_proxy_capability()
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if name.startswith('_') or object.__getattribute__(self, '_langbot_initializing'):
            super().__delattr__(name)
            return
        self._require_proxy_capability()
        super().__delattr__(name)

    def get_bind(
        self,
        mapper: typing.Any = None,
        *,
        clause: typing.Any = None,
        bind: typing.Any = None,
        **kwargs: typing.Any,
    ) -> sqlalchemy.engine.Engine | sqlalchemy.engine.Connection:
        self._require_proxy_capability()
        expected_bind = object.__getattribute__(self, '_langbot_expected_bind')
        if bind is not None and bind is not expected_bind:
            self._reject_proxy_escape('foreign database bind')
        resolved = super().get_bind(mapper, clause=clause, bind=bind, **kwargs)
        if resolved is not expected_bind:
            self._reject_proxy_escape('foreign database bind')
        return resolved

    def flush(self, objects: typing.Sequence[typing.Any] | None = None) -> None:
        """Reject caller-supplied SQL expressions hidden in ORM state."""

        self._require_proxy_capability()
        for instance in self.new.union(self.dirty):
            state = sqlalchemy.inspect(instance)
            for column_property in state.mapper.column_attrs:
                for value in state.attrs[column_property.key].history.added:
                    if isinstance(value, sqlalchemy.sql.elements.ClauseElement):
                        self._reject_proxy_escape('ORM SQL expression attribute value')
                    clause_factory = getattr(value, '__clause_element__', None)
                    if callable(clause_factory) and isinstance(
                        clause_factory(),
                        sqlalchemy.sql.elements.ClauseElement,
                    ):
                        self._reject_proxy_escape('ORM SQL expression attribute value')
        super().flush(objects)

    def _guard_method_call(self, method: types.MethodType) -> typing.Callable[..., typing.Any]:
        @functools.wraps(method)
        def guarded(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            self._require_proxy_capability()
            return method(*args, **kwargs)

        return guarded

    def _require_proxy_capability(self) -> None:
        if object.__getattribute__(self, '_langbot_initializing'):
            return
        guard = object.__getattribute__(self, '_langbot_guard_state')
        if not guard.active:
            raise ScopedSessionTransactionError('TenantUnitOfWork scoped Session is no longer active')
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if guard.owner_task is not current_task:
            raise CrossScopeTransactionError(
                'Scoped database sessions cannot be inherited by child tasks; open an explicit task scope'
            )
        if _SYNC_PROXY_CAPABILITY.get() is not guard:
            self._reject_proxy_escape('synchronous Session access')

    def _reject_proxy_escape(self, operation: str) -> typing.NoReturn:
        guard = object.__getattribute__(self, '_langbot_guard_state')
        if guard.transaction_state is not None:
            error = ScopedSessionTransactionError(
                f'TenantUnitOfWork owns AsyncSession lifecycle; direct {operation} is not allowed'
            )
            guard.transaction_state.mark_rollback_only(error)
            raise error
        raise ScopedSessionTransactionError(
            f'TenantUnitOfWork owns AsyncSession lifecycle; direct {operation} is not allowed'
        )


class TenantScopedAsyncSession(sqlalchemy_asyncio.AsyncSession):
    """An AsyncSession whose task and transaction lifecycle are UoW-owned.

    Normal ORM operations remain available to the task which opened the UoW.
    Transaction-control and connection-escape APIs are deliberately withheld:
    committing, rolling back, or closing the raw Session would otherwise let a
    nested caller defeat the outer unit of work.  A blanket public-attribute
    owner check also covers a Session captured in the parent task and later
    passed directly to a child task.
    """

    def __init__(
        self,
        bind: sqlalchemy_asyncio.AsyncEngine,
        *,
        owner_task: asyncio.Task[typing.Any] | None,
        **kwargs: typing.Any,
    ) -> None:
        guard = _ScopedSessionGuardState(owner_task=owner_task)
        object.__setattr__(self, '_langbot_guard_state', guard)
        object.__setattr__(self, '_langbot_bind', None)
        object.__setattr__(self, '_langbot_internal_access_depth', 0)
        object.__setattr__(self, '_langbot_sync_capability_tokens', [])
        object.__setattr__(self, '_langbot_initializing', True)
        capability_token = _SYNC_PROXY_CAPABILITY.set(guard)
        try:
            super().__init__(
                bind,
                sync_session_class=TenantScopedSyncSession,
                langbot_guard_state=guard,
                **kwargs,
            )
        finally:
            _SYNC_PROXY_CAPABILITY.reset(capability_token)
            object.__setattr__(self, '_langbot_initializing', False)

    def __getattribute__(self, name: str) -> typing.Any:
        # ContextVars are copied into asyncio child tasks, and callers can also
        # copy the Session object itself.  Guard the whole supported public
        # surface rather than trying to enumerate every current/future ORM I/O
        # method. Private attributes remain an internal implementation detail.
        if name.startswith('_'):
            return super().__getattribute__(name)

        self._require_owner_task()
        if (
            name in {'sync_session', 'binds', 'object_session'}
            and object.__getattribute__(self, '_langbot_internal_access_depth') == 0
        ):
            self._reject_transaction_escape(f'{name} access')
        self._enter_internal_access()
        try:
            attribute = super().__getattribute__(name)
        finally:
            self._exit_internal_access()
        if isinstance(attribute, types.MethodType):
            return self._guard_method_call(attribute)
        return attribute

    def __setattr__(self, name: str, value: typing.Any) -> None:
        if name.startswith('_'):
            super().__setattr__(name, value)
            return
        self._require_owner_task()
        if not object.__getattribute__(self, '_langbot_initializing') and name in {'bind', 'binds', 'sync_session'}:
            self._reject_transaction_escape(f'{name} replacement')
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if name.startswith('_'):
            super().__delattr__(name)
            return
        self._require_owner_task()
        if name in {'bind', 'binds', 'sync_session'}:
            self._reject_transaction_escape(f'{name} deletion')
        super().__delattr__(name)

    @property
    def bind(self) -> typing.NoReturn:
        self._reject_transaction_escape('bind access')

    @bind.setter
    def bind(self, value: sqlalchemy_asyncio.AsyncEngine) -> None:
        existing = object.__getattribute__(self, '_langbot_bind')
        if existing is not None:
            self._reject_transaction_escape('bind replacement')
        object.__setattr__(self, '_langbot_bind', value)

    @property
    def no_autoflush(self) -> typing.ContextManager[None]:
        """Preserve SQLAlchemy's helper without exposing the synchronous Session."""

        @contextlib.contextmanager
        def boundary() -> typing.Iterator[None]:
            self._require_owner_task()
            sync_session = object.__getattribute__(self, '_proxied')
            previous = object.__getattribute__(sync_session, 'autoflush')
            object.__setattr__(sync_session, 'autoflush', False)
            try:
                yield
            finally:
                self._require_owner_task()
                object.__setattr__(sync_session, 'autoflush', previous)

        return boundary()

    def _bind_transaction_state(self, capability: object, state: ActiveScopedTransaction) -> None:
        self._require_control_capability(capability, 'transaction-state binding')
        self._require_owner_task()
        object.__getattribute__(self, '_langbot_guard_state').transaction_state = state

    def begin(self) -> typing.NoReturn:
        self._reject_transaction_escape('begin')

    def begin_nested(self) -> typing.NoReturn:
        self._reject_transaction_escape('begin_nested')

    async def commit(self) -> typing.NoReturn:
        self._reject_transaction_escape('commit')

    async def rollback(self) -> typing.NoReturn:
        self._reject_transaction_escape('rollback')

    async def close(self) -> typing.NoReturn:
        self._reject_transaction_escape('close')

    async def aclose(self) -> typing.NoReturn:
        self._reject_transaction_escape('aclose')

    async def reset(self) -> typing.NoReturn:
        self._reject_transaction_escape('reset')

    async def invalidate(self) -> typing.NoReturn:
        self._reject_transaction_escape('invalidate')

    async def close_all(self) -> typing.NoReturn:
        self._reject_transaction_escape('close_all')

    async def connection(self, *args: typing.Any, **kwargs: typing.Any) -> typing.NoReturn:
        del args, kwargs
        self._reject_transaction_escape('connection')

    def get_bind(self, *args: typing.Any, **kwargs: typing.Any) -> typing.NoReturn:
        del args, kwargs
        self._reject_transaction_escape('get_bind')

    def get_transaction(self) -> typing.NoReturn:
        self._reject_transaction_escape('get_transaction')

    def get_nested_transaction(self) -> typing.NoReturn:
        self._reject_transaction_escape('get_nested_transaction')

    async def run_sync(self, *args: typing.Any, **kwargs: typing.Any) -> typing.NoReturn:
        del args, kwargs
        self._reject_transaction_escape('run_sync')

    async def __aenter__(self) -> typing.NoReturn:
        self._reject_transaction_escape('context-manager entry')

    async def __aexit__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.NoReturn:
        del args, kwargs
        self._reject_transaction_escape('context-manager exit')

    async def _start_owned_transaction(self, capability: object) -> sqlalchemy_asyncio.AsyncSessionTransaction:
        """Start the one root transaction; callable only by TenantUnitOfWork."""

        self._require_control_capability(capability, 'owned transaction start')
        self._require_owner_task()
        self._enter_internal_access()
        try:
            transaction = super().begin()
            await transaction
            return transaction
        finally:
            self._exit_internal_access()

    async def _close_owned_session(self, capability: object) -> None:
        """Close the Session after its root transaction has been finalized."""

        self._require_control_capability(capability, 'owned Session close')
        self._require_owner_task()
        self._enter_internal_access()
        try:
            await super().close()
        finally:
            try:
                self._exit_internal_access()
            finally:
                guard = object.__getattribute__(self, '_langbot_guard_state')
                guard.active = False
                guard.transaction_state = None
                guard.owner_task = None

    async def _commit_owned_transaction(
        self,
        capability: object,
        transaction: sqlalchemy_asyncio.AsyncSessionTransaction,
    ) -> None:
        self._require_control_capability(capability, 'owned transaction commit')
        self._require_owner_task()
        self._enter_internal_access()
        try:
            await transaction.commit()
        finally:
            self._exit_internal_access()

    async def _rollback_owned_transaction(
        self,
        capability: object,
        transaction: sqlalchemy_asyncio.AsyncSessionTransaction,
    ) -> None:
        self._require_control_capability(capability, 'owned transaction rollback')
        self._require_owner_task()
        self._enter_internal_access()
        try:
            await transaction.rollback()
        finally:
            self._exit_internal_access()

    async def _apply_owned_scope_setting(
        self,
        capability: object,
        setting_name: str,
        setting_value: str,
    ) -> None:
        self._require_control_capability(capability, 'tenant scope configuration')
        if setting_name not in {
            TENANT_SETTING,
            ACCOUNT_SETTING,
            API_KEY_HASH_SETTING,
            INVITATION_HASH_SETTING,
            INSTANCE_SETTING,
            IDENTITY_DIGEST_SETTING,
        }:
            self._reject_transaction_escape('unknown tenant scope configuration')
        self._require_owner_task()
        self._enter_internal_access()
        try:
            await super().execute(
                sqlalchemy.text('SELECT set_config(:setting_name, :setting_value, true)'),
                {'setting_name': setting_name, 'setting_value': setting_value},
            )
        finally:
            self._exit_internal_access()

    async def execute_on_transaction_connection(
        self,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> sqlalchemy.engine.cursor.CursorResult[typing.Any]:
        """Execute Core SQL without exposing the transaction-bound Connection."""

        self._require_owner_task()
        self._validate_statement_or_reject(args, kwargs)
        self._enter_internal_access()
        try:
            await super().flush()
            connection = await super().connection()
            return await connection.execute(*args, **kwargs)
        finally:
            self._exit_internal_access()

    async def execute(self, *args: typing.Any, **kwargs: typing.Any) -> sqlalchemy.engine.Result[typing.Any]:
        self._validate_statement_or_reject(args, kwargs)
        return await super().execute(*args, **kwargs)

    async def get(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        self._reject_nonempty_orm_options(
            'get',
            kwargs,
            {'options', 'with_for_update', 'identity_token', 'execution_options', 'bind_arguments'},
        )
        return await super().get(*args, **kwargs)

    async def get_one(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        self._reject_nonempty_orm_options(
            'get_one',
            kwargs,
            {'options', 'with_for_update', 'identity_token', 'execution_options', 'bind_arguments'},
        )
        return await super().get_one(*args, **kwargs)

    async def refresh(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self._reject_nonempty_orm_options('refresh', kwargs, {'with_for_update'})
        await super().refresh(*args, **kwargs)

    async def merge(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        self._reject_nonempty_orm_options('merge', kwargs, {'options'})
        return await super().merge(*args, **kwargs)

    async def scalar(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        self._validate_statement_or_reject(args, kwargs)
        return await super().scalar(*args, **kwargs)

    async def scalars(self, *args: typing.Any, **kwargs: typing.Any) -> sqlalchemy.engine.ScalarResult[typing.Any]:
        self._validate_statement_or_reject(args, kwargs)
        return await super().scalars(*args, **kwargs)

    async def stream(self, *args: typing.Any, **kwargs: typing.Any) -> sqlalchemy_asyncio.AsyncResult[typing.Any]:
        del args, kwargs
        self._reject_transaction_escape('stream; live database results cannot outlive the task-owned UoW operation')

    async def stream_scalars(
        self,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> sqlalchemy_asyncio.AsyncScalarResult[typing.Any]:
        del args, kwargs
        self._reject_transaction_escape(
            'stream_scalars; live database results cannot outlive the task-owned UoW operation'
        )

    def _validate_statement_or_reject(
        self,
        args: tuple[typing.Any, ...],
        kwargs: dict[str, typing.Any],
    ) -> None:
        try:
            _validate_scoped_statement_call(args, kwargs)
        except ScopedSessionTransactionError as exc:
            guard = object.__getattribute__(self, '_langbot_guard_state')
            if guard.transaction_state is not None:
                guard.transaction_state.mark_rollback_only(exc)
            raise

    def _reject_nonempty_orm_options(
        self,
        operation: str,
        kwargs: dict[str, typing.Any],
        option_names: set[str],
    ) -> None:
        for option_name in option_names:
            value = kwargs.get(option_name)
            if option_name == 'with_for_update':
                if value is None or value is False:
                    continue
                self._reject_transaction_escape(f'{operation} option {option_name}')
            if option_name == 'identity_token':
                if value is None:
                    continue
                self._reject_transaction_escape(f'{operation} option {option_name}')
            if value is None or value is False:
                continue
            if isinstance(value, collections.abc.Sized) and len(value) == 0:
                continue
            self._reject_transaction_escape(f'{operation} option {option_name}')

    def _guard_method_call(self, method: types.MethodType) -> typing.Callable[..., typing.Any]:
        if asyncio.iscoroutinefunction(method):

            @functools.wraps(method)
            async def guarded_async(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                self._require_owner_task()
                self._enter_internal_access()
                try:
                    return await method(*args, **kwargs)
                finally:
                    self._exit_internal_access()

            return guarded_async

        @functools.wraps(method)
        def guarded_sync(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            self._require_owner_task()
            self._enter_internal_access()
            try:
                return method(*args, **kwargs)
            finally:
                self._exit_internal_access()

        return guarded_sync

    def _enter_internal_access(self) -> None:
        depth = object.__getattribute__(self, '_langbot_internal_access_depth')
        guard = object.__getattribute__(self, '_langbot_guard_state')
        tokens = object.__getattribute__(self, '_langbot_sync_capability_tokens')
        tokens.append(_SYNC_PROXY_CAPABILITY.set(guard))
        object.__setattr__(self, '_langbot_internal_access_depth', depth + 1)

    def _exit_internal_access(self) -> None:
        depth = object.__getattribute__(self, '_langbot_internal_access_depth')
        if depth <= 0:
            raise RuntimeError('Scoped Session internal access stack underflow')
        tokens = object.__getattribute__(self, '_langbot_sync_capability_tokens')
        _SYNC_PROXY_CAPABILITY.reset(tokens.pop())
        object.__setattr__(self, '_langbot_internal_access_depth', depth - 1)

    def _require_control_capability(self, capability: object, operation: str) -> None:
        if capability is not _UOW_SESSION_CONTROL_CAPABILITY:
            self._reject_transaction_escape(operation)

    def _require_owner_task(self) -> None:
        guard = object.__getattribute__(self, '_langbot_guard_state')
        if not guard.active:
            raise ScopedSessionTransactionError('TenantUnitOfWork scoped Session is no longer active')
        owner_task = guard.owner_task
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if owner_task is not current_task:
            raise CrossScopeTransactionError(
                'Scoped database sessions cannot be inherited by child tasks; open an explicit task scope'
            )

    def _reject_transaction_escape(self, operation: str) -> typing.NoReturn:
        self._require_owner_task()
        error = ScopedSessionTransactionError(
            f'TenantUnitOfWork owns AsyncSession transaction lifecycle; direct {operation} is not allowed'
        )
        state = object.__getattribute__(self, '_langbot_guard_state').transaction_state
        if state is not None:
            state.mark_rollback_only(error)
        raise error


ActiveTransactionVar = contextvars.ContextVar[ActiveScopedTransaction | None]

# ``AsyncSession`` delegates database I/O to a greenlet-backed synchronous
# Engine, but Python context variables are preserved across that boundary.  A
# per-engine ``handle_error`` listener therefore covers DBAPI failures from all
# direct Session APIs (execute/scalar/get/flush) as well as callers which obtain
# the transaction-bound Connection.  The owner-task and engine checks prevent
# copied child-task contexts or unrelated database engines from poisoning this
# transaction.
_DATABASE_OPERATION_TRANSACTION: contextvars.ContextVar[ActiveScopedTransaction | None] = contextvars.ContextVar(
    'langbot_database_operation_transaction',
    default=None,
)


def _mark_current_transaction_rollback_only(exception_context: typing.Any) -> None:
    state = _DATABASE_OPERATION_TRANSACTION.get()
    if state is None:
        return
    try:
        current_task = asyncio.current_task()
    except RuntimeError:  # pragma: no cover - async engines always run in an event loop
        return
    if state.owner_task is not current_task or exception_context.engine is not state.engine.sync_engine:
        return
    cause = exception_context.sqlalchemy_exception or exception_context.original_exception
    state.mark_rollback_only(cause)


def _install_rollback_only_error_listener(engine: sqlalchemy_asyncio.AsyncEngine) -> None:
    sync_engine = engine.sync_engine
    if not sqlalchemy.event.contains(sync_engine, 'handle_error', _mark_current_transaction_rollback_only):
        sqlalchemy.event.listen(sync_engine, 'handle_error', _mark_current_transaction_rollback_only)


@dataclasses.dataclass(slots=True)
class ActivePersistenceScope:
    """A trusted visibility scope without an open database transaction."""

    scope: PersistenceScope
    owner_task: asyncio.Task[typing.Any] | None
    depth: int = 1


ActivePersistenceScopeVar = contextvars.ContextVar[ActivePersistenceScope | None]


class PersistenceScopeBoundary:
    """Carry a trusted persistence scope across long-running async work.

    Unlike :class:`TenantUnitOfWork`, this boundary never opens a database
    session. ``PersistenceManager.execute_async`` materializes the scope as a
    short transaction for each database call. This makes the boundary suitable
    for request and pipeline lifetimes which can spend substantial time waiting
    on model providers, tools, or streaming clients.

    Context variables are copied into child tasks, so implicit use from a child
    task is rejected by the manager. A child may establish its own explicit
    boundary because the scope value still comes from trusted application code.
    """

    def __init__(
        self,
        scope: PersistenceScope,
        *,
        active_scope: ActivePersistenceScopeVar,
        active_transaction: ActiveTransactionVar,
    ) -> None:
        self.scope = scope
        self._active_scope = active_scope
        self._active_transaction = active_transaction
        self._active_state: ActivePersistenceScope | None = None
        self._context_token: contextvars.Token[ActivePersistenceScope | None] | None = None
        self._used = False
        self._owns_scope = False

    async def __aenter__(self) -> PersistenceScopeBoundary:
        if self._used:
            raise RuntimeError('PersistenceScopeBoundary instances cannot be reused')
        self._used = True

        transaction = self._active_transaction.get()
        if transaction is not None:
            if transaction.owner_task is not asyncio.current_task():
                raise CrossScopeTransactionError(
                    'Scoped database transactions cannot be inherited by child tasks; open an explicit task scope'
                )
            if transaction.scope != self.scope:
                raise CrossScopeTransactionError(
                    f'Cannot enter {self.scope.kind.value} scope while {transaction.scope.kind.value} scope is active'
                )

        active = self._active_scope.get()
        if active is not None and active.owner_task is asyncio.current_task():
            if active.scope != self.scope:
                raise CrossScopeTransactionError(
                    f'Cannot enter {self.scope.kind.value} scope while {active.scope.kind.value} scope is active'
                )
            active.depth += 1
            self._active_state = active
            return self

        state = ActivePersistenceScope(
            scope=self.scope,
            owner_task=asyncio.current_task(),
        )
        self._active_state = state
        self._context_token = self._active_scope.set(state)
        self._owns_scope = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> bool:
        del exc_type, exc_value, traceback
        state = self._active_state
        if state is None:
            raise RuntimeError('PersistenceScopeBoundary has no active state')
        if state.owner_task is not asyncio.current_task():
            raise CrossScopeTransactionError('Scoped persistence boundaries cannot be exited by a different task')

        if not self._owns_scope:
            state.depth -= 1
            self._active_state = None
            return False

        if self._context_token is None:
            raise RuntimeError('PersistenceScopeBoundary has no context token')
        self._active_scope.reset(self._context_token)
        state.depth = 0
        self._active_state = None
        return False


class TenantUnitOfWork:
    """Bind one trusted visibility scope to one database transaction.

    PostgreSQL receives transaction-local settings consumed by RLS policies.
    SQLite keeps the same transaction boundary so OSS code exercises the same
    request/task ownership and rollback semantics. A manager-owned ContextVar
    lets all legacy ``execute_async`` helpers reuse this exact session.
    """

    def __init__(
        self,
        engine: sqlalchemy_asyncio.AsyncEngine,
        workspace_uuid: str | None = None,
        *,
        scope: PersistenceScope | None = None,
        active_transaction: ActiveTransactionVar | None = None,
        active_scope: ActivePersistenceScopeVar | None = None,
    ) -> None:
        if (workspace_uuid is None) == (scope is None):
            raise ValueError('TenantUnitOfWork requires exactly one Workspace or persistence scope')

        self._engine = engine
        self.scope = scope or PersistenceScope.workspace(typing.cast(str, workspace_uuid))
        self.workspace_uuid = self.scope.settings[0][1] if self.scope.kind == PersistenceScopeKind.WORKSPACE else None
        self._active_transaction = active_transaction
        self._active_scope = active_scope
        self._session: sqlalchemy_asyncio.AsyncSession | None = None
        self._transaction: sqlalchemy_asyncio.AsyncSessionTransaction | None = None
        self._active_state: ActiveScopedTransaction | None = None
        self._context_token: contextvars.Token[ActiveScopedTransaction | None] | None = None
        self._database_operation_token: contextvars.Token[ActiveScopedTransaction | None] | None = None
        self._used = False
        self._owns_transaction = False
        _install_rollback_only_error_listener(engine)

    @property
    def session(self) -> sqlalchemy_asyncio.AsyncSession:
        if self._session is None:
            raise RuntimeError('TenantUnitOfWork is not active')
        if self._active_state is not None:
            self._require_owner_task(self._active_state)
        return self._session

    async def __aenter__(self) -> TenantUnitOfWork:
        if self._used:
            raise RuntimeError('TenantUnitOfWork instances cannot be reused')
        self._used = True

        active_scope = self._active_scope.get() if self._active_scope is not None else None
        if active_scope is not None and active_scope.owner_task is asyncio.current_task():
            if active_scope.scope != self.scope:
                # A request/runtime Workspace boundary is transaction-free and
                # may temporarily enter a narrower trusted discovery UoW (for
                # example, resolving an account record by its verified UUID).
                # It must still never switch directly to another Workspace.
                workspace_to_discovery = (
                    active_scope.scope.kind == PersistenceScopeKind.WORKSPACE
                    and self.scope.kind != PersistenceScopeKind.WORKSPACE
                )
                if not workspace_to_discovery:
                    raise CrossScopeTransactionError(
                        f'Cannot enter {self.scope.kind.value} scope '
                        f'while {active_scope.scope.kind.value} scope is active'
                    )

        active = self._active_transaction.get() if self._active_transaction is not None else None
        if active is not None:
            if active.owner_task is asyncio.current_task():
                if active.scope != self.scope:
                    raise CrossScopeTransactionError(
                        f'Cannot enter {self.scope.kind.value} scope while {active.scope.kind.value} scope is active'
                    )
                active.depth += 1
                self._active_state = active
                self._session = active.session
                return self
            # ContextVars are copied into child tasks. Merely calling a helper
            # there must fail (PersistenceManager enforces that), but an
            # explicit UoW is allowed to replace the inherited pointer with an
            # independent transaction owned by the child task.

        owner_task = asyncio.current_task()
        session = TenantScopedAsyncSession(
            self._engine,
            owner_task=owner_task,
            expire_on_commit=False,
            close_resets_only=False,
        )
        self._session = session
        transaction: sqlalchemy_asyncio.AsyncSessionTransaction | None = None
        try:
            transaction = await session._start_owned_transaction(_UOW_SESSION_CONTROL_CAPABILITY)
            self._transaction = transaction
            if self._engine.dialect.name == 'postgresql':
                for setting_name, setting_value in self.scope.settings:
                    await session._apply_owned_scope_setting(
                        _UOW_SESSION_CONTROL_CAPABILITY,
                        setting_name,
                        setting_value,
                    )
            state = ActiveScopedTransaction(
                scope=self.scope,
                session=session,
                engine=self._engine,
                owner_task=owner_task,
            )
            session._bind_transaction_state(_UOW_SESSION_CONTROL_CAPABILITY, state)
            self._active_state = state
            if self._active_transaction is not None:
                self._context_token = self._active_transaction.set(state)
            self._database_operation_token = _DATABASE_OPERATION_TRANSACTION.set(state)
            self._owns_transaction = True
        except BaseException:
            if self._database_operation_token is not None:
                _DATABASE_OPERATION_TRANSACTION.reset(self._database_operation_token)
                self._database_operation_token = None
            if self._active_transaction is not None and self._context_token is not None:
                self._active_transaction.reset(self._context_token)
                self._context_token = None
            if transaction is not None and transaction.sync_transaction is not None:
                await session._rollback_owned_transaction(_UOW_SESSION_CONTROL_CAPABILITY, transaction)
            await session._close_owned_session(_UOW_SESSION_CONTROL_CAPABILITY)
            self._session = None
            self._transaction = None
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> bool:
        state = self._active_state
        if state is None:
            raise RuntimeError('TenantUnitOfWork has no active transaction state')
        self._require_owner_task(state)

        if not self._owns_transaction:
            if exc_type is not None:
                state.mark_rollback_only(exc_value)
            state.depth -= 1
            self._session = None
            self._active_state = None
            return False

        session = self.session
        transaction = self._transaction
        if transaction is None:
            raise RuntimeError('TenantUnitOfWork has no active root transaction')
        if exc_type is not None:
            state.mark_rollback_only(exc_value)
        rollback_only = state.rollback_only
        committed = False
        try:
            if exc_type is None and not rollback_only:
                await typing.cast(TenantScopedAsyncSession, session)._commit_owned_transaction(
                    _UOW_SESSION_CONTROL_CAPABILITY,
                    transaction,
                )
                committed = True
            else:
                await typing.cast(TenantScopedAsyncSession, session)._rollback_owned_transaction(
                    _UOW_SESSION_CONTROL_CAPABILITY,
                    transaction,
                )
        finally:
            try:
                if self._active_transaction is not None and self._context_token is not None:
                    self._active_transaction.reset(self._context_token)
                await typing.cast(TenantScopedAsyncSession, session)._close_owned_session(
                    _UOW_SESSION_CONTROL_CAPABILITY
                )
            finally:
                if self._database_operation_token is not None:
                    _DATABASE_OPERATION_TRANSACTION.reset(self._database_operation_token)
                self._database_operation_token = None
                self._session = None
                self._transaction = None
                self._active_state = None
                state.depth = 0
                self._complete_after_commit_waiters(state, committed=committed)

        if exc_type is None and rollback_only:
            raise TransactionRollbackOnlyError(
                'A scoped database operation failed or rolled back; '
                'the transaction was rolled back and after-commit work was cancelled'
            ) from state.rollback_only_cause
        return False

    async def execute(self, *args: typing.Any, **kwargs: typing.Any) -> sqlalchemy.engine.Result[typing.Any]:
        try:
            return await self.session.execute(*args, **kwargs)
        except BaseException as exc:
            self._mark_rollback_only(exc)
            raise

    async def flush(self) -> None:
        try:
            await self.session.flush()
        except BaseException as exc:
            self._mark_rollback_only(exc)
            raise

    def _mark_rollback_only(self, cause: BaseException) -> None:
        state = self._active_state
        if state is not None:
            state.mark_rollback_only(cause)

    @staticmethod
    def _require_owner_task(state: ActiveScopedTransaction) -> None:
        if state.owner_task is not asyncio.current_task():
            raise CrossScopeTransactionError(
                'Scoped database transactions cannot be inherited by child tasks; open an explicit task scope'
            )

    @staticmethod
    def _complete_after_commit_waiters(
        state: ActiveScopedTransaction,
        *,
        committed: bool,
    ) -> None:
        for waiter in state.after_commit_waiters:
            if waiter.done():
                continue
            if committed:
                waiter.set_result(None)
            else:
                waiter.cancel()
        state.after_commit_waiters.clear()
