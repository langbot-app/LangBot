"""STREAM-mode handler for DingTalk card action button clicks.

DingTalk delivers card-action callbacks over the same WebSocket stream used
for chatbot messages, under the topic `/v1.0/card/instances/callback`. This
module subclasses `dingtalk_stream.CallbackHandler` and forwards the parsed
payload to a coroutine the adapter registers, so the resume-paused-workflow
logic stays in the platform adapter where it belongs.

The `CardCallbackMessage` returned by `from_dict` exposes:

* `card_instance_id` (from `outTrackId`) — the card whose button was clicked
* `user_id`  — the clicker's userId
* `content`  — parsed JSON; the click params live here. Where exactly inside
               `content` they sit depends on the template binding. We probe
               the common paths.
* `extension` — parsed JSON; any extra data we set when delivering the card.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

import dingtalk_stream  # type: ignore
from dingtalk_stream import AckMessage
from dingtalk_stream.card_callback import CardCallbackMessage


_PARAM_PATHS = (
    ('params',),
    ('cardPrivateData', 'params'),
    ('userPrivateData', 'params'),
    ('actionData', 'cardPrivateData', 'params'),
)


def _extract_params(content: dict) -> dict:
    """Return the action params dict regardless of where the template put it."""
    for path in _PARAM_PATHS:
        node = content
        for key in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
            if node is None:
                break
        if isinstance(node, dict) and node:
            return node
    return {}


def _merge_params(*sources: dict) -> dict:
    merged = {}
    for source in sources:
        if isinstance(source, dict):
            merged.update(source)
    return merged


class DingTalkCardActionHandler(dingtalk_stream.CallbackHandler):
    def __init__(
        self,
        dingtalk_stream_client,
        on_action: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        super().__init__()
        self.dingtalk_client = dingtalk_stream_client
        self.on_action = on_action

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        try:
            message = CardCallbackMessage.from_dict(callback.data)
            content = message.content if isinstance(message.content, dict) else {}

            # `CardCallbackMessage.from_dict` does not surface `actionId` (the
            # top-level field that ButtonGroup's sendCardRequest event puts
            # there). Pull it from the raw callback.data instead.
            raw = callback.data if isinstance(callback.data, dict) else {}
            params = _merge_params(_extract_params(content), _extract_params(raw))
            action_id = raw.get('actionId') or ''
            if not action_id:
                # Some templates nest it under actionData / cardPrivateData.
                action_data = raw.get('actionData') or {}
                if isinstance(action_data, dict):
                    action_id = action_data.get('actionId') or action_id
                    if not action_id:
                        cpd = action_data.get('cardPrivateData') or {}
                        if isinstance(cpd, dict):
                            ids = cpd.get('actionIds')
                            if isinstance(ids, list) and ids:
                                action_id = str(ids[0])

            payload = {
                'out_track_id': message.card_instance_id,
                'user_id': message.user_id,
                'corp_id': message.corp_id,
                'action_id': action_id,
                'params': params,
                'raw_content': message.content,
                'extension': message.extension if isinstance(message.extension, dict) else {},
            }
            if self.on_action is not None:
                await self.on_action(payload)
        except Exception as e:
            self.logger.error(f'DingTalkCardActionHandler.process error: {e}')
        return AckMessage.STATUS_OK, 'OK'
