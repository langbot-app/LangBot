"""Execute one rendered step of a workflow."""

import asyncio
import json
import re

import aiohttp
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
from langbot_plugin.api.entities.builtin.provider.message import Message

from ..utils.outbound_url import assert_safe_outbound_url


def matches(rule):
    left, right, op = rule['left'], rule.get('right', ''), rule['op']
    if op in ('gt', 'lt'):
        try:
            return float(left) > float(right) if op == 'gt' else float(left) < float(right)
        except ValueError:
            return False
    if op == 'regex':
        return re.search(right, left) is not None
    return {
        'equals': left == right,
        'not_equals': left != right,
        'contains': right in left,
        'not_contains': right not in left,
        'starts_with': left.startswith(right),
        'ends_with': left.endswith(right),
        'is_empty': not left,
        'not_empty': bool(left),
    }[op]


async def request(config):
    url = await asyncio.to_thread(assert_safe_outbound_url, config['url'])
    timeout = aiohttp.ClientTimeout(total=min(30, max(1, float(config.get('timeout', 30)))))
    headers = {item['key']: item['value'] for item in config.get('headers', [])}
    async with aiohttp.ClientSession(timeout=timeout) as client:
        async with client.request(
            config.get('method', 'GET'), url, headers=headers, data=config.get('body'), allow_redirects=False
        ) as response:
            body = await response.text()
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = None
            response.raise_for_status()
            return {'status': response.status, 'body': body, 'json': parsed}


async def model_text(ap, runtime, config, conversation):
    model = await ap.model_mgr.get_model_by_uuid(runtime.execution_context, config['model_uuid'])
    answer = await model.provider.invoke_llm(
        query=None,
        execution_context=runtime.execution_context,
        model=model,
        messages=[Message(**message) for message in conversation],
        funcs=None,
        extra_args={key: config[key] for key in ('temperature', 'max_tokens') if config.get(key) is not None},
    )
    if isinstance(answer.content, str):
        return answer.content
    return ''.join(part if isinstance(part, str) else getattr(part, 'text', '') for part in answer.content or [])


async def run_step(kind, config, message, *, ap, runtime, memory, save_memory, history):
    if kind == 'start':
        return message, None
    if kind == 'llm':
        conversation = list(history[-20:]) if config.get('use_history', True) else []
        conversation.append({'role': 'user', 'content': config['prompt']})
        return {'text': await model_text(ap, runtime, config, conversation)}, None
    if kind in ('classify', 'extract'):
        if kind == 'classify':
            prompt = (
                'Return only the matching category ID, or else. Categories: '
                + json.dumps(config['categories'], ensure_ascii=False)
                + '\n'
                + config.get('instruction', '')
            )
        else:
            prompt = 'Return a JSON object with these typed fields: ' + json.dumps(config['fields'], ensure_ascii=False)
        response = await model_text(
            ap, runtime, config, [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': message['text']}]
        )
        if kind == 'classify':
            for category in config['categories']:
                if response.strip() in (category['id'], category['label']):
                    return {'category': category['label']}, category['id']
            return {'category': 'else'}, 'else'
        try:
            values = json.loads(response)
        except ValueError:
            values = {}
        result = {}
        for field in config['fields']:
            value = values.get(field['key']) if isinstance(values, dict) else None
            expected = {'text': (str,), 'boolean': (bool,), 'number': (int, float)}[field['type']]
            result[field['key']] = value if type(value) in expected else None
        return {**result, 'ok': all(value is not None for value in result.values())}, None
    if kind == 'condition':
        for case in config['cases']:
            check = all if case.get('match', 'all') == 'all' else any
            if check(matches(rule) for rule in case['rules']):
                return {'matched': case.get('label') or case['id']}, case['id']
        return {'matched': 'else'}, 'else'
    if kind == 'remember':
        values = {item['key']: item['value'] for item in config['items']}
        if config.get('scope', 'run') == 'session':
            await save_memory(values)
        memory.update(values)
        return values, None
    if kind in ('reply', 'send'):
        chain = MessageChain([Plain(text=config['text'])])
        if kind == 'reply':
            reason = await runtime.reply(chain)
            if reason:
                raise ValueError(reason)
        else:
            await runtime.send(config['target_type'], config['target_id'], chain)
        return {'sent': True}, None
    if kind == 'http':
        return await request(config), None
    if kind == 'handoff':
        runtime.handoff = dict(config, text=config.get('text') or message['text'])
        return {}, None
    raise ValueError(f'Unknown workflow step: {kind}')
