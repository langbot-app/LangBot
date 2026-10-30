"""Standard interaction adapter methods backed by existing platform renderers."""

from __future__ import annotations

from langbot_plugin.api.entities.builtin.runner.interaction import (
    InteractionHandle,
    InteractionRequest,
    InteractionSubmission,
)


class InteractionAdapterMixin:
    async def send_interaction(
        self,
        target_type: str,
        target_id: str,
        request: InteractionRequest,
        callback_token: str,
        reply_to: str | None = None,
    ) -> InteractionHandle:
        result = await self.call_platform_api(
            'interaction.request',
            {
                'request': request.model_dump(mode='json'),
                'callback_token': callback_token,
                'reply_target': {
                    'target_type': target_type,
                    'target_id': target_id,
                    'message_id': reply_to,
                },
            },
        )
        handle = InteractionHandle.model_validate(result)
        handle.context['request'] = request.model_dump(mode='json')
        return handle

    async def update_interaction(
        self,
        handle: InteractionHandle,
        state: str,
        submission: InteractionSubmission | None = None,
    ) -> InteractionHandle:
        if 'interaction.acknowledge' not in self.get_supported_apis():
            return handle
        result = await self.call_platform_api(
            'interaction.acknowledge',
            {
                'update_target': handle.model_dump(mode='json'),
                'request': handle.context.get('request') or {},
                'callback_context': handle.context.get('callback_context') or {},
                'submission': submission.model_dump(mode='json') if submission else {},
                'state': state,
            },
        )
        return InteractionHandle.model_validate(result) if isinstance(result, dict) else handle
