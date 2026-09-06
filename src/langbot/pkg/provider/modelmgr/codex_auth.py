"""ChatGPT device auth with server-only credentials and cross-process refresh leases.

Network I/O never holds a DB transaction. A persisted CAS lease serializes refresh
and poll; cancel fences device exchanges but waits for existing-token refreshes.
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
import sqlalchemy as sa

from ...entity.persistence.model import CodexCredential, ModelProvider
from ...api.http.context import PrincipalType, RequestContext
from ...api.http.authz import Permission, has_permission
from ...api.http.service.tenant import require_workspace_uuid
from ...workspace.errors import WorkspaceNotFoundError

REQUESTER = 'openai-codex'
BASE_URL = 'https://chatgpt.com/backend-api/codex'
ISSUER = 'https://auth.openai.com'
CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann'
LOGIN_REQUIRED = 'ChatGPT sign-in required. Open this provider and sign in again.'
LEASE_SECONDS = 90


def validate_config(data: dict) -> None:
    if data.get('requester') != REQUESTER:
        return
    if data.get('base_url') not in (None, '', BASE_URL):
        raise ValueError('Codex uses the fixed ChatGPT endpoint; custom base URLs are not supported')
    if data.get('api_keys') not in (None, [], ''):
        raise ValueError('Codex uses ChatGPT sign-in, not API keys')
    data['base_url'] = BASE_URL
    data['api_keys'] = []


def _claims(token: str) -> dict:
    """Read routing metadata, NOT trusted LangBot identity, from issuer tokens."""
    try:
        part = token.split('.')[1]
        value = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
        return value if isinstance(value, dict) else {}
    except (ValueError, IndexError, TypeError):
        return {}


def _tokens(data: dict, previous: dict | None = None) -> dict:
    previous = previous or {}
    access = data.get('access_token')
    refresh = data.get('refresh_token') or previous.get('refresh_token')
    account = None
    for token in (access, data.get('id_token')):
        namespace = _claims(token or '').get('https://api.openai.com/auth', {})
        if isinstance(namespace, dict) and isinstance(namespace.get('chatgpt_account_id'), str):
            account = namespace['chatgpt_account_id']
            break
    account = account or previous.get('account_id')
    try:
        expires_at = (
            time.time() + float(data['expires_in'])
            if data.get('expires_in') is not None
            else float(_claims(access or '').get('exp', 0))
        )
    except (TypeError, ValueError):
        expires_at = 0
    if (
        not all(isinstance(v, str) and v for v in (access, refresh, account))
        or not math.isfinite(expires_at)
        or expires_at <= time.time()
    ):
        raise ValueError('ChatGPT returned an incomplete authorization. Please sign in again.')
    return {
        'access_token': access,
        'refresh_token': refresh,
        'account_id': account,
        'expires_at': expires_at,
        'connection_id': previous.get('connection_id') or secrets.token_urlsafe(24),
    }


class CodexAuth:
    def __init__(self, ap):
        self.ap = ap

    def _where(self, workspace: str, provider: str):
        return (CodexCredential.workspace_uuid == workspace, CodexCredential.provider_uuid == provider)

    async def _execute(self, statement):
        # SQLAlchemy/driver/serialization errors may embed the entire secret payload.
        try:
            return await self.ap.persistence_mgr.execute_async(statement)
        except Exception:
            raise ValueError('ChatGPT credential storage failed. Please retry.') from None

    async def _read(self, workspace: str, provider: str) -> dict | None:
        result = await self._execute(sa.select(CodexCredential).where(*self._where(workspace, provider)))
        try:
            row = result.first()
            return dict(row._mapping) if row is not None else None
        except Exception:
            raise ValueError('ChatGPT credential storage failed. Please retry.') from None

    async def _provider(self, context, provider: str, *, user: bool = False) -> str:
        workspace = require_workspace_uuid(context)
        if user and (
            not isinstance(context, RequestContext)
            or context.principal.principal_type != PrincipalType.ACCOUNT
            or not context.account_uuid
            or not has_permission(context, Permission.PROVIDER_SECRET_MANAGE)
        ):
            raise ValueError('ChatGPT authorization requires an authorized workspace user')
        result = await self._execute(
            sa.select(ModelProvider.requester).where(
                ModelProvider.workspace_uuid == workspace, ModelProvider.uuid == provider
            )
        )
        kind = result.scalar()
        if kind is None:
            raise WorkspaceNotFoundError('Provider not found')
        if kind != REQUESTER:
            raise ValueError('This provider does not use ChatGPT sign-in')
        return workspace

    @asynccontextmanager
    async def _lease(self, workspace: str, provider: str, *, refresh: bool = False):
        owner = ('refresh:' if refresh else 'device:') + secrets.token_urlsafe(32)
        deadline = time.monotonic() + 65
        while True:
            now = time.time()
            result = await self._execute(
                sa.update(CodexCredential)
                .where(
                    *self._where(workspace, provider),
                    sa.or_(CodexCredential.lease_owner.is_(None), CodexCredential.lease_until < now),
                )
                .values(lease_owner=owner, lease_until=now + LEASE_SECONDS)
            )
            if result.rowcount == 1:
                break
            if await self._read(workspace, provider) is None:
                raise ValueError(LOGIN_REQUIRED)
            if time.monotonic() >= deadline:
                raise ValueError('ChatGPT authorization is busy. Please retry shortly.')
            await asyncio.sleep(0.1)
        try:
            yield owner
        finally:
            await self._execute(
                sa.update(CodexCredential)
                .where(*self._where(workspace, provider), CodexCredential.lease_owner == owner)
                .values(lease_owner=None, lease_until=0)
            )

    async def _save(self, workspace: str, provider: str, owner: str, payload: dict) -> None:
        result = await self._execute(
            sa.update(CodexCredential)
            .where(
                *self._where(workspace, provider),
                CodexCredential.lease_owner == owner,
                CodexCredential.lease_until > time.time(),
            )
            .values(payload=payload, version=CodexCredential.version + 1)
        )
        if result.rowcount != 1:
            raise ValueError('ChatGPT authorization was cancelled or replaced. Please retry.')

    async def _post(self, path: str, *, data=None, json_body=None) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                return await asyncio.wait_for(
                    client.post(
                        ISSUER + path,
                        data=data,
                        json=json_body,
                        headers={'Accept': 'application/json', 'User-Agent': 'LangBot'},
                    ),
                    25,
                )
        except (httpx.HTTPError, TimeoutError):
            raise ValueError('ChatGPT authorization network error. Please retry.') from None

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        try:
            value = response.json()
            if not isinstance(value, dict):
                raise ValueError
            return value
        except ValueError:
            raise ValueError('ChatGPT returned an invalid authorization response') from None

    async def status(self, context, provider: str) -> dict:
        workspace = await self._provider(context, provider, user=True)
        row = await self._read(workspace, provider)
        payload = row['payload'] if row else {}
        tokens = payload.get('tokens')
        connected = bool(tokens and not payload.get('invalid'))
        return {
            'status': 'connected' if connected else 'expired' if payload.get('invalid') else 'disconnected',
            'connected': connected,
            'expires_at': tokens.get('expires_at') if tokens else None,
        }

    async def start(self, context, provider: str) -> dict:
        workspace = await self._provider(context, provider, user=True)
        async with self._lease(workspace, provider) as owner:
            response = await self._post('/api/accounts/deviceauth/usercode', json_body={'client_id': CLIENT_ID})
            if response.status_code != 200:
                raise ValueError('Unable to start ChatGPT device login. Enable device code login in ChatGPT settings.')
            data = self._json(response)
            try:
                code = data.get('user_code') or data['usercode']
                device = data['device_auth_id']
                interval = max(5, min(60, int(data.get('interval') or 5)))
                if not isinstance(code, str) or not isinstance(device, str) or not code or not device:
                    raise ValueError
            except (KeyError, ValueError, TypeError):
                raise ValueError('ChatGPT returned an invalid device code') from None
            now = time.time()
            try:
                expiry = data.get('expires_at')
                if expiry is None:
                    expiry = now + float(data.get('expires_in', 900))
                try:
                    expires_at = float(expiry)
                except ValueError:
                    parsed = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    expires_at = parsed.timestamp()
                if not math.isfinite(expires_at) or expires_at <= now:
                    raise ValueError
                expires_at = min(now + 900, expires_at)
            except (ValueError, TypeError):
                raise ValueError('ChatGPT returned an invalid device code expiry') from None
            pending = {
                'authorization_id': secrets.token_urlsafe(32),
                'user_code': code,
                'device_auth_id': device,
                'account_uuid': context.account_uuid,
                'interval': interval,
                'expires_at': expires_at,
                'next_poll_at': now + interval,
            }
            row = await self._read(workspace, provider)
            payload = dict(row['payload'])
            payload['pending'] = pending
            await self._save(workspace, provider, owner, payload)
            return {k: pending[k] for k in ('authorization_id', 'user_code', 'interval', 'expires_at')} | {
                'verification_uri': ISSUER + '/codex/device'
            }

    @staticmethod
    def _attempt(payload: dict, context, authorization_id: str) -> dict | None:
        pending = payload.get('pending')
        if not pending or pending.get('authorization_id') != authorization_id:
            return None
        if pending.get('account_uuid') != context.account_uuid:
            raise WorkspaceNotFoundError('Authorization not found')
        return pending

    async def poll(self, context, provider: str, authorization_id: str) -> dict:
        workspace = await self._provider(context, provider, user=True)
        if not isinstance(authorization_id, str) or not authorization_id:
            raise ValueError('authorization_id is required')
        async with self._lease(workspace, provider) as owner:
            row = await self._read(workspace, provider)
            payload = dict(row['payload'])
            pending = self._attempt(payload, context, authorization_id)
            if pending is None:
                completed = payload.get('completed', {})
                if (
                    completed.get('authorization_id') == authorization_id
                    and completed.get('account_uuid') == context.account_uuid
                ):
                    return {'status': 'connected'}
                return {'status': 'expired'}
            now = time.time()
            if pending['expires_at'] <= now or pending.get('consumed'):
                payload.pop('pending', None)
                await self._save(workspace, provider, owner, payload)
                return {'status': 'expired'}
            if pending['next_poll_at'] > now:
                return {'status': 'pending', 'interval': pending['interval']}
            pending['next_poll_at'] = now + pending['interval']
            await self._save(workspace, provider, owner, payload)
            response = await self._post(
                '/api/accounts/deviceauth/token',
                json_body={'device_auth_id': pending['device_auth_id'], 'user_code': pending['user_code']},
            )
            if response.status_code in (403, 404, 429):
                if response.status_code == 429:
                    pending['interval'] = min(60, pending['interval'] + 5)
                    pending['next_poll_at'] = time.time() + pending['interval']
                    await self._save(workspace, provider, owner, payload)
                return {'status': 'pending', 'interval': pending['interval']}
            if response.status_code != 200:
                payload.pop('pending', None)
                await self._save(workspace, provider, owner, payload)
                raise ValueError('ChatGPT device authorization failed. Please start again.')
            data = self._json(response)
            if not data.get('authorization_code') or not data.get('code_verifier'):
                payload.pop('pending', None)
                await self._save(workspace, provider, owner, payload)
                raise ValueError('ChatGPT returned an incomplete device authorization')
            # Keep an attempt tombstone so cancel can preempt exchange, but never replay a code.
            pending['consumed'] = True
            await self._save(workspace, provider, owner, payload)
            response = await self._post(
                '/oauth/token',
                data={
                    'grant_type': 'authorization_code',
                    'client_id': CLIENT_ID,
                    'code': data['authorization_code'],
                    'code_verifier': data['code_verifier'],
                    'redirect_uri': ISSUER + '/deviceauth/callback',
                },
            )
            if response.status_code != 200:
                raise ValueError('ChatGPT token exchange failed. Please start sign-in again.')
            tokens = _tokens(self._json(response))
            await self._save(
                workspace,
                provider,
                owner,
                {
                    'tokens': tokens,
                    'completed': {'authorization_id': authorization_id, 'account_uuid': context.account_uuid},
                },
            )
            return {'status': 'connected'}

    async def disconnect(self, context, provider: str) -> None:
        workspace = await self._provider(context, provider, user=True)
        await self._execute(
            sa.update(CodexCredential)
            .where(*self._where(workspace, provider))
            .values(payload={}, lease_owner=None, lease_until=0, version=CodexCredential.version + 1)
        )

    async def cancel(self, context, provider: str, authorization_id: str) -> None:
        workspace = await self._provider(context, provider, user=True)
        deadline = time.monotonic() + 65
        while time.monotonic() < deadline:
            row = await self._read(workspace, provider)
            if row is None:
                return
            old = row['payload']
            if self._attempt(old, context, authorization_id) is None:
                return
            lease_owner = row['lease_owner']
            if lease_owner and lease_owner.startswith('refresh:') and row['lease_until'] > time.time():
                # A rotated refresh token must be committed before removing the attempt.
                await asyncio.sleep(0.1)
                continue
            payload = dict(old)
            payload.pop('pending', None)
            result = await self._execute(
                sa.update(CodexCredential)
                .where(
                    *self._where(workspace, provider),
                    CodexCredential.version == row['version'],
                    # Lease acquisition does not change version; fence that race too.
                    CodexCredential.lease_owner == lease_owner,
                )
                .values(payload=payload, lease_owner=None, lease_until=0, version=CodexCredential.version + 1)
            )
            if result.rowcount == 1:
                return
        raise ValueError('Authorization changed concurrently. Please retry cancellation.')

    async def access(self, context, provider: str, *, rejected_token: str | None = None) -> dict:
        workspace = await self._provider(context, provider)
        row = await self._read(workspace, provider)
        payload = row['payload'] if row else {}
        tokens = payload.get('tokens')
        if not tokens or payload.get('invalid'):
            raise ValueError(LOGIN_REQUIRED)
        if tokens['expires_at'] > time.time() + 120 and tokens['access_token'] != rejected_token:
            return tokens
        async with self._lease(workspace, provider, refresh=True) as owner:
            row = await self._read(workspace, provider)
            payload = dict(row['payload'])
            tokens = payload.get('tokens')
            if not tokens or payload.get('invalid'):
                raise ValueError(LOGIN_REQUIRED)
            if tokens['expires_at'] > time.time() + 120 and tokens['access_token'] != rejected_token:
                return tokens
            response = await self._post(
                '/oauth/token',
                data={'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'refresh_token': tokens['refresh_token']},
            )
            error = self._json(response).get('error') if response.status_code in (400, 401, 403) else None
            error_code = error.get('code') if isinstance(error, dict) else error
            if error_code in (
                'invalid_grant',
                'refresh_token_reused',
                'refresh_token_expired',
                'refresh_token_revoked',
            ):
                payload['invalid'] = True
                payload.pop('tokens', None)
                payload.pop('completed', None)
                await self._save(workspace, provider, owner, payload)
                raise ValueError(LOGIN_REQUIRED)
            if response.status_code != 200:
                raise ValueError('ChatGPT token refresh temporarily failed. Please retry.')
            refreshed = _tokens(self._json(response), tokens)
            payload['tokens'] = refreshed
            await self._save(workspace, provider, owner, payload)
            return refreshed
