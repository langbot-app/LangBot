"""Execute one rendered step of a workflow."""

import asyncio
import base64
import json

import aiohttp
import regex
from langbot_plugin.api.entities.builtin.platform.message import At, Image, MessageChain, Plain, Voice
from langbot_plugin.api.entities.builtin.provider.message import Message

from ..utils.outbound_url import assert_safe_outbound_url


def matches(rule, diagnostics, location):
    left, right, op = rule['left'], rule.get('right', ''), rule['op']
    if op in ('gt', 'lt'):
        try:
            return float(left) > float(right) if op == 'gt' else float(left) < float(right)
        except ValueError:
            return False
    if op == 'regex':
        if len(left) > 10_000:
            diagnostics.append(f'{location}: regex input exceeds 10000 characters')
            return False
        try:
            return regex.search(right, left, timeout=0.1) is not None
        except TimeoutError:
            diagnostics.append(f'{location}: regex match timed out')
        except regex.error as exc:
            diagnostics.append(f'{location}: invalid regex: {exc}')
        return False
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
            result = {'status': response.status, 'body': body, 'json': parsed}
            if not 200 <= response.status < 300:
                result['error'] = f'HTTP {response.status} {response.reason or ""}'.strip()
            return result


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


async def run_step(kind, config, message, *, ap, runtime, memory, save_memory, history, now=None):
    from . import operations

    if kind == 'random':
        return {'value': operations.draw(config, now)}, None
    if kind in ('code', 'knowledge', 'history', 'tts', 'asr', 'platform'):
        return await getattr(operations, kind)(config, ap, runtime), None
    if kind == 'start':
        return message, None
    if kind == 'llm':
        conversation = list(history[-20:]) if config.get('use_history', True) else []
        content = config['prompt']
        if config.get('use_images') and message.get('images'):
            content = [{'type': 'text', 'text': config['prompt']}]
            for url in message['images']:
                if url.startswith('/api/v1/files/media/'):
                    media = await ap.storage_mgr.media_cache.get_media(url.rsplit('/', 1)[1])
                    if media is None:
                        raise ValueError('Workflow image reference is no longer available')
                    data, mime = media
                    url = f'data:{mime};base64,{base64.b64encode(data).decode("ascii")}'
                else:
                    await asyncio.to_thread(assert_safe_outbound_url, url)
                content.append({'type': 'image_url', 'image_url': {'url': url}})
        conversation.append({'role': 'user', 'content': content})
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
        diagnostics = []
        branch = label = 'else'
        for case in config['cases']:
            check = all if case.get('match', 'all') == 'all' else any
            if check(matches(rule, diagnostics, f'{case["id"]}.rules.{i}') for i, rule in enumerate(case['rules'])):
                branch = case['id']
                label = case.get('label') or branch
                break
        return {'matched': label, **({'error': '; '.join(diagnostics)} if diagnostics else {})}, branch
    if kind == 'remember':
        values = await save_memory(config.get('scope', 'run'), config['items'])
        return {'value': values}, None
    if kind in ('reply', 'send'):
        parts = []
        for part in config.get('content', [{'type': 'text', 'text': config.get('text', '')}]):
            match part['type']:
                case 'text':
                    parts.append(Plain(text=part['text']))
                case 'at':
                    parts.append(At(target=part['user_id']))
                case 'image' | 'voice':
                    ref = part.get('ref') or part.get('url')
                    if isinstance(ref, str) and ref.startswith('/api/v1/files/media/'):
                        # Cached media (incoming files, synthesized speech) is embedded:
                        # adapters cannot fetch a relative LangBot URL.
                        from .operations import media_bytes

                        data, mime = await media_bytes(ap, ref)
                        encoded = f'data:{mime};base64,{base64.b64encode(data).decode("ascii")}'
                        parts.append(Image(base64=encoded) if part['type'] == 'image' else Voice(base64=encoded))
                        continue
                    await asyncio.to_thread(assert_safe_outbound_url, ref)
                    parts.append(Image(url=ref) if part['type'] == 'image' else Voice(url=ref))
                case _:
                    raise ValueError('Unknown workflow message part')
        chain = MessageChain(parts)
        if kind == 'reply':
            reason = await runtime.reply(chain)
            if reason:
                raise ValueError(reason)
        else:
            if runtime.target_sender is None:
                raise ValueError('This workflow test has no sending bot')
            if config.get('bot_uuid') and config['bot_uuid'] != runtime.execution_context.bot_uuid:
                bot = await ap.platform_mgr.get_bot_by_uuid(runtime.execution_context, config['bot_uuid'])
                if bot is None:
                    raise ValueError('Target bot is not running')
                await bot.adapter.send_message(config['target_type'], config['target_id'], chain)
            else:
                await runtime.send(config['target_type'], config['target_id'], chain)
        return {'sent': True}, None
    if kind == 'http':
        return await request(config), None
    if kind == 'handoff':
        runtime.handoff = dict(config)
        return {}, None
    raise ValueError(f'Unknown workflow step: {kind}')
