"""Registration and encrypted RPC endpoints for Harness."""

import asyncio
import hmac
import json
import os

import quart

from .....harness.binding import HarnessBindings
from .....harness.oauth import HarnessOAuthService
from .....harness.rpc import HarnessRpc, RpcError
from .....harness.rotation import HarnessKeyRotation, RotationError
from ...authz import Permission
from ...context import PrincipalType, RequestContext
from .. import group


@group.group_class('harness', '/api/v1/harness')
class HarnessRouterGroup(group.RouterGroup):
    def _service(self):
        if not quart.request.is_secure:
            return None
        try:
            return HarnessBindings(self.ap)
        except ValueError:
            return None

    def _unavailable(self):
        return self.http_status(404, 'harness_registration_unavailable', 'Resource not found')

    def _enrollment_service(self):
        service = self._service()
        origin = quart.request.headers.get('Origin')
        return service if service is not None and (origin is None or origin == service.client_origin) else None

    async def initialize(self):
        rpc = HarnessRpc(self.ap)

        async def read_rpc_payload():
            limit = 40_960
            if (quart.request.content_length or 0) > limit:
                raise RpcError('invalid_request', 413)
            if not quart.request.is_json:
                raise RpcError('invalid_request')
            body = bytearray()
            try:
                async with asyncio.timeout(10):
                    async for chunk in quart.request.body:
                        if len(body) + len(chunk) > limit:
                            raise RpcError('invalid_request', 413)
                        body.extend(chunk)
            except TimeoutError:
                raise RpcError('invalid_request', 408) from None
            try:
                return json.loads(body)
            except (ValueError, RecursionError):
                raise RpcError('invalid_request') from None

        async def run_rpc(handler):
            try:
                if self._enrollment_service() is None:
                    raise RpcError('rpc_unavailable', 404)
                response = quart.jsonify(await handler(await read_rpc_payload()))
            except RpcError as exc:
                response = quart.jsonify({'code': str(exc)})
                response.status_code = exc.status
            response.headers['Cache-Control'] = 'no-store'
            return response

        @self.route('/rpc/handshake', methods=['POST'], auth_type=group.AuthType.NONE)
        async def rpc_handshake():
            return await run_rpc(rpc.start)

        @self.route('/rpc', methods=['POST'], auth_type=group.AuthType.NONE)
        async def rpc_execute():
            return await run_rpc(rpc.execute)

        @self.route('/instance/key-rotation', methods=['POST'], auth_type=group.AuthType.NONE)
        async def rotate_keys():
            # Instance operators provision this separate secret on the host.
            # Workspace roles, API keys, account cookies and Harness grants do not authorize rotation.
            secret = os.environ.get('LANGBOT_HARNESS_ROTATION_TOKEN', '')
            supplied = quart.request.headers.get('Authorization', '')
            if (self._service() is None or len(secret) < 32 or quart.request.headers.get('Origin') is not None
                    or not hmac.compare_digest(supplied.encode(), f'Bearer {secret}'.encode())):
                return self._unavailable()
            service = HarnessKeyRotation(self.ap)
            try:
                payload = await read_rpc_payload()
                if (not isinstance(payload, dict) or set(payload) != {'mode', 'kid'}
                        or payload['mode'] not in ('planned', 'emergency')
                        or not isinstance(payload['kid'], str) or not 0 < len(payload['kid']) <= 128):
                    raise RpcError('invalid_request')
                handler = service.plan if payload['mode'] == 'planned' else service.emergency
                response = quart.jsonify(await handler(payload['kid']))
            except RpcError as exc:
                response = quart.jsonify({'code': str(exc)})
                response.status_code = exc.status
            except RotationError as exc:
                response = quart.jsonify({'code': str(exc)})
                response.status_code = 409
            response.headers['Cache-Control'] = 'no-store'
            return response

        @self.route('/register', methods=['POST'], auth_type=group.AuthType.NONE)
        async def register():
            service = self._enrollment_service()
            if service is None:
                return self._unavailable()
            payload = await quart.request.get_json(silent=True)
            if not isinstance(payload, dict) or set(payload) != {'token'}:
                return self.http_status(400, 'invalid_registration_payload', 'Invalid request parameters')
            result = await service.redeem(payload['token'])
            if result is None:
                return self.http_status(404, 'invalid_registration_link', 'Resource not found')
            response = quart.jsonify(result)
            response.headers['Cache-Control'] = 'no-store'
            return response

        def management_service(ctx):
            return self._service() if ctx.principal.principal_type == PrincipalType.ACCOUNT else None

        @self.route('/registration-links', methods=['POST'], permission=Permission.HARNESS_MANAGE)
        async def issue(request_context: RequestContext):
            service = management_service(request_context)
            if service is None:
                return self._unavailable()
            payload = await quart.request.get_json(silent=True)
            label = payload.get('label') if isinstance(payload, dict) else None
            auth = payload.get('preferred_auth') if isinstance(payload, dict) else None
            if not isinstance(label, str) or not 0 < len(label.strip()) <= 100 or auth not in (None, 'local', 'space'):
                return self.http_status(400, 'invalid_registration_payload', 'Invalid request parameters')
            result = await service.issue(request_context, label=label.strip(), preferred_auth=auth)
            response = self.success(result)
            response.headers['Cache-Control'] = 'no-store'
            return response

        async def list_active(ctx, *, links):
            service = management_service(ctx)
            if service is None:
                return self._unavailable()
            return self.success(await service.list_active(ctx, links=links))

        async def revoke(ctx, target_id, *, links):
            service = management_service(ctx)
            if service is None or not await service.revoke(ctx, str(target_id), links=links):
                return self._unavailable()
            return self.success()

        @self.route('/registration-links', methods=['GET'], permission=Permission.HARNESS_MANAGE)
        async def list_links(request_context: RequestContext):
            return await list_active(request_context, links=True)

        @self.route('/registration-links/<uuid:link_id>', methods=['DELETE'], permission=Permission.HARNESS_MANAGE)
        async def revoke_link(request_context: RequestContext, link_id):
            return await revoke(request_context, link_id, links=True)

        @self.route('/bindings', methods=['GET'], permission=Permission.HARNESS_MANAGE)
        async def list_bindings(request_context: RequestContext):
            return await list_active(request_context, links=False)

        @self.route('/bindings/<uuid:binding_id>', methods=['DELETE'], permission=Permission.HARNESS_MANAGE)
        async def revoke_binding(request_context: RequestContext, binding_id):
            return await revoke(request_context, binding_id, links=False)

        @self.route('/bindings/<uuid:binding_id>/devices', methods=['POST'], auth_type=group.AuthType.NONE)
        async def register_device(binding_id):
            if self._enrollment_service() is None:
                return self._unavailable()
            payload = await quart.request.get_json(silent=True)
            if not isinstance(payload, dict):
                return self._unavailable()
            enrollment_token = payload.pop('enrollment_token', None)
            if not isinstance(enrollment_token, str) or len(enrollment_token) > 256:
                return self.http_status(401, 'invalid_device_enrollment', 'Invalid authentication credentials')
            try:
                result = await HarnessOAuthService(self.ap).register_device(str(binding_id), enrollment_token, payload)
            except ValueError:
                return self.http_status(400, 'invalid_device_key', 'Invalid request parameters')
            if result is None:
                return self.http_status(401, 'invalid_device_enrollment', 'Invalid authentication credentials')
            response = self.success(result)
            response.headers['Cache-Control'] = 'no-store'
            return response

        @self.route('/devices/<device_id>/revoke', methods=['POST'], auth_type=group.AuthType.NONE)
        async def revoke_device(device_id):
            """Revoke the calling device and evict its OAuth sessions."""
            authorization = quart.request.headers.get('Authorization', '')
            token = authorization[7:].strip() if authorization.startswith('Bearer ') else ''
            if not token:
                return self.http_status(401, 'invalid_harness_access_token', 'Invalid authentication credentials')
            try:
                from .....harness.auth import _oauth_context

                context, _ = await _oauth_context(self.ap, token)
                if context.harness_device_id != str(device_id):
                    return self.http_status(403, 'device_forbidden', 'Forbidden')
                revoked = await HarnessOAuthService(self.ap).revoke_device(
                    str(device_id), context.account_uuid
                )
            except ValueError as exc:
                return self.http_status(401, str(exc), 'Invalid authentication credentials')
            if not revoked:
                return self.http_status(404, 'device_not_found', 'Resource not found')
            return self.success()

        @self.route('/oauth/token', methods=['POST'], auth_type=group.AuthType.NONE)
        async def token():
            # Do not read credentials or dispatch grants through the retired route.
            response = quart.jsonify({'error': 'encrypted_transport_required'})
            response.status_code = 415
            response.headers['Cache-Control'] = 'no-store'
            return response
