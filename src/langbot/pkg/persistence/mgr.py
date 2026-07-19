from __future__ import annotations

import datetime
import sqlite3
import typing


import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
import sqlalchemy

from . import database, migration, sqlite_migration_backup
from ..entity.persistence import base, metadata, model as persistence_model
from ..entity.persistence import workspace as persistence_workspace
from ..entity import persistence
from ..core import app
from ..utils import constants, importutil
from . import databases, migrations

importutil.import_modules_in_pkg(databases)
importutil.import_modules_in_pkg(migrations)
importutil.import_modules_in_pkg(persistence)


_ALEMBIC_TENANT_TABLES = {
    'workspaces',
    'workspace_memberships',
    'workspace_invitations',
    'workspace_execution_states',
    'workspace_metadata',
    'api_keys',
    'bots',
    'bot_admins',
    'binary_storages',
    'mcp_servers',
    'model_providers',
    'llm_models',
    'embedding_models',
    'rerank_models',
    'legacy_pipelines',
    'pipeline_run_records',
    'plugin_settings',
    'knowledge_bases',
    'knowledge_base_files',
    'knowledge_base_chunks',
    'webhooks',
    'monitoring_messages',
    'monitoring_llm_calls',
    'monitoring_tool_calls',
    'monitoring_sessions',
    'monitoring_errors',
    'monitoring_embedding_calls',
    'monitoring_feedback',
}

_PRE_WORKSPACE_ALEMBIC_REVISIONS = {
    '0001_baseline',
    '0002_sample',
    '0003_add_rerank_models',
    '0004_add_mcp_readme',
    '0005_add_llm_context_length',
    '0006_normalize_mcp_remote_mode',
    '0007_add_bot_admins',
    '0008_mcp_resource_prefs',
}
_WORKSPACE_ALEMBIC_REVISION = '0009_workspace_tenancy'
_RESOURCE_SCOPE_ALEMBIC_REVISION = '0010_scope_resources'


