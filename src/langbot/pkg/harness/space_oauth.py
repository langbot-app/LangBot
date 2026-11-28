"""Confidential Space code exchange for the explicitly configured Harness pilot."""

import asyncio
import json
import os
import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

import aiohttp

from .binding import _https_origin


def canonical_uuid(value):
    try:
        return isinstance(value, str) and len(value) == 36 and str(uuid.UUID(value)) == value
    except ValueError:
        return False


@dataclass(frozen=True)
class SpaceOAuthClient:
    endpoint: str
    redirect_uri: str
    workspace_uuid: str

    @classmethod
    def configured(cls, ap):
        config = ap.instance_config.data.get('harness', {}).get('space_oauth', {})
        if config.get('enabled') is not True:
            raise ValueError('harness_oauth_disabled')
        redirect = config.get('redirect_uri', '')
        try:
            origin = _https_origin(config.get('space_origin'))
            parsed = urlsplit(redirect)
            if (parsed.scheme != 'https' or not parsed.hostname or not parsed.path
                    or parsed.username is not None or any(c in redirect for c in '?#\\')
                    or any(ord(c) <= 32 for c in redirect)
                    or not canonical_uuid(config.get('workspace_uuid'))):
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError('harness_oauth_disabled') from None
        return cls(origin + '/api/v1/accounts/harness/oauth/token', redirect, config['workspace_uuid'])

    def validate(self, params):
        if set(params) != {'code', 'code_verifier', 'redirect_uri', 'workspace_uuid', 'account_uuid'}:
            raise ValueError('invalid_request')
        if params['workspace_uuid'] != self.workspace_uuid:
            raise ValueError('workspace_forbidden')
        if (params['redirect_uri'] != self.redirect_uri or not canonical_uuid(params['account_uuid'])
                or not isinstance(params['code'], str) or not re.fullmatch(r'h1_[A-Za-z0-9_-]{43}', params['code'])
                or not isinstance(params['code_verifier'], str)
                or not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', params['code_verifier'])):
            raise ValueError('invalid_grant')

    async def consume(self, params, *, instance_id, binding_id, device_id):
        secret = os.getenv('LANGBOT_HARNESS_SPACE_CLIENT_SECRET', '')
        if len(secret) < 32 or len(secret) > 256 or any(c.isspace() for c in secret):
            raise ValueError('harness_oauth_disabled')
        target = {
            'client_id': 'harness', 'instance_id': instance_id, 'binding_id': binding_id, 'device_id': device_id,
            'account_uuid': params['account_uuid'], 'workspace_uuid': self.workspace_uuid,
            'redirect_uri': self.redirect_uri,
        }
        payload = {**target, 'grant_type': 'authorization_code', 'code': params['code'],
                   'code_verifier': params['code_verifier']}
        # No redirects, retries or browser-supplied endpoint; never log credentials.
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.post(self.endpoint, json=payload, allow_redirects=False,
                                        headers={'Authorization': f'Bearer {secret}'}) as response:
                    errors = {400: 'invalid_grant', 401: 'invalid_client', 404: 'harness_oauth_disabled'}
                    if response.status != 200:
                        raise ValueError(errors.get(response.status, 'space_exchange_unavailable'))
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(4096):
                        body.extend(chunk)
                        if len(body) > 8192:
                            raise ValueError('space_exchange_unavailable')
                    try:
                        result = json.loads(body)
                    except (ValueError, RecursionError):
                        raise ValueError('space_exchange_unavailable') from None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise ValueError('space_exchange_unavailable') from None
        if not isinstance(result, dict) or result.get('code') != 0 or result.get('data') != target:
            raise ValueError('invalid_grant')
