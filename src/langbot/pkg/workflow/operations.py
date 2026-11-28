import json
import random
import shlex
import uuid
from datetime import datetime, timedelta, timezone
from textwrap import indent

import sqlalchemy as sa

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
