"""HTTP Bot protocol helpers for the regression suites."""

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request


def signature(secret, body, timestamp):
    return 'sha256=' + hmac.new(secret.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()


def signed_headers(body, secret, timestamp=None):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    signed = signature(secret, body, timestamp)
    return {'Content-Type': 'application/json', 'X-LB-Timestamp': timestamp, 'X-LB-Signature': signed}


def valid_group_settings(settings):
    if not isinstance(settings, dict):
        return False
    required = {'url', 'secret_env', 'message'}
    if not required <= set(settings) or set(settings) - required - {'components'}:
        return False
    if any(not isinstance(settings[key], str) or not settings[key] for key in required):
        return False
    components = settings.get('components', [])
    if not isinstance(components, list) or len(components) > 1:
        return False
    for component in components:
        if not isinstance(component, dict) or set(component) != {'type', 'base64'} or component['type'] != 'Image':
            return False
        data = component['base64']
        prefix = 'data:image/png;base64,'
        if not isinstance(data, str) or len(data) > 16384 or not data.startswith(prefix):
            return False
        try:
            if not base64.b64decode(data[len(prefix) :], validate=True).startswith(b'\x89PNG\r\n\x1a\n'):
                return False
        except ValueError:
            return False
    return True


def group_request(case, group_id, member_id, turn, token, previous, env=None, *, timeout=90):
    """Send one signed GroupMessage through the existing HTTP Bot adapter."""
    settings = case['http_group']
    secret = (os.environ if env is None else env)[settings['secret_env']]
    marker = f'LB_GROUP={group_id} LB_TURN={turn} LB_TOKEN={token} LB_PREVIOUS={previous}'
    body = json.dumps(
        {
            'session_id': group_id,
            'session_type': 'group',
            'sender': {'id': member_id, 'name': member_id, 'group_name': group_id},
            'message': [{'type': 'Plain', 'text': settings['message'] + ' ' + marker}, *settings.get('components', [])],
        }
    ).encode()
    request = urllib.request.Request(
        settings['url'],
        data=body,
        headers={
            **signed_headers(body, secret),
            'X-LB-Idempotency-Key': token,
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        payload = json.load(response)
        if response.status != 200 or not isinstance(payload, dict) or payload.get('code') != 0:
            raise ValueError('group ingress did not return a completed response')
    data = payload.get('data', {})
    if not isinstance(data, dict):
        raise ValueError('group ingress response data must be an object')
    parts = data.get('message')
    if not isinstance(parts, list) or any(not isinstance(part, dict) for part in parts):
        raise ValueError('group reply must contain message components')
    text = ''.join(str(part.get('text', '')) for part in parts if part.get('type') == 'Plain')
    if data.get('session_id') != group_id or not data.get('reply_to'):
        raise ValueError('group reply session or message correlation is missing')
    if case['expect'] not in text or f'GROUP_ACK={token}' not in text:
        raise ValueError('group reply failed its business or conversation-history oracle')
    return payload
