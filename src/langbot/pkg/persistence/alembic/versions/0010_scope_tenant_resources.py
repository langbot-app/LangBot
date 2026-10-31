"""scope every tenant-owned resource to a workspace

Revision ID: 0010_scope_resources
Revises: 0009_workspace_tenancy
Create Date: 2026-07-19

This migration is intentionally expand/backfill/contract.  Existing rows are
bound to the single local Workspace created by revision 0009 before any
non-null or scoped-key constraint is installed.
"""

from __future__ import annotations

import hashlib
import uuid

import sqlalchemy as sa
from alembic import op

revision = '0010_scope_resources'
down_revision = '0009_workspace_tenancy'
branch_labels = None
depends_on = None


_TENANT_TABLES = (
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
)

_COMPOSITE_PRIMARY_KEYS = {
    'binary_storages': ('workspace_uuid', 'unique_key'),
    'plugin_settings': ('workspace_uuid', 'plugin_author', 'plugin_name'),
    'monitoring_sessions': ('workspace_uuid', 'session_id'),
}

_COMPOSITE_FOREIGN_KEYS = {
    'bot_admins': (
        (
            'fk_bot_admins_workspace_bot',
            ('workspace_uuid', 'bot_uuid'),
            'bots',
            ('workspace_uuid', 'uuid'),
            'CASCADE',
        ),
    ),
    'llm_models': (
        (
            'fk_llm_models_workspace_provider',
            ('workspace_uuid', 'provider_uuid'),
            'model_providers',
            ('workspace_uuid', 'uuid'),
            None,
        ),
    ),
    'embedding_models': (
        (
            'fk_embedding_models_workspace_provider',
            ('workspace_uuid', 'provider_uuid'),
            'model_providers',
            ('workspace_uuid', 'uuid'),
            None,
        ),
    ),
    'rerank_models': (
        (
            'fk_rerank_models_workspace_provider',
            ('workspace_uuid', 'provider_uuid'),
            'model_providers',
            ('workspace_uuid', 'uuid'),
            None,
        ),
    ),
    'pipeline_run_records': (
        (
            'fk_pipeline_run_records_workspace_pipeline',
            ('workspace_uuid', 'pipeline_uuid'),
            'legacy_pipelines',
            ('workspace_uuid', 'uuid'),
            'CASCADE',
        ),
    ),
    'knowledge_base_files': (
        (
            'fk_knowledge_base_files_workspace_kb',
            ('workspace_uuid', 'kb_id'),
            'knowledge_bases',
            ('workspace_uuid', 'uuid'),
            'CASCADE',
        ),
    ),
    'knowledge_base_chunks': (
        (
            'fk_knowledge_base_chunks_workspace_file',
            ('workspace_uuid', 'file_id'),
            'knowledge_base_files',
            ('workspace_uuid', 'uuid'),
            'CASCADE',
        ),
    ),
}

