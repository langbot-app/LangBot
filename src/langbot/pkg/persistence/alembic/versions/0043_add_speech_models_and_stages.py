"""Add STT and TTS models and speech pipeline stages.

Revision ID: 0043_add_speech_models_and_stages
Revises: 0042_sqlite_incremental_vacuum
"""

import json
from alembic import op
import sqlalchemy as sa

revision = '0043_add_speech_models_and_stages'
down_revision = '0042_sqlite_incremental_vacuum'
branch_labels = None
depends_on = None

DEFAULT_SPEECH_CONFIG = {
    'speech-to-text': {
        'enabled': False,
        'model': '',
        'max-duration': 60,
        'keep-original-voice': False,
        'on-failure': 'ignore',
    },
    'text-to-speech': {
        'enabled': False,
        'model': '',
        'trigger': 'voice-input-only',
        'output': 'voice-only',
        'max-text-length': 1000,
        'voice': '',
        'speed': 1.0,
    },
}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'stt_models' not in existing_tables:
        op.create_table(
            'stt_models',
            sa.Column('uuid', sa.String(255), primary_key=True, unique=True),
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('provider_uuid', sa.String(255), nullable=False),
            sa.Column('extra_args', sa.JSON, nullable=False, server_default='{}'),
            sa.Column('prefered_ranking', sa.Integer, nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ['workspace_uuid', 'provider_uuid'],
                ['model_providers.workspace_uuid', 'model_providers.uuid'],
                name='fk_stt_models_workspace_provider',
            ),
        )
        op.create_index(
            'ix_stt_models_workspace_provider',
            'stt_models',
            ['workspace_uuid', 'provider_uuid'],
        )
        op.create_index(
            'ix_stt_models_workspace_name',
            'stt_models',
            ['workspace_uuid', 'name'],
        )

    if 'tts_models' not in existing_tables:
        op.create_table(
            'tts_models',
            sa.Column('uuid', sa.String(255), primary_key=True, unique=True),
            sa.Column(
                'workspace_uuid',
                sa.String(36),
                sa.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('provider_uuid', sa.String(255), nullable=False),
            sa.Column('extra_args', sa.JSON, nullable=False, server_default='{}'),
            sa.Column('prefered_ranking', sa.Integer, nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ['workspace_uuid', 'provider_uuid'],
                ['model_providers.workspace_uuid', 'model_providers.uuid'],
                name='fk_tts_models_workspace_provider',
            ),
        )
        op.create_index(
            'ix_tts_models_workspace_provider',
            'tts_models',
            ['workspace_uuid', 'provider_uuid'],
        )
        op.create_index(
            'ix_tts_models_workspace_name',
            'tts_models',
            ['workspace_uuid', 'name'],
        )

    if conn.dialect.name == 'postgresql':
        for tbl in ('stt_models', 'tts_models'):
            op.execute(f'ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY')
            op.execute(f'DROP POLICY IF EXISTS langbot_workspace_isolation ON {tbl}')
            op.execute(f"""CREATE POLICY langbot_workspace_isolation ON {tbl}
                USING (workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), ''))
                WITH CHECK (workspace_uuid::text = NULLIF(current_setting('langbot.workspace_uuid', true), ''))""")

    # Migrate legacy_pipelines stages and config
    if 'legacy_pipelines' in existing_tables:
        metadata = sa.MetaData()
        pipelines_tbl = sa.Table('legacy_pipelines', metadata, autoload_with=conn)
        rows = conn.execute(sa.select(pipelines_tbl.c.uuid, pipelines_tbl.c.stages, pipelines_tbl.c.config)).fetchall()

        for row in rows:
            p_uuid, stages_raw, config_raw = row[0], row[1], row[2]
            stages = stages_raw if isinstance(stages_raw, list) else json.loads(stages_raw or '[]')
            config = config_raw if isinstance(config_raw, dict) else json.loads(config_raw or '{}')

            stages_changed = False
            config_changed = False

            if 'SpeechToTextStage' not in stages:
                # Place after BanSessionCheckStage or GroupRespondRuleCheckStage, and before PreContentFilterStage
                if 'BanSessionCheckStage' in stages:
                    idx = stages.index('BanSessionCheckStage') + 1
                    stages.insert(idx, 'SpeechToTextStage')
                elif 'GroupRespondRuleCheckStage' in stages:
                    idx = stages.index('GroupRespondRuleCheckStage') + 1
                    stages.insert(idx, 'SpeechToTextStage')
                elif 'PreContentFilterStage' in stages:
                    idx = stages.index('PreContentFilterStage')
                    stages.insert(idx, 'SpeechToTextStage')
                else:
                    stages.append('SpeechToTextStage')
                stages_changed = True

            if 'TextToSpeechStage' not in stages:
                # Place after ResponseWrapper, before LongTextProcessStage
                if 'ResponseWrapper' in stages:
                    idx = stages.index('ResponseWrapper') + 1
                    stages.insert(idx, 'TextToSpeechStage')
                elif 'LongTextProcessStage' in stages:
                    idx = stages.index('LongTextProcessStage')
                    stages.insert(idx, 'TextToSpeechStage')
                else:
                    stages.append('TextToSpeechStage')
                stages_changed = True

            if 'speech' not in config:
                config['speech'] = DEFAULT_SPEECH_CONFIG.copy()
                config_changed = True

            if stages_changed or config_changed:
                conn.execute(
                    sa.update(pipelines_tbl)
                    .where(pipelines_tbl.c.uuid == p_uuid)
                    .values(stages=stages, config=config)
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())
    if 'tts_models' in existing_tables:
        op.drop_table('tts_models')
    if 'stt_models' in existing_tables:
        op.drop_table('stt_models')
