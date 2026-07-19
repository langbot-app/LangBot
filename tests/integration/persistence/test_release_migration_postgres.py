"""Real PostgreSQL coverage for the one-shot Cloud release migration job."""

from __future__ import annotations

import logging
import os
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from langbot.pkg.persistence import release_migration
from langbot.pkg.persistence.alembic_runner import (
    get_alembic_current,
    get_alembic_head,
    run_alembic_stamp,
    run_alembic_upgrade,
)
from langbot.pkg.persistence.mgr import (
    PersistenceManager,
    PersistenceMode,
    _RELEASE_MIGRATION_ADVISORY_LOCK_ID,
)
from langbot.pkg.utils import constants


pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.asyncio]
_RUNTIME_PASSWORD = 'runtime-secret-not-used-by-migration'


@pytest.fixture
def postgres_url() -> str:
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL not set')
    return url


@pytest.fixture
async def postgres_engine(postgres_url: str):
    engine = create_async_engine(postgres_url, isolation_level='AUTOCOMMIT')
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_database(postgres_engine: AsyncEngine):
    async def clean() -> None:
        async with postgres_engine.begin() as conn:
            table_names = await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_table_names())
            quote = postgres_engine.dialect.identifier_preparer.quote
            for table_name in table_names:
                await conn.execute(text(f'DROP TABLE {quote(table_name)} CASCADE'))

    await clean()
    yield
    await clean()


def _restore_postgres_registry(monkeypatch) -> None:
    from langbot.pkg.persistence import mgr as persistence_mgr_module
    from langbot.pkg.persistence.databases.postgresql import PostgreSQLDatabaseManager

    monkeypatch.setattr(
        persistence_mgr_module.database,
        'preregistered_managers',
        [PostgreSQLDatabaseManager],
    )


def _application(postgres_url: str, *, runtime_role: str = 'langbot_runtime_not_used_by_migration') -> SimpleNamespace:
    url = sa.engine.make_url(postgres_url)
    return SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'use': 'postgresql',
                    'postgresql': {
                        'host': url.host,
                        'port': url.port,
                        # This is deliberately not the operator role in the DSN.
                        'user': runtime_role,
                        'password': _RUNTIME_PASSWORD,
                        'database': url.database,
                    },
                    'cloud_migration': {'operator_dsn_env': 'TEST_RELEASE_OPERATOR_DSN'},
                },
                'vdb': {
                    'use': 'pgvector',
                    'pgvector': {
                        'use_business_database': True,
                        'allowed_dimensions': [384, 512, 768, 1024, 1536],
                    },
                },
            }
        ),
        logger=logging.getLogger('cloud-release-migration-entrypoint-test'),
        persistence_mgr=None,
    )