_SCOPED_INDEXES: dict[str, tuple[tuple[str, tuple[str, ...], bool, sa.TextClause | None], ...]] = {
    'api_keys': (
        ('uq_api_keys_uuid', ('uuid',), True, None),
        ('uq_api_keys_key_hash', ('key_hash',), True, None),
        ('ix_api_keys_workspace_name', ('workspace_uuid', 'name'), False, None),
        ('ix_api_keys_workspace_status', ('workspace_uuid', 'status'), False, None),
    ),
    'bots': (
        ('uq_bots_workspace_uuid', ('workspace_uuid', 'uuid'), True, None),
        ('ix_bots_workspace_name', ('workspace_uuid', 'name'), False, None),
        ('ix_bots_workspace_updated', ('workspace_uuid', 'updated_at'), False, None),
    ),
    'bot_admins': (
        (
            'uq_bot_admin',
            ('workspace_uuid', 'bot_uuid', 'launcher_type', 'launcher_id'),
            True,
            None,
        ),
        ('ix_bot_admins_workspace_bot', ('workspace_uuid', 'bot_uuid'), False, None),
    ),
    'binary_storages': (
        (
            'ix_binary_storages_workspace_owner',
            ('workspace_uuid', 'owner_type', 'owner'),
            False,
            None,
        ),
    ),
    'mcp_servers': (
        ('uq_mcp_servers_workspace_name', ('workspace_uuid', 'name'), True, None),
        ('ix_mcp_servers_workspace_enable', ('workspace_uuid', 'enable'), False, None),
        ('ix_mcp_servers_workspace_updated', ('workspace_uuid', 'updated_at'), False, None),
    ),
    'model_providers': (
        ('uq_model_providers_workspace_uuid', ('workspace_uuid', 'uuid'), True, None),
        ('ix_model_providers_workspace_name', ('workspace_uuid', 'name'), False, None),
        ('ix_model_providers_workspace_requester', ('workspace_uuid', 'requester'), False, None),
    ),
    'llm_models': (
        ('ix_llm_models_workspace_provider', ('workspace_uuid', 'provider_uuid'), False, None),
        ('ix_llm_models_workspace_name', ('workspace_uuid', 'name'), False, None),
    ),
    'embedding_models': (
        ('ix_embedding_models_workspace_provider', ('workspace_uuid', 'provider_uuid'), False, None),
        ('ix_embedding_models_workspace_name', ('workspace_uuid', 'name'), False, None),
    ),
    'rerank_models': (
        ('ix_rerank_models_workspace_provider', ('workspace_uuid', 'provider_uuid'), False, None),
        ('ix_rerank_models_workspace_name', ('workspace_uuid', 'name'), False, None),
    ),
    'legacy_pipelines': (
        ('uq_legacy_pipelines_workspace_uuid', ('workspace_uuid', 'uuid'), True, None),
        ('ix_legacy_pipelines_workspace_name', ('workspace_uuid', 'name'), False, None),
        ('ix_legacy_pipelines_workspace_default', ('workspace_uuid', 'is_default'), False, None),
        ('ix_legacy_pipelines_workspace_updated', ('workspace_uuid', 'updated_at'), False, None),
    ),
    'pipeline_run_records': (
        (
            'ix_pipeline_run_records_workspace_pipeline',
            ('workspace_uuid', 'pipeline_uuid'),
            False,
            None,
        ),
        (
            'ix_pipeline_run_records_workspace_created',
            ('workspace_uuid', 'created_at'),
            False,
            None,
        ),
    ),
    'plugin_settings': (('ix_plugin_settings_workspace_enabled', ('workspace_uuid', 'enabled'), False, None),),
    'knowledge_bases': (
        ('uq_knowledge_bases_workspace_uuid', ('workspace_uuid', 'uuid'), True, None),
        ('ix_knowledge_bases_workspace_name', ('workspace_uuid', 'name'), False, None),
        (
            'uq_knowledge_bases_workspace_collection',
            ('workspace_uuid', 'collection_id'),
            True,
            sa.text('collection_id IS NOT NULL'),
        ),
    ),
    'knowledge_base_files': (
        ('uq_knowledge_base_files_workspace_uuid', ('workspace_uuid', 'uuid'), True, None),
        ('ix_knowledge_base_files_workspace_kb', ('workspace_uuid', 'kb_id'), False, None),
    ),
    'knowledge_base_chunks': (('ix_knowledge_base_chunks_workspace_file', ('workspace_uuid', 'file_id'), False, None),),
    'webhooks': (
        ('ix_webhooks_workspace_name', ('workspace_uuid', 'name'), False, None),
        ('ix_webhooks_workspace_enabled', ('workspace_uuid', 'enabled'), False, None),
        ('ix_webhooks_workspace_created', ('workspace_uuid', 'created_at'), False, None),
    ),
    'monitoring_messages': (
        ('ix_monitoring_messages_workspace_timestamp', ('workspace_uuid', 'timestamp'), False, None),
        ('ix_monitoring_messages_workspace_bot', ('workspace_uuid', 'bot_id', 'timestamp'), False, None),
        (
            'ix_monitoring_messages_workspace_pipeline',
            ('workspace_uuid', 'pipeline_id', 'timestamp'),
            False,
            None,
        ),
        ('ix_monitoring_messages_workspace_session', ('workspace_uuid', 'session_id'), False, None),
    ),
    'monitoring_llm_calls': (
        ('ix_monitoring_llm_calls_workspace_timestamp', ('workspace_uuid', 'timestamp'), False, None),
        ('ix_monitoring_llm_calls_workspace_session', ('workspace_uuid', 'session_id'), False, None),
        ('ix_monitoring_llm_calls_workspace_message', ('workspace_uuid', 'message_id'), False, None),
    ),
    'monitoring_tool_calls': (
        ('ix_monitoring_tool_calls_workspace_timestamp', ('workspace_uuid', 'timestamp'), False, None),
        ('ix_monitoring_tool_calls_workspace_session', ('workspace_uuid', 'session_id'), False, None),
        ('ix_monitoring_tool_calls_workspace_message', ('workspace_uuid', 'message_id'), False, None),
    ),
    'monitoring_sessions': (
        ('ix_monitoring_sessions_workspace_activity', ('workspace_uuid', 'last_activity'), False, None),
        ('ix_monitoring_sessions_workspace_active', ('workspace_uuid', 'is_active'), False, None),
        ('ix_monitoring_sessions_workspace_bot', ('workspace_uuid', 'bot_id', 'last_activity'), False, None),
    ),
    'monitoring_errors': (
        ('ix_monitoring_errors_workspace_timestamp', ('workspace_uuid', 'timestamp'), False, None),
        ('ix_monitoring_errors_workspace_session', ('workspace_uuid', 'session_id'), False, None),
        ('ix_monitoring_errors_workspace_message', ('workspace_uuid', 'message_id'), False, None),
    ),
    'monitoring_embedding_calls': (
        (
            'ix_monitoring_embedding_calls_workspace_timestamp',
            ('workspace_uuid', 'timestamp'),
            False,
            None,
        ),
        (
            'ix_monitoring_embedding_calls_workspace_kb',
            ('workspace_uuid', 'knowledge_base_id'),
            False,
            None,
        ),
        (
            'ix_monitoring_embedding_calls_workspace_session',
            ('workspace_uuid', 'session_id'),
            False,
            None,
        ),
    ),
    'monitoring_feedback': (
        (
            'uq_monitoring_feedback_workspace_feedback_id',
            ('workspace_uuid', 'feedback_id'),
            True,
            None,
        ),
        ('ix_monitoring_feedback_workspace_timestamp', ('workspace_uuid', 'timestamp'), False, None),
        ('ix_monitoring_feedback_workspace_session', ('workspace_uuid', 'session_id'), False, None),
        ('ix_monitoring_feedback_workspace_message', ('workspace_uuid', 'message_id'), False, None),
    ),
}


