from __future__ import annotations

import types
import typing

import sqlalchemy
import sqlalchemy.ext.asyncio as sqlalchemy_asyncio


TENANT_SETTING = 'langbot.workspace_uuid'
TENANT_POLICY_NAME = 'langbot_workspace_isolation'

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
}


class TenantUnitOfWork:
    """Bind one Workspace scope to one database transaction.

    PostgreSQL receives a transaction-local setting used by RLS policies.
    SQLite keeps the same transaction boundary without a database setting so
    OSS callers can adopt this API without changing database engines.
    """

    def __init__(self, engine: sqlalchemy_asyncio.AsyncEngine, workspace_uuid: str) -> None:
        workspace_uuid = workspace_uuid.strip()
        if not workspace_uuid:
            raise ValueError('TenantUnitOfWork requires a non-empty workspace_uuid')

        self._engine = engine
        self.workspace_uuid = workspace_uuid
        self._session: sqlalchemy_asyncio.AsyncSession | None = None
        self._used = False

    @property
    def session(self) -> sqlalchemy_asyncio.AsyncSession:
        if self._session is None:
            raise RuntimeError('TenantUnitOfWork is not active')
        return self._session

    async def __aenter__(self) -> TenantUnitOfWork:
        if self._used:
            raise RuntimeError('TenantUnitOfWork instances cannot be reused')
        self._used = True

        session = sqlalchemy_asyncio.AsyncSession(self._engine, expire_on_commit=False)
        self._session = session
        try:
            await session.begin()
            if self._engine.dialect.name == 'postgresql':
                await session.execute(
                    sqlalchemy.text(f"SELECT set_config('{TENANT_SETTING}', :workspace_uuid, true)"),
                    {'workspace_uuid': self.workspace_uuid},
                )
        except BaseException:
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
        session = self.session
        try:
            if exc_type is None:
                await session.commit()
            else:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
        return False

    async def execute(self, *args: typing.Any, **kwargs: typing.Any) -> sqlalchemy.engine.Result[typing.Any]:
        return await self.session.execute(*args, **kwargs)

    async def flush(self) -> None:
        await self.session.flush()
