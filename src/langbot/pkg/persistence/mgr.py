from __future__ import annotations

import datetime
import enum
import sqlite3
import typing
import contextvars
import asyncio
import contextlib
import re


import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
import sqlalchemy

from . import database, migration, sqlite_migration_backup
from ..entity.persistence import base, metadata, model as persistence_model
from ..entity.persistence import workspace as persistence_workspace
from ..entity import persistence
from ..core import app
from ..utils import constants, importutil
from . import databases, migrations
from .tenant_uow import (
    ActivePersistenceScope,
    ActiveScopedTransaction,
    API_KEY_DISCOVERY_POLICY_NAME,
    ACCOUNT_DISCOVERY_POLICY_NAME,
    INSTANCE_DISCOVERY_POLICY_NAME,
    INVITATION_DISCOVERY_POLICY_NAME,
    TENANT_POLICY_NAME,
    TENANT_SETTING,
    TENANT_TABLE_COLUMNS,
    CrossScopeTransactionError,
    PersistenceScope,
    PersistenceScopeBoundary,
    PersistenceScopeKind,
    TenantScopeRequiredError,
    TenantUnitOfWork,
)

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
    'langbot_vectors',
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
_OSS_WORKSPACE_METADATA_KEY = 'oss_workspace_uuid'
_RELEASE_MIGRATION_ADVISORY_LOCK_ID = 0x4C414E47424F5432
_PGVECTOR_ALLOWED_DIMENSIONS = (384, 512, 768, 1024, 1536)
_RUNTIME_SCHEMA = 'public'
_ALEMBIC_RUNTIME_TABLE = 'alembic_version'
_RUNTIME_TABLE_PRIVILEGES = frozenset({'SELECT', 'INSERT', 'UPDATE', 'DELETE'})
_RUNTIME_SEQUENCE_PRIVILEGES = frozenset({'USAGE', 'SELECT'})
_RUNTIME_ALLOWED_EXTENSIONS = frozenset({'plpgsql', 'vector'})


class PersistenceMode(enum.StrEnum):
    """Trusted persistence startup mode selected by the process entrypoint."""

    OSS_COMPAT = 'oss_compat'
    CLOUD_RUNTIME = 'cloud_runtime'
    RELEASE_MIGRATION = 'release_migration'