def _inspector(conn: sa.Connection) -> sa.Inspector:
    return sa.inspect(conn)


def _table_names(conn: sa.Connection) -> set[str]:
    return set(_inspector(conn).get_table_names())


def _columns(conn: sa.Connection, table_name: str) -> dict[str, dict]:
    return {column['name']: column for column in _inspector(conn).get_columns(table_name)}


def _index_names(conn: sa.Connection, table_name: str) -> set[str]:
    return {index['name'] for index in _inspector(conn).get_indexes(table_name)}


def _unique_column_sets(conn: sa.Connection, table_name: str) -> set[tuple[str, ...]]:
    inspector = _inspector(conn)
    result = {
        tuple(constraint.get('column_names') or ()) for constraint in inspector.get_unique_constraints(table_name)
    }
    result.update(
        tuple(index.get('column_names') or ()) for index in inspector.get_indexes(table_name) if index.get('unique')
    )
    return result


def _foreign_key_exists(
    conn: sa.Connection,
    table_name: str,
    local_columns: tuple[str, ...],
    referred_table: str,
    referred_columns: tuple[str, ...],
) -> bool:
    return any(
        tuple(foreign_key.get('constrained_columns') or ()) == local_columns
        and foreign_key.get('referred_table') == referred_table
        and tuple(foreign_key.get('referred_columns') or ()) == referred_columns
        for foreign_key in _inspector(conn).get_foreign_keys(table_name)
    )


def _metadata_value(conn: sa.Connection, key: str) -> str | None:
    if 'metadata' not in _table_names(conn):
        return None
    metadata = sa.table(
        'metadata',
        sa.column('key', sa.String(255)),
        sa.column('value', sa.String(255)),
    )
    value = conn.execute(sa.select(metadata.c.value).where(metadata.c.key == key)).scalar_one_or_none()
    return value.strip() if isinstance(value, str) and value.strip() else None


