from __future__ import annotations

import uuid
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain

from ..authz import Permission, require_permission
from ..context import ExecutionContext, RequestContext
from ....workflow.entities import MessageContext
from ....workflow.runtime import WorkflowRuntime
from .workflow import WorkflowExecutionFailedError


async def run_workflow(
    ap,
    context: RequestContext,
    workflow_uuid: str,
    message: str,
    *,
    session_type: str = 'person',
    graph: dict | None = None,
) -> dict:
    require_permission(context, Permission.RUNTIME_OPERATE)
    if graph is not None:
        require_permission(context, Permission.RESOURCE_MANAGE)
        if not isinstance(graph, dict):
            raise ValueError('graph must be an object')
    if not isinstance(message, str) or not message.strip() or len(message) > 100_000:
        raise ValueError('message must contain 1..100000 characters')
    if session_type not in ('person', 'group'):
        raise ValueError('session_type must be person or group')
    execution_context = ExecutionContext.from_request(context)
    runtime = WorkflowRuntime(execution_context, test=True)
    session_id = str(uuid.uuid4())
    message_context = MessageContext(
        message_id=str(uuid.uuid4()),
        message_content=message,
        sender_id='manual',
        sender_name='Manual run',
        platform='manual',
        conversation_id=session_id,
        is_group=session_type == 'group',
        group_id=session_id if session_type == 'group' else None,
    )

    def dispatcher(parent, original):
        async def forward(handoff):
            target, ident = handoff['target_type'], handoff['target_uuid']
            text = handoff.get('text') or original
            if target == 'chat':
                from .pipeline_run import run_pipeline

                result = await run_pipeline(ap, context, ident, text)
                if result['status'] != 'completed':
                    raise ValueError(result.get('error') or 'Chat handoff failed')
                parent.replies.extend(MessageChain([Plain(text=item['content'])]) for item in result['replies'])
            elif target == 'agent':
                result = await ap.agent_service.debug_agent(
                    context, ident, {'text': text, 'conversation_id': session_id}
                )
                if result['final_text']:
                    parent.replies.append(MessageChain([Plain(text=result['final_text'])]))
            elif target == 'workflow':
                child = WorkflowRuntime(execution_context, depth=parent.depth + 1, test=True)
                child.dispatch = dispatcher(child, text)
                await ap.workflow_service.execute_workflow(
                    execution_context,
                    ident,
                    trigger_type='workflow',
                    session_id=session_id,
                    message_context=message_context.model_copy(update={'message_content': text}),
                    runtime=child,
                )
                parent.replies.extend(child.replies)

        return forward

    runtime.dispatch = dispatcher(runtime, message)
    error = None
    try:
        execution_uuid, runtime = await ap.workflow_service.execute_workflow(
            execution_context,
            workflow_uuid,
            trigger_type='test',
            graph=graph,
            trigger_data={'message': message},
            message_context=message_context,
            session_id=session_id,
            user_id='manual',
            runtime=runtime,
        )
        status = 'completed'
    except WorkflowExecutionFailedError as exc:
        execution_uuid, status, error = exc.execution_id, 'failed', exc.message
    execution = await ap.workflow_service.get_execution(context, workflow_uuid, execution_uuid)
    return {
        'execution_uuid': execution_uuid,
        'status': status,
        'error': error,
        'steps': execution['steps'],
        'handoff': execution.get('handoff'),
        'replies': [''.join(part.text for part in chain if isinstance(part, Plain)) for chain in runtime.replies],
    }
