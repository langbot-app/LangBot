from __future__ import annotations

import datetime
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sqlalchemy
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects import postgresql

from langbot.pkg.api.http.service.kuku import KukuService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.bot import Bot
from langbot.pkg.entity.persistence.kuku import KukuGroupSetting


class FakePersistenceManager:
    def __init__(self, engine: sqlalchemy.Engine) -> None:
        self.engine = engine
        self.db = SimpleNamespace(name='sqlite')

    async def execute_async(self, statement, params=None):
        with self.engine.connect() as conn:
            result = conn.execute(statement, params or {})
            conn.commit()
            return result

    def serialize_model(self, model, data, masked_columns=None):
        masked_columns = masked_columns or []

        if hasattr(data, '_mapping') and len(data) == 1:
            data = data[0]

        return {
            column.name: getattr(data, column.name)
            if not isinstance(getattr(data, column.name), datetime.datetime)
            else getattr(data, column.name).isoformat()
            for column in model.__table__.columns
            if column.name not in masked_columns
        }


@pytest.mark.asyncio
async def test_list_personas_returns_fixed_mvp_personas():
    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=SimpleNamespace(db=SimpleNamespace(name='sqlite')),
    )
    kuku_service = KukuService(app)

    personas = await kuku_service.list_personas()

    assert [persona['id'] for persona in personas] == ['kuku-sunny']
    assert personas[0]['name'] == 'KUKU'
    assert personas[0]['silence_trigger_style'] == 'question'


@pytest.mark.asyncio
async def test_get_group_settings_returns_existing_row():
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    _seed_bot(engine, adapter='discord')

    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.insert(KukuGroupSetting).values(
                uuid='group-settings-1',
                bot_uuid='bot-1',
                platform='discord',
                group_id='123',
                persona_id='kuku-sunny',
                silence_minutes=30,
                quiet_hours={'start': '00:00', 'end': '08:00', 'timezone': 'UTC'},
                cooldown_minutes=10,
                enabled=True,
            )
        )

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )
    kuku_service = KukuService(app)

    result = await kuku_service.get_group_settings('bot-1', 'discord', '123')

    assert result is not None
    assert result['uuid'] == 'group-settings-1'
    assert result['bot_uuid'] == 'bot-1'
    assert result['group_id'] == '123'
    assert result['persona_id'] == 'kuku-sunny'
    assert result['silence_minutes'] == 30
    assert result['quiet_hours'] == {'start': '00:00', 'end': '08:00', 'timezone': 'UTC'}
    assert result['enabled'] is True


@pytest.mark.asyncio
async def test_get_group_settings_returns_none_for_missing_group():
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    _seed_bot(engine, adapter='discord')

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )
    kuku_service = KukuService(app)

    result = await kuku_service.get_group_settings('bot-1', 'discord', 'missing')

    assert result is None


@pytest.mark.asyncio
async def test_upsert_group_settings_persists_persona_and_threshold():
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.insert(Bot).values(
                uuid='bot-1',
                name='Discord Bot',
                description='KUKU test bot',
                adapter='discord',
                adapter_config={},
                enable=True,
            )
        )

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )
    kuku_service = KukuService(app)

    payload = {
        'bot_uuid': 'bot-1',
        'platform': 'discord',
        'group_id': '123',
        'persona_id': 'kuku-sunny',
        'silence_minutes': 30,
        'quiet_hours': {'start': '00:00', 'end': '08:00', 'timezone': 'UTC'},
        'enabled': True,
    }

    saved = await kuku_service.upsert_group_settings(payload)

    assert saved['bot_uuid'] == 'bot-1'
    assert saved['group_id'] == '123'
    assert saved['persona_id'] == 'kuku-sunny'
    assert saved['silence_minutes'] == 30
    assert saved['enabled'] is True

    with engine.connect() as conn:
        persisted = conn.execute(
            sqlalchemy.select(KukuGroupSetting.__table__).where(
                KukuGroupSetting.uuid == saved['uuid'],
            )
        ).mappings().first()

    assert persisted is not None
    assert persisted['persona_id'] == 'kuku-sunny'
    assert persisted['silence_minutes'] == 30
    assert persisted['cooldown_minutes'] == 10
    assert persisted['enabled'] is True
    assert persisted['quiet_hours'] == {'start': '00:00', 'end': '08:00', 'timezone': 'UTC'}