def _default_workspace_uuid(conn: sa.Connection) -> str | None:
    if 'workspaces' not in _table_names(conn):
        return None
    workspaces = sa.table(
        'workspaces',
        sa.column('uuid', sa.String(36)),
        sa.column('instance_uuid', sa.String(255)),
        sa.column('source', sa.String(32)),
    )
    instance_uuid = _metadata_value(conn, 'instance_uuid')
    query = sa.select(workspaces.c.uuid).where(workspaces.c.source == 'local')
    if instance_uuid is not None:
        query = query.where(workspaces.c.instance_uuid == instance_uuid)
    rows = conn.execute(query).all()
    if len(rows) > 1:
        raise RuntimeError('Cannot backfill tenant resources: multiple local Workspaces exist')
    return rows[0][0] if rows else None


def _upgrade_normalized_email(conn: sa.Connection) -> None:
    if 'users' not in _table_names(conn):
        return
    columns = _columns(conn, 'users')
    if 'normalized_email' not in columns:
        op.add_column('users', sa.Column('normalized_email', sa.String(320), nullable=True))

    users = sa.table(
        'users',
        sa.column('id', sa.Integer()),
        sa.column('user', sa.String(255)),
        sa.column('normalized_email', sa.String(320)),
    )
    # Use the exact same normalization algorithm as the runtime. Database
    # ``lower()`` is ASCII-only on SQLite and is not equivalent to Python
    # ``casefold()`` (for example, Straße -> strasse). Recompute every row so
    # an interrupted expand/backfill attempt using an older migration body can
    # be resumed safely.
    seen_emails: dict[str, int] = {}
    for user_id, email in conn.execute(sa.select(users.c.id, users.c.user).order_by(users.c.id)).all():
        normalized_email = str(email or '').strip().casefold()
        if not normalized_email:
            raise RuntimeError(f'Cannot normalize empty account identity for user row {user_id}')
        if len(normalized_email) > 320:
            raise RuntimeError(
                f'Cannot normalize account identity for user row {user_id}: canonical value exceeds 320 characters'
            )
        duplicate_user_id = seen_emails.get(normalized_email)
        if duplicate_user_id is not None:
            raise RuntimeError(
                f'Cannot create normalized account identity: user rows '
                f'{duplicate_user_id} and {user_id} both normalize to {normalized_email!r}'
            )
        seen_emails[normalized_email] = user_id
        conn.execute(users.update().where(users.c.id == user_id).values(normalized_email=normalized_email))

    columns = _columns(conn, 'users')
    checks = {
        constraint.get('name'): constraint
        for constraint in _inspector(conn).get_check_constraints('users')
        if constraint.get('name') is not None
    }
    identity_check = checks.get('ck_users_normalized_email')
    identity_check_sql = str((identity_check or {}).get('sqltext') or '').casefold()
    # Python casefold is the canonical identity algorithm. SQL ``lower`` is
    # dialect/locale dependent (notably Cherokee folds to uppercase in Python
    # but PostgreSQL lowercases it), so the database validates only portable
    # structural invariants and uniqueness.
    replace_legacy_identity_check = identity_check is not None and 'lower' in identity_check_sql
    needs_contract = columns['normalized_email']['nullable'] or identity_check is None or replace_legacy_identity_check
    if needs_contract:
        with op.batch_alter_table('users') as batch_op:
            if replace_legacy_identity_check:
                batch_op.drop_constraint('ck_users_normalized_email', type_='check')
            if columns['normalized_email']['nullable']:
                batch_op.alter_column(
                    'normalized_email',
                    existing_type=columns['normalized_email']['type'],
                    nullable=False,
                )
            if identity_check is None or replace_legacy_identity_check:
                batch_op.create_check_constraint(
                    'ck_users_normalized_email',
                    'normalized_email = trim(normalized_email) '
                    'AND length(normalized_email) > 0 '
                    'AND length(normalized_email) <= 320',
                )
    if 'uq_users_normalized_email' not in _index_names(conn, 'users'):
        op.create_index('uq_users_normalized_email', 'users', ['normalized_email'], unique=True)


def _api_key_owner(conn: sa.Connection, workspace_uuid: str | None) -> str | None:
    if workspace_uuid is None or 'workspace_memberships' not in _table_names(conn):
        return None
    memberships = sa.table(
        'workspace_memberships',
        sa.column('workspace_uuid', sa.String(36)),
        sa.column('account_uuid', sa.String(36)),
        sa.column('role', sa.String(32)),
    )
    return conn.execute(
        sa.select(memberships.c.account_uuid)
        .where(
            memberships.c.workspace_uuid == workspace_uuid,
            memberships.c.role == 'owner',
        )
        .limit(1)
    ).scalar_one_or_none()


