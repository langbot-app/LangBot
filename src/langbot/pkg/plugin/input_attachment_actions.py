"""Run-scoped access to the bytes of current-event input attachments."""

from __future__ import annotations

import base64
from typing import Any

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.runtime.io.handler import ActionResponse

from ..agent.runner import input_media
from ..box.runner import input_files
from .agent_run_support import _validate_agent_run_session


def register(h):
    @h.action(Action.READ_INPUT_ATTACHMENT)
    async def read_input_attachment(data: dict[str, Any]) -> ActionResponse:
        """Resolve one attachment of the run's own input by ref.

        Bytes are resolved on demand and never cached or logged; each read is
        bounded per attachment and cumulatively per run.
        """
        from .handler import _resolve_action_query

        run_id = data.get('run_id')
        ref = data.get('ref')
        if not run_id:
            return ActionResponse.error('run_id is required')
        if not isinstance(ref, str) or not ref:
            return ActionResponse.error('ref is required')

        action_context, _ = await h._require_plugin_action_context()
        session, error = await _validate_agent_run_session(
            run_id,
            data.get('caller_plugin_identity'),
            h.ap,
            'Input attachment',
            api_capability='input_attachments',
        )
        if error:
            return error
        query = _resolve_action_query(data, session, h.ap, action_context)
        if query is None:
            return ActionResponse.error('The current execution context has expired')

        component = input_files(query).get(ref)
        if component is None:
            return ActionResponse.error(f'Unknown input attachment reference: {ref}')

        already_read = getattr(query, '_input_attachment_read_bytes', 0)
        remaining = input_media.MAX_RUN_READ_BYTES - already_read
        if remaining <= 0:
            return ActionResponse.error('Input attachment read budget for this run is exhausted')
        resolved = await input_media.read_component_bytes(
            component,
            max_bytes=min(input_media.MAX_ATTACHMENT_BYTES, remaining),
            adapter=getattr(query, 'adapter', None),
        )
        if resolved is None:
            return ActionResponse.error(
                f'Input attachment {ref} cannot be read: no payload is available or it exceeds the size limit'
            )
        payload, mime_type = resolved
        object.__setattr__(query, '_input_attachment_read_bytes', already_read + len(payload))
        h.ap.logger.debug(f'Read input attachment {ref} for run {run_id}: {len(payload)} bytes')
        return ActionResponse.success(
            {
                'ref': ref,
                'name': getattr(component, 'name', None) or None,
                'mime_type': mime_type,
                'size': len(payload),
                'content': base64.b64encode(payload).decode('ascii'),
            }
        )
