from __future__ import annotations

import asyncio
import copy
import datetime
import logging
import time
import traceback
from zoneinfo import ZoneInfo

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from ..core.app import Application

TICK_INTERVAL_SEC = 20


def _parse_hhmm(value: str) -> datetime.time | None:
    parts = value.strip().split(':')
    if len(parts) != 2:
        return None
    try:
        return datetime.time(int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def in_quiet_hours(quiet_hours: dict) -> bool:
    """Return True if current local time in configured timezone falls inside quiet_hours."""
    if not quiet_hours:
        return False
    start_s = quiet_hours.get('start')
    end_s = quiet_hours.get('end')
    if not start_s or not end_s:
        return False
    t_start = _parse_hhmm(str(start_s))
    t_end = _parse_hhmm(str(end_s))
    if t_start is None or t_end is None:
        return False

    tz_name = (quiet_hours.get('timezone') or 'UTC').strip()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = datetime.timezone.utc

    now_t = datetime.datetime.now(tz).time()

    if t_start <= t_end:
        return t_start <= now_t <= t_end
    return now_t >= t_start or now_t <= t_end


def _unwrap_invoke_llm_result(raw):
    """Normalize provider.invoke_llm return value to a single Message."""
    if isinstance(raw, tuple) and len(raw) >= 1:
        return raw[0]
    return raw


class KukuRuntime:
    """Background silence detection and proactive Discord messages for KUKU."""

    ap: Application

    _last_human_message_ts: dict[tuple[str, str, str], float]
    _last_kuku_fire_ts: dict[tuple[str, str, str], float]
    _settings_cache: dict[tuple[str, str], tuple[float, dict | None]]
    _settings_ttl_sec: float
    _tick_lock: asyncio.Lock

    def __init__(self, ap: Application) -> None:
        self.ap = ap
        self._last_human_message_ts = {}
        self._last_kuku_fire_ts = {}
        self._settings_cache = {}
        self._settings_ttl_sec = 30.0
        self._tick_lock = asyncio.Lock()
        self._logger = logging.getLogger('langbot.kuku')

    async def record_discord_channel_activity(self, bot_uuid: str, channel_id: str) -> None:
        """Record a human Discord message in a channel when KUKU is enabled for that scope."""
        now = time.time()
        settings = await self._get_settings_cached(bot_uuid, 'discord', channel_id, now)
        if not settings or not settings.get('enabled', True):
            return
        scope = (bot_uuid, 'discord', str(channel_id))
        self._last_human_message_ts[scope] = now

    async def maybe_handle_discord_group_message(self, bot_uuid: str, event) -> bool:
        """Immediately reply when a Discord group message directly targets KUKU."""
        now = time.time()
        group_id = str(event.group.id)
        settings = await self._get_settings_cached(bot_uuid, 'discord', group_id, now)
        if not settings or not settings.get('enabled', True):
            return False

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None or not runtime_bot.enable:
            return False
        if runtime_bot.bot_entity.adapter != 'discord':
            return False

        bot_account_id = str(getattr(runtime_bot.adapter, 'bot_account_id', '') or '')
        if not bot_account_id:
            return False

        mentions_bot, cleaned_message_chain = _strip_direct_bot_mentions(event.message_chain, bot_account_id)
        is_reply_to_bot = _is_reply_to_discord_bot(
            getattr(event, 'source_platform_object', None),
            bot_account_id,
        )
        if not mentions_bot and not is_reply_to_bot:
            return False

        persona_id = settings.get('persona_id') or 'kuku-sunny'
        persona = await self.ap.kuku_service.get_persona(persona_id)
        if persona is None:
            self._logger.warning('KUKU: persona %s not found', persona_id)
            return False

        reply_text = await self._generate_reactive_reply(
            persona,
            bot_uuid,
            cleaned_message_chain,
            reply_context=_get_discord_reply_context(getattr(event, 'source_platform_object', None)),
        )
        if not reply_text:
            return False

        reply_chain = platform_message.MessageChain([platform_message.Plain(text=reply_text)])
        try:
            await runtime_bot.adapter.reply_message(event, reply_chain, quote_origin=True)
        except Exception:
            self._logger.error('KUKU reply_message failed:\n%s', traceback.format_exc())
            return False

        return True

    async def _get_settings_cached(self, bot_uuid: str, platform: str, group_id: str, now: float) -> dict | None:
        cache_key = (bot_uuid, group_id)
        hit = self._settings_cache.get(cache_key)
        if hit is not None:
            exp, val = hit
            if now < exp:
                return val
        row = await self.ap.kuku_service.get_group_settings(bot_uuid, platform, group_id)
        self._settings_cache[cache_key] = (now + self._settings_ttl_sec, row)
        return row

    def invalidate_settings_cache(self, bot_uuid: str, group_id: str) -> None:
        self._settings_cache.pop((bot_uuid, group_id), None)

    async def _resolve_llm_model(self, pipeline_uuid: str | None):
        if not pipeline_uuid:
            return None
        pipeline = await self.ap.pipeline_mgr.get_pipeline_by_uuid(pipeline_uuid)
        if pipeline is None:
            return None
        cfg = pipeline.pipeline_entity.config
        runner = cfg.get('ai', {}).get('runner', {}).get('runner')
        if runner != 'local-agent':
            self._logger.warning('KUKU requires pipeline ai.runner.runner == local-agent')
            return None
        model_cfg = cfg.get('ai', {}).get('local-agent', {}).get('model', {})
        if isinstance(model_cfg, str):
            primary_uuid = model_cfg
        else:
            primary_uuid = model_cfg.get('primary', '') if isinstance(model_cfg, dict) else ''
        if not primary_uuid:
            return None
        try:
            return await self.ap.model_mgr.get_model_by_uuid(primary_uuid)
        except ValueError:
            self._logger.warning('KUKU: LLM model %s not found for pipeline %s', primary_uuid, pipeline_uuid)
            return None

    async def _generate_opener(self, persona: dict, bot_uuid: str, silence_minutes: int) -> str | None:
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None:
            return None
        llm_model = await self._resolve_llm_model(runtime_bot.bot_entity.use_pipeline_uuid)
        if llm_model is None:
            return None

        silence_minutes = max(1, silence_minutes)
        system = str(persona.get('system_prompt') or '')
        user_instruction = (
            f'The group chat has had no messages for about {silence_minutes} minutes. '
            'Write ONE short, natural message to gently restart conversation. '
            'Stay in character. No preface or meta commentary. No quotes.'
        )
        messages = [
            provider_message.Message(role='system', content=[provider_message.ContentElement.from_text(system)]),
            provider_message.Message(role='user', content=[provider_message.ContentElement.from_text(user_instruction)]),
        ]
        try:
            raw = await llm_model.provider.invoke_llm(
                None,
                llm_model,
                messages,
                [],
                extra_args=llm_model.model_entity.extra_args,
            )
            assistant = _unwrap_invoke_llm_result(raw)
            chain = assistant.get_content_platform_message_chain()
            text = str(chain).strip()
            return text or None
        except Exception:
            self._logger.error('KUKU LLM invoke failed:\n%s', traceback.format_exc())
            return None

    async def _generate_reactive_reply(
        self,
        persona: dict,
        bot_uuid: str,
        message_chain: platform_message.MessageChain,
        reply_context: str | None = None,
    ) -> str | None:
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None:
            return None
        llm_model = await self._resolve_llm_model(runtime_bot.bot_entity.use_pipeline_uuid)
        if llm_model is None:
            return None

        system = str(persona.get('system_prompt') or '')
        user_text = str(message_chain).strip()
        context_lines = []
        if reply_context:
            context_lines.append(f'The user is replying to this previous KUKU message:\n{reply_context}')
        if user_text:
            context_lines.append(f'The user said:\n{user_text}')
        else:
            context_lines.append('The user directly mentioned you in the channel.')

        user_instruction = (
            '\n\n'.join(context_lines)
            + '\n\nWrite ONE short, natural in-character reply. '
            'No preface, no meta commentary, no quotes.'
        )
        messages = [
            provider_message.Message(role='system', content=[provider_message.ContentElement.from_text(system)]),
            provider_message.Message(role='user', content=[provider_message.ContentElement.from_text(user_instruction)]),
        ]
        try:
            raw = await llm_model.provider.invoke_llm(
                None,
                llm_model,
                messages,
                [],
                extra_args=llm_model.model_entity.extra_args,
            )
            assistant = _unwrap_invoke_llm_result(raw)
            chain = assistant.get_content_platform_message_chain()
            text = str(chain).strip()
            return text or None
        except Exception:
            self._logger.error('KUKU reactive LLM invoke failed:\n%s', traceback.format_exc())
            return None

    async def _try_send_kuku(self, settings: dict) -> bool:
        bot_uuid = settings['bot_uuid']
        group_id = str(settings['group_id'])

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None or not runtime_bot.enable:
            return False
        if runtime_bot.bot_entity.adapter != 'discord':
            return False

        persona_id = settings.get('persona_id') or 'kuku-sunny'
        persona = await self.ap.kuku_service.get_persona(persona_id)
        if persona is None:
            self._logger.warning('KUKU: persona %s not found', persona_id)
            return False

        silence_minutes = int(settings.get('silence_minutes') or 30)
        opener = await self._generate_opener(persona, bot_uuid, silence_minutes)
        if not opener:
            return False

        message_chain = platform_message.MessageChain([platform_message.Plain(text=opener)])
        try:
            await runtime_bot.adapter.send_message('group', group_id, message_chain)
        except Exception:
            self._logger.error('KUKU send_message failed:\n%s', traceback.format_exc())
            return False

        return True

    async def _tick_once(self) -> None:
        rows = await self.ap.kuku_service.list_enabled_discord_group_settings()
        now = time.time()

        for row in rows:
            qh = row.get('quiet_hours') or {}
            if isinstance(qh, dict) and in_quiet_hours(dict(qh)):
                continue

            bot_uuid = row['bot_uuid']
            platform = row['platform']
            group_id = str(row['group_id'])
            scope = (bot_uuid, platform, group_id)

            last_human = self._last_human_message_ts.get(scope)
            if last_human is None:
                continue

            silence_minutes = int(row.get('silence_minutes') or 30)
            if now - last_human < silence_minutes * 60:
                continue

            cooldown_minutes = int(row.get('cooldown_minutes') or 10)
            last_kuku = self._last_kuku_fire_ts.get(scope, 0.0)
            if last_kuku and now - last_kuku < cooldown_minutes * 60:
                continue

            async with self._tick_lock:
                now2 = time.time()
                last_human2 = self._last_human_message_ts.get(scope)
                if last_human2 is None or now2 - last_human2 < silence_minutes * 60:
                    continue
                last_kuku2 = self._last_kuku_fire_ts.get(scope, 0.0)
                if last_kuku2 and now2 - last_kuku2 < cooldown_minutes * 60:
                    continue

                if await self._try_send_kuku(row):
                    self._last_kuku_fire_ts[scope] = time.time()

    async def run_background_loop(self) -> None:
        """Periodic silence checks while the application runs."""
        while True:
            try:
                await self._tick_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.error('KUKU tick error:\n%s', traceback.format_exc())
            await asyncio.sleep(TICK_INTERVAL_SEC)


def _strip_direct_bot_mentions(
    message_chain: platform_message.MessageChain,
    bot_account_id: str,
) -> tuple[bool, platform_message.MessageChain]:
    cleaned = copy.deepcopy(message_chain)
    found = False
    filtered_root = []
    for component in cleaned.root:
        if isinstance(component, platform_message.At) and str(component.target) == str(bot_account_id):
            found = True
            continue
        filtered_root.append(component)
    cleaned.root = filtered_root
    return found, cleaned


def _is_reply_to_discord_bot(source_platform_object, bot_account_id: str) -> bool:
    if source_platform_object is None:
        return False

    reference = getattr(source_platform_object, 'reference', None)
    if reference is None:
        return False

    resolved = getattr(reference, 'resolved', None)
    author = getattr(resolved, 'author', None)
    author_id = getattr(author, 'id', None)
    if author_id is None:
        return False

    return str(author_id) == str(bot_account_id)


def _get_discord_reply_context(source_platform_object) -> str | None:
    reference = getattr(source_platform_object, 'reference', None)
    resolved = getattr(reference, 'resolved', None)
    content = getattr(resolved, 'content', None)
    if content is None:
        return None
    text = str(content).strip()
    return text or None
