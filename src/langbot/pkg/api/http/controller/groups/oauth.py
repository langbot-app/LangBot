"""OAuth token endpoints for the Harness account client."""

import quart

from .....oauth.errors import OAuthError, TotpHandoffRequired
from .....oauth.service import OAuthService
from .. import group


@group.group_class('oauth', '/api/v1/oauth')
class OAuthRouterGroup(group.RouterGroup):
    async def initialize(self):
        @self.route('/token', methods=['POST'], auth_type=group.AuthType.NONE)
        async def token():
            payload = await quart.request.get_json(silent=True)
            if not isinstance(payload, dict):
                return quart.jsonify({'error': 'invalid_request'}), 400
            try:
                result = await OAuthService(self.ap).token(payload)
            except TotpHandoffRequired as exc:
                response = quart.jsonify({'error': exc.code, 'handoff_ticket': exc.ticket})
                response.status_code = exc.status
                response.headers['Cache-Control'] = 'no-store'
                return response
            except OAuthError as exc:
                response = quart.jsonify({'error': exc.code})
                response.status_code = exc.status
                response.headers['Cache-Control'] = 'no-store'
                return response
            response = quart.jsonify(result)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Pragma'] = 'no-cache'
            return response

        @self.route('/revoke', methods=['POST'], auth_type=group.AuthType.NONE)
        async def revoke():
            payload = await quart.request.get_json(silent=True)
            token_value = payload.get('token') if isinstance(payload, dict) else None
            try:
                await OAuthService(self.ap).revoke(token_value)
            except OAuthError as exc:
                return quart.jsonify({'error': exc.code}), exc.status
            # RFC 7009-style revocation is intentionally idempotent; callers must
            # not distinguish an unknown token from an already revoked one.
            return quart.jsonify({'revoked': True})