async def test_release_entrypoint_holds_lock_migrates_validates_and_disposes(
    postgres_url: str,
    postgres_engine: AsyncEngine,
    clean_database,
    monkeypatch,
) -> None:
    _restore_postgres_registry(monkeypatch)
    monkeypatch.setattr(constants, 'instance_id', 'release-migration-entrypoint-test')
    original_validate = PersistenceManager._validate_release_schema
    validation_observed_lock = False
    runtime_role = f'lb_release_runtime_{uuid.uuid4().hex[:12]}'
    quote = postgres_engine.dialect.identifier_preparer.quote

    async def validate_while_asserting_lock(self: PersistenceManager) -> None:
        nonlocal validation_observed_lock
        async with postgres_engine.connect() as conn:
            acquired = await conn.scalar(
                text('SELECT pg_try_advisory_lock(:lock_id)'),
                {'lock_id': _RELEASE_MIGRATION_ADVISORY_LOCK_ID},
            )
            if acquired:
                await conn.scalar(
                    text('SELECT pg_advisory_unlock(:lock_id)'),
                    {'lock_id': _RELEASE_MIGRATION_ADVISORY_LOCK_ID},
                )
            assert acquired is False
            validation_observed_lock = True
        await original_validate(self)

    monkeypatch.setattr(PersistenceManager, '_validate_release_schema', validate_while_asserting_lock)
    async with postgres_engine.connect() as conn:
        await conn.execute(text(f"CREATE ROLE {quote(runtime_role)} LOGIN PASSWORD '{_RUNTIME_PASSWORD}'"))
        # The release job must make this otherwise bare LOGIN usable without
        # relying on pre-provisioned object ACLs.
        assert (
            await conn.scalar(
                text(
                    """
                    SELECT NOT EXISTS (
                        SELECT 1
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        CROSS JOIN LATERAL aclexplode(c.relacl) acl
                        JOIN pg_roles grantee ON grantee.oid = acl.grantee
                        WHERE n.nspname = current_schema()
                          AND grantee.rolname = :runtime_role
                    )
                    """
                ),
                {'runtime_role': runtime_role},
            )
            is True
        )
    ap = _application(postgres_url, runtime_role=runtime_role)
    try:
        await release_migration.run_cloud_release_migration(
            ap,
            environ={'TEST_RELEASE_OPERATOR_DSN': postgres_url},
        )

        assert validation_observed_lock is True
        assert await get_alembic_current(postgres_engine) == get_alembic_head()
        manager = ap.persistence_mgr
        assert isinstance(manager, PersistenceManager)
        business_tables = set(manager._runtime_business_table_names())
        async with postgres_engine.connect() as conn:
            assert await conn.scalar(text("SELECT to_regclass('langbot_vectors') IS NOT NULL")) is True
            assert (
                await conn.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")) is True
            )
            runtime_role_state = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT
                            rolcanlogin,
                            rolsuper,
                            rolbypassrls,
                            rolcreatedb,
                            rolcreaterole,
                            rolreplication
                        FROM pg_roles
                        WHERE rolname = :runtime_role
                        """
                        ),
                        {'runtime_role': runtime_role},
                    )
                )
                .mappings()
                .one()
            )
            assert dict(runtime_role_state) == {
                'rolcanlogin': True,
                'rolsuper': False,
                'rolbypassrls': False,
                'rolcreatedb': False,
                'rolcreaterole': False,
                'rolreplication': False,
            }

            database_privileges = set(
                (
                    await conn.execute(
                        text(
                            """
                            SELECT acl.privilege_type
                            FROM pg_database database
                            CROSS JOIN LATERAL aclexplode(database.datacl) acl
                            JOIN pg_roles grantee ON grantee.oid = acl.grantee
                            WHERE database.datname = current_database()
                              AND grantee.rolname = :runtime_role
                              AND acl.is_grantable IS FALSE
                            """
                        ),
                        {'runtime_role': runtime_role},
                    )
                )
                .scalars()
                .all()
            )
            schema_privileges = set(
                (
                    await conn.execute(
                        text(
                            """
                            SELECT acl.privilege_type
                            FROM pg_namespace namespace
                            CROSS JOIN LATERAL aclexplode(namespace.nspacl) acl
                            JOIN pg_roles grantee ON grantee.oid = acl.grantee
                            WHERE namespace.nspname = current_schema()
                              AND grantee.rolname = :runtime_role
                              AND acl.is_grantable IS FALSE
                            """
                        ),
                        {'runtime_role': runtime_role},
                    )
                )
                .scalars()
                .all()
            )
            assert database_privileges == {'CONNECT'}
            assert schema_privileges == {'USAGE'}
            assert (
                await conn.scalar(
                    text("SELECT has_database_privilege(:runtime_role, current_database(), 'CREATE')"),
                    {'runtime_role': runtime_role},
                )
                is False
            )
            assert (
                await conn.scalar(
                    text("SELECT has_schema_privilege(:runtime_role, current_schema(), 'CREATE')"),
                    {'runtime_role': runtime_role},
                )
                is False
            )
            # PostgreSQL grants TEMP to PUBLIC by default. The first Cloud
            # release deliberately tolerates that inherited compatibility
            # privilege while granting no direct TEMP ACL to the runtime role.
            assert (
                await conn.scalar(
                    text("SELECT has_database_privilege(:runtime_role, current_database(), 'TEMP')"),
                    {'runtime_role': runtime_role},
                )
                is True
            )

            object_grants = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT
                            c.relname,
                            c.relkind::text AS relkind,
                            acl.privilege_type,
                            acl.is_grantable
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        CROSS JOIN LATERAL aclexplode(c.relacl) acl
                        JOIN pg_roles grantee ON grantee.oid = acl.grantee
                        WHERE n.nspname = current_schema()
                          AND c.relkind IN ('r', 'p', 'S')
                          AND grantee.rolname = :runtime_role
                        ORDER BY c.relname, acl.privilege_type
                        """
                        ),
                        {'runtime_role': runtime_role},
                    )
                )
                .mappings()
                .all()
            )
            direct_table_grants: dict[str, set[str]] = {}
            direct_sequence_grants: dict[str, set[str]] = {}
            for grant in object_grants:
                assert grant['is_grantable'] is False
                target = direct_sequence_grants if grant['relkind'] == 'S' else direct_table_grants
                target.setdefault(grant['relname'], set()).add(grant['privilege_type'])

            assert set(direct_table_grants) == business_tables | {'alembic_version'}
            assert all(
                privileges == {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}
                for table_name, privileges in direct_table_grants.items()
                if table_name != 'alembic_version'
            )
            assert direct_table_grants['alembic_version'] == {'SELECT'}
            assert direct_sequence_grants
            assert all(privileges == {'USAGE', 'SELECT'} for privileges in direct_sequence_grants.values())
            # The session-level lock must be released before the one-shot job exits.
            assert (
                await conn.scalar(
                    text('SELECT pg_try_advisory_lock(:lock_id)'),
                    {'lock_id': _RELEASE_MIGRATION_ADVISORY_LOCK_ID},
                )
                is True
            )
            assert (
                await conn.scalar(
                    text('SELECT pg_advisory_unlock(:lock_id)'),
                    {'lock_id': _RELEASE_MIGRATION_ADVISORY_LOCK_ID},
                )
                is True
            )

        runtime_url = (
            sa.engine.make_url(postgres_url)
            .set(username=runtime_role, password=_RUNTIME_PASSWORD)
            .render_as_string(hide_password=False)
        )
        runtime_engine = create_async_engine(runtime_url)
        try:
            async with runtime_engine.begin() as conn:
                assert await conn.scalar(text('SELECT current_user')) == runtime_role
                await conn.execute(text("INSERT INTO metadata (key, value) VALUES ('runtime-grant-smoke', 'created')"))
                await conn.execute(text("UPDATE metadata SET value = 'updated' WHERE key = 'runtime-grant-smoke'"))
                assert (
                    await conn.scalar(text("SELECT value FROM metadata WHERE key = 'runtime-grant-smoke'")) == 'updated'
                )
                await conn.execute(text("DELETE FROM metadata WHERE key = 'runtime-grant-smoke'"))
                await conn.scalar(
                    text('SELECT nextval(CAST(:sequence_name AS regclass))'),
                    {'sequence_name': f'public.{sorted(direct_sequence_grants)[0]}'},
                )
        finally:
            await runtime_engine.dispose()

        runtime_application = _application(postgres_url, runtime_role=runtime_role)
        runtime_manager = PersistenceManager(runtime_application, mode=PersistenceMode.CLOUD_RUNTIME)
        runtime_application.persistence_mgr = runtime_manager
        try:
            # This reads alembic_version as the actual runtime role and then
            # reruns the complete grant/catalog validator before startup.
            await runtime_manager.initialize()
        finally:
            await runtime_manager.get_db_engine().dispose()

        # The catalog validator must fail closed if the role is no longer
        # deployable, even though the remaining grants still look plausible.
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'REVOKE DELETE ON TABLE public.metadata FROM {quote(runtime_role)}'))
        with pytest.raises(RuntimeError, match="table 'metadata' grants are incomplete"):
            await manager._validate_configured_runtime_postgres_role(require_grants=True)
    finally:
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'DROP OWNED BY {quote(runtime_role)}'))
            await conn.execute(text(f'DROP ROLE IF EXISTS {quote(runtime_role)}'))