class PersistenceManager:
    """Persistence module manager"""

    ap: app.Application

    db: database.BaseDatabaseManager
    """Database manager"""

    meta: sqlalchemy.MetaData

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.meta = base.Base.metadata

    async def initialize(self):
        database_type = self.ap.instance_config.data.get('database', {}).get('use', 'sqlite')
        self.ap.logger.info(f'Initializing database type: {database_type}...')
        for manager in database.preregistered_managers:
            if manager.name == database_type:
                self.db = manager(self.ap)
                await self.db.initialize()
                break

        self._enable_sqlite_foreign_keys()

        await self.create_tables()

        # run migrations
        database_version = await self.execute_async(
            sqlalchemy.select(metadata.Metadata).where(metadata.Metadata.key == 'database_version')
        )

        database_version = int(database_version.fetchone()[1])
        required_database_version = constants.required_database_version

        if database_version < required_database_version:
            migrations = migration.preregistered_db_migrations
            migrations.sort(key=lambda x: x.number)

            last_migration_number = database_version

            for migration_cls in migrations:
                migration_instance = migration_cls(self.ap)

                if (
                    migration_instance.number > database_version
                    and migration_instance.number <= required_database_version
                ):
                    await migration_instance.upgrade()
                    await self.execute_async(
                        sqlalchemy.update(metadata.Metadata)
                        .where(metadata.Metadata.key == 'database_version')
                        .values({'value': str(migration_instance.number)})
                    )
                    last_migration_number = migration_instance.number
                    self.ap.logger.info(f'Migration {migration_instance.number} completed.')

            self.ap.logger.info(f'Successfully upgraded database to version {last_migration_number}.')

        # Run Alembic migrations (new migration system)
        await self._run_alembic_migrations()

        # A legacy database may not contain tenant tables introduced by a
        # newer release.  They were deliberately deferred before 0009 because
        # their Workspace/account FK targets did not exist yet; create them
        # now that the tenancy contract is in place.
        await self.create_tables()

        await self.write_space_model_providers()

    async def create_tables(self):
        async with self.get_db_engine().connect() as conn:

            def create_compatible_tables(sync_conn: sqlalchemy.Connection) -> None:
                inspector = sqlalchemy.inspect(sync_conn)
                existing_tables = set(inspector.get_table_names())
                legacy_users = 'users' in existing_tables and (
                    'uuid' not in {column['name'] for column in inspector.get_columns('users')}
                    or 'workspaces' not in existing_tables
                )
                # On a legacy installation, resource tables already exist
                # without workspace_uuid and Workspace itself references the
                # account UUID introduced by 0009.  Alembic must expand those
                # tables before SQLAlchemy may create any new tenant table.
                excluded_tables = _ALEMBIC_TENANT_TABLES if legacy_users else set()
                tables_to_create = [table for table in self.meta.sorted_tables if table.name not in excluded_tables]
                self.meta.create_all(sync_conn, tables=tables_to_create)

            await conn.run_sync(create_compatible_tables)

            await conn.commit()

        # ======= write initial data =======

        # write initial metadata
        self.ap.logger.info('Creating initial metadata...')
        for item in metadata.initial_metadata:
            # check if the item exists
            result = await self.execute_async(
                sqlalchemy.select(metadata.Metadata).where(metadata.Metadata.key == item['key'])
            )
            row = result.first()
            if row is None:
                await self.execute_async(sqlalchemy.insert(metadata.Metadata).values(item))

        await self._ensure_instance_uuid_metadata()

    def _enable_sqlite_foreign_keys(self) -> None:
        """Enable SQLite FK enforcement for every pooled runtime connection."""
        engine = self.get_db_engine()
        if engine.dialect.name != 'sqlite':
            return
        if getattr(self, '_sqlite_fk_listener_installed', False):
            return

        def set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            # aiosqlite exposes the normal sqlite cursor API through its
            # SQLAlchemy adapter.  Guard the direct sqlite type too for tests.
            if isinstance(dbapi_connection, sqlite3.Connection) or hasattr(dbapi_connection, 'cursor'):
                cursor = dbapi_connection.cursor()
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.close()

        sqlalchemy.event.listen(engine.sync_engine, 'connect', set_sqlite_pragma)
        self._sqlite_fk_listener_installed = True

    async def _ensure_instance_uuid_metadata(self) -> None:
        """Persist the runtime instance identifier before tenant migrations run."""
        runtime_instance_uuid = constants.instance_id.strip()
        if not runtime_instance_uuid:
            raise RuntimeError('LangBot instance UUID is empty before persistence initialization')

        result = await self.execute_async(
            sqlalchemy.select(metadata.Metadata.value).where(metadata.Metadata.key == 'instance_uuid')
        )
        persisted_instance_uuid = result.scalar_one_or_none()

        if persisted_instance_uuid is None:
            await self.execute_async(
                sqlalchemy.insert(metadata.Metadata).values(key='instance_uuid', value=runtime_instance_uuid)
            )
            return

        if persisted_instance_uuid != runtime_instance_uuid:
            raise RuntimeError(
                'LangBot instance UUID does not match the value bound to this database: '
                f'{runtime_instance_uuid!r} != {persisted_instance_uuid!r}'
            )

    async def write_space_model_providers(self):
        if constants.edition != 'community':
            # SaaS Workspace/provider linkage is explicit control-plane state;
            # a process-level compatibility provider must never be projected
            # into an arbitrary cloud Workspace.
            return

        space_models_gateway_api_url = self.ap.instance_config.data.get('space', {}).get(
            'models_gateway_api_url', 'https://api.langbot.cloud/v1'
        )

        workspace_result = await self.execute_async(
            sqlalchemy.select(persistence_workspace.Workspace.uuid).where(
                persistence_workspace.Workspace.instance_uuid == constants.instance_id,
                persistence_workspace.Workspace.source == persistence_workspace.WorkspaceSource.LOCAL.value,
            )
        )
        workspace_uuids = workspace_result.scalars().all()
        if len(workspace_uuids) != 1:
            raise RuntimeError(
                f'The fixed LangBot Models provider requires exactly one local Workspace; found {len(workspace_uuids)}'
            )
        workspace_uuid = workspace_uuids[0]

        # The compatibility Space provider belongs to the OSS singleton
        # Workspace.  It must never be discovered or inserted globally.
        result = await self.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.workspace_uuid == workspace_uuid,
                persistence_model.ModelProvider.requester == 'space-chat-completions',
            )
        )
        exists_space_chat_completions_model_provider = result.first()

        # api keys will be set/updated when the oauth callback
        if exists_space_chat_completions_model_provider is None:
            self.ap.logger.info('Creating space model providers...')
            space_chat_completions_model_provider = {
                'uuid': '00000000-0000-0000-0000-000000000000',
                'workspace_uuid': workspace_uuid,
                'name': 'LangBot Models',
                'requester': 'space-chat-completions',
                'base_url': space_models_gateway_api_url,
                'api_keys': [],
            }

            await self.execute_async(
                sqlalchemy.insert(persistence_model.ModelProvider).values(space_chat_completions_model_provider)
            )
        else:
            if exists_space_chat_completions_model_provider.base_url != space_models_gateway_api_url:
                await self.execute_async(
                    sqlalchemy.update(persistence_model.ModelProvider)
                    .where(
                        persistence_model.ModelProvider.workspace_uuid == workspace_uuid,
                        persistence_model.ModelProvider.uuid == exists_space_chat_completions_model_provider.uuid,
                    )
                    .values({'base_url': space_models_gateway_api_url})
                )

    # =================================

    async def _run_alembic_migrations(self):
        """Run Alembic-based migrations after legacy migrations complete."""
        from . import alembic_runner

        engine = self.get_db_engine()

        try:
            current_rev = await alembic_runner.get_alembic_current(engine)

            if current_rev is None:
                # First time: stamp baseline so Alembic knows existing schema is up-to-date
                self.ap.logger.info('Alembic: no revision found, stamping baseline...')
                await alembic_runner.run_alembic_stamp(engine, '0001_baseline')
                current_rev = '0001_baseline'

            if engine.dialect.name == 'sqlite':
                if current_rev in _PRE_WORKSPACE_ALEMBIC_REVISIONS:
                    await self._run_verified_sqlite_migration(
                        engine,
                        source_revision=current_rev,
                        target_revision=_WORKSPACE_ALEMBIC_REVISION,
                    )
                    current_rev = await alembic_runner.get_alembic_current(engine)
                if current_rev == _WORKSPACE_ALEMBIC_REVISION:
                    await self._run_verified_sqlite_migration(
                        engine,
                        source_revision=current_rev,
                        target_revision=_RESOURCE_SCOPE_ALEMBIC_REVISION,
                    )

            # PostgreSQL has transactional DDL. SQLite has already crossed the
            # two destructive tenancy boundaries under verified backups; this
            # final call is a no-op today and applies future migrations.
            await alembic_runner.run_alembic_upgrade(engine, 'head')
            self.ap.logger.info('Alembic migrations completed.')
        except Exception as e:
            self.ap.logger.error(f'Alembic migration failed: {e}', exc_info=True)
            raise

    async def _run_verified_sqlite_migration(
        self,
        engine: sqlalchemy_asyncio.AsyncEngine,
        *,
        source_revision: str,
        target_revision: str,
    ) -> None:
        from . import alembic_runner

        backup = await sqlite_migration_backup.create_verified_backup(
            engine,
            source_revision=source_revision,
            target_revision=target_revision,
        )
        self.ap.logger.info(f'Created verified SQLite migration backup {backup.backup_path} before {target_revision}.')
        try:
            await alembic_runner.run_alembic_upgrade(engine, target_revision)
            completed_revision = await alembic_runner.get_alembic_current(engine)
            if completed_revision != target_revision:
                raise RuntimeError(f'Alembic stopped at {completed_revision!r}, expected {target_revision!r}')
            await sqlite_migration_backup.mark_migration_succeeded(
                backup,
                completed_revision=completed_revision,
            )
        except BaseException:
            await sqlite_migration_backup.restore_verified_backup(engine, backup)
            restored_revision = await alembic_runner.get_alembic_current(engine)
            if restored_revision != source_revision:
                raise RuntimeError(
                    f'SQLite migration recovery restored revision {restored_revision!r}, expected {source_revision!r}'
                )
            self.ap.logger.error(
                f'SQLite migration to {target_revision} failed; restored verified backup '
                f'{backup.backup_path} at revision {source_revision}.'
            )
            raise

    async def execute_async(self, *args, **kwargs) -> sqlalchemy.engine.cursor.CursorResult:
        async with self.get_db_engine().connect() as conn:
            result = await conn.execute(*args, **kwargs)
            await conn.commit()
            return result

    def get_db_engine(self) -> sqlalchemy_asyncio.AsyncEngine:
        return self.db.get_engine()

    def serialize_model(
        self, model: typing.Type[sqlalchemy.Base], data: sqlalchemy.Base, masked_columns: list[str] = []
    ) -> dict:
        return {
            column.name: getattr(data, column.name)
            if not isinstance(getattr(data, column.name), (datetime.datetime))
            else getattr(data, column.name).isoformat()
            for column in model.__table__.columns
            if column.name not in masked_columns
        }
