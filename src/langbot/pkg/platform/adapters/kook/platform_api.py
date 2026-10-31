from __future__ import annotations

import typing
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


async def get_current_user(adapter, params: dict) -> dict:
    return await adapter._request('GET', '/user/me')


async def get_user(adapter, params: dict) -> dict:
    return await adapter._request('GET', '/user/view', params={'user_id': params['user_id']})


async def get_channel(adapter, params: dict) -> dict:
    return await adapter._request('GET', '/channel/view', params={'target_id': params['target_id']})


async def get_guild(adapter, params: dict) -> dict:
    return await adapter._request('GET', '/guild/view', params={'guild_id': params['guild_id']})


async def get_gateway(adapter, params: dict) -> dict:
    raw = await adapter._request('GET', '/gateway/index', params={'compress': int(params.get('compress', 1))})
    data = raw.get('data')
    if isinstance(data, dict) and data.get('url'):
        data = {**data, 'url': _redact_url_token(str(data['url']))}
        raw = {**raw, 'data': data}
    return raw


async def send_direct_message(adapter, params: dict) -> dict:
    payload = {
        'content': params['content'],
        'type': params.get('type', 1),
    }
    if params.get('chat_code'):
        payload['chat_code'] = params['chat_code']
    else:
        payload['target_id'] = params['target_id']
    return await adapter._request('POST', '/direct-message/create', json=payload)


PLATFORM_API_MAP: dict[str, typing.Callable[[typing.Any, dict], typing.Awaitable[dict]]] = {
    'get_current_user': get_current_user,
    'get_user': get_user,
    'get_channel': get_channel,
    'get_guild': get_guild,
    'get_gateway': get_gateway,
    'send_direct_message': send_direct_message,
}


def _redact_url_token(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        [(key, '<redacted>' if key.lower() == 'token' else value) for key, value in parse_qsl(parts.query)],
        doseq=True,
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
