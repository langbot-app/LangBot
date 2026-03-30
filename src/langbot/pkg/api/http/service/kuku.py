from __future__ import annotations

import datetime
import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ....entity.persistence import bot as persistence_bot
from ....entity.persistence import kuku as persistence_kuku

if TYPE_CHECKING:
    from ....core import app


MVP_PERSONAS: list[dict] = [
    {
        'id': 'kuku-sunny',
        'name': 'KUKU',
        'tags': ['cheerful', 'energetic'],
        'tagline': 'A bright group member who restarts quiet chats naturally.',
        'system_prompt': 'You are KUKU, a cheerful and naturally curious group chat member.',
        'silence_trigger_style': 'question',
    }
]


class KukuService:
    """KUKU service for group settings persistence."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_persona(self, persona_id: str) -> dict | None:
        """Return a single MVP persona by id, or None if unknown."""
        for persona in MVP_PERSONAS:
            if persona['id'] == persona_id:
                return {
                    'id': persona['id'],
                    'name': persona['name'],
                    'tags': list(persona['tags']),
                    'tagline': persona['tagline'],
                    'system_prompt': persona['system_prompt'],
                    'silence_trigger_style': persona['silence_trigger_style'],
                }
        return None

    async def list_enabled_discord_group_settings(self) -> list[dict]:
        """All enabled KUKU rows for Discord (for the runtime loop)."""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_kuku.KukuGroupSetting.__table__).where(
                (persistence_kuku.KukuGroupSetting.platform == 'discord')
                & (persistence_kuku.KukuGroupSetting.enabled.is_(True))
            )
        )
        return [self._row_to_dict(row) for row in result.mappings().all()]

    async def list_personas(self) -> list[dict]:
        """Return the fixed MVP persona list."""
        # Return a copy so request-time consumers can shape or serialize the payload
        # without mutating the in-process MVP catalog.
        return [
            {
                'id': persona['id'],
                'name': persona['name'],
                'tags': list(persona['tags']),
                'tagline': persona['tagline'],
                'system_prompt': persona['system_prompt'],
                'silence_trigger_style': persona['silence_trigger_style'],
            }
            for persona in MVP_PERSONAS
        ]

    async def get_group_settings(self, bot_uuid: str, platform: str, group_id: str) -> dict | None:
        """Load an existing KUKU group setting."""
        await self._validate_kuku_scope(bot_uuid, platform, group_id)

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_kuku.KukuGroupSetting.__table__).where(
                (persistence_kuku.KukuGroupSetting.bot_uuid == bot_uuid)
                & (persistence_kuku.KukuGroupSetting.platform == platform)
                & (persistence_kuku.KukuGroupSetting.group_id == group_id)
            )
        )

        row = result.mappings().first()
        if row is None:
            return None

        return self._row_to_dict(row)

    async def upsert_group_settings(self, payload: dict) -> dict:
        """Insert or update KUKU group settings."""
        bot_uuid = payload.get('bot_uuid')
        platform = payload.get('platform')
        group_id = payload.get('group_id')

        if not bot_uuid:
            raise ValueError('bot_uuid is required')
        if not platform:
            raise ValueError('platform is required')
        if not group_id:
            raise ValueError('group_id is required')
        await self._validate_kuku_scope(bot_uuid, platform, group_id)

        settings_table = persistence_kuku.KukuGroupSetting.__table__
        settings_filter = (
            (settings_table.c.bot_uuid == bot_uuid)
            & (settings_table.c.platform == platform)
            & (settings_table.c.group_id == group_id)
        )

        setting_data = {
            'bot_uuid': bot_uuid,
            'platform': platform,
            'group_id': group_id,
            'persona_id': payload.get('persona_id') or 'kuku-sunny',
            'silence_minutes': self._as_non_negative_int(payload.get('silence_minutes'), 30, 'silence_minutes'),
            'silence_seconds': self._normalize_silence_seconds(payload.get('silence_seconds')),
            'quiet_hours': self._normalize_quiet_hours(payload.get('quiet_hours')),
            'cooldown_minutes': self._as_non_negative_int(payload.get('cooldown_minutes'), 10, 'cooldown_minutes'),
            'enabled': self._parse_bool(payload.get('enabled', True), 'enabled'),
        }

        setting_uuid = payload.get('uuid') or str(uuid.uuid4())
        insert_stmt = self._build_upsert_statement(settings_table, setting_uuid, setting_data)
        await self.ap.persistence_mgr.execute_async(insert_stmt)

        saved_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(settings_table).where(settings_filter)
        )
        saved = saved_result.mappings().first()
        if saved is None:
            raise RuntimeError('Failed to load saved KUKU group settings')

        saved_dict = self._row_to_dict(saved)
        runtime = getattr(self.ap, 'kuku_runtime', None)
        if runtime is not None:
            runtime.invalidate_settings_cache(bot_uuid, group_id)
        return saved_dict

    async def _validate_kuku_scope(self, bot_uuid: str, platform: str, group_id: str) -> None:
        # The persisted config is intentionally constrained to the current Discord-first
        # MVP so later runtime work can rely on one validated adapter path.
        if platform != 'discord':
            raise ValueError('KUKU MVP only supports discord')

        bot_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.Bot.__table__).where(persistence_bot.Bot.uuid == bot_uuid)
        )
        bot = bot_result.mappings().first()
        if bot is None:
            raise ValueError('Bot not found')
        if bot['adapter'] != 'discord':
            raise ValueError('KUKU MVP only supports discord bots')

    def _as_non_negative_int(self, value, default: int, field_name: str) -> int:
        if value is None:
            return default
        if isinstance(value, bool):
            raise ValueError(f'{field_name} must be an integer greater than or equal to 0')
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{field_name} must be an integer greater than or equal to 0') from exc
        if parsed < 0:
            raise ValueError(f'{field_name} must be an integer greater than or equal to 0')
        return parsed

    def _normalize_silence_seconds(self, value) -> int | None:
        """Optional sub-minute silence threshold. None = use silence_minutes only."""
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError('silence_seconds must be a positive integer or omitted')
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError('silence_seconds must be a positive integer or omitted') from exc
        if parsed < 0:
            raise ValueError('silence_seconds must be a positive integer or omitted')
        if parsed == 0:
            return None
        if parsed > 86400:
            raise ValueError('silence_seconds must be at most 86400 (24 hours)')
        return parsed

    def _normalize_quiet_hours(self, value) -> dict:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError('quiet_hours must be a JSON object')
        quiet_hours = dict(value)
        allowed_keys = {'start', 'end', 'timezone'}
        unknown_keys = set(quiet_hours) - allowed_keys
        if unknown_keys:
            raise ValueError('quiet_hours may only contain start, end, and timezone')

        for key in ('start', 'end', 'timezone'):
            if key not in quiet_hours:
                continue
            if not isinstance(quiet_hours[key], str) or not quiet_hours[key].strip():
                raise ValueError(f'quiet_hours.{key} must be a non-empty string')

        return quiet_hours

    def _parse_bool(self, value, field_name: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in {0, 1}:
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {'1', 'true', 'yes', 'y', 'on'}:
                return True
            if normalized in {'0', 'false', 'no', 'n', 'off'}:
                return False
        raise ValueError(
            f"{field_name} must be a boolean value (accepted: true, false, yes, no, on, off, 1, 0)"
        )

    def _build_upsert_statement(
        self, settings_table: sqlalchemy.Table, setting_uuid: str, setting_data: dict
    ) -> sqlalchemy.sql.dml.Insert:
        insert_stmt = self._get_insert_statement(settings_table).values(uuid=setting_uuid, **setting_data)
        update_values = dict(setting_data)
        update_values['updated_at'] = sqlalchemy.func.now()
        # Reuse the same composite scope across SQLite and PostgreSQL so repeated setup
        # calls overwrite the group config instead of creating duplicate rows.
        return insert_stmt.on_conflict_do_update(
            index_elements=['bot_uuid', 'platform', 'group_id'],
            set_=update_values,
        )

    def _get_insert_statement(self, settings_table: sqlalchemy.Table):
        if self.ap.persistence_mgr.db.name == 'postgresql':
            return postgres_insert(settings_table)
        return sqlite_insert(settings_table)

    def _row_to_dict(self, row) -> dict:
        result: dict = {}
        for key, value in row.items():
            if isinstance(value, datetime.datetime):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result