async def test_release_entrypoint_rejects_privileged_or_table_owning_runtime_role(
    postgres_url: str,
    postgres_engine: AsyncEngine,
    clean_database,
    monkeypatch,
) -> None:
    _restore_postgres_registry(monkeypatch)
    monkeypatch.setattr(constants, 'instance_id', 'release-runtime-role-validation-test')
    runtime_role = f'lb_release_runtime_{uuid.uuid4().hex[:12]}'
    quote = postgres_engine.dialect.identifier_preparer.quote
    async with postgres_engine.connect() as conn:
        operator_role = await conn.scalar(text('SELECT current_user'))
        await conn.execute(text(f'CREATE ROLE {quote(runtime_role)} LOGIN'))

    ap = _application(postgres_url, runtime_role=runtime_role)
    try:
        await release_migration.run_cloud_release_migration(
            ap,
            environ={'TEST_RELEASE_OPERATOR_DSN': postgres_url},
        )

        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} SUPERUSER'))
        with pytest.raises(RuntimeError, match='must not be superuser or BYPASSRLS'):
            await release_migration.run_cloud_release_migration(
                ap,
                environ={'TEST_RELEASE_OPERATOR_DSN': postgres_url},
            )

        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} NOSUPERUSER BYPASSRLS'))
        with pytest.raises(RuntimeError, match='must not be superuser or BYPASSRLS'):
            await release_migration.run_cloud_release_migration(
                ap,
                environ={'TEST_RELEASE_OPERATOR_DSN': postgres_url},
            )

        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} NOBYPASSRLS'))
            await conn.execute(text(f'ALTER TABLE bots OWNER TO {quote(runtime_role)}'))
        with pytest.raises(RuntimeError, match='owns tenant tables'):
            await release_migration.run_cloud_release_migration(
                ap,
                environ={'TEST_RELEASE_OPERATOR_DSN': postgres_url},
            )
    finally:
        async with postgres_engine.connect() as conn:
            table_exists = await conn.scalar(text("SELECT to_regclass('bots') IS NOT NULL"))
            if table_exists:
                await conn.execute(text(f'ALTER TABLE bots OWNER TO {quote(operator_role)}'))
            await conn.execute(text(f'DROP OWNED BY {quote(runtime_role)}'))
            await conn.execute(text(f'DROP ROLE IF EXISTS {quote(runtime_role)}'))


