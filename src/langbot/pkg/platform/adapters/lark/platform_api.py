from __future__ import annotations

import json

from lark_oapi.api.im.v1 import GetChatRequest, GetMessageRequest, GetMessageResourceRequest


async def check_tenant_access_token(adapter, params: dict) -> dict:
    tenant_key = params.get('tenant_key') or getattr(adapter, 'lark_tenant_key', None)
    token = adapter.get_tenant_access_token(tenant_key)
    return {'ok': bool(token) or adapter.config.get('app_type', 'self') != 'isv'}


async def refresh_app_access_token(adapter, params: dict) -> dict:
    adapter.app_access_token = None
    adapter.app_access_token_expire_at = None
    token = adapter.get_app_access_token()
    return {'ok': bool(token) or adapter.config.get('app_type', 'self') != 'isv'}


async def refresh_tenant_access_token(adapter, params: dict) -> dict:
    tenant_key = params.get('tenant_key') or getattr(adapter, 'lark_tenant_key', None)
    if tenant_key:
        adapter.tenant_access_tokens.pop(tenant_key, None)
    token = adapter.get_tenant_access_token(tenant_key)
    return {'ok': bool(token) or adapter.config.get('app_type', 'self') != 'isv'}


async def get_chat(adapter, params: dict) -> dict:
    request = GetChatRequest.builder().chat_id(params['chat_id']).build()
    response = await adapter.api_client.im.v1.chat.aget(request, adapter.request_option(params.get('tenant_key')))
    return _response_to_dict(response)


async def get_message(adapter, params: dict) -> dict:
    request = GetMessageRequest.builder().message_id(params['message_id']).build()
    response = await adapter.api_client.im.v1.message.aget(request, adapter.request_option(params.get('tenant_key')))
    return _response_to_dict(response)


async def get_message_resource(adapter, params: dict) -> dict:
    request = (
        GetMessageResourceRequest.builder()
        .message_id(params['message_id'])
        .file_key(params['file_key'])
        .type(params.get('type', 'file'))
        .build()
    )
    response = await adapter.api_client.im.v1.message_resource.aget(
        request, adapter.request_option(params.get('tenant_key'))
    )
    if not response.success():
        return _response_to_dict(response)
    content_type = response.raw.headers.get('content-type', 'application/octet-stream')
    data = response.file.read()
    return {'ok': True, 'content_type': content_type, 'size': len(data)}


def _response_to_dict(response) -> dict:
    if not response.success():
        return {'ok': False, 'code': response.code, 'msg': response.msg, 'log_id': response.get_log_id()}
    data = getattr(response, 'data', None)
    if hasattr(data, 'to_json'):
        data = data.to_json()
    return {'ok': True, 'data': _jsonable(data)}


def _jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {'bytes': len(value)}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        pass
    raw = getattr(value, '__dict__', None)
    if raw:
        return {key: _jsonable(item) for key, item in raw.items() if not key.startswith('_')}
    return str(value)


PLATFORM_API_MAP = {
    'check_tenant_access_token': check_tenant_access_token,
    'refresh_app_access_token': refresh_app_access_token,
    'refresh_tenant_access_token': refresh_tenant_access_token,
    'get_chat': get_chat,
    'get_message': get_message,
    'get_message_resource': get_message_resource,
}
