from __future__ import annotations

import quart

from .. import group


@group.group_class('human-takeover', '/api/v1/human-takeover')
class HumanTakeoverRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/sessions', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def get_sessions():
            """Get list of takeover sessions, optionally filtered by bot UUID."""
            bot_uuid = quart.request.args.get('botUuid')
            limit = int(quart.request.args.get('limit', 100))
            offset = int(quart.request.args.get('offset', 0))

            sessions, total = await self.ap.human_takeover_service.get_active_sessions(
                bot_uuid=bot_uuid if bot_uuid else None,
                limit=limit,
                offset=offset,
            )

            return self.success(
                data={
                    'sessions': sessions,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            )

        @self.route('/sessions/<session_id>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def get_session_detail(session_id: str):
            """Get detail for a specific takeover session."""
            detail = await self.ap.human_takeover_service.get_session_detail(session_id)
            if not detail:
                return self.success(data={'found': False, 'session_id': session_id})
            return self.success(data={'found': True, 'session': detail})

        @self.route('/sessions/<session_id>/takeover', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def takeover_session(session_id: str, user_email: str = None):
            """Take over a conversation session."""
            data = await quart.request.get_json(silent=True) or {}

            bot_uuid = data.get('bot_uuid')
            if not bot_uuid:
                return self.fail(-1, 'bot_uuid is required')

            platform = data.get('platform')
            user_id = data.get('user_id')
            user_name = data.get('user_name')

            try:
                result = await self.ap.human_takeover_service.takeover_session(
                    session_id=session_id,
                    bot_uuid=bot_uuid,
                    taken_by=user_email or data.get('taken_by'),
                    platform=platform,
                    user_id=user_id,
                    user_name=user_name,
                )
                return self.success(data=result)
            except ValueError as e:
                return self.fail(-1, str(e))

        @self.route('/sessions/<session_id>/release', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def release_session(session_id: str):
            """Release a taken-over session back to AI pipeline."""
            try:
                result = await self.ap.human_takeover_service.release_session(session_id)
                return self.success(data=result)
            except ValueError as e:
                return self.fail(-1, str(e))

        @self.route('/sessions/<session_id>/message', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def send_message(session_id: str, user_email: str = None):
            """Send a message from the operator to the user."""
            data = await quart.request.get_json(silent=True) or {}

            message_text = data.get('message')
            if not message_text:
                return self.fail(-1, 'message is required')

            operator_name = user_email or data.get('operator_name', 'Operator')

            try:
                result = await self.ap.human_takeover_service.send_message(
                    session_id=session_id,
                    message_text=message_text,
                    operator_name=operator_name,
                )
                return self.success(data=result)
            except ValueError as e:
                return self.fail(-1, str(e))
            except RuntimeError as e:
                return self.fail(-2, str(e))
