"""Run-authorized input reads, backed by Artifact storage on first model read."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import replace
import mimetypes
from typing import Any

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.runtime.io.handler import ActionResponse

from ..agent.runner import input_media
from ..api.context import PrincipalContext, PrincipalType
from ..box.runner import input_files
from ..i18n import t
from ..storage.artifact_reader import read_artifact_content
from .agent_run_support import _validate_agent_run_session


def register(h):
    async def handle(data, *, render):
        from .handler import _resolve_action_query

        run_id, ref = data.get('run_id'), data.get('ref')
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
        lock = getattr(query, '_input_attachment_lock', None)
        if lock is None:
            lock = asyncio.Lock()
            object.__setattr__(query, '_input_attachment_lock', lock)
        async with lock:
            already_read = getattr(query, '_input_attachment_read_bytes', 0)
            remaining = input_media.MAX_RUN_READ_BYTES - already_read
            materialized = getattr(query, '_input_materialized_refs', set())
            charge_source = not render or ref not in materialized
            if charge_source and remaining <= 0:
                return ActionResponse.error('Input attachment read budget for this run is exhausted')
            returned_bytes = getattr(query, '_input_content_read_bytes', 0)
            if render and returned_bytes >= input_media.MAX_RUN_READ_BYTES:
                return ActionResponse.error(t('Input attachment content budget for this run is exhausted'))
            limit = (
                min(input_media.MAX_ATTACHMENT_BYTES, remaining) if charge_source else input_media.MAX_ATTACHMENT_BYTES
            )
            uploaded_ids = getattr(query, '_input_artifact_ids', frozenset())
            cached = getattr(query, '_input_artifact_refs', {})
            run_context = getattr(query, '_execution_context', None)
            if run_context is not None:
                run_context = replace(
                    run_context, trigger_principal=PrincipalContext(PrincipalType.PROCESSOR, run_id=run_id)
                )
            if ref in uploaded_ids:
                result = await h.ap.artifact_service.read_bound_run_input(run_context, ref, max_bytes=limit)
                payload, metadata = result['content'], result['metadata']
            elif ref in cached:
                result = await h.ap.artifact_service.read_run_input(run_context, cached[ref], max_bytes=limit)
                payload, metadata = result['content'], result['metadata']
            else:
                component = input_files(query).get(ref)
                if component is None:
                    return ActionResponse.error(f'Unknown input attachment reference: {ref}')
                resolved = await input_media.read_component_bytes(
                    component,
                    max_bytes=limit,
                    adapter=getattr(query, 'adapter', None),
                )
                if resolved is None:
                    return ActionResponse.error(
                        f'Input attachment {ref} cannot be read: no payload is available or it exceeds the size limit'
                    )
                payload, mime_type = resolved
                name = getattr(component, 'name', None) or None
                metadata = {'ref': ref, 'name': name, 'mime_type': mime_type, 'size': len(payload)}
                if render:
                    name = (name or ref).replace('\\', '/').rsplit('/', 1)[-1]
                    mime_type = mime_type.split(';', 1)[0].strip()
                    if mime_type == 'application/octet-stream':
                        mime_type = mimetypes.guess_type(name)[0] or mime_type
                    metadata = await h.ap.artifact_service.create_run_input(run_context, name, payload, mime_type)
                    cached[ref] = metadata['id']
                    object.__setattr__(query, '_input_artifact_refs', cached)
            if charge_source:
                object.__setattr__(query, '_input_attachment_read_bytes', already_read + len(payload))
            if render:
                materialized.add(ref)
                object.__setattr__(query, '_input_materialized_refs', materialized)
                contents = await read_artifact_content(
                    payload,
                    {**metadata, 'ref': ref},
                    **{
                        key: data[key]
                        for key in ('mode', 'offset', 'max_chars', 'page_start', 'page_end')
                        if key in data
                    },
                )
                # Text continuation pays for returned content, not the entire cached source again.
                output_size = sum(len(item['text'].encode('utf-8')) for item in contents if item['type'] == 'text')
                if any(item['type'] != 'text' for item in contents):
                    output_size += len(payload)
                if output_size > input_media.MAX_RUN_READ_BYTES - returned_bytes:
                    return ActionResponse.error(t('Input attachment content budget for this run is exhausted'))
                object.__setattr__(query, '_input_content_read_bytes', returned_bytes + output_size)
                return ActionResponse.success({'contents': contents})
            return ActionResponse.success(
                {
                    'ref': ref,
                    'name': metadata['name'],
                    'mime_type': metadata['mime_type'],
                    'size': len(payload),
                    'content': base64.b64encode(payload).decode('ascii'),
                }
            )

    @h.action(Action.READ_INPUT_ATTACHMENT)
    async def read_input_attachment(data: dict[str, Any]) -> ActionResponse:
        return await handle(data, render=False)

    @h.action(Action.READ_INPUT_ATTACHMENT_CONTENT)
    async def read_input_attachment_content(data: dict[str, Any]) -> ActionResponse:
        return await handle(data, render=True)
