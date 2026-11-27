"""Reject direct HTTP OAuth requests until HTS1 transport is wired."""

import quart

from .. import group


@group.group_class('oauth', '/api/v1/oauth')
class OAuthRouterGroup(group.RouterGroup):
    async def initialize(self):
        @self.route('/token', methods=['POST'], auth_type=group.AuthType.NONE)
        @self.route('/revoke', methods=['POST'], auth_type=group.AuthType.NONE)
        async def require_encrypted_transport():
            response = quart.jsonify({'error': 'encrypted_transport_required'})
            response.status_code = 415
            response.headers['Cache-Control'] = 'no-store'
            return response
