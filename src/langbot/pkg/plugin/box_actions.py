"""Authenticated plugin Box resources and invocation file operations."""

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.runtime.io.handler import ActionResponse
from ..box.runner import RunnerBoxService
from .agent_run_support import _validate_agent_run_session


def register(h):
    async def dispatch(action, data):
        from .handler import _resolve_action_query

        action_context, _ = await h._require_plugin_action_context()
        context = h._execution_context(action_context)
        query = None
        run_id = data.get('run_id')
        context_actions = {Action.BIND_BOX, Action.IMPORT_BOX_ATTACHMENTS, Action.EXPORT_BOX_FILES}
        if action in context_actions and not run_id:
            return ActionResponse.error('run_id is required for Box context operations')
        if run_id:
            session, error = await _validate_agent_run_session(
                run_id,
                data.get('caller_plugin_identity'),
                h.ap,
                'Box API',
                api_capability='box',
            )
            if error:
                return error
            query = _resolve_action_query(data, session, h.ap, action_context)
            if query is None:
                return ActionResponse.error('The current execution context has expired')
        service = RunnerBoxService(h.ap.box_service)
        if action == Action.GET_BOX_STATUS:
            return ActionResponse.success(await service.status(context))
        if action == Action.LIST_BOXES:
            return ActionResponse.success(
                {'items': [service.public_session(s) for s in await service.sessions(context)]}
            )
        if action == Action.ACQUIRE_BOX:
            request = {k: v for k, v in data.items() if k not in {'run_id', 'caller_plugin_identity'}}
            return ActionResponse.success(await service.acquire(context, request, query))
        if action == Action.BIND_BOX:
            return ActionResponse.success(await service.bind(context, query, run_id, data['box_id']))
        if action == Action.IMPORT_BOX_ATTACHMENTS:
            return ActionResponse.success(await service.import_attachments(query, data.get('attachment_ids')))
        if action == Action.EXPORT_BOX_FILES:
            return ActionResponse.success(await service.export_files(query))
        raise ValueError('Unsupported Box action')

    def register_action(action):
        @h.action(action)
        async def invoke(data):
            try:
                return await dispatch(action, data)
            except Exception as exc:
                return ActionResponse.error(f'{type(exc).__name__}: {exc}')

    for action in (
        Action.GET_BOX_STATUS,
        Action.LIST_BOXES,
        Action.ACQUIRE_BOX,
        Action.BIND_BOX,
        Action.IMPORT_BOX_ATTACHMENTS,
        Action.EXPORT_BOX_FILES,
    ):
        register_action(action)
