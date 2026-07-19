from __future__ import annotations

import datetime

import sqlalchemy as sa


TENANT_TABLES = (
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


def _uuid_table(metadata: sa.MetaData, name: str, *columns: sa.Column) -> sa.Table:
    return sa.Table(name, metadata, sa.Column('uuid', sa.String(255), primary_key=True), *columns)


async def create_legacy_resource_schema(engine, *, instance_uuid: str) -> None:
    """Create the smallest representative pre-0010 schema with one row/table."""
    metadata = sa.MetaData()
    system_metadata = sa.Table(
        'metadata',
        metadata,
        sa.Column('key', sa.String(255), primary_key=True),
        sa.Column('value', sa.String(255)),
    )
    users = sa.Table(
        'users',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user', sa.String(255), nullable=False),
        sa.Column('password', sa.String(255), nullable=False),
    )
    api_keys = sa.Table(
        'api_keys',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key', sa.String(255), nullable=False, unique=True),
    )
    bots = _uuid_table(
        metadata,
        'bots',
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    bot_admins = sa.Table(
        'bot_admins',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('bot_uuid', sa.String(255), nullable=False),
        sa.Column('launcher_type', sa.String(64), nullable=False),
        sa.Column('launcher_id', sa.String(255), nullable=False),
        sa.UniqueConstraint('bot_uuid', 'launcher_type', 'launcher_id', name='uq_bot_admin'),
    )
    binary_storages = sa.Table(
        'binary_storages',
        metadata,
        sa.Column('unique_key', sa.String(255), primary_key=True),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('owner_type', sa.String(255), nullable=False),
        sa.Column('owner', sa.String(255), nullable=False),
    )
    mcp_servers = _uuid_table(
        metadata,
        'mcp_servers',
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('enable', sa.Boolean, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    model_providers = _uuid_table(
        metadata,
        'model_providers',
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('requester', sa.String(255), nullable=False),
    )
    llm_models = _uuid_table(
        metadata,
        'llm_models',
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('provider_uuid', sa.String(255), nullable=False),
    )
    embedding_models = _uuid_table(
        metadata,
        'embedding_models',
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('provider_uuid', sa.String(255), nullable=False),
    )
    rerank_models = _uuid_table(
        metadata,
        'rerank_models',
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('provider_uuid', sa.String(255), nullable=False),
    )
    legacy_pipelines = _uuid_table(
        metadata,
        'legacy_pipelines',
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_default', sa.Boolean, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    pipeline_run_records = _uuid_table(
        metadata,
        'pipeline_run_records',
        sa.Column('pipeline_uuid', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    plugin_settings = sa.Table(
        'plugin_settings',
        metadata,
        sa.Column('plugin_author', sa.String(255), primary_key=True),
        sa.Column('plugin_name', sa.String(255), primary_key=True),
        sa.Column('enabled', sa.Boolean, nullable=False),
    )
    knowledge_bases = _uuid_table(
        metadata,
        'knowledge_bases',
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('collection_id', sa.String(255), nullable=True),
    )
    knowledge_base_files = _uuid_table(
        metadata,
        'knowledge_base_files',
        sa.Column('kb_id', sa.String(255), nullable=True),
    )
    knowledge_base_chunks = _uuid_table(
        metadata,
        'knowledge_base_chunks',
        sa.Column('file_id', sa.String(255), nullable=True),
    )
    webhooks = sa.Table(
        'webhooks',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('enabled', sa.Boolean, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )

    monitoring_tables: dict[str, sa.Table] = {}
    for table_name in (
        'monitoring_messages',
        'monitoring_llm_calls',
        'monitoring_tool_calls',
        'monitoring_errors',
        'monitoring_embedding_calls',
    ):
        monitoring_tables[table_name] = sa.Table(
            table_name,
            metadata,
            sa.Column('id', sa.String(255), primary_key=True),
            sa.Column('timestamp', sa.DateTime, nullable=False),
            sa.Column('session_id', sa.String(255), nullable=True),
            sa.Column('message_id', sa.String(255), nullable=True),
        )
    monitoring_tables['monitoring_sessions'] = sa.Table(
        'monitoring_sessions',
        metadata,
        sa.Column('session_id', sa.String(255), primary_key=True),
        sa.Column('bot_id', sa.String(255), nullable=False),
        sa.Column('last_activity', sa.DateTime, nullable=False),
        sa.Column('is_active', sa.Boolean, nullable=False),
    )
    monitoring_tables['monitoring_feedback'] = sa.Table(
        'monitoring_feedback',
        metadata,
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('feedback_id', sa.String(255), nullable=False, unique=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('session_id', sa.String(255), nullable=True),
        sa.Column('message_id', sa.String(255), nullable=True),
    )

    now = datetime.datetime(2026, 1, 1)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(
            system_metadata.insert(),
            [
                {'key': 'database_version', 'value': '25'},
                {'key': 'instance_uuid', 'value': instance_uuid},
                {'key': 'wizard_status', 'value': 'completed'},
                {'key': 'wizard_progress', 'value': '3'},
                {'key': 'rag_plugin_migration_needed', 'value': 'true'},
            ],
        )
        await conn.execute(users.insert().values(user='Owner@Example.COM', password='hash'))
        await conn.execute(api_keys.insert().values(name='legacy', key='lbk_legacy-secret'))
        await conn.execute(bots.insert().values(uuid='bot-1', name='bot', updated_at=now))
        await conn.execute(bot_admins.insert().values(bot_uuid='bot-1', launcher_type='person', launcher_id='owner'))
        await conn.execute(
            binary_storages.insert().values(unique_key='plugin:demo:key', key='key', owner_type='plugin', owner='demo')
        )
        await conn.execute(mcp_servers.insert().values(uuid='mcp-1', name='shared-name', enable=True, updated_at=now))
        await conn.execute(model_providers.insert().values(uuid='provider-1', name='provider', requester='openai'))
        for table in (llm_models, embedding_models, rerank_models):
            await conn.execute(table.insert().values(uuid=f'{table.name}-1', name='model', provider_uuid='provider-1'))
        await conn.execute(
            legacy_pipelines.insert().values(uuid='pipeline-1', name='pipeline', is_default=True, updated_at=now)
        )
        await conn.execute(
            pipeline_run_records.insert().values(uuid='run-1', pipeline_uuid='pipeline-1', created_at=now)
        )
        await conn.execute(plugin_settings.insert().values(plugin_author='author', plugin_name='plugin', enabled=True))
        await conn.execute(knowledge_bases.insert().values(uuid='kb-1', name='knowledge', collection_id='collection-1'))
        await conn.execute(knowledge_base_files.insert().values(uuid='file-1', kb_id='kb-1'))
        await conn.execute(knowledge_base_chunks.insert().values(uuid='chunk-1', file_id='file-1'))
        await conn.execute(webhooks.insert().values(name='hook', enabled=True, created_at=now))
        for table_name, table in monitoring_tables.items():
            if table_name == 'monitoring_sessions':
                values = {
                    'session_id': 'session-1',
                    'bot_id': 'bot-1',
                    'last_activity': now,
                    'is_active': True,
                }
            elif table_name == 'monitoring_feedback':
                values = {
                    'id': 'feedback-row-1',
                    'feedback_id': 'feedback-1',
                    'timestamp': now,
                    'session_id': 'session-1',
                    'message_id': 'message-1',
                }
            else:
                values = {
                    'id': f'{table_name}-1',
                    'timestamp': now,
                    'session_id': 'session-1',
                    'message_id': 'message-1',
                }
            await conn.execute(table.insert().values(**values))