class PersistenceManager:
    """Persistence module manager"""

    ap: app.Application

    db: database.BaseDatabaseManager
    """Database manager"""

    meta: sqlalchemy.MetaData

    def __init__(
        self,
        ap: app.Application,
        *,
        mode: PersistenceMode = PersistenceMode.OSS_COMPAT,
        database_url: sqlalchemy.engine.URL | None = None,
    ):
        if not isinstance(mode, PersistenceMode):
            raise TypeError('PersistenceManager mode must be a trusted PersistenceMode value')
        if database_url is not None:
            if mode != PersistenceMode.RELEASE_MIGRATION:
                raise ValueError('A database URL override is reserved for the release migration process')
            if not isinstance(database_url, sqlalchemy.engine.URL):
                raise TypeError('Release migration database URL must be a parsed SQLAlchemy URL')
            if database_url.drivername != 'postgresql+asyncpg':
                raise ValueError('Release migration database URL must use postgresql+asyncpg')
        self.ap = ap
        self.meta = base.Base.metadata
        self.mode = mode
        self._database_url_override = database_url
        self._active_transaction: contextvars.ContextVar[ActiveScopedTransaction | None] = contextvars.ContextVar(
            f'langbot_persistence_scope_{id(self)}',
            default=None,
        )
        self._active_scope: contextvars.ContextVar[ActivePersistenceScope | None] = contextvars.ContextVar(
            f'langbot_persistence_boundary_{id(self)}',
            default=None,
        )

    async def initialize(self):
        database_type = self.ap.instance_config.data.get('database', {}).get('use', 'sqlite')
        self.ap.logger.info(f'Initializing database type: {database_type}...')
        selected_manager: database.BaseDatabaseManager | None = None
        for manager in database.preregistered_managers:
            if manager.name == database_type:
                self.db = manager(self.ap, url_override=self._database_url_override)
                await self.db.initialize()
                selected_manager = self.db
                break
        if selected_manager is None:
            raise RuntimeError(f'Unsupported database type: {database_type!r}')

        engine = self.get_db_engine()
        if self.mode in {PersistenceMode.CLOUD_RUNTIME, PersistenceMode.RELEASE_MIGRATION}:
            if engine.dialect.name != 'postgresql':
                raise RuntimeError(f'{self.mode.value} persistence mode requires PostgreSQL')
            await self._validate_postgres_public_schema_session()

        if self.mode == PersistenceMode.CLOUD_RUNTIME:
            await self._validate_cloud_runtime()
            return

        self._enable_sqlite_foreign_keys()
        if self.mode == PersistenceMode.RELEASE_MIGRATION:
            async with self._release_migration_lock():
                await self._initialize_managed_schema()
                await self._validate_release_schema()
            return

        await self._initialize_managed_schema()

        if self.mode == PersistenceMode.OSS_COMPAT:
            await self.write_space_model_providers()

    @contextlib.asynccontextmanager
    async def _release_migration_lock(self) -> typing.AsyncIterator[None]:
        """Serialize the complete PostgreSQL migration and validation window."""

        engine = self.get_db_engine()
        if engine.dialect.name != 'postgresql':
            raise RuntimeError('Release migration advisory lock requires PostgreSQL')
        async with engine.connect() as lock_connection:
            acquired = await lock_connection.scalar(
                sqlalchemy.text('SELECT pg_try_advisory_lock(:lock_id)'),
                {'lock_id': _RELEASE_MIGRATION_ADVISORY_LOCK_ID},
            )
            if acquired is not True:
                raise RuntimeError('Another Cloud release migration already holds the advisory lock')
            self.ap.logger.info('Acquired the Cloud release migration advisory lock.')
            try:
                yield
            finally:
                unlocked = await lock_connection.scalar(
                    sqlalchemy.text('SELECT pg_advisory_unlock(:lock_id)'),
                    {'lock_id': _RELEASE_MIGRATION_ADVISORY_LOCK_ID},
                )
                if unlocked is not True:
                    raise RuntimeError('Cloud release migration advisory lock ownership was lost')

    async def _initialize_managed_schema(self) -> None:
        """Create or migrate schema only in OSS and release processes."""
        from . import alembic_runner

        engine = self.get_db_engine()
        release_bootstrap = self.mode == PersistenceMode.RELEASE_MIGRATION and await self._is_empty_schema()

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

        if engine.dialect.name == 'postgresql':
            current_revision = await alembic_runner.get_alembic_current(engine)
            head_revision = alembic_runner.get_alembic_head()

            if release_bootstrap:
                # Base.metadata represents the complete 0010 schema. An empty
                # Cloud database has no legacy data to transform and must not
                # run 0009's OSS singleton Workspace bootstrap.
                if current_revision is not None:
                    raise RuntimeError('Empty PostgreSQL release bootstrap unexpectedly has an Alembic revision')
                await alembic_runner.run_alembic_stamp(engine, _RESOURCE_SCOPE_ALEMBIC_REVISION)
            elif current_revision != head_revision:
                # A legacy database may not contain tenant tables introduced
                # by a newer release. Upgrade the account/resource contract,
                # then create deferred tables before the RLS migration runs.
                await self._run_alembic_migrations(_RESOURCE_SCOPE_ALEMBIC_REVISION)
                await self.create_tables()

            await self._run_alembic_migrations()
            await self._validate_postgres_tenant_schema(validate_runtime_role=False)

            if self.mode == PersistenceMode.OSS_COMPAT:
                await self._install_oss_postgres_tenant_scope()
        else:
            await self._run_alembic_migrations()

            # SQLite keeps the historical post-migration create_all pass. New
            # tenant tables are deferred until the Workspace/account schema is
            # compatible with their foreign keys.
            await self.create_tables()

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

    async def _is_empty_schema(self) -> bool:
        async with self.get_db_engine().connect() as conn:
            table_names = await conn.run_sync(lambda sync_conn: set(sqlalchemy.inspect(sync_conn).get_table_names()))
        return not table_names

    async def _install_oss_postgres_tenant_scope(self) -> None:
        """Default every OSS PostgreSQL transaction to its singleton Workspace."""
        if getattr(self, '_oss_tenant_scope_listener_installed', False):
            return

        async with self.get_db_engine().connect() as conn:
            workspace_uuid = await conn.scalar(
                sqlalchemy.select(metadata.Metadata.value).where(
                    metadata.Metadata.key == _OSS_WORKSPACE_METADATA_KEY,
                )
            )
        if not isinstance(workspace_uuid, str) or not workspace_uuid.strip():
            raise RuntimeError(
                'PostgreSQL OSS mode requires exactly one local Workspace recorded before tenant RLS is enabled'
            )
        workspace_uuid = workspace_uuid.strip()

        def set_oss_tenant_scope(conn: sqlalchemy.Connection) -> None:
            conn.execute(
                sqlalchemy.text(f"SELECT set_config('{TENANT_SETTING}', :workspace_uuid, true)"),
                {'workspace_uuid': workspace_uuid},
            )

        sqlalchemy.event.listen(self.get_db_engine().sync_engine, 'begin', set_oss_tenant_scope)
        self._oss_tenant_scope_listener_installed = True

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

    async def _validate_cloud_runtime(self) -> None:
        """Validate a release-prepared schema without performing any DDL."""
        from . import alembic_runner

        engine = self.get_db_engine()
        current_revision = await alembic_runner.get_alembic_current(engine)
        head_revision = alembic_runner.get_alembic_head()
        if current_revision != head_revision:
            raise RuntimeError(
                f'Cloud runtime database schema is not at the release head: {current_revision!r} != {head_revision!r}'
            )

        runtime_instance_uuid = constants.instance_id.strip()
        if not runtime_instance_uuid:
            raise RuntimeError('LangBot instance UUID is empty before Cloud persistence validation')
        async with engine.connect() as conn:
            persisted_instance_uuid = await conn.scalar(
                sqlalchemy.select(metadata.Metadata.value).where(metadata.Metadata.key == 'instance_uuid')
            )
        if persisted_instance_uuid is None:
            raise RuntimeError("Cloud runtime database is missing metadata['instance_uuid']")
        if persisted_instance_uuid != runtime_instance_uuid:
            raise RuntimeError(
                'LangBot instance UUID does not match the value bound to this database: '
                f'{runtime_instance_uuid!r} != {persisted_instance_uuid!r}'
            )

        await self._validate_postgres_tenant_schema(validate_runtime_role=True)
        await self._validate_postgres_pgvector_schema()
        await self._validate_configured_runtime_postgres_role(
            require_grants=True,
            require_current_user=True,
        )

    async def _validate_postgres_public_schema_session(self) -> None:
        """Pin the first Cloud release to one explicit PostgreSQL schema."""

        async with self.get_db_engine().connect() as conn:
            schema_state = (
                (
                    await conn.execute(
                        sqlalchemy.text(
                            """
                        SELECT
                            current_schema() AS current_schema,
                            current_schemas(false) AS effective_schemas,
                            current_setting('session_replication_role') AS session_replication_role,
                            current_setting('row_security') AS row_security,
                            current_setting('lo_compat_privileges') AS lo_compat_privileges
                        """
                        )
                    )
                )
                .mappings()
                .one()
            )
        if schema_state['current_schema'] != _RUNTIME_SCHEMA or list(schema_state['effective_schemas']) != [
            _RUNTIME_SCHEMA
        ]:
            raise RuntimeError('Cloud PostgreSQL search_path must resolve exclusively to the public business schema')
        if schema_state['session_replication_role'] != 'origin':
            raise RuntimeError('Cloud PostgreSQL session_replication_role must be origin')
        if schema_state['row_security'] != 'on':
            raise RuntimeError('Cloud PostgreSQL row_security must be on')
        if schema_state['lo_compat_privileges'] != 'off':
            raise RuntimeError('Cloud PostgreSQL lo_compat_privileges must be off')

    async def _validate_release_schema(self) -> None:
        """Verify the complete Cloud business schema before releasing the lock."""
        from . import alembic_runner

        engine = self.get_db_engine()
        current_revision = await alembic_runner.get_alembic_current(engine)
        head_revision = alembic_runner.get_alembic_head()
        if current_revision != head_revision:
            raise RuntimeError(
                'Cloud release migration did not reach the exact Alembic head: '
                f'{current_revision!r} != {head_revision!r}'
            )
        await self._validate_postgres_tenant_schema(validate_runtime_role=False)
        await self._validate_postgres_pgvector_schema()
        if self._database_url_override is not None:
            # The one-shot operator process never authenticates with the
            # runtime password. It validates the configured role before
            # granting access, provisions only the current business objects,
            # then validates the resulting ACLs before declaring the release
            # deployable.
            await self._grant_configured_runtime_postgres_role_privileges()
            await self._validate_configured_runtime_postgres_role(require_grants=True)

    def _configured_runtime_postgres_role(self) -> str:
        postgresql_config = self.ap.instance_config.data.get('database', {}).get('postgresql')
        if not isinstance(postgresql_config, dict):
            raise RuntimeError('Cloud runtime PostgreSQL configuration is missing')
        explicit_url = postgresql_config.get('url')
        if explicit_url:
            if not isinstance(explicit_url, str):
                raise RuntimeError('Cloud runtime PostgreSQL URL must be a string')
            try:
                runtime_url = sqlalchemy.engine.make_url(explicit_url)
            except Exception:
                raise RuntimeError('Cloud runtime PostgreSQL URL is invalid') from None
            if runtime_url.drivername not in {'postgresql', 'postgresql+asyncpg'}:
                raise RuntimeError('Cloud runtime database URL must use PostgreSQL')
            runtime_role = (runtime_url.username or '').strip()
        else:
            runtime_role = str(postgresql_config.get('user', 'postgres') or '').strip()
        if not runtime_role:
            raise RuntimeError('Cloud runtime PostgreSQL role is missing')
        return runtime_role

    def _runtime_business_table_names(self) -> tuple[str, ...]:
        """Return release-managed application tables, excluding migration metadata."""

        return tuple(sorted({table.name for table in self.meta.tables.values()} | {'langbot_vectors'}))

    def _runtime_table_privilege_allowlist(self) -> dict[str, frozenset[str]]:
        return {
            **{table_name: _RUNTIME_TABLE_PRIVILEGES for table_name in self._runtime_business_table_names()},
            _ALEMBIC_RUNTIME_TABLE: frozenset({'SELECT'}),
        }

    async def _runtime_business_sequence_names(
        self,
        conn: sqlalchemy_asyncio.AsyncConnection,
        table_names: tuple[str, ...],
    ) -> tuple[str, ...]:
        sequence_query = sqlalchemy.text(
            """
            SELECT DISTINCT sequence.relname
            FROM pg_class sequence
            JOIN pg_namespace sequence_namespace ON sequence_namespace.oid = sequence.relnamespace
            JOIN pg_depend dependency
              ON dependency.classid = 'pg_class'::regclass
             AND dependency.objid = sequence.oid
             AND dependency.refclassid = 'pg_class'::regclass
             AND dependency.deptype IN ('a', 'i')
            JOIN pg_class business_table ON business_table.oid = dependency.refobjid
            JOIN pg_namespace table_namespace ON table_namespace.oid = business_table.relnamespace
            WHERE sequence.relkind = 'S'
              AND sequence_namespace.nspname = 'public'
              AND table_namespace.nspname = 'public'
              AND business_table.relname IN :table_names
            ORDER BY sequence.relname
            """
        ).bindparams(sqlalchemy.bindparam('table_names', expanding=True))
        return tuple((await conn.execute(sequence_query, {'table_names': table_names})).scalars().all())

    async def _grant_configured_runtime_postgres_role_privileges(self) -> None:
        """Provision the nonprivileged runtime role using the operator connection."""

        await self._validate_configured_runtime_postgres_role(require_grants=False)
        runtime_role = self._configured_runtime_postgres_role()
        table_names = self._runtime_business_table_names()
        relation_allowlist = self._runtime_table_privilege_allowlist()
        engine = self.get_db_engine()
        quote = engine.dialect.identifier_preparer.quote

        async with engine.begin() as conn:
            database_name = await conn.scalar(sqlalchemy.text('SELECT current_database()'))
            if not isinstance(database_name, str):
                raise RuntimeError('Cloud release migration could not resolve its PostgreSQL database')

            existing_tables = set(
                (
                    await conn.execute(
                        sqlalchemy.text(
                            """
                            SELECT c.relname
                            FROM pg_class c
                            JOIN pg_namespace n ON n.oid = c.relnamespace
                            WHERE n.nspname = 'public'
                              AND c.relkind IN ('r', 'p')
                              AND c.relname IN :relation_names
                            """
                        ).bindparams(sqlalchemy.bindparam('relation_names', expanding=True)),
                        {'relation_names': tuple(relation_allowlist)},
                    )
                )
                .scalars()
                .all()
            )
            missing_tables = sorted(set(relation_allowlist) - existing_tables)
            if missing_tables:
                raise RuntimeError(f'Cloud runtime allowlisted tables are missing: {missing_tables!r}')

            sequence_names = await self._runtime_business_sequence_names(conn, table_names)
            quoted_role = quote(runtime_role)
            quoted_schema = quote(_RUNTIME_SCHEMA)
            quoted_tables = ', '.join(f'{quoted_schema}.{quote(table_name)}' for table_name in table_names)

            await conn.execute(sqlalchemy.text(f'GRANT CONNECT ON DATABASE {quote(database_name)} TO {quoted_role}'))
            await conn.execute(sqlalchemy.text(f'GRANT USAGE ON SCHEMA {quoted_schema} TO {quoted_role}'))
            await conn.execute(
                sqlalchemy.text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {quoted_tables} TO {quoted_role}')
            )
            await conn.execute(
                sqlalchemy.text(
                    f'GRANT SELECT ON TABLE {quoted_schema}.{quote(_ALEMBIC_RUNTIME_TABLE)} TO {quoted_role}'
                )
            )
            if sequence_names:
                quoted_sequences = ', '.join(
                    f'{quoted_schema}.{quote(sequence_name)}' for sequence_name in sequence_names
                )
                await conn.execute(
                    sqlalchemy.text(f'GRANT USAGE, SELECT ON SEQUENCE {quoted_sequences} TO {quoted_role}')
                )

    async def _validate_configured_runtime_postgres_role(
        self,
        *,
        require_grants: bool = True,
        require_current_user: bool = False,
    ) -> None:
        """Validate the configured least-privilege role using operator catalogs."""

        runtime_role = self._configured_runtime_postgres_role()
        table_names = self._runtime_business_table_names()
        relation_allowlist = self._runtime_table_privilege_allowlist()

        role_query = sqlalchemy.text(
            """
            SELECT
                oid,
                rolcanlogin,
                rolsuper,
                rolbypassrls,
                rolcreatedb,
                rolcreaterole,
                rolreplication
            FROM pg_roles
            WHERE rolname = :runtime_role
            """
        )
        membership_query = sqlalchemy.text(
            """
            SELECT
                granted_role.rolname AS granted_role,
                member_role.rolname AS member_role,
                grantor_role.rolname AS grantor_role,
                membership.admin_option,
                membership.inherit_option,
                membership.set_option
            FROM pg_auth_members membership
            JOIN pg_roles granted_role ON granted_role.oid = membership.roleid
            JOIN pg_roles member_role ON member_role.oid = membership.member
            JOIN pg_roles grantor_role ON grantor_role.oid = membership.grantor
            WHERE membership.roleid = :runtime_oid
               OR membership.member = :runtime_oid
               OR membership.grantor = :runtime_oid
            ORDER BY granted_role.rolname, member_role.rolname
            """
        )
        persistent_settings_query = sqlalchemy.text(
            """
            SELECT
                setting.setdatabase,
                setting.setrole,
                lower(split_part(config.value, '=', 1)) AS parameter_name
            FROM pg_db_role_setting setting
            JOIN pg_database database ON database.datname = current_database()
            CROSS JOIN LATERAL unnest(setting.setconfig) config(value)
            WHERE (
                    (
                        setting.setrole = :runtime_oid
                        AND setting.setdatabase IN (0, database.oid)
                    )
                    OR (setting.setrole = 0 AND setting.setdatabase = database.oid)
              )
            ORDER BY setting.setdatabase, setting.setrole, parameter_name
            """
        )
        owned_objects_query = sqlalchemy.text(
            """
            SELECT c.relname, c.relkind::text AS relkind
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
              AND c.relowner = :runtime_oid
            ORDER BY c.relname
            """
        )
        database_schema_owner_query = sqlalchemy.text(
            """
            SELECT
                pg_get_userbyid(database.datdba) = :runtime_role AS owns_database,
                pg_get_userbyid(namespace.nspowner) = :runtime_role AS owns_schema
            FROM pg_database database
            CROSS JOIN pg_namespace namespace
            WHERE database.datname = current_database()
              AND namespace.nspname = 'public'
            """
        )
        other_schema_privileges_query = sqlalchemy.text(
            """
            SELECT
                namespace.nspname,
                namespace.nspowner = :runtime_oid AS owned_by_runtime,
                has_schema_privilege(:runtime_role, namespace.oid, 'USAGE') AS can_use,
                has_schema_privilege(:runtime_role, namespace.oid, 'CREATE') AS can_create
            FROM pg_namespace namespace
            WHERE namespace.nspname <> 'public'
              AND namespace.nspname <> 'information_schema'
              AND left(namespace.nspname, 3) <> 'pg_'
            ORDER BY namespace.nspname
            """
        )
        database_acl_query = sqlalchemy.text(
            """
            SELECT acl.privilege_type, acl.is_grantable
            FROM pg_database database
            CROSS JOIN LATERAL aclexplode(database.datacl) acl
            WHERE database.datname = current_database()
              AND acl.grantee = :runtime_oid
            ORDER BY acl.privilege_type
            """
        )
        schema_acl_query = sqlalchemy.text(
            """
            SELECT acl.privilege_type, acl.is_grantable
            FROM pg_namespace namespace
            CROSS JOIN LATERAL aclexplode(namespace.nspacl) acl
            WHERE namespace.nspname = 'public'
              AND acl.grantee = :runtime_oid
            ORDER BY acl.privilege_type
            """
        )
        object_acl_query = sqlalchemy.text(
            """
            SELECT
                c.relname,
                c.relkind::text AS relkind,
                acl.privilege_type,
                acl.is_grantable
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            CROSS JOIN LATERAL aclexplode(c.relacl) acl
            WHERE n.nspname = 'public'
              AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
              AND acl.grantee = :runtime_oid
            ORDER BY c.relname, acl.privilege_type
            """
        )
        table_privileges_query = sqlalchemy.text(
            """
            SELECT
                c.relname,
                has_table_privilege(:runtime_role, c.oid, 'SELECT') AS can_select,
                has_table_privilege(:runtime_role, c.oid, 'INSERT') AS can_insert,
                has_table_privilege(:runtime_role, c.oid, 'UPDATE') AS can_update,
                has_table_privilege(:runtime_role, c.oid, 'DELETE') AS can_delete,
                has_table_privilege(:runtime_role, c.oid, 'TRUNCATE') AS can_truncate,
                has_table_privilege(:runtime_role, c.oid, 'REFERENCES') AS can_reference,
                has_table_privilege(:runtime_role, c.oid, 'TRIGGER') AS can_trigger,
                has_table_privilege(:runtime_role, c.oid, 'SELECT WITH GRANT OPTION') AS can_grant_select,
                has_table_privilege(:runtime_role, c.oid, 'INSERT WITH GRANT OPTION') AS can_grant_insert,
                has_table_privilege(:runtime_role, c.oid, 'UPDATE WITH GRANT OPTION') AS can_grant_update,
                has_table_privilege(:runtime_role, c.oid, 'DELETE WITH GRANT OPTION') AS can_grant_delete,
                has_table_privilege(:runtime_role, c.oid, 'TRUNCATE WITH GRANT OPTION') AS can_grant_truncate,
                has_table_privilege(:runtime_role, c.oid, 'REFERENCES WITH GRANT OPTION') AS can_grant_reference,
                has_table_privilege(:runtime_role, c.oid, 'TRIGGER WITH GRANT OPTION') AS can_grant_trigger
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
            ORDER BY c.relname
            """
        )
        sequence_privileges_query = sqlalchemy.text(
            """
            SELECT
                c.relname,
                has_sequence_privilege(:runtime_role, c.oid, 'USAGE') AS can_use,
                has_sequence_privilege(:runtime_role, c.oid, 'SELECT') AS can_select,
                has_sequence_privilege(:runtime_role, c.oid, 'UPDATE') AS can_update,
                has_sequence_privilege(:runtime_role, c.oid, 'USAGE WITH GRANT OPTION') AS can_grant_use,
                has_sequence_privilege(:runtime_role, c.oid, 'SELECT WITH GRANT OPTION') AS can_grant_select,
                has_sequence_privilege(:runtime_role, c.oid, 'UPDATE WITH GRANT OPTION') AS can_grant_update
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'S'
            ORDER BY c.relname
            """
        )
        ddl_privileges_query = sqlalchemy.text(
            """
            SELECT
                current_user AS connected_role,
                current_schema() AS current_schema,
                current_schemas(false) AS effective_schemas,
                has_database_privilege(:runtime_role, current_database(), 'CONNECT') AS can_connect,
                has_database_privilege(
                    :runtime_role,
                    current_database(),
                    'CONNECT WITH GRANT OPTION'
                ) AS can_grant_connect,
                has_database_privilege(:runtime_role, current_database(), 'CREATE') AS can_create_database_objects,
                has_database_privilege(:runtime_role, current_database(), 'TEMP') AS can_create_temp_objects,
                has_schema_privilege(:runtime_role, 'public', 'USAGE') AS can_use_schema,
                has_schema_privilege(
                    :runtime_role,
                    'public',
                    'USAGE WITH GRANT OPTION'
                ) AS can_grant_schema_usage,
                has_schema_privilege(:runtime_role, 'public', 'CREATE') AS can_create_schema_objects
            """
        )
        existing_tables_query = sqlalchemy.text(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind IN ('r', 'p')
              AND c.relname IN :relation_names
            ORDER BY c.relname
            """
        ).bindparams(sqlalchemy.bindparam('relation_names', expanding=True))
        column_acl_query = sqlalchemy.text(
            """
            SELECT c.relname, attribute.attname, acl.privilege_type, acl.is_grantable
            FROM pg_attribute attribute
            JOIN pg_class c ON c.oid = attribute.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            CROSS JOIN LATERAL aclexplode(attribute.attacl) acl
            WHERE n.nspname = 'public'
              AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
              AND attribute.attnum > 0
              AND NOT attribute.attisdropped
              AND acl.grantee IN (0, :runtime_oid)
            ORDER BY c.relname, attribute.attname, acl.privilege_type
            """
        )
        routine_acl_query = sqlalchemy.text(
            """
            SELECT
                namespace.nspname,
                procedure.oid::regprocedure::text AS routine,
                acl.grantee,
                acl.privilege_type,
                acl.is_grantable
            FROM pg_proc procedure
            JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
            CROSS JOIN LATERAL aclexplode(procedure.proacl) acl
            WHERE acl.grantee IN (0, :runtime_oid)
            ORDER BY namespace.nspname, routine, acl.grantee
            """
        )
        owned_routines_query = sqlalchemy.text(
            """
            SELECT namespace.nspname, procedure.oid::regprocedure::text AS routine
            FROM pg_proc procedure
            JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
            WHERE procedure.proowner = :runtime_oid
            ORDER BY namespace.nspname, routine
            """
        )
        parameter_acl_query = sqlalchemy.text(
            """
            SELECT
                parameter.parname,
                acl.grantee,
                acl.privilege_type,
                acl.is_grantable
            FROM pg_parameter_acl parameter
            CROSS JOIN LATERAL aclexplode(parameter.paracl) acl
            WHERE acl.grantee IN (0, :runtime_oid)
            ORDER BY parameter.parname, acl.grantee, acl.privilege_type
            """
        )
        extensions_query = sqlalchemy.text(
            """
            SELECT extension.extname, extension.extowner = :runtime_oid AS owned_by_runtime
            FROM pg_extension extension
            ORDER BY extension.extname
            """
        )
        # pg_user_mapping is intentionally unreadable by ordinary roles because
        # its options may contain credentials. pg_user_mappings is the public
        # view: it exposes all identities while redacting inaccessible options.
        # Never select umoptions into the validator or its diagnostics.
        foreign_objects_query = sqlalchemy.text(
            """
            SELECT 'foreign data wrapper' AS object_kind, wrapper.fdwname AS object_name
            FROM pg_foreign_data_wrapper wrapper
            UNION ALL
            SELECT 'foreign server', server.srvname
            FROM pg_foreign_server server
            UNION ALL
            SELECT 'user mapping', mapping.srvname || ':' || mapping.usename
            FROM pg_catalog.pg_user_mappings mapping
            ORDER BY object_kind, object_name
            """
        )
        security_definer_query = sqlalchemy.text(
            """
            SELECT namespace.nspname, procedure.oid::regprocedure::text AS routine
            FROM pg_proc procedure
            JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
            WHERE procedure.prosecdef
              AND has_schema_privilege(:runtime_role, namespace.oid, 'USAGE')
              AND has_function_privilege(:runtime_role, procedure.oid, 'EXECUTE')
            ORDER BY namespace.nspname, routine
            """
        )

        async with self.get_db_engine().connect() as conn:
            role = (await conn.execute(role_query, {'runtime_role': runtime_role})).mappings().one_or_none()
            if role is None:
                raise RuntimeError('Configured Cloud runtime PostgreSQL role does not exist')
            if role['rolcanlogin'] is not True:
                raise RuntimeError('Configured Cloud runtime PostgreSQL role must have LOGIN')
            if role['rolsuper'] is True or role['rolbypassrls'] is True:
                raise RuntimeError('Configured Cloud runtime PostgreSQL role must not be superuser or BYPASSRLS')
            if role['rolcreatedb'] is True or role['rolcreaterole'] is True or role['rolreplication'] is True:
                raise RuntimeError(
                    'Configured Cloud runtime PostgreSQL role must not have CREATEDB, CREATEROLE, or REPLICATION'
                )

            query_parameters = {
                'runtime_role': runtime_role,
                'runtime_oid': role['oid'],
                'table_names': table_names,
                'relation_names': tuple(relation_allowlist),
            }
            existing_tables = set((await conn.execute(existing_tables_query, query_parameters)).scalars().all())
            missing_tables = sorted(set(relation_allowlist) - existing_tables)
            if missing_tables:
                raise RuntimeError(f'Cloud runtime allowlisted tables are missing: {missing_tables!r}')

            sequence_names = set(await self._runtime_business_sequence_names(conn, table_names))
            owned_objects = (await conn.execute(owned_objects_query, query_parameters)).mappings().all()
            ownership = (await conn.execute(database_schema_owner_query, query_parameters)).mappings().one()
            memberships = (await conn.execute(membership_query, query_parameters)).mappings().all()
            persistent_settings = (await conn.execute(persistent_settings_query, query_parameters)).mappings().all()
            other_schema_privileges = (
                (await conn.execute(other_schema_privileges_query, query_parameters)).mappings().all()
            )
            database_acl = (await conn.execute(database_acl_query, query_parameters)).mappings().all()
            schema_acl = (await conn.execute(schema_acl_query, query_parameters)).mappings().all()
            object_acl = (await conn.execute(object_acl_query, query_parameters)).mappings().all()
            table_privileges = (await conn.execute(table_privileges_query, query_parameters)).mappings().all()
            sequence_privileges = (await conn.execute(sequence_privileges_query, query_parameters)).mappings().all()
            ddl_privileges = (await conn.execute(ddl_privileges_query, query_parameters)).mappings().one()
            column_acl = (await conn.execute(column_acl_query, query_parameters)).mappings().all()
            routine_acl = (await conn.execute(routine_acl_query, query_parameters)).mappings().all()
            owned_routines = (await conn.execute(owned_routines_query, query_parameters)).mappings().all()
            parameter_acl = (await conn.execute(parameter_acl_query, query_parameters)).mappings().all()
            extensions = (await conn.execute(extensions_query, query_parameters)).mappings().all()
            foreign_objects = (await conn.execute(foreign_objects_query)).mappings().all()
            security_definers = (await conn.execute(security_definer_query, query_parameters)).mappings().all()

        if require_current_user and ddl_privileges['connected_role'] != runtime_role:
            raise RuntimeError('Cloud runtime PostgreSQL connection user does not match the configured runtime role')
        if ddl_privileges['current_schema'] != _RUNTIME_SCHEMA or list(ddl_privileges['effective_schemas']) != [
            _RUNTIME_SCHEMA
        ]:
            raise RuntimeError('Cloud PostgreSQL search_path must resolve exclusively to the public business schema')
        if memberships:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL role must not participate in role memberships: '
                f'{[dict(row) for row in memberships]!r}'
            )
        if persistent_settings:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL role/current database must not define persistent session '
                'overrides: '
                f'{[(row["parameter_name"], row["setdatabase"], row["setrole"]) for row in persistent_settings]!r}'
            )

        extension_names = {str(row['extname']) for row in extensions}
        runtime_owned_extensions = sorted(str(row['extname']) for row in extensions if row['owned_by_runtime'] is True)
        if runtime_owned_extensions:
            raise RuntimeError(
                f'Configured Cloud runtime PostgreSQL role must not own extensions: {runtime_owned_extensions!r}'
            )
        unexpected_extensions = sorted(extension_names - _RUNTIME_ALLOWED_EXTENSIONS)
        if 'vector' not in extension_names or unexpected_extensions:
            raise RuntimeError(
                'Cloud business PostgreSQL extensions must include vector and be limited to plpgsql/vector: '
                f'{sorted(extension_names)!r}'
            )
        if foreign_objects:
            raise RuntimeError(
                'Cloud business PostgreSQL database must not contain foreign data wrappers, servers, or user '
                f'mappings: {[(row["object_kind"], row["object_name"]) for row in foreign_objects]!r}'
            )

        owned_tables = sorted(row['relname'] for row in owned_objects if row['relkind'] in {'r', 'p', 'v', 'm', 'f'})
        owned_sequences = sorted(row['relname'] for row in owned_objects if row['relkind'] == 'S')
        if owned_tables:
            raise RuntimeError(f'Configured Cloud runtime PostgreSQL role owns tenant tables: {owned_tables!r}')
        if owned_sequences:
            raise RuntimeError(f'Configured Cloud runtime PostgreSQL role owns business sequences: {owned_sequences!r}')
        if ownership['owns_database'] is True or ownership['owns_schema'] is True:
            raise RuntimeError('Configured Cloud runtime PostgreSQL role must not own the runtime database or schema')
        unsafe_other_schemas = sorted(
            row['nspname']
            for row in other_schema_privileges
            if row['owned_by_runtime'] is True or row['can_use'] is True or row['can_create'] is True
        )
        if unsafe_other_schemas:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL role can access or own non-business schemas: '
                f'{unsafe_other_schemas!r}'
            )

        if ddl_privileges['can_connect'] is not True and require_grants:
            raise RuntimeError('Configured Cloud runtime PostgreSQL database CONNECT grant is incomplete')
        if ddl_privileges['can_grant_connect'] is True:
            raise RuntimeError('Configured Cloud runtime PostgreSQL database CONNECT has effective GRANT OPTION')
        if ddl_privileges['can_create_database_objects'] is True:
            raise RuntimeError('Configured Cloud runtime PostgreSQL role must not have database CREATE')
        # PostgreSQL commonly grants TEMP to PUBLIC when a database is created.
        # The first Cloud release tolerates that inherited compatibility
        # privilege, but never grants TEMP directly to the runtime role.
        if ddl_privileges['can_create_schema_objects'] is True:
            raise RuntimeError('Configured Cloud runtime PostgreSQL role must not have schema CREATE')
        if ddl_privileges['can_use_schema'] is not True and require_grants:
            raise RuntimeError('Configured Cloud runtime PostgreSQL public schema USAGE grant is incomplete')
        if ddl_privileges['can_grant_schema_usage'] is True:
            raise RuntimeError('Configured Cloud runtime PostgreSQL schema USAGE has effective GRANT OPTION')
        if column_acl:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL role has forbidden column-level ACLs: '
                f'{[(row["relname"], row["attname"]) for row in column_acl]!r}'
            )
        if owned_routines:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL role must not own routines: '
                f'{[(row["nspname"], row["routine"]) for row in owned_routines]!r}'
            )
        if routine_acl:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL role or PUBLIC has forbidden explicit EXECUTE privileges on '
                'routines: '
                f'{[(row["nspname"], row["routine"], "PUBLIC" if row["grantee"] == 0 else runtime_role, row["is_grantable"]) for row in routine_acl]!r}'
            )
        if parameter_acl:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL role or PUBLIC has forbidden explicit SET or ALTER SYSTEM '
                'parameter privileges: '
                f'{[(row["parname"], "PUBLIC" if row["grantee"] == 0 else runtime_role, row["privilege_type"], row["is_grantable"]) for row in parameter_acl]!r}'
            )
        if security_definers:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL role can execute SECURITY DEFINER routines: '
                f'{[(row["nspname"], row["routine"]) for row in security_definers]!r}'
            )

        def validate_direct_acl(
            rows: typing.Iterable[typing.Mapping[str, typing.Any]],
            expected: frozenset[str],
            label: str,
        ) -> None:
            actual = {str(row['privilege_type']) for row in rows}
            grantable = sorted(str(row['privilege_type']) for row in rows if row['is_grantable'] is True)
            if grantable:
                raise RuntimeError(
                    f'Configured Cloud runtime PostgreSQL {label} grants have GRANT OPTION: {grantable!r}'
                )
            unexpected = sorted(actual - expected)
            if unexpected:
                raise RuntimeError(
                    f'Configured Cloud runtime PostgreSQL {label} grants are overprivileged: {unexpected!r}'
                )
            if require_grants and actual != expected:
                missing = sorted(expected - actual)
                raise RuntimeError(f'Configured Cloud runtime PostgreSQL {label} grants are incomplete: {missing!r}')

        validate_direct_acl(database_acl, frozenset({'CONNECT'}), 'database')
        validate_direct_acl(schema_acl, frozenset({'USAGE'}), 'schema')

        direct_table_acl: dict[str, list[typing.Mapping[str, typing.Any]]] = {}
        direct_sequence_acl: dict[str, list[typing.Mapping[str, typing.Any]]] = {}
        unexpected_acl_objects: set[str] = set()
        for row in object_acl:
            object_name = str(row['relname'])
            if row['relkind'] == 'S':
                if object_name in sequence_names:
                    direct_sequence_acl.setdefault(object_name, []).append(row)
                else:
                    unexpected_acl_objects.add(object_name)
            elif object_name in relation_allowlist:
                direct_table_acl.setdefault(object_name, []).append(row)
            else:
                unexpected_acl_objects.add(object_name)
        if unexpected_acl_objects:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL role has grants on non-business objects: '
                f'{sorted(unexpected_acl_objects)!r}'
            )

        for table_name, expected_privileges in relation_allowlist.items():
            validate_direct_acl(
                direct_table_acl.get(table_name, ()),
                expected_privileges,
                f'table {table_name!r}',
            )
        for sequence_name in sorted(sequence_names):
            validate_direct_acl(
                direct_sequence_acl.get(sequence_name, ()),
                _RUNTIME_SEQUENCE_PRIVILEGES,
                f'sequence {sequence_name!r}',
            )

        unsafe_tables: list[str] = []
        unavailable_tables: list[str] = []
        for row in table_privileges:
            table_name = str(row['relname'])
            expected_privileges = relation_allowlist.get(table_name, frozenset())
            actual_privileges = {
                privilege
                for privilege, key in (
                    ('SELECT', 'can_select'),
                    ('INSERT', 'can_insert'),
                    ('UPDATE', 'can_update'),
                    ('DELETE', 'can_delete'),
                    ('TRUNCATE', 'can_truncate'),
                    ('REFERENCES', 'can_reference'),
                    ('TRIGGER', 'can_trigger'),
                )
                if row[key] is True
            }
            effective_grant_options = {
                privilege
                for privilege, key in (
                    ('SELECT', 'can_grant_select'),
                    ('INSERT', 'can_grant_insert'),
                    ('UPDATE', 'can_grant_update'),
                    ('DELETE', 'can_grant_delete'),
                    ('TRUNCATE', 'can_grant_truncate'),
                    ('REFERENCES', 'can_grant_reference'),
                    ('TRIGGER', 'can_grant_trigger'),
                )
                if row[key] is True
            }
            if actual_privileges - expected_privileges or effective_grant_options:
                unsafe_tables.append(table_name)
            if require_grants and expected_privileges - actual_privileges:
                unavailable_tables.append(table_name)
        if unsafe_tables:
            raise RuntimeError(
                f'Configured Cloud runtime PostgreSQL table privileges are unsafe: {sorted(unsafe_tables)!r}'
            )
        if unavailable_tables:
            raise RuntimeError(
                f'Configured Cloud runtime PostgreSQL table privileges are incomplete: {sorted(unavailable_tables)!r}'
            )

        unsafe_sequences: list[str] = []
        unavailable_sequences: list[str] = []
        for row in sequence_privileges:
            sequence_name = str(row['relname'])
            expected_privileges = _RUNTIME_SEQUENCE_PRIVILEGES if sequence_name in sequence_names else frozenset()
            actual_privileges = {
                privilege
                for privilege, key in (
                    ('USAGE', 'can_use'),
                    ('SELECT', 'can_select'),
                    ('UPDATE', 'can_update'),
                )
                if row[key] is True
            }
            effective_grant_options = {
                privilege
                for privilege, key in (
                    ('USAGE', 'can_grant_use'),
                    ('SELECT', 'can_grant_select'),
                    ('UPDATE', 'can_grant_update'),
                )
                if row[key] is True
            }
            if actual_privileges - expected_privileges or effective_grant_options:
                unsafe_sequences.append(sequence_name)
            if require_grants and expected_privileges - actual_privileges:
                unavailable_sequences.append(sequence_name)
        if unsafe_sequences:
            raise RuntimeError(
                f'Configured Cloud runtime PostgreSQL sequence privileges are unsafe: {sorted(unsafe_sequences)!r}'
            )
        if unavailable_sequences:
            raise RuntimeError(
                'Configured Cloud runtime PostgreSQL sequence privileges are incomplete: '
                f'{sorted(unavailable_sequences)!r}'
            )

    async def _validate_postgres_pgvector_schema(self) -> None:
        """Fail closed when the release-owned pgvector contract has drifted."""

        engine = self.get_db_engine()
        if engine.dialect.name != 'postgresql':
            raise RuntimeError('PostgreSQL pgvector schema validation requires PostgreSQL')

        column_query = sqlalchemy.text(
            """
            SELECT
                a.attname AS column_name,
                format_type(a.atttypid, a.atttypmod) AS type_name,
                a.attnotnull AS not_null
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = 'langbot_vectors'
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
            """
        )
        constraint_query = sqlalchemy.text(
            """
            SELECT
                c.relname AS table_name,
                con.conname AS constraint_name,
                con.contype::text AS constraint_type,
                pg_get_constraintdef(con.oid) AS definition
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname IN ('knowledge_bases', 'langbot_vectors')
            ORDER BY c.relname, con.conname
            """
        )
        index_query = sqlalchemy.text(
            """
            SELECT
                idx.relname AS index_name,
                am.amname AS access_method,
                ix.indisvalid AS is_valid,
                ix.indisready AS is_ready,
                pg_get_indexdef(ix.indexrelid) AS definition,
                pg_get_expr(ix.indpred, ix.indrelid) AS predicate
            FROM pg_index ix
            JOIN pg_class tbl ON tbl.oid = ix.indrelid
            JOIN pg_namespace n ON n.oid = tbl.relnamespace
            JOIN pg_class idx ON idx.oid = ix.indexrelid
            JOIN pg_am am ON am.oid = idx.relam
            WHERE n.nspname = 'public'
              AND tbl.relname = 'langbot_vectors'
            ORDER BY idx.relname
            """
        )

        async with engine.connect() as conn:
            extension_installed = await conn.scalar(
                sqlalchemy.text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            )
            columns = (await conn.execute(column_query)).mappings().all()
            constraints = (await conn.execute(constraint_query)).mappings().all()
            indexes = (await conn.execute(index_query)).mappings().all()

        if extension_installed is not True:
            raise RuntimeError('PostgreSQL vector extension is not installed')

        expected_columns = {
            'workspace_uuid': ('character varying(36)', True),
            'knowledge_base_uuid': ('character varying(255)', True),
            'vector_id': ('character varying(255)', True),
            'embedding_dimension': ('integer', True),
            # An untyped pgvector column is required because enabled dimensions
            # share the table and are selected by release-created partial indexes.
            'embedding': ('vector', True),
            'text': ('text', False),
            'file_id': ('character varying(255)', False),
            'chunk_uuid': ('character varying(255)', False),
        }
        actual_columns = {row['column_name']: (row['type_name'], row['not_null']) for row in columns}
        if actual_columns != expected_columns:
            raise RuntimeError('PostgreSQL pgvector columns do not match the release contract')

        by_constraint = {(row['table_name'], row['constraint_name']): row for row in constraints}
        required_constraints = {
            ('knowledge_bases', 'ck_knowledge_bases_embedding_dimension_positive'),
            ('langbot_vectors', 'pk_langbot_vectors'),
            ('langbot_vectors', 'fk_langbot_vectors_workspace_kb'),
            ('langbot_vectors', 'ck_langbot_vectors_embedding_dimension'),
            ('langbot_vectors', 'ck_langbot_vectors_embedding_dimension_enabled'),
        }
        missing_constraints = sorted(required_constraints - set(by_constraint))
        if missing_constraints:
            raise RuntimeError(f'PostgreSQL pgvector constraints are missing: {missing_constraints!r}')

        def normalized(value: str | None) -> str:
            return ' '.join((value or '').lower().split())

        primary_key = normalized(by_constraint[('langbot_vectors', 'pk_langbot_vectors')]['definition'])
        if primary_key != 'primary key (workspace_uuid, knowledge_base_uuid, vector_id)':
            raise RuntimeError('PostgreSQL pgvector primary key does not match the release contract')

        foreign_key = normalized(by_constraint[('langbot_vectors', 'fk_langbot_vectors_workspace_kb')]['definition'])
        if (
            'foreign key (workspace_uuid, knowledge_base_uuid)' not in foreign_key
            or 'references knowledge_bases(workspace_uuid, uuid)' not in foreign_key
            or 'on delete cascade' not in foreign_key
        ):
            raise RuntimeError('PostgreSQL pgvector foreign key does not match the release contract')

        kb_dimension = normalized(
            by_constraint[('knowledge_bases', 'ck_knowledge_bases_embedding_dimension_positive')]['definition']
        )
        if 'embedding_dimension is null' not in kb_dimension or 'embedding_dimension > 0' not in kb_dimension:
            raise RuntimeError('PostgreSQL knowledge-base embedding dimension check is invalid')

        vector_dimension = normalized(
            by_constraint[('langbot_vectors', 'ck_langbot_vectors_embedding_dimension')]['definition']
        )
        if 'vector_dims(embedding)' not in vector_dimension or 'embedding_dimension' not in vector_dimension:
            raise RuntimeError('PostgreSQL pgvector dimension check is invalid')

        allowed_dimension = normalized(
            by_constraint[('langbot_vectors', 'ck_langbot_vectors_embedding_dimension_enabled')]['definition']
        )
        if {int(item) for item in re.findall(r'\b\d+\b', allowed_dimension)} != set(_PGVECTOR_ALLOWED_DIMENSIONS):
            raise RuntimeError('PostgreSQL pgvector enabled-dimension check is invalid')

        by_index = {row['index_name']: row for row in indexes}
        expected_btree_indexes = {
            'ix_langbot_vectors_workspace_kb_file': '(workspace_uuid, knowledge_base_uuid, file_id)',
            'ix_langbot_vectors_workspace_kb_chunk': '(workspace_uuid, knowledge_base_uuid, chunk_uuid)',
        }
        for index_name, columns_fragment in expected_btree_indexes.items():
            index = by_index.get(index_name)
            if (
                index is None
                or index['access_method'] != 'btree'
                or index['is_valid'] is not True
                or index['is_ready'] is not True
                or columns_fragment not in index['definition']
            ):
                raise RuntimeError(f'PostgreSQL pgvector index {index_name!r} is invalid')

        for dimension in _PGVECTOR_ALLOWED_DIMENSIONS:
            index_name = f'ix_langbot_vectors_hnsw_cosine_{dimension}'
            index = by_index.get(index_name)
            index_definition = normalized(None if index is None else index['definition'])
            predicate = normalized(None if index is None else index['predicate'])
            if (
                index is None
                or index['access_method'] != 'hnsw'
                or index['is_valid'] is not True
                or index['is_ready'] is not True
                or f'vector({dimension})' not in index_definition
                or f'(embedding)::vector({dimension})' not in index_definition
                or 'vector_cosine_ops' not in index_definition
                or predicate.strip('() ') != f'embedding_dimension = {dimension}'
            ):
                raise RuntimeError(f'PostgreSQL pgvector ANN index {index_name!r} is invalid')

    async def _validate_postgres_tenant_schema(self, *, validate_runtime_role: bool) -> None:
        """Fail closed when PostgreSQL cannot enforce the tenant contract."""
        engine = self.get_db_engine()
        if engine.dialect.name != 'postgresql':
            raise RuntimeError('PostgreSQL tenant schema validation requires PostgreSQL')

        table_query = sqlalchemy.text(
            """
            SELECT
                c.relname AS table_name,
                c.relrowsecurity AS rls_enabled,
                c.relforcerowsecurity AS rls_forced,
                pg_get_userbyid(c.relowner) = current_user AS owned_by_runtime
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind IN ('r', 'p')
              AND c.relname IN :table_names
            """
        ).bindparams(sqlalchemy.bindparam('table_names', expanding=True))
        policy_query = sqlalchemy.text(
            """
            SELECT
                c.relname AS table_name,
                p.polname AS policy_name,
                p.polcmd::text AS command,
                p.polpermissive AS permissive,
                p.polroles = ARRAY[0::oid] AS public_only,
                pg_get_expr(p.polqual, p.polrelid) AS using_expression,
                pg_get_expr(p.polwithcheck, p.polrelid) AS check_expression
            FROM pg_policy p
            JOIN pg_class c ON c.oid = p.polrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname IN :table_names
            ORDER BY c.relname, p.polname
            """
        ).bindparams(sqlalchemy.bindparam('table_names', expanding=True))

        async with engine.connect() as conn:
            if validate_runtime_role:
                role = (
                    (
                        await conn.execute(
                            sqlalchemy.text(
                                """
                            SELECT rolsuper, rolbypassrls
                            FROM pg_roles
                            WHERE rolname = current_user
                            """
                            )
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if role is None:
                    raise RuntimeError('Cloud runtime PostgreSQL role could not be inspected')
                if role['rolsuper']:
                    raise RuntimeError('Cloud runtime PostgreSQL role must not be a superuser')
                if role['rolbypassrls']:
                    raise RuntimeError('Cloud runtime PostgreSQL role must not have BYPASSRLS')

            rows = (
                (
                    await conn.execute(
                        table_query,
                        {
                            'table_names': tuple(TENANT_TABLE_COLUMNS),
                        },
                    )
                )
                .mappings()
                .all()
            )
            policy_rows = (
                (
                    await conn.execute(
                        policy_query,
                        {'table_names': tuple(TENANT_TABLE_COLUMNS)},
                    )
                )
                .mappings()
                .all()
            )

        by_table = {row['table_name']: row for row in rows}
        missing_tables = set(TENANT_TABLE_COLUMNS) - set(by_table)
        if missing_tables:
            raise RuntimeError(f'PostgreSQL tenant tables are missing: {sorted(missing_tables)!r}')

        invalid_rls = sorted(
            table_name for table_name, row in by_table.items() if not row['rls_enabled'] or not row['rls_forced']
        )
        if invalid_rls:
            raise RuntimeError(f'PostgreSQL tenant RLS contract is incomplete for tables: {invalid_rls!r}')

        expected_policies = self._expected_postgres_tenant_policies()
        actual_policies = {(row['table_name'], row['policy_name']): row for row in policy_rows}
        expected_keys = {
            (table_name, policy_name) for table_name, policies in expected_policies.items() for policy_name in policies
        }
        actual_keys = set(actual_policies)
        if actual_keys != expected_keys:
            missing = sorted(expected_keys - actual_keys)
            extra = sorted(actual_keys - expected_keys)
            raise RuntimeError(
                f'PostgreSQL tenant policy set does not match the release contract; missing={missing!r}, extra={extra!r}'
            )

        invalid_policies: list[tuple[str, str]] = []
        for table_name, policies in expected_policies.items():
            for policy_name, expected in policies.items():
                actual = actual_policies[(table_name, policy_name)]
                if (
                    actual['command'] != expected['command']
                    or actual['permissive'] is not True
                    or actual['public_only'] is not True
                    or actual['using_expression'] != expected['using_expression']
                    or actual['check_expression'] != expected['check_expression']
                ):
                    invalid_policies.append((table_name, policy_name))
        if invalid_policies:
            raise RuntimeError(f'PostgreSQL tenant policy definitions are invalid: {invalid_policies!r}')

        if validate_runtime_role:
            owned_tables = sorted(table_name for table_name, row in by_table.items() if row['owned_by_runtime'])
            if owned_tables:
                raise RuntimeError(f'Cloud runtime PostgreSQL role must not own tenant tables: {owned_tables!r}')

    @staticmethod
    def _expected_postgres_tenant_policies() -> dict[str, dict[str, dict[str, str | None]]]:
        """Return the exact PostgreSQL 16 policy expressions emitted by 0011."""

        def setting(name: str) -> str:
            return f"NULLIF(current_setting('{name}'::text, true), ''::text)"

        policies: dict[str, dict[str, dict[str, str | None]]] = {}
        for table_name, tenant_column in TENANT_TABLE_COLUMNS.items():
            expression = f'(({tenant_column})::text = {setting(TENANT_SETTING)})'
            policies[table_name] = {
                TENANT_POLICY_NAME: {
                    'command': '*',
                    'using_expression': expression,
                    'check_expression': expression,
                }
            }

        policies['workspace_memberships'][ACCOUNT_DISCOVERY_POLICY_NAME] = {
            'command': 'r',
            'using_expression': (
                f"(((account_uuid)::text = {setting('langbot.account_uuid')}) AND ((status)::text = 'active'::text))"
            ),
            'check_expression': None,
        }
        policies['api_keys'][API_KEY_DISCOVERY_POLICY_NAME] = {
            'command': 'r',
            'using_expression': (
                f'(((key_hash)::text = {setting("langbot.api_key_hash")}) '
                "AND ((status)::text = 'active'::text) "
                'AND ((expires_at IS NULL) OR (expires_at > CURRENT_TIMESTAMP)))'
            ),
            'check_expression': None,
        }
        policies['workspace_invitations'][INVITATION_DISCOVERY_POLICY_NAME] = {
            'command': 'r',
            'using_expression': f'((token_hash)::text = {setting("langbot.invitation_hash")})',
            'check_expression': None,
        }
        policies['workspace_execution_states'][INSTANCE_DISCOVERY_POLICY_NAME] = {
            'command': 'r',
            'using_expression': (
                f'(((instance_uuid)::text = {setting("langbot.instance_uuid")}) '
                "AND ((state)::text = 'active'::text) AND (write_fenced = false))"
            ),
            'check_expression': None,
        }
        return policies

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

    async def _run_alembic_migrations(self, target_revision: str = 'head'):
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
            await alembic_runner.run_alembic_upgrade(engine, target_revision)
            self.ap.logger.info(f'Alembic migrations completed at {target_revision}.')
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
        active = self._get_active_transaction()
        if active is not None:
            try:
                return await self._execute_on_scoped_connection(active.session, *args, **kwargs)
            except BaseException as exc:
                # Business code may intentionally catch a constraint failure.
                # PostgreSQL still leaves that transaction aborted, so record
                # the failure here and make the owning UoW fail closed on exit.
                active.mark_rollback_only(exc)
                raise
        active_scope = self._get_active_scope()
        if active_scope is not None:
            async with self._scoped_uow(active_scope.scope) as uow:
                return await self._execute_on_scoped_connection(uow.session, *args, **kwargs)
        if self.mode == PersistenceMode.CLOUD_RUNTIME:
            raise TenantScopeRequiredError(
                'Cloud persistence access requires an explicit Workspace or discovery scope/unit of work'
            )
        async with self.get_db_engine().connect() as conn:
            result = await conn.execute(*args, **kwargs)
            await conn.commit()
            return result

    @staticmethod
    async def _execute_on_scoped_connection(
        session: sqlalchemy_asyncio.AsyncSession,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> sqlalchemy.engine.cursor.CursorResult:
        """Preserve the historical ``execute_async`` Core-result contract.

        ``execute_async`` originally delegated to ``AsyncConnection.execute``.
        Routing it through ``AsyncSession.execute`` inside a tenant unit of work
        subtly changes ``select(Model)`` from a flat column row into a one-item
        ORM row.  Legacy callers consequently lose attributes such as ``uuid``
        and ``user``.  Flush pending ORM state, then execute on the Session's
        transaction-bound connection so row, scalar, and cursor consumers keep
        the same behavior without escaping the scoped transaction.

        Explicit ``TenantUnitOfWork.session`` and ``TenantUnitOfWork.execute``
        calls retain normal ORM result semantics.
        """

        await session.flush()
        connection = await session.connection()
        return await connection.execute(*args, **kwargs)

    def tenant_uow(self, workspace_uuid: str) -> TenantUnitOfWork:
        return self._scoped_uow(PersistenceScope.workspace(workspace_uuid))

    def tenant_scope(self, workspace_uuid: str) -> PersistenceScopeBoundary:
        """Bind a Workspace without holding a database session between calls."""

        return PersistenceScopeBoundary(
            PersistenceScope.workspace(workspace_uuid),
            active_scope=self._active_scope,
            active_transaction=self._active_transaction,
        )

    def account_discovery_uow(self, account_uuid: str) -> TenantUnitOfWork:
        return self._scoped_uow(PersistenceScope.account(account_uuid))

    def api_key_discovery_uow(self, key_hash: str) -> TenantUnitOfWork:
        return self._scoped_uow(PersistenceScope.api_key(key_hash))

    def invitation_discovery_uow(self, invitation_hash: str) -> TenantUnitOfWork:
        return self._scoped_uow(PersistenceScope.invitation(invitation_hash))

    def instance_discovery_uow(self, instance_uuid: str) -> TenantUnitOfWork:
        return self._scoped_uow(PersistenceScope.instance(instance_uuid))

    def identity_discovery_uow(self, identity_digest: str) -> TenantUnitOfWork:
        return self._scoped_uow(PersistenceScope.identity(identity_digest))

    def current_session(self) -> sqlalchemy_asyncio.AsyncSession | None:
        """Return the transaction-bound session for the current task, if any."""

        active = self._get_active_transaction()
        return None if active is None else active.session

    def current_scope(self) -> PersistenceScope | None:
        active = self._get_active_transaction()
        if active is not None:
            return active.scope
        active_scope = self._get_active_scope()
        return None if active_scope is None else active_scope.scope

    def create_after_commit_gate(self) -> asyncio.Future[None] | None:
        """Return a gate resolved only after the current scoped transaction commits.

        Detached tasks register while still in the request task, before its
        ContextVars are cleared.  When there is no active transaction they may
        start immediately.  A rollback cancels the gate so no side effect is
        launched for data that was never committed.
        """

        active = self._get_active_transaction()
        if active is None:
            return None
        gate = asyncio.get_running_loop().create_future()
        active.after_commit_waiters.append(gate)
        return gate

    def require_current_session(
        self,
        *allowed_scope_kinds: PersistenceScopeKind,
    ) -> sqlalchemy_asyncio.AsyncSession:
        active = self._get_active_transaction()
        if active is None:
            raise TenantScopeRequiredError('An explicit persistence unit of work is required')
        if allowed_scope_kinds and active.scope.kind not in allowed_scope_kinds:
            allowed = ', '.join(kind.value for kind in allowed_scope_kinds)
            raise CrossScopeTransactionError(
                f'Persistence scope {active.scope.kind.value} is not valid here; expected one of: {allowed}'
            )
        return active.session

    def _scoped_uow(self, scope: PersistenceScope) -> TenantUnitOfWork:
        return TenantUnitOfWork(
            self.get_db_engine(),
            scope=scope,
            active_transaction=self._active_transaction,
            active_scope=self._active_scope,
        )

    def _get_active_transaction(self) -> ActiveScopedTransaction | None:
        active = self._active_transaction.get()
        if active is not None and active.owner_task is not asyncio.current_task():
            raise CrossScopeTransactionError(
                'Scoped database transactions cannot be inherited by child tasks; open an explicit task scope'
            )
        return active

    def _get_active_scope(self) -> ActivePersistenceScope | None:
        active = self._active_scope.get()
        if active is not None and active.owner_task is not asyncio.current_task():
            raise CrossScopeTransactionError(
                'Scoped persistence boundaries cannot be inherited by child tasks; open an explicit task scope'
            )
        return active

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