@pytest.mark.asyncio
async def test_upsert_group_settings_updates_existing_row_and_parses_false_string():
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    _seed_bot(engine, adapter='discord')

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )
    kuku_service = KukuService(app)

    first_saved = await kuku_service.upsert_group_settings(
        {
            'bot_uuid': 'bot-1',
            'platform': 'discord',
            'group_id': '123',
            'persona_id': 'kuku-sunny',
            'silence_minutes': 30,
            'quiet_hours': {'start': '00:00', 'end': '08:00', 'timezone': 'UTC'},
            'enabled': True,
        }
    )

    second_saved = await kuku_service.upsert_group_settings(
        {
            'bot_uuid': 'bot-1',
            'platform': 'discord',
            'group_id': '123',
            'persona_id': 'kuku-rainy',
            'silence_minutes': 45,
            'quiet_hours': {'start': '01:00', 'end': '09:00', 'timezone': 'UTC'},
            'enabled': 'false',
        }
    )

    assert second_saved['uuid'] == first_saved['uuid']
    assert second_saved['persona_id'] == 'kuku-rainy'
    assert second_saved['silence_minutes'] == 45
    assert second_saved['enabled'] is False

    with engine.connect() as conn:
        persisted = conn.execute(
            sqlalchemy.select(KukuGroupSetting.__table__).where(
                KukuGroupSetting.uuid == first_saved['uuid'],
            )
        ).mappings().first()

    assert persisted is not None
    assert persisted['persona_id'] == 'kuku-rainy'
    assert persisted['silence_minutes'] == 45
    assert persisted['cooldown_minutes'] == 10
    assert persisted['enabled'] is False
    assert persisted['quiet_hours'] == {'start': '01:00', 'end': '09:00', 'timezone': 'UTC'}


@pytest.mark.asyncio
async def test_upsert_group_settings_persists_non_default_cooldown_minutes():
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    _seed_bot(engine, adapter='discord')

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )
    kuku_service = KukuService(app)

    saved = await kuku_service.upsert_group_settings(
        {
            'bot_uuid': 'bot-1',
            'platform': 'discord',
            'group_id': '123',
            'persona_id': 'kuku-sunny',
            'cooldown_minutes': 17,
        }
    )

    assert saved['cooldown_minutes'] == 17

    with engine.connect() as conn:
        persisted = conn.execute(
            sqlalchemy.select(KukuGroupSetting.__table__).where(
                KukuGroupSetting.uuid == saved['uuid'],
            )
        ).mappings().first()

    assert persisted is not None
    assert persisted['cooldown_minutes'] == 17


