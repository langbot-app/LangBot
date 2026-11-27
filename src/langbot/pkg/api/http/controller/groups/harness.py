"""Registration endpoints for the Harness client and LangBot WebUI."""

import quart

from .....harness.binding import HarnessBindings
from .....harness.oauth import HarnessOAuthService
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

    async def initialize(self):
        @self.route('/register', methods=['POST'], auth_type=group.AuthType.NONE)
        async def register():
            service = self._service()
            origin = quart.request.headers.get('Origin')
            if service is None or (origin is not None and origin != service.client_origin):
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
            service = self._service()
            payload = await quart.request.get_json(silent=True)
            if service is None or not isinstance(payload, dict):
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
            return self.success(result)

        @self.route('/oauth/token', methods=['POST'], auth_type=group.AuthType.NONE)
        async def token():
            payload = await quart.request.get_json(silent=True)
            if not isinstance(payload, dict):
                return self.http_status(400, 'invalid_request', 'Invalid request parameters')
            service = HarnessOAuthService(self.ap)
            try:
                if payload.get('grant_type') == 'refresh_token':
                    result = await service.refresh_grant(payload.get('refresh_token', ''))
                else:
                    result = await service.password_grant(payload.get('binding_id', ''), payload)
            except ValueError as exc:
                return self.http_status(401, str(exc), 'Invalid authentication credentials')
            response = self.success(result)
            response.headers['Cache-Control'] = 'no-store'
            return response
