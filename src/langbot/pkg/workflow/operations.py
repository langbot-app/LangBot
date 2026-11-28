import json
import random
import shlex
import uuid
from datetime import datetime, timedelta, timezone
from textwrap import indent

import sqlalchemy as sa
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain

from ..entity.persistence.monitoring import MonitoringMessage


def draw(config, now):
    mode = config['mode']
    if mode == 'number':
        return random.randint(int(config['min']), int(config['max']))
    if mode not in ('pick', 'seeded_pick'):
        raise ValueError('Unknown random mode')
    items = config['items']
    if not isinstance(items, list) or not items:
        raise ValueError('Provide at least one random item')
    generator = random.Random(f'{now.date()}:{config["seed"]}') if mode == 'seeded_pick' else random.SystemRandom()
    return generator.choices(items, weights=config.get('weights'), k=1)[0]


async def code(config, ap, runtime):
    box = getattr(ap, 'box_service', None)
    if not box or not box.available:
        raise ValueError('Box runtime is unavailable')
    program = (
        'import json, sys\ndef main(inputs):\n'
        + indent(config['code'], '    ')
        + '\nprint(json.dumps(main(json.loads(sys.argv[1])),allow_nan=False))'
    )
    result = await box.execute_in_context(
        runtime.execution_context,
        {
            'session_id': str(uuid.uuid4()),
            'timeout_sec': 10,
            'cmd': shlex.join(['python3', '-c', program, json.dumps(config.get('inputs', {}))]),
        },
    )
    if not result.ok:
        raise ValueError(result.stderr.strip() or 'Box execution failed')
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError('Code must return a JSON object')
    return value


async def knowledge(config, ap, runtime):
    context = runtime.execution_context
    kb = await ap.rag_mgr.get_knowledge_base_by_uuid(context, config['kb_uuid'])
    if kb is None:
        raise ValueError('Knowledge base not found')
    limit = int(config.get('top_k', 5))
    if limit < 1:
        raise ValueError('top_k must be positive')
    entries = await kb.retrieve(context, config['query'], {'top_k': limit})
    chunks = [
        {'id': entry.id, 'text': '\n'.join(part.text for part in entry.content if part.type == 'text' and part.text)}
        for entry in entries[:limit]
    ]
    return {'chunks': chunks, 'text': '\n'.join(chunk['text'] for chunk in chunks)}


async def history(config, ap, runtime):
    context = runtime.execution_context
    if not context.bot_uuid or not runtime.session_id:
        raise ValueError('History requires a bot conversation')
    if config.get('scope') == 'group' and not runtime.session_id.startswith('group_'):
        raise ValueError('Group history requires a group conversation')
    model = MonitoringMessage
    query = sa.select(model.timestamp, model.user_name, model.role, model.message_content).where(
        model.workspace_uuid == context.workspace_uuid,
        model.bot_id == context.bot_uuid,
        model.session_id == runtime.session_id,
    )
    if 'since_hours' in config:
        query = query.where(
            model.timestamp
            >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=float(config['since_hours']))
        )
    limit = int(config.get('limit', 200))
    if not 1 <= limit <= 200:
        raise ValueError('History limit must be between 1 and 200')
    rows = (
        await ap.persistence_mgr.execute_async(query.order_by(model.timestamp.desc(), model.id.desc()).limit(limit))
    ).all()
    messages = [
        {'sender_name': row.user_name or row.role, 'text': row.message_content, 'time': row.timestamp.isoformat()}
        for row in reversed(rows)
    ]
    return {'messages': messages, 'text': '\n'.join(f'{item["sender_name"]}: {item["text"]}' for item in messages)}


MEDIA_PREFIX = '/api/v1/files/media/'


async def media_bytes(ap, ref):
    """Load a cached media reference (`/api/v1/files/media/<file>`) as bytes and MIME type."""
    if not isinstance(ref, str) or not ref.startswith(MEDIA_PREFIX):
        raise ValueError('Expected a voice or image from an earlier step')
    media = await ap.storage_mgr.media_cache.get_media(ref.rsplit('/', 1)[1])
    if media is None:
        raise ValueError('The media file is no longer available')
    return media


async def save_media(ap, data, mime):
    _, key, _ = await ap.storage_mgr.media_cache.save_media(data, mime)
    return MEDIA_PREFIX + key.rsplit('/', 1)[1]


async def tts(config, ap, runtime):
    model = await ap.model_mgr.get_tts_model_by_uuid(runtime.execution_context, config['model_uuid'])
    if model is None:
        raise ValueError('Text-to-speech model not found')
    text = str(config.get('text') or '').strip()
    if not text:
        raise ValueError('Nothing to read aloud')
    extra = dict(getattr(model, 'extra_args', None) or getattr(model.model_entity, 'extra_args', None) or {})
    extra = {'response_format': 'mp3', **({'voice': extra['voice']} if extra.get('voice') else {})}
    if config.get('voice'):
        extra['voice'] = config['voice']
    audio, mime = await model.provider.invoke_tts(
        model=model, text=text, extra_args=extra, execution_context=model.execution_context
    )
    return {'voice': await save_media(ap, audio, mime)}


async def asr(config, ap, runtime):
    from ..utils import audio as audio_utils

    model = await ap.model_mgr.get_asr_model_by_uuid(runtime.execution_context, config['model_uuid'])
    if model is None:
        raise ValueError('Speech-to-text model not found')
    audio, mime = await media_bytes(ap, config.get('voice'))
    source = audio_utils.detect_audio_format(audio)
    target = source if source in ('wav', 'mp3', 'ogg', 'm4a', 'flac') else 'wav'
    if source != target:
        if not audio_utils.is_ffmpeg_available():
            raise ValueError(f'Cannot convert {source} audio without ffmpeg')
        audio = await audio_utils.transcode_audio(audio, target, source)
    text = await model.provider.invoke_asr(
        model=model, audio=audio, mime=f'audio/{target}', execution_context=model.execution_context
    )
    return {'text': (text or '').strip()}