@pytest.mark.asyncio
async def test_upsert_group_settings_rejects_non_discord_platform():
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    _seed_bot(engine, adapter='discord')

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )
    kuku_service = KukuService(app)

    with pytest.raises(ValueError, match='KUKU MVP only supports discord'):
        await kuku_service.upsert_group_settings(
            {
                'bot_uuid': 'bot-1',
                'platform': 'slack',
                'group_id': '123',
                'persona_id': 'kuku-sunny',
            }
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'payload, expected_message',
    [
        ({'silence_minutes': -1}, 'silence_minutes must be an integer greater than or equal to 0'),
        ({'cooldown_minutes': -2}, 'cooldown_minutes must be an integer greater than or equal to 0'),
        ({'silence_minutes': True}, 'silence_minutes must be an integer greater than or equal to 0'),
        ({'cooldown_minutes': False}, 'cooldown_minutes must be an integer greater than or equal to 0'),
        ({'silence_minutes': 'abc'}, 'silence_minutes must be an integer greater than or equal to 0'),
        ({'quiet_hours': 'always-on'}, 'quiet_hours must be a JSON object'),
        ({'quiet_hours': {'start': '00:00', 'bad': 'x'}}, 'quiet_hours may only contain start, end, and timezone'),
        ({'quiet_hours': {'start': ''}}, 'quiet_hours.start must be a non-empty string'),
        ({'quiet_hours': {'timezone': '   '}}, 'quiet_hours.timezone must be a non-empty string'),
    ],
)
async def test_upsert_group_settings_rejects_invalid_operational_settings(payload, expected_message):
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    _seed_bot(engine, adapter='discord')

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )
    kuku_service = KukuService(app)

    base_payload = {
        'bot_uuid': 'bot-1',
        'platform': 'discord',
        'group_id': '123',
        'persona_id': 'kuku-sunny',
    }
    base_payload.update(payload)

    with pytest.raises(ValueError, match=expected_message):
        await kuku_service.upsert_group_settings(base_payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'enabled_value',
    ['maybe', '', '  ', [], {}, object(), 2, -1, 0.5, None],
)
async def test_upsert_group_settings_rejects_invalid_enabled_values(enabled_value):
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    _seed_bot(engine, adapter='discord')

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )
    kuku_service = KukuService(app)

    with pytest.raises(ValueError, match='enabled must be a boolean value'):
        await kuku_service.upsert_group_settings(
            {
                'bot_uuid': 'bot-1',
                'platform': 'discord',
                'group_id': '123',
                'persona_id': 'kuku-sunny',
                'enabled': enabled_value,
            }
        )


def test_postgresql_upsert_statement_uses_pg_dialect_conflict_path():
    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=SimpleNamespace(db=SimpleNamespace(name='postgresql')),
    )
    kuku_service = KukuService(app)

    statement = kuku_service._get_insert_statement(KukuGroupSetting.__table__)
    assert statement.__class__.__module__.startswith('sqlalchemy.dialects.postgresql')

    upsert = kuku_service._build_upsert_statement(
        KukuGroupSetting.__table__,
        'group-settings-1',
        {
            'bot_uuid': 'bot-1',
            'platform': 'discord',
            'group_id': '123',
            'persona_id': 'kuku-sunny',
            'silence_minutes': 30,
            'quiet_hours': {},
            'cooldown_minutes': 10,
            'enabled': True,
        },
    )
    compiled_sql = str(upsert.compile(dialect=postgresql.dialect()))

    assert 'ON CONFLICT (bot_uuid, platform, group_id) DO UPDATE' in compiled_sql
    assert 'updated_at' in compiled_sql


def test_migration_25_uses_explicit_backend_specific_column_sql():
    original_core_pkg = sys.modules.get('langbot.pkg.core')
    original_core_app = sys.modules.get('langbot.pkg.core.app')
    core_pkg = types.ModuleType('langbot.pkg.core')
    core_pkg.__path__ = []  # type: ignore[attr-defined]
    core_app = types.ModuleType('langbot.pkg.core.app')
    core_app.Application = object
    sys.modules['langbot.pkg.core'] = core_pkg
    sys.modules['langbot.pkg.core.app'] = core_app

    try:
        from langbot.pkg.persistence.migrations.dbm025_kuku_group_settings import DBMigrateKukuGroupSettings

        postgres_migration = DBMigrateKukuGroupSettings(
            SimpleNamespace(persistence_mgr=SimpleNamespace(db=SimpleNamespace(name='postgresql')))
        )
        sqlite_migration = DBMigrateKukuGroupSettings(
            SimpleNamespace(persistence_mgr=SimpleNamespace(db=SimpleNamespace(name='sqlite')))
        )
    finally:
        if original_core_pkg is None:
            sys.modules.pop('langbot.pkg.core', None)
        else:
            sys.modules['langbot.pkg.core'] = original_core_pkg

        if original_core_app is None:
            sys.modules.pop('langbot.pkg.core.app', None)
        else:
            sys.modules['langbot.pkg.core.app'] = original_core_app

    postgres_sql = postgres_migration._build_create_table_sql()
    sqlite_sql = sqlite_migration._build_create_table_sql()

    assert "quiet_hours JSONB NOT NULL DEFAULT '{}'::jsonb" in postgres_sql
    assert 'enabled BOOLEAN NOT NULL DEFAULT TRUE' in postgres_sql
    assert 'created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP' in postgres_sql

    assert "quiet_hours JSON NOT NULL DEFAULT '{}'" in sqlite_sql
    assert 'enabled BOOLEAN NOT NULL DEFAULT 1' in sqlite_sql
    assert 'created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP' in sqlite_sql


