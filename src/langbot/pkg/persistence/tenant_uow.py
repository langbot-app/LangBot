from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import enum
import types
import typing

import sqlalchemy
import sqlalchemy.ext.asyncio as sqlalchemy_asyncio


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

        session = sqlalchemy_asyncio.AsyncSession(self._engine, expire_on_commit=False)
        self._session = session
        try:
            await session.begin()
            if self._engine.dialect.name == 'postgresql':
                for setting_name, setting_value in self.scope.settings:
                    await session.execute(
                        sqlalchemy.text('SELECT set_config(:setting_name, :setting_value, true)'),
                        {'setting_name': setting_name, 'setting_value': setting_value},
                    )
            state = ActiveScopedTransaction(
                scope=self.scope,
                session=session,
                engine=self._engine,
                owner_task=asyncio.current_task(),
            )
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
            await session.rollback()
            await session.close()
            self._session = None
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
        if exc_type is not None:
            state.mark_rollback_only(exc_value)
        rollback_only = state.rollback_only
        committed = False
        try:
            if exc_type is None and not rollback_only:
                await session.commit()
                committed = True
            else:
                await session.rollback()
        finally:
            try:
                if self._active_transaction is not None and self._context_token is not None:
                    self._active_transaction.reset(self._context_token)
                await session.close()
            finally:
                if self._database_operation_token is not None:
                    _DATABASE_OPERATION_TRANSACTION.reset(self._database_operation_token)
                    self._database_operation_token = None
                self._session = None
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
