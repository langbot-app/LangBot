"""One-request HTS1 HTTP sessions for explicitly supported Harness operations."""

import base64
import json
import re
import secrets
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from nacl.exceptions import CryptoError

from ..api.authz import AuthorizationError, permissions_for_role
from ..workspace.errors import WorkspaceExecutionUnavailableError, WorkspaceNotFoundError
from .auth import _oauth_context
from .crypto.suite import open_, seal
from .crypto.transport import begin_handshake, finish_handshake
from .oauth import HarnessOAuthService

_SELECTOR = re.compile(r'[A-Za-z0-9_-]{1,128}')
_MAX_PENDING = 1024
_MAX_BOX = 32_768
_GRANT_ERRORS = {'invalid_grant', 'invalid_device', 'invalid_binding', 'interaction_required',
                 'refresh_token_reuse', 'workspace_forbidden', 'insufficient_scope'}


class RpcError(ValueError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.status = status


@dataclass(frozen=True)
class Challenge:
    selector: tuple[str, str, str]
    device_id: str
    deadline: float
    ephemeral: x25519.X25519PrivateKey
    transcript: bytes


class HarnessRpc:
    def __init__(self, ap):
        self.ap = ap
        self.pending: dict[str, Challenge] = {}

    def _factory(self):
        factory = getattr(self.ap, 'harness_transport_factory', None)
        if factory is None:
            raise RpcError('rpc_unavailable', 503)
        return factory

    @staticmethod
    def _selector(payload):
        if not isinstance(payload, dict) or type(payload.get('v')) is not int or payload['v'] != 1:
            raise RpcError('invalid_request')
        values = tuple(payload.get(key) for key in ('harness_id', 'device_kid', 'pinned_kid'))
        if not all(isinstance(value, str) and _SELECTOR.fullmatch(value) for value in values):
            raise RpcError('invalid_request')
        return values

    @staticmethod
    async def _identity(factory, kid):
        try:
            return await factory.load_identity(kid)
        except ValueError:
            raise RpcError('key_unavailable', 404) from None

    async def start(self, payload):
        selector = self._selector(payload)
        factory = self._factory()
        harness_id, device_kid, pinned_kid = selector
        device = await factory.client_key_lookup(harness_id, device_kid)
        if device is None:
            raise RpcError('invalid_device', 404)
        kid, _, server_signing = await self._identity(factory, pinned_kid)
        now = time.monotonic()
        while self.pending and next(iter(self.pending.values())).deadline <= now:
            del self.pending[next(iter(self.pending))]
        if len(self.pending) >= _MAX_PENDING:
            raise RpcError('rpc_busy', 429)
        nonce = secrets.token_urlsafe(32)
        hs1, ephemeral, transcript = begin_handshake(kid, server_signing, nonce)
        self.pending[nonce] = Challenge(selector, device['id'], now + 60, ephemeral, transcript)
        return {'v': 1, 'hs1': hs1}

    async def execute(self, payload):
        selector = self._selector(payload)
        factory = self._factory()
        nonce = payload.get('nonce_s')
        if not isinstance(nonce, str) or len(nonce) != 43:
            raise RpcError('invalid_hs2')
        challenge = self.pending.get(nonce)
        if challenge is None or challenge.selector != selector or challenge.deadline <= time.monotonic():
            raise RpcError('invalid_hs2')
        del self.pending[nonce]
        harness_id, device_kid, kid = selector
        device = await factory.client_key_lookup(harness_id, device_kid)
        if device is None or device['id'] != challenge.device_id:
            raise RpcError('invalid_device', 404)
        _, server_static, _ = await self._identity(factory, kid)
        frame = payload.get('frame')
        header = {'v': 1, 'kid': kid, 'kind': 'rpc', 'seq': '0'}
        if (
            not isinstance(frame, dict) or type(frame.get('v')) is not int
            or any(frame.get(key) != value for key, value in header.items())
        ):
            raise RpcError('invalid_request')
        box = frame.get('box')
        if not isinstance(box, str) or len(box) > _MAX_BOX:
            raise RpcError('invalid_request')
        try:
            c2h, h2c = finish_handshake(
                kid, challenge.transcript, challenge.ephemeral, server_static,
                x25519.X25519PublicKey.from_public_bytes(base64.b64decode(device['x25519_pub'], validate=True)),
                ed25519.Ed25519PublicKey.from_public_bytes(base64.b64decode(device['ed25519_pub'], validate=True)),
                payload.get('hs2'),
            )
            request = json.loads(open_(c2h, 0, base64.b64decode(box, validate=True)))
        except (InvalidSignature, CryptoError, ValueError, RecursionError):
            raise RpcError('invalid_hs2') from None
        if (
            not isinstance(request, dict) or type(request.get('v')) is not int or request['v'] != 1
            or not isinstance(request.get('id'), str) or not 0 < len(request['id']) <= 128
        ):
            raise RpcError('invalid_request')
        reply = {'v': 1, 'id': request['id']}
        try:
            result = await self._dispatch(harness_id, device['id'], request)
            reply.update(ok=True, result=result)
        except (AuthorizationError, WorkspaceNotFoundError, WorkspaceExecutionUnavailableError):
            reply.update(ok=False, error={'code': 'workspace_forbidden'})
        except ValueError as exc:
            code = str(exc)
            if not isinstance(exc, RpcError) and code not in _GRANT_ERRORS:
                code = 'invalid_grant'
            reply.update(ok=False, error={'code': code})
        return {'frame': {**header, 'box': base64.b64encode(seal(h2c, 0, json.dumps(reply).encode())).decode()}}

    async def _dispatch(self, harness_id, device_id, request):
        method, params = request.get('method'), request.get('params')
        if not isinstance(params, dict):
            raise RpcError('invalid_request')
        service = HarnessOAuthService(self.ap)
        if method == 'oauth.password':
            if set(params) != {'email', 'password', 'workspace_uuid'}:
                raise RpcError('invalid_request')
            return await service.password_grant(harness_id, {
                'grant_type': 'password', 'device_id': device_id, 'username': params['email'],
                'password': params['password'], 'workspace_uuid': params['workspace_uuid'],
            })
        if method == 'oauth.refresh':
            token = params.get('refresh_token')
            if set(params) != {'refresh_token'} or not isinstance(token, str) or not 0 < len(token) <= 256:
                raise RpcError('invalid_request')
            return await service.refresh_grant(token, binding_id=harness_id, device_id=device_id)
        if method in ('workspace.list', 'workspace.select'):
            expected = {'access_token'} if method == 'workspace.list' else {'access_token', 'workspace_uuid'}
            token = params.get('access_token')
            if set(params) != expected or not isinstance(token, str) or not 0 < len(token) <= 8192:
                raise RpcError('invalid_request')
            context, _ = await _oauth_context(self.ap, token, device_id=device_id, binding_id=harness_id)
            if 'workspace.view' not in context.workspace.permissions:
                raise RpcError('insufficient_scope')
            if method == 'workspace.list':
                accesses = await self.ap.workspace_collaboration_service.list_account_workspaces(context.account_uuid)
                return {'workspace_uuid': context.workspace_uuid, 'workspaces': [
                    {'id': item.workspace.uuid, 'label': item.workspace.name} for item in accesses
                    if 'workspace.view' in permissions_for_role(item.membership.role)
                ]}
            target = params['workspace_uuid']
            if not isinstance(target, str) or not 0 < len(target) <= 36:
                raise RpcError('invalid_request')
            return await service.switch_workspace(context.account_uuid, harness_id, device_id, target)
        raise RpcError('unsupported_rpc_method')