@pytest.mark.asyncio
async def test_migration_25_creates_indexes_for_kuku_group_settings():
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )

    original_core_pkg = sys.modules.get('langbot.pkg.core')
    original_core_app = sys.modules.get('langbot.pkg.core.app')
    core_pkg = types.ModuleType('langbot.pkg.core')
    core_pkg.__path__ = []  # type: ignore[attr-defined]
    core_app = types.ModuleType('langbot.pkg.core.app')
    core_app.Application = object
    sys.modules['langbot.pkg.core'] = core_pkg
    sys.modules['langbot.pkg.core.app'] = core_app

    try:
        from langbot.pkg.persistence.migrations.dbm025_kuku_group_settings import DBMigrateKukuGroupSettings

        await DBMigrateKukuGroupSettings(app).upgrade()
    finally:
        if original_core_pkg is None:
            sys.modules.pop('langbot.pkg.core', None)
        else:
            sys.modules['langbot.pkg.core'] = original_core_pkg

        if original_core_app is None:
            sys.modules.pop('langbot.pkg.core.app', None)
        else:
            sys.modules['langbot.pkg.core.app'] = original_core_app

    inspector = sqlalchemy.inspect(engine)
    assert 'kuku_group_settings' in inspector.get_table_names()

    index_names = {index['name'] for index in inspector.get_indexes('kuku_group_settings')}
    assert 'idx_kuku_group_settings_bot_uuid' in index_names
    assert 'idx_kuku_group_settings_group_id' in index_names

    unique_constraints = {constraint['name'] for constraint in inspector.get_unique_constraints('kuku_group_settings')}
    assert 'uq_kuku_group_settings_scope' in unique_constraints


@pytest.mark.asyncio
async def test_get_persona_resolves_mvp_catalog():
    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=SimpleNamespace(db=SimpleNamespace(name='sqlite')),
    )
    kuku_service = KukuService(app)

    persona = await kuku_service.get_persona('kuku-sunny')
    assert persona is not None
    assert persona['id'] == 'kuku-sunny'
    assert 'cheerful' in persona['system_prompt'].lower() or 'KUKU' in persona['system_prompt']

    assert await kuku_service.get_persona('unknown-persona') is None


@pytest.mark.asyncio
async def test_list_enabled_discord_group_settings_excludes_disabled_rows():
    engine = sqlalchemy.create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    _seed_bot(engine, adapter='discord')

    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.insert(KukuGroupSetting).values(
                uuid='ks-off',
                bot_uuid='bot-1',
                platform='discord',
                group_id='off',
                persona_id='kuku-sunny',
                silence_minutes=30,
                quiet_hours={},
                cooldown_minutes=10,
                enabled=False,
            )
        )
        conn.execute(
            sqlalchemy.insert(KukuGroupSetting).values(
                uuid='ks-on',
                bot_uuid='bot-1',
                platform='discord',
                group_id='on',
                persona_id='kuku-sunny',
                silence_minutes=30,
                quiet_hours={},
                cooldown_minutes=10,
                enabled=True,
            )
        )

    app = SimpleNamespace(
        logger=Mock(),
        persistence_mgr=FakePersistenceManager(engine),
    )
    kuku_service = KukuService(app)

    rows = await kuku_service.list_enabled_discord_group_settings()
    assert len(rows) == 1
    assert rows[0]['group_id'] == 'on'
    assert rows[0]['enabled'] is True


def _seed_bot(engine: sqlalchemy.Engine, adapter: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.insert(Bot).values(
                uuid='bot-1',
                name='Discord Bot',
                description='KUKU test bot',
                adapter=adapter,
                adapter_config={},
                enable=True,
            )
        )