async def test_runtime_role_catalog_validator_rejects_delegation_and_escape_hatches(
    postgres_url: str,
    postgres_engine: AsyncEngine,
    clean_database,
    monkeypatch,
) -> None:
    _restore_postgres_registry(monkeypatch)
    monkeypatch.setattr(constants, 'instance_id', 'release-runtime-role-catalog-test')
    suffix = uuid.uuid4().hex[:12]
    runtime_role = f'lb_release_runtime_{suffix}'
    delegated_role = f'lb_release_delegate_{suffix}'
    extra_schema = f'lb_release_schema_{suffix}'
    extra_view = f'lb_release_view_{suffix}'
    owned_routine = f'lb_release_owned_routine_{suffix}'
    security_definer = f'lb_release_definer_{suffix}'
    foreign_wrapper = f'lb_release_fdw_{suffix}'
    foreign_server = f'lb_release_server_{suffix}'
    persistent_setting_secret = f'lb_release_secret_{suffix}'
    database_name = sa.engine.make_url(postgres_url).database
    assert database_name
    quote = postgres_engine.dialect.identifier_preparer.quote

    async with postgres_engine.connect() as conn:
        await conn.execute(text(f"CREATE ROLE {quote(runtime_role)} LOGIN PASSWORD '{_RUNTIME_PASSWORD}'"))
        await conn.execute(text(f'CREATE ROLE {quote(delegated_role)}'))

    ap = _application(postgres_url, runtime_role=runtime_role)
    try:
        await release_migration.run_cloud_release_migration(
            ap,
            environ={'TEST_RELEASE_OPERATOR_DSN': postgres_url},
        )
        manager = ap.persistence_mgr
        assert isinstance(manager, PersistenceManager)

        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'GRANT pg_read_all_data TO {quote(runtime_role)}'))
        with pytest.raises(RuntimeError, match='must not participate in role memberships'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'REVOKE pg_read_all_data FROM {quote(runtime_role)}'))

            # Reject delegation in the other direction too: no role may be
            # allowed to SET ROLE to the runtime identity or administer it.
            await conn.execute(text(f'GRANT {quote(runtime_role)} TO {quote(delegated_role)} WITH ADMIN OPTION'))
        with pytest.raises(RuntimeError, match='must not participate in role memberships'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'REVOKE {quote(runtime_role)} FROM {quote(delegated_role)}'))

            await conn.execute(
                text(f'GRANT SELECT ON TABLE public.metadata TO {quote(runtime_role)} WITH GRANT OPTION')
            )
        with pytest.raises(RuntimeError, match='GRANT OPTION'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(
                text(f'REVOKE GRANT OPTION FOR SELECT ON TABLE public.metadata FROM {quote(runtime_role)}')
            )

            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} SET search_path TO public'))
        with pytest.raises(RuntimeError, match='persistent session overrides'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} RESET search_path'))

            await conn.execute(text(f'ALTER DATABASE {quote(database_name)} SET search_path TO public'))
        with pytest.raises(RuntimeError, match='persistent session overrides'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'ALTER DATABASE {quote(database_name)} RESET search_path'))

            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} SET session_replication_role TO replica'))
        with pytest.raises(RuntimeError, match='persistent session overrides'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} RESET session_replication_role'))

            await conn.execute(
                text(f"ALTER ROLE {quote(runtime_role)} SET application_name TO '{persistent_setting_secret}'")
            )
        with pytest.raises(RuntimeError, match='persistent session overrides') as error:
            await manager._validate_configured_runtime_postgres_role()
        assert persistent_setting_secret not in str(error.value)
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} RESET application_name'))

            await conn.execute(text('CREATE EXTENSION dblink'))
        with pytest.raises(RuntimeError, match='extensions must include vector and be limited'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text('DROP EXTENSION dblink'))
        await manager._validate_configured_runtime_postgres_role()

        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'GRANT CREATE ON DATABASE {quote(database_name)} TO {quote(runtime_role)}'))
            await conn.execute(text(f'GRANT CREATE ON SCHEMA public TO {quote(runtime_role)}'))
        runtime_url = (
            sa.engine.make_url(postgres_url)
            .set(username=runtime_role, password=_RUNTIME_PASSWORD)
            .render_as_string(hide_password=False)
        )
        runtime_engine = create_async_engine(runtime_url)
        try:
            async with runtime_engine.begin() as conn:
                # hstore is a trusted extension in the production PG16 image,
                # so this creates a real runtime-owned extension catalog row.
                await conn.execute(text('CREATE EXTENSION hstore'))
        finally:
            await runtime_engine.dispose()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'REVOKE CREATE ON SCHEMA public FROM {quote(runtime_role)}'))
            await conn.execute(text(f'REVOKE CREATE ON DATABASE {quote(database_name)} FROM {quote(runtime_role)}'))
        with pytest.raises(RuntimeError, match='must not own extensions'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text('DROP EXTENSION hstore CASCADE'))
        await manager._validate_configured_runtime_postgres_role()

        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'CREATE FOREIGN DATA WRAPPER {quote(foreign_wrapper)}'))
            await conn.execute(
                text(f'CREATE SERVER {quote(foreign_server)} FOREIGN DATA WRAPPER {quote(foreign_wrapper)}')
            )
            await conn.execute(text(f'CREATE USER MAPPING FOR {quote(runtime_role)} SERVER {quote(foreign_server)}'))
        with pytest.raises(RuntimeError, match='foreign data wrappers, servers, or user mappings'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'DROP FOREIGN DATA WRAPPER {quote(foreign_wrapper)} CASCADE'))
        await manager._validate_configured_runtime_postgres_role()

        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'CREATE SCHEMA {quote(extra_schema)} AUTHORIZATION {quote(runtime_role)}'))
        with pytest.raises(RuntimeError, match='non-business schemas'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'DROP SCHEMA {quote(extra_schema)} CASCADE'))

            await conn.execute(text(f'CREATE VIEW public.{quote(extra_view)} AS SELECT key FROM public.metadata'))
            await conn.execute(text(f'GRANT SELECT ON public.{quote(extra_view)} TO {quote(runtime_role)}'))
        with pytest.raises(RuntimeError, match='non-business objects|table privileges are unsafe'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'DROP VIEW public.{quote(extra_view)}'))

            await conn.execute(text(f'GRANT SELECT (key) ON public.metadata TO {quote(runtime_role)}'))
        with pytest.raises(RuntimeError, match='column-level ACLs'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'REVOKE SELECT (key) ON public.metadata FROM {quote(runtime_role)}'))

            # System file access functions are not SECURITY DEFINER, so the
            # validator must reject their explicit EXECUTE ACL independently.
            await conn.execute(
                text(f'GRANT EXECUTE ON FUNCTION pg_catalog.pg_read_file(text) TO {quote(runtime_role)}')
            )
        runtime_application = _application(postgres_url, runtime_role=runtime_role)
        runtime_manager = PersistenceManager(runtime_application, mode=PersistenceMode.CLOUD_RUNTIME)
        runtime_application.persistence_mgr = runtime_manager
        try:
            with pytest.raises(RuntimeError, match='explicit EXECUTE privileges on routines'):
                await runtime_manager.initialize()
        finally:
            await runtime_manager.get_db_engine().dispose()
        async with postgres_engine.connect() as conn:
            await conn.execute(
                text(f'REVOKE EXECUTE ON FUNCTION pg_catalog.pg_read_file(text) FROM {quote(runtime_role)}')
            )
        await manager._validate_configured_runtime_postgres_role()

        async with postgres_engine.connect() as conn:
            # replica disables ordinary triggers/rules and foreign-key
            # enforcement; it must never reach the runtime identity.
            await conn.execute(text(f'GRANT SET ON PARAMETER session_replication_role TO {quote(runtime_role)}'))
        with pytest.raises(RuntimeError, match='explicit SET or ALTER SYSTEM parameter privileges'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'REVOKE SET ON PARAMETER session_replication_role FROM {quote(runtime_role)}'))
        await manager._validate_configured_runtime_postgres_role()

        async with postgres_engine.connect() as conn:
            await conn.execute(
                text(f"CREATE FUNCTION public.{quote(owned_routine)}() RETURNS integer LANGUAGE sql AS 'SELECT 1'")
            )
            await conn.execute(text(f'ALTER FUNCTION public.{quote(owned_routine)}() OWNER TO {quote(runtime_role)}'))
        with pytest.raises(RuntimeError, match='must not own routines'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'DROP FUNCTION public.{quote(owned_routine)}()'))

        async with postgres_engine.connect() as conn:
            await conn.execute(
                text(
                    f'CREATE FUNCTION public.{quote(security_definer)}() RETURNS integer '
                    "LANGUAGE sql SECURITY DEFINER AS 'SELECT 1'"
                )
            )
            # Extension membership must not exempt an executable definer from
            # the runtime audit, even for an allowlisted extension.
            await conn.execute(text(f'ALTER EXTENSION vector ADD FUNCTION public.{quote(security_definer)}()'))
        with pytest.raises(RuntimeError, match='SECURITY DEFINER'):
            await manager._validate_configured_runtime_postgres_role()
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'ALTER EXTENSION vector DROP FUNCTION public.{quote(security_definer)}()'))
    finally:
        async with postgres_engine.connect() as conn:
            await conn.execute(text(f'ALTER DATABASE {quote(database_name)} RESET search_path'))
            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} RESET search_path'))
            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} RESET session_replication_role'))
            await conn.execute(text(f'ALTER ROLE {quote(runtime_role)} RESET application_name'))
            await conn.execute(text(f'REVOKE pg_read_all_data FROM {quote(runtime_role)}'))
            await conn.execute(text(f'REVOKE {quote(runtime_role)} FROM {quote(delegated_role)}'))
            await conn.execute(text(f'REVOKE CREATE ON SCHEMA public FROM {quote(runtime_role)}'))
            await conn.execute(text(f'REVOKE CREATE ON DATABASE {quote(database_name)} FROM {quote(runtime_role)}'))
            await conn.execute(
                text(f'REVOKE EXECUTE ON FUNCTION pg_catalog.pg_read_file(text) FROM {quote(runtime_role)}')
            )
            await conn.execute(text(f'REVOKE SET ON PARAMETER session_replication_role FROM {quote(runtime_role)}'))
            await conn.execute(text('DROP EXTENSION IF EXISTS dblink CASCADE'))
            await conn.execute(text('DROP EXTENSION IF EXISTS hstore CASCADE'))
            await conn.execute(text(f'DROP FOREIGN DATA WRAPPER IF EXISTS {quote(foreign_wrapper)} CASCADE'))
            await conn.execute(text(f'DROP FUNCTION IF EXISTS public.{quote(owned_routine)}()'))
            security_definer_is_extension_member = await conn.scalar(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_depend dependency
                        JOIN pg_extension extension ON extension.oid = dependency.refobjid
                        WHERE dependency.classid = 'pg_proc'::regclass
                          AND dependency.objid = to_regprocedure(:routine)
                          AND dependency.refclassid = 'pg_extension'::regclass
                          AND dependency.deptype = 'e'
                          AND extension.extname = 'vector'
                    )
                    """
                ),
                {'routine': f'public.{security_definer}()'},
            )
            if security_definer_is_extension_member:
                await conn.execute(text(f'ALTER EXTENSION vector DROP FUNCTION public.{quote(security_definer)}()'))
            await conn.execute(text(f'DROP FUNCTION IF EXISTS public.{quote(security_definer)}()'))
            await conn.execute(text(f'DROP VIEW IF EXISTS public.{quote(extra_view)}'))
            await conn.execute(text(f'DROP SCHEMA IF EXISTS {quote(extra_schema)} CASCADE'))
            await conn.execute(text(f'DROP OWNED BY {quote(runtime_role)}'))
            await conn.execute(text(f'DROP ROLE IF EXISTS {quote(delegated_role)}'))
            await conn.execute(text(f'DROP ROLE IF EXISTS {quote(runtime_role)}'))


async def test_direct_postgres_head_stamp_fails_without_business_schema(
    postgres_engine: AsyncEngine,
    clean_database,
) -> None:
    await run_alembic_stamp(postgres_engine, '0012_plugin_identity')

    with pytest.raises(RuntimeError, match='requires the knowledge_bases table'):
        await run_alembic_upgrade(postgres_engine)

    assert await get_alembic_current(postgres_engine) == '0012_plugin_identity'


async def test_release_entrypoint_fails_immediately_when_another_job_holds_lock(
    postgres_url: str,
    postgres_engine: AsyncEngine,
    clean_database,
    monkeypatch,
) -> None:
    _restore_postgres_registry(monkeypatch)
    ap = _application(postgres_url)

    async with postgres_engine.connect() as lock_connection:
        assert (
            await lock_connection.scalar(
                text('SELECT pg_try_advisory_lock(:lock_id)'),
                {'lock_id': _RELEASE_MIGRATION_ADVISORY_LOCK_ID},
            )
            is True
        )
        try:
            with pytest.raises(RuntimeError, match='already holds the advisory lock'):
                await release_migration.run_cloud_release_migration(
                    ap,
                    environ={'TEST_RELEASE_OPERATOR_DSN': postgres_url},
                )
        finally:
            assert (
                await lock_connection.scalar(
                    text('SELECT pg_advisory_unlock(:lock_id)'),
                    {'lock_id': _RELEASE_MIGRATION_ADVISORY_LOCK_ID},
                )
                is True
            )

    async with postgres_engine.connect() as conn:
        assert await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_table_names()) == []