def _plain(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


# Standard APIs outside the Agent platform tool catalog, with each parameter's
# type. Catalog tools (event_* and platform_*) run through execute_platform_tool.
CHAT = ('chat_type', 'chat_id', 'message_id')
PLATFORM_APIS = {
    'edit_message': (*CHAT, 'new_content:chain'),
    'delete_message': CHAT,
    'forward_message': ('from_chat_type', 'from_chat_id', 'message_id', 'to_chat_type', 'to_chat_id'),
    'get_message': CHAT,
    'get_group_info': ('group_id',),
    'get_group_list': (),
    'get_group_member_list': ('group_id',),
    'get_group_member_info': ('group_id', 'user_id'),
    'set_group_name': ('group_id', 'name'),
    'mute_member': ('group_id', 'user_id', 'duration:int'),
    'unmute_member': ('group_id', 'user_id'),
    'kick_member': ('group_id', 'user_id'),
    'leave_group': ('group_id',),
    'get_user_info': ('user_id',),
    'get_friend_list': (),
    'approve_friend_request': ('request_id', 'approve:bool', 'remark:optional'),
    'approve_group_invite': ('request_id', 'approve:bool'),
    'upload_file': ('file_data:media', 'filename'),
    'get_file_url': ('file_id',),
    'call_platform_api': ('action', 'params:dict'),
}
# Messages go out through the reply/send steps so the bot's output policy applies.
STEP_ONLY_TOOLS = {'event_reply', 'platform_send_message', 'request_interaction'}


def _flag(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ('', '0', 'false', 'no', 'off', 'reject')


async def _platform_params(ap, action, raw):
    params = {}
    for spec in PLATFORM_APIS[action]:
        name, _, kind = spec.partition(':')
        value = raw.get(name)
        if kind == 'int':
            params[name] = int(value or 0)
        elif kind == 'bool':
            params[name] = True if value is None else _flag(value)
        elif kind == 'optional':
            if value not in (None, ''):
                params[name] = str(value)
        elif kind == 'chain':
            params[name] = MessageChain([Plain(text=str(value or ''))])
        elif kind == 'media':
            params[name] = (await media_bytes(ap, value))[0]
        elif kind == 'dict':
            params[name] = value if isinstance(value, dict) else {}
        else:
            if value in (None, ''):
                raise ValueError(f'{name} is required')
            params[name] = str(value)
    return params


def _tool_params(definition, raw):
    """Coerce rendered template strings to the tool schema; drop empty optional values."""
    properties = definition.parameters.get('properties') or {}
    required = set(definition.parameters.get('required') or [])
    params = {}
    for name, field in properties.items():
        value = raw.get(name)
        if value in (None, '') and name not in required and field.get('type') != 'boolean':
            continue
        kind = field.get('type')
        if kind == 'integer':
            params[name] = int(value or 0)
        elif kind == 'boolean':
            params[name] = True if value is None else _flag(value)
        elif value is not None:
            params[name] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return params


def platform_session(*, bot_uuid=None, context=None, run_id=''):
    """A run session shaped like the Agent one, so platform tools bind the same event targets."""
    return {
        'run_id': run_id,
        'authorization': {
            'bot_id': bot_uuid,
            'processor_type': 'workflow',
            'platform_context': context or {},
        },
    }


async def platform(config, ap, runtime):
    from ..agent.runner.platform_tools import PLATFORM_TOOLS_BY_NAME, execute_platform_tool

    action = config['action']
    raw = dict(config.get('params') or {})
    session = getattr(runtime, 'platform_session', None) or platform_session(
        bot_uuid=runtime.execution_context.bot_uuid
    )
    context = session['authorization']['platform_context']
    mock = ((context.get('delivery') or {}).get('platform_capabilities') or {}).get('debug_mock') is True
    definition = PLATFORM_TOOLS_BY_NAME.get(action)
    if definition is not None:
        if action in STEP_ONLY_TOOLS:
            raise ValueError('Use the reply or send step to send messages')
        if definition.scope == 'platform' and config.get('bot_uuid') and not mock:
            session = {**session, 'authorization': {**session['authorization'], 'bot_id': config['bot_uuid']}}
        if definition.scope == 'event' and not context.get('event_type'):
            raise ValueError('This action needs the event that started the workflow')
        result = await execute_platform_tool(
            ap, runtime.execution_context, session, action, _tool_params(definition, raw)
        )
        return {'result': _plain(result)}
    if action not in PLATFORM_APIS:
        raise ValueError(f'{action} cannot be called from a workflow')
    if mock:
        return {'result': {'ok': True, 'mock': True, 'api': action, 'parameters': _plain(raw), 'result': None}}
    bot_uuid = config.get('bot_uuid') or session['authorization'].get('bot_id')
    if not bot_uuid:
        raise ValueError('Choose the bot that performs this action')
    bot = await ap.platform_mgr.get_bot_by_uuid(runtime.execution_context, bot_uuid)
    if bot is None:
        raise ValueError('The bot is not running')
    if action not in bot.adapter.get_supported_apis():
        raise ValueError(f'{action} is not supported by this platform')
    params = await _platform_params(ap, action, raw)
    result = await getattr(bot.adapter, action)(**params)
    return {'result': _plain(result)}
