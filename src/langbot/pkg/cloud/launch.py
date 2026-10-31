from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import heapq
import json
import os
import time
import typing
from collections.abc import Callable, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .support_admin import SupportAdminReplayError, SupportAdminSessionError, hash_grant_jti

if typing.TYPE_CHECKING:
    from ..core.app import Application


CONTROL_PLANE_TYP = 'langbot-control-plane+jwt'
LAUNCH_KIND = 'workspace.launch'
SUPPORT_ADMIN_LAUNCH_KIND = 'workspace.support_admin_launch'
EXPECTED_ISSUER = 'langbot-space'
EXPECTED_AUDIENCE = 'langbot-cloud-runtime'
_CONSUMED_JTI_MAX_ENTRIES = 4096
_CONSUMED_JTI_HEAP_COMPACT_FLOOR = 64
_CONSUMED_JTI_HEAP_MAX_MULTIPLIER = 4


class SpaceLaunchError(ValueError):
    """Raised when a Space-issued Cloud launch assertion is not admissible."""


def _decode_base64url(value: str, *, label: str) -> bytes:
    if not value or any(character.isspace() for character in value):
        raise SpaceLaunchError(f'Launch assertion {label} is not canonical base64url')
    try:
        raw = base64.b64decode(value + ('=' * (-len(value) % 4)), altchars=b'-_', validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SpaceLaunchError(f'Launch assertion {label} is not valid base64url') from exc
    if base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii') != value:
        raise SpaceLaunchError(f'Launch assertion {label} is not canonical base64url')
    return raw


def _strict_json_object(value: bytes, *, label: str) -> dict[str, typing.Any]:
    def reject_duplicate_keys(pairs: Iterable[tuple[str, typing.Any]]) -> dict[str, typing.Any]:
        result: dict[str, typing.Any] = {}
        for key, item in pairs:
            if key in result:
                raise SpaceLaunchError(f'Launch assertion {label} contains duplicate key {key!r}')
            result[key] = item
        return result

    try:
        decoded = json.loads(value, object_pairs_hook=reject_duplicate_keys)
    except SpaceLaunchError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpaceLaunchError(f'Launch assertion {label} is not valid JSON') from exc
    if not isinstance(decoded, dict):
        raise SpaceLaunchError(f'Launch assertion {label} must be a JSON object')
    return decoded


def _required_string(claims: dict[str, typing.Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value or value != value.strip():
        raise SpaceLaunchError(f'Launch assertion claim {name} must be a non-empty string')
    return value


def _required_int(claims: dict[str, typing.Any], name: str, *, minimum: int = 0) -> int:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise SpaceLaunchError(f'Launch assertion claim {name} must be an integer >= {minimum}')
    return value


def _load_ed25519_public_key(encoded: str) -> Ed25519PublicKey:
    value = encoded.strip()
    if value.startswith('-----BEGIN'):
        try:
            key = serialization.load_pem_public_key(value.encode('ascii'))
        except (ValueError, TypeError) as exc:
            raise SpaceLaunchError('Space launch public key is not valid PEM') from exc
        if not isinstance(key, Ed25519PublicKey):
            raise SpaceLaunchError('Space launch public key must be Ed25519')
        return key

    try:
        raw = base64.b64decode(value + ('=' * (-len(value) % 4)), altchars=b'-_', validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SpaceLaunchError('Space launch public key must be base64 encoded') from exc
    if len(raw) != 32:
        raise SpaceLaunchError('Space launch Ed25519 public key must contain 32 bytes')
    return Ed25519PublicKey.from_public_bytes(raw)


class SpaceLaunchService:
    """Verify and single-use consume Space Cloud direct-launch assertions."""

    def __init__(
        self,
        ap: Application,
        *,
        wall_time: Callable[[], float] = time.time,
    ) -> None:
        self.ap = ap
        self._wall_time = wall_time
        self._replay_lock = asyncio.Lock()
        self._consumed_jtis: dict[str, int] = {}
        self._consumed_jti_expiry_heap: list[tuple[int, str]] = []

    async def consume_assertion(
        self,
        assertion: str,
        *,
        expected_workspace_uuid: str | None = None,
    ) -> dict[str, str]:
        claims = self._verify_assertion(assertion)
        payload = claims.get('payload')
        if not isinstance(payload, dict):
            raise SpaceLaunchError('Launch assertion payload must be a JSON object')
        kind = _required_string(claims, 'kind')
        workspace_uuid = _required_string(payload, 'workspace_uuid')
        if expected_workspace_uuid is not None and workspace_uuid != expected_workspace_uuid:
            raise SpaceLaunchError('Launch assertion targets another Workspace')
        if kind == SUPPORT_ADMIN_LAUNCH_KIND:
            if 'account_uuid' in payload:
                raise SpaceLaunchError('Admin launch assertion must not identify a customer Account')
            if payload.get('launch_mode') != 'support_admin' or payload.get('principal_type') != 'support_admin':
                raise SpaceLaunchError('Admin launch principal must be support_admin')
            actor_account_uuid = _required_string(payload, 'actor_account_uuid')
            if _required_string(payload, 'effective_role') != 'owner':
                raise SpaceLaunchError('Admin launch effective role must be owner')
            issued_at = _required_int(claims, 'iat')
            expires_at = _required_int(claims, 'exp', minimum=1)
            if expires_at - issued_at > 90:
                raise SpaceLaunchError('Admin launch assertion lifetime exceeds 90 seconds')
            grant_jti_hash = hash_grant_jti(_required_string(claims, 'jti'))
            result = {
                'workspace_uuid': workspace_uuid,
                'launch_mode': 'support_admin',
                'actor_account_uuid': actor_account_uuid,
                'effective_role': 'owner',
                'grant_jti_hash': grant_jti_hash,
            }
            support_service = getattr(self.ap, 'support_admin_session_service', None)
            if support_service is None or not callable(getattr(support_service, 'consume_launch_grant', None)):
                raise SpaceLaunchError('Durable support admin session service is unavailable')
            try:
                support_session = await support_service.consume_launch_grant(
                    grant_jti_hash=grant_jti_hash,
                    workspace_uuid=workspace_uuid,
                    actor_account_uuid=actor_account_uuid,
                )
            except SupportAdminReplayError as exc:
                raise SpaceLaunchError('Launch assertion has already been consumed') from exc
            except SupportAdminSessionError as exc:
                raise SpaceLaunchError(str(exc)) from exc
            result['support_admin_token'] = support_session.token
            self.ap.logger.info(
                'cloud_support_admin_launch_consumed actor_account_uuid=%s workspace_uuid=%s',
                result['actor_account_uuid'],
                workspace_uuid,
            )
            return result

        if payload.get('launch_mode') is not None:
            raise SpaceLaunchError('Launch assertion mode is unsupported')
        account_uuid = _required_string(payload, 'account_uuid')
        result = {
            'account_uuid': account_uuid,
            'workspace_uuid': workspace_uuid,
        }
        await self._consume_jti(_required_string(claims, 'jti'), _required_int(claims, 'exp', minimum=1))
        return result

    def _verify_assertion(self, token: str) -> dict[str, typing.Any]:
        if not getattr(getattr(self.ap, 'deployment', None), 'multi_workspace_enabled', False):
            raise SpaceLaunchError('Space direct launch requires verified Cloud mode')
        public_key, key_id, clock_skew_seconds = self._trust_config()
        segments = token.split('.')
        if len(segments) != 3:
            raise SpaceLaunchError('Launch assertion must be a compact JWS')
        encoded_header, encoded_claims, encoded_signature = segments
        header = _strict_json_object(_decode_base64url(encoded_header, label='header'), label='header')
        if set(header) != {'alg', 'kid', 'typ'}:
            raise SpaceLaunchError('Launch assertion header contains unsupported fields')
        if header.get('alg') != 'EdDSA':
            raise SpaceLaunchError('Launch assertion algorithm must be EdDSA')
        if header.get('kid') != key_id:
            raise SpaceLaunchError('Launch assertion key ID does not match Cloud trust')
        if header.get('typ') != CONTROL_PLANE_TYP:
            raise SpaceLaunchError('Launch assertion type is not a control-plane payload')

        signature = _decode_base64url(encoded_signature, label='signature')
        if len(signature) != 64:
            raise SpaceLaunchError('Launch assertion signature must contain 64 bytes')
        try:
            public_key.verify(signature, f'{encoded_header}.{encoded_claims}'.encode('ascii'))
        except InvalidSignature as exc:
            raise SpaceLaunchError('Launch assertion signature is invalid') from exc

        claims = _strict_json_object(_decode_base64url(encoded_claims, label='claims'), label='claims')
        instance_uuid = self.ap.workspace_service.instance_uuid
        if _required_string(claims, 'iss') != EXPECTED_ISSUER:
            raise SpaceLaunchError('Launch assertion issuer is not LangBot Space')
        if _required_string(claims, 'aud') != EXPECTED_AUDIENCE:
            raise SpaceLaunchError('Launch assertion audience does not target Cloud runtime')
        if _required_string(claims, 'sub') != f'langbot-instance:{instance_uuid}':
            raise SpaceLaunchError('Launch assertion subject targets another instance')
        if _required_string(claims, 'instance_uuid') != instance_uuid:
            raise SpaceLaunchError('Launch assertion instance UUID does not match this Core')
        kind = _required_string(claims, 'kind')
        if kind not in {LAUNCH_KIND, SUPPORT_ADMIN_LAUNCH_KIND}:
            raise SpaceLaunchError('Launch assertion kind is not supported')

        issued_at = _required_int(claims, 'iat')
        not_before = _required_int(claims, 'nbf')
        expires_at = _required_int(claims, 'exp', minimum=1)
        now = self._wall_time()
        if issued_at > now + clock_skew_seconds:
            raise SpaceLaunchError('Launch assertion was issued in the future')
        if not_before > now + clock_skew_seconds:
            raise SpaceLaunchError('Launch assertion is not active yet')
        if expires_at <= now - clock_skew_seconds:
            raise SpaceLaunchError('Launch assertion is expired')
        if expires_at <= max(issued_at, not_before):
            raise SpaceLaunchError('Launch assertion expiry must follow issue time')
        return claims

    def _trust_config(self) -> tuple[Ed25519PublicKey, str, float]:
        data = getattr(getattr(self.ap, 'instance_config', None), 'data', {}) or {}
        space_config = data.get('space', {})
        launch_config = space_config.get('launch', {}) if isinstance(space_config, dict) else {}
        if not isinstance(launch_config, dict):
            launch_config = {}
        public_key_value = (
            os.environ.get('LANGBOT_SPACE_CONTROL_PLANE_PUBLIC_KEY', '').strip()
            or str(launch_config.get('control_plane_public_key', '') or '').strip()
        )
        key_id = (
            os.environ.get('LANGBOT_SPACE_CONTROL_PLANE_KEY_ID', '').strip()
            or str(launch_config.get('control_plane_key_id', '') or '').strip()
            or str(getattr(getattr(self.ap, 'deployment', None), 'verification_key_id', '') or '').strip()
        )
        if not public_key_value or not key_id:
            raise SpaceLaunchError('Space launch control-plane trust is not configured')
        clock_skew = self._bounded_float(
            os.environ.get('LANGBOT_SPACE_CONTROL_PLANE_CLOCK_SKEW_SECONDS') or launch_config.get('clock_skew_seconds'),
            default=30.0,
            minimum=0.0,
            maximum=300.0,
        )
        return _load_ed25519_public_key(public_key_value), key_id, clock_skew

    async def _consume_jti(self, jti: str, expires_at: int) -> None:
        digest = hashlib.sha256(jti.encode('utf-8')).hexdigest()
        now = int(self._wall_time())
        async with self._replay_lock:
            self._prune_consumed_jtis(now)
            if digest in self._consumed_jtis:
                raise SpaceLaunchError('Launch assertion has already been consumed')
            if len(self._consumed_jtis) >= _CONSUMED_JTI_MAX_ENTRIES:
                # Evicting a still-valid digest would make a signed launch
                # assertion replayable. Bound memory by failing closed instead.
                raise SpaceLaunchError('Launch assertion replay cache capacity reached')
            self._consumed_jtis[digest] = expires_at
            heapq.heappush(
                self._consumed_jti_expiry_heap,
                (expires_at, digest),
            )

    def _prune_consumed_jtis(self, now: int) -> None:
        while self._consumed_jti_expiry_heap:
            expires_at, digest = self._consumed_jti_expiry_heap[0]
            current_expiry = self._consumed_jtis.get(digest)
            if current_expiry != expires_at:
                heapq.heappop(self._consumed_jti_expiry_heap)
                continue
            if expires_at > now:
                break
            heapq.heappop(self._consumed_jti_expiry_heap)
            self._consumed_jtis.pop(digest, None)

        max_heap_entries = max(
            _CONSUMED_JTI_HEAP_COMPACT_FLOOR,
            len(self._consumed_jtis) * _CONSUMED_JTI_HEAP_MAX_MULTIPLIER,
        )
        if len(self._consumed_jti_expiry_heap) > max_heap_entries:
            self._consumed_jti_expiry_heap[:] = [(expiry, digest) for digest, expiry in self._consumed_jtis.items()]
            heapq.heapify(self._consumed_jti_expiry_heap)

    @staticmethod
    def _bounded_float(
        value: typing.Any,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default
        if not minimum <= result <= maximum:
            return default
        return result