def _expand_and_hash_api_keys(conn: sa.Connection, workspace_uuid: str | None) -> None:
    if 'api_keys' not in _table_names(conn):
        return
    columns = _columns(conn, 'api_keys')
    additions = (
        ('uuid', sa.Column('uuid', sa.String(36), nullable=True)),
        ('created_by_account_uuid', sa.Column('created_by_account_uuid', sa.String(36), nullable=True)),
        ('key_hash', sa.Column('key_hash', sa.String(64), nullable=True)),
        ('scopes', sa.Column('scopes', sa.JSON(), nullable=True)),
        ('status', sa.Column('status', sa.String(32), nullable=True, server_default='active')),
        ('expires_at', sa.Column('expires_at', sa.DateTime(), nullable=True)),
        ('last_used_at', sa.Column('last_used_at', sa.DateTime(), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column('api_keys', column)

    columns = _columns(conn, 'api_keys')
    api_key_columns = [sa.column('id', sa.Integer())]
    for name in ('uuid', 'created_by_account_uuid', 'key_hash', 'scopes', 'status', 'key'):
        if name in columns:
            api_key_columns.append(sa.column(name, columns[name]['type']))
    api_keys = sa.table('api_keys', *api_key_columns)
    owner_uuid = _api_key_owner(conn, workspace_uuid)
    selected_columns = [api_keys.c.id, api_keys.c.uuid, api_keys.c.key_hash]
    if 'key' in api_keys.c:
        selected_columns.append(api_keys.c.key)
    rows = conn.execute(sa.select(*selected_columns).order_by(api_keys.c.id)).mappings().all()
    for row in rows:
        values: dict[str, object] = {}
        if not row['uuid']:
            values['uuid'] = str(uuid.uuid4())
        if not row['key_hash']:
            plaintext = row.get('key')
            if not isinstance(plaintext, str) or not plaintext:
                raise RuntimeError(f'API key row {row["id"]} has no secret to hash')
            values['key_hash'] = hashlib.sha256(plaintext.encode()).hexdigest()
        if values:
            conn.execute(api_keys.update().where(api_keys.c.id == row['id']).values(**values))
    # Pre-tenancy API keys historically had unrestricted instance access.  A
    # wildcard preserves that behavior while binding it to the backfilled
    # Workspace; new keys must store their requested explicit scopes.
    conn.execute(api_keys.update().where(api_keys.c.scopes.is_(None)).values(scopes=['*']))
    conn.execute(api_keys.update().where(api_keys.c.status.is_(None)).values(status='active'))
    if owner_uuid is not None:
        conn.execute(
            api_keys.update()
            .where(api_keys.c.created_by_account_uuid.is_(None))
            .values(created_by_account_uuid=owner_uuid)
        )

    columns = _columns(conn, 'api_keys')
    check_names = {constraint.get('name') for constraint in _inspector(conn).get_check_constraints('api_keys')}
    existing_fks = _inspector(conn).get_foreign_keys('api_keys')
    creator_fk_exists = any(
        tuple(foreign_key.get('constrained_columns') or ()) == ('created_by_account_uuid',)
        and foreign_key.get('referred_table') == 'users'
        and tuple(foreign_key.get('referred_columns') or ()) == ('uuid',)
        for foreign_key in existing_fks
    )
    has_legacy_key = 'key' in columns
    needs_contract = (
        any(columns[name]['nullable'] for name in ('uuid', 'key_hash', 'scopes', 'status'))
        or 'ck_api_keys_status' not in check_names
        or not creator_fk_exists
        or has_legacy_key
    )
    if needs_contract:
        naming = {'uq': 'uq_%(table_name)s_%(column_0_name)s'}
        with op.batch_alter_table('api_keys', naming_convention=naming) as batch_op:
            for name in ('uuid', 'key_hash', 'scopes', 'status'):
                if columns[name]['nullable']:
                    batch_op.alter_column(name, existing_type=columns[name]['type'], nullable=False)
            if 'ck_api_keys_status' not in check_names:
                batch_op.create_check_constraint('ck_api_keys_status', "status IN ('active', 'revoked')")
            if not creator_fk_exists:
                batch_op.create_foreign_key(
                    'fk_api_keys_created_by_account',
                    'users',
                    ['created_by_account_uuid'],
                    ['uuid'],
                    ondelete='SET NULL',
                )
            if has_legacy_key:
                # Dropping the column also removes its old global plaintext
                # unique constraint/index during SQLite's batch rebuild.
                batch_op.drop_column('key')


def _expand_workspace_columns(conn: sa.Connection, workspace_uuid: str | None) -> None:
    tables = _table_names(conn)
    for table_name in _TENANT_TABLES:
        if table_name not in tables:
            continue
        columns = _columns(conn, table_name)
        if 'workspace_uuid' not in columns:
            op.add_column(table_name, sa.Column('workspace_uuid', sa.String(36), nullable=True))
        tenant_table = sa.table(table_name, sa.column('workspace_uuid', sa.String(36)))
        null_count = conn.scalar(
            sa.select(sa.func.count()).select_from(tenant_table).where(tenant_table.c.workspace_uuid.is_(None))
        )
        if null_count:
            if workspace_uuid is None:
                raise RuntimeError(f'Cannot backfill {table_name}: the instance has no unique local Workspace')
            conn.execute(
                tenant_table.update()
                .where(tenant_table.c.workspace_uuid.is_(None))
                .values(workspace_uuid=workspace_uuid)
            )


def _mark_legacy_vector_collections(conn: sa.Connection, workspace_uuid: str | None) -> None:
    """Persist which pre-tenancy KBs must keep using ``collection_id``.

    The marker is backfilled only when this migration introduces the column,
    or resumes while that newly added column is still nullable.  A fresh
    schema already contains the non-null column with ``false`` as its default,
    so knowledge bases created under the scoped-vector contract can never be
    mistaken for legacy data during a later migration retry.
    """

    if 'knowledge_bases' not in _table_names(conn):
        return
    columns = _columns(conn, 'knowledge_bases')
    introduced = 'legacy_vector_collection' not in columns
    if introduced:
        op.add_column(
            'knowledge_bases',
            sa.Column('legacy_vector_collection', sa.Boolean(), nullable=True),
        )
        columns = _columns(conn, 'knowledge_bases')
    needs_legacy_backfill = introduced or columns['legacy_vector_collection']['nullable']

    knowledge_bases = sa.table(
        'knowledge_bases',
        sa.column('collection_id', columns['collection_id']['type']),
        sa.column('legacy_vector_collection', sa.Boolean()),
        *((sa.column('workspace_uuid', columns['workspace_uuid']['type']),) if 'workspace_uuid' in columns else ()),
    )
    if needs_legacy_backfill and workspace_uuid is not None:
        legacy_filter = sa.and_(
            knowledge_bases.c.collection_id.is_not(None),
            sa.func.length(sa.func.trim(knowledge_bases.c.collection_id)) > 0,
        )
        if 'workspace_uuid' in knowledge_bases.c:
            # A partially migrated database may already have Workspace
            # columns.  Never mark a projected cloud row as legacy.
            legacy_filter = sa.and_(
                legacy_filter,
                sa.or_(
                    knowledge_bases.c.workspace_uuid.is_(None),
                    knowledge_bases.c.workspace_uuid == workspace_uuid,
                ),
            )
        conn.execute(knowledge_bases.update().where(legacy_filter).values(legacy_vector_collection=True))

    conn.execute(
        knowledge_bases.update()
        .where(knowledge_bases.c.legacy_vector_collection.is_(None))
        .values(legacy_vector_collection=False)
    )
    columns = _columns(conn, 'knowledge_bases')
    if columns['legacy_vector_collection']['nullable']:
        with op.batch_alter_table('knowledge_bases') as batch_op:
            batch_op.alter_column(
                'legacy_vector_collection',
                existing_type=columns['legacy_vector_collection']['type'],
                nullable=False,
                server_default=sa.false(),
            )


def _drop_legacy_uniqueness(conn: sa.Connection) -> None:
    if 'bot_admins' in _table_names(conn):
        for constraint in _inspector(conn).get_unique_constraints('bot_admins'):
            if tuple(constraint.get('column_names') or ()) == ('bot_uuid', 'launcher_type', 'launcher_id'):
                with op.batch_alter_table('bot_admins') as batch_op:
                    batch_op.drop_constraint(constraint['name'], type_='unique')
                break

    if 'monitoring_feedback' in _table_names(conn):
        dropped_constraint = False
        for constraint in _inspector(conn).get_unique_constraints('monitoring_feedback'):
            if tuple(constraint.get('column_names') or ()) == ('feedback_id',):
                convention = {'uq': 'uq_%(table_name)s_%(column_0_name)s'}
                constraint_name = constraint.get('name') or 'uq_monitoring_feedback_feedback_id'
                with op.batch_alter_table(
                    'monitoring_feedback',
                    naming_convention=convention,
                ) as batch_op:
                    batch_op.drop_constraint(constraint_name, type_='unique')
                dropped_constraint = True
                break
        if not dropped_constraint:
            for index in _inspector(conn).get_indexes('monitoring_feedback'):
                if index.get('unique') and tuple(index.get('column_names') or ()) == ('feedback_id',):
                    op.drop_index(index['name'], table_name='monitoring_feedback')


def _create_index_if_missing(
    conn: sa.Connection,
    table_name: str,
    name: str,
    columns: tuple[str, ...],
    unique: bool,
    predicate: sa.TextClause | None,
) -> None:
    if name in _index_names(conn, table_name):
        return
    if unique and predicate is None and columns in _unique_column_sets(conn, table_name):
        return
    kwargs = {}
    if predicate is not None:
        kwargs = {'sqlite_where': predicate, 'postgresql_where': predicate}
    op.create_index(name, table_name, list(columns), unique=unique, **kwargs)


def _validate_scoped_unique_data(conn: sa.Connection) -> None:
    checks = (
        ('mcp_servers', ('workspace_uuid', 'name')),
        ('knowledge_bases', ('workspace_uuid', 'collection_id')),
    )
    for table_name, column_names in checks:
        if table_name not in _table_names(conn):
            continue
        columns = _columns(conn, table_name)
        if not all(column_name in columns for column_name in column_names):
            continue
        table = sa.table(
            table_name,
            *(sa.column(column_name, columns[column_name]['type']) for column_name in column_names),
        )
        group_columns = [table.c[column_name] for column_name in column_names]
        query = sa.select(*group_columns, sa.func.count()).group_by(*group_columns).having(sa.func.count() > 1)
        if column_names[-1] == 'collection_id':
            query = query.where(group_columns[-1].is_not(None))
        duplicate = conn.execute(query.limit(1)).first()
        if duplicate is not None:
            raise RuntimeError(
                f'Cannot create scoped unique key on {table_name}{column_names}: duplicate {duplicate!r}'
            )


def _create_parent_and_scoped_indexes(conn: sa.Connection) -> None:
    _validate_scoped_unique_data(conn)
    tables = _table_names(conn)
    for table_name, indexes in _SCOPED_INDEXES.items():
        if table_name not in tables:
            continue
        available_columns = _columns(conn, table_name)
        for name, columns, unique, predicate in indexes:
            if all(column in available_columns for column in columns):
                _create_index_if_missing(conn, table_name, name, columns, unique, predicate)


def _contract_table(conn: sa.Connection, table_name: str) -> None:
    columns = _columns(conn, table_name)
    if 'workspace_uuid' not in columns:
        return
    direct_workspace_fk = _foreign_key_exists(
        conn,
        table_name,
        ('workspace_uuid',),
        'workspaces',
        ('uuid',),
    )
    current_pk = tuple(_inspector(conn).get_pk_constraint(table_name).get('constrained_columns') or ())
    desired_pk = _COMPOSITE_PRIMARY_KEYS.get(table_name)
    missing_composite_fks = [
        foreign_key
        for foreign_key in _COMPOSITE_FOREIGN_KEYS.get(table_name, ())
        if not _foreign_key_exists(
            conn,
            table_name,
            foreign_key[1],
            foreign_key[2],
            foreign_key[3],
        )
    ]
    needs_contract = (
        columns['workspace_uuid']['nullable']
        or not direct_workspace_fk
        or (desired_pk is not None and current_pk != desired_pk)
        or bool(missing_composite_fks)
    )
    if not needs_contract:
        return

    naming = {
        'pk': 'pk_%(table_name)s',
        'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    }
    pk_name = _inspector(conn).get_pk_constraint(table_name).get('name') or f'pk_{table_name}'
    with op.batch_alter_table(table_name, naming_convention=naming) as batch_op:
        if columns['workspace_uuid']['nullable']:
            batch_op.alter_column(
                'workspace_uuid',
                existing_type=columns['workspace_uuid']['type'],
                nullable=False,
            )
        if desired_pk is not None and current_pk != desired_pk:
            batch_op.drop_constraint(pk_name, type_='primary')
            batch_op.create_primary_key(f'pk_{table_name}', list(desired_pk))
        if not direct_workspace_fk:
            batch_op.create_foreign_key(
                f'fk_{table_name}_workspace',
                'workspaces',
                ['workspace_uuid'],
                ['uuid'],
                ondelete='CASCADE',
            )
        for name, local_columns, referred_table, referred_columns, ondelete in missing_composite_fks:
            batch_op.create_foreign_key(
                name,
                referred_table,
                list(local_columns),
                list(referred_columns),
                ondelete=ondelete,
            )


def _contract_workspace_columns(conn: sa.Connection) -> None:
    tables = _table_names(conn)
    # Parents must be contracted before their children so SQLite can validate
    # the exact composite target key during a batch-table rebuild.
    order = (
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
    )
    for table_name in order:
        if table_name in tables:
            _contract_table(conn, table_name)


def _migrate_workspace_metadata(conn: sa.Connection, workspace_uuid: str | None) -> None:
    tables = _table_names(conn)
    if 'workspaces' not in tables:
        return
    if 'workspace_metadata' not in tables:
        op.create_table(
            'workspace_metadata',
            sa.Column('workspace_uuid', sa.String(36), nullable=False),
            sa.Column('key', sa.String(255), nullable=False),
            sa.Column('value', sa.String(255), nullable=True),
            sa.ForeignKeyConstraint(
                ['workspace_uuid'],
                ['workspaces.uuid'],
                name='fk_workspace_metadata_workspace',
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('workspace_uuid', 'key', name='pk_workspace_metadata'),
        )
    if workspace_uuid is None or 'metadata' not in tables:
        return
    metadata = sa.table(
        'metadata',
        sa.column('key', sa.String(255)),
        sa.column('value', sa.String(255)),
    )
    workspace_metadata = sa.table(
        'workspace_metadata',
        sa.column('workspace_uuid', sa.String(36)),
        sa.column('key', sa.String(255)),
        sa.column('value', sa.String(255)),
    )
    tenant_keys = ('wizard_status', 'wizard_progress', 'rag_plugin_migration_needed')
    rows = conn.execute(sa.select(metadata.c.key, metadata.c.value).where(metadata.c.key.in_(tenant_keys))).all()
    for key, value in rows:
        exists = conn.execute(
            sa.select(workspace_metadata.c.key).where(
                workspace_metadata.c.workspace_uuid == workspace_uuid,
                workspace_metadata.c.key == key,
            )
        ).first()
        if exists is None:
            conn.execute(
                workspace_metadata.insert().values(
                    workspace_uuid=workspace_uuid,
                    key=key,
                    value=value,
                )
            )
    if rows:
        conn.execute(metadata.delete().where(metadata.c.key.in_(tenant_keys)))


def _validate_contract(conn: sa.Connection) -> None:
    for table_name in _TENANT_TABLES:
        if table_name not in _table_names(conn):
            continue
        columns = _columns(conn, table_name)
        if 'workspace_uuid' not in columns or columns['workspace_uuid']['nullable']:
            raise RuntimeError(f'{table_name}.workspace_uuid was not contracted to NOT NULL')
        table = sa.table(table_name, sa.column('workspace_uuid', sa.String(36)))
        if conn.scalar(sa.select(sa.func.count()).select_from(table).where(table.c.workspace_uuid.is_(None))):
            raise RuntimeError(f'{table_name} still contains unscoped rows')
    if conn.dialect.name == 'sqlite':
        violations = conn.execute(sa.text('PRAGMA foreign_key_check')).all()
        if violations:
            raise RuntimeError(f'SQLite foreign key validation failed: {violations[:5]!r}')


def upgrade() -> None:
    conn = op.get_bind()
    _upgrade_normalized_email(conn)
    workspace_uuid = _default_workspace_uuid(conn)
    _mark_legacy_vector_collections(conn, workspace_uuid)
    _expand_workspace_columns(conn, workspace_uuid)
    _expand_and_hash_api_keys(conn, workspace_uuid)
    _drop_legacy_uniqueness(conn)
    _create_parent_and_scoped_indexes(conn)
    _contract_workspace_columns(conn)
    _migrate_workspace_metadata(conn, workspace_uuid)
    _validate_contract(conn)


def downgrade() -> None:
    raise RuntimeError(
        '0010_scope_resources is intentionally irreversible because plaintext API key secrets were securely removed'
    )
