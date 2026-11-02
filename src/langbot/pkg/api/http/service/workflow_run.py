from __future__ import annotations

import uuid
from langbot_plugin.api.entities.builtin.platform.message import Plain

from ..authz import Permission, require_permission
from ..context import ExecutionContext, RequestContext
from ....workflow.entities import MessageContext
from ....workflow.runtime import WorkflowRuntime
from .workflow import WorkflowExecutionFailedError


async def run_workflow(
    ap, context: RequestContext, workflow_uuid: str, message: str, *, session_type: str = 'person'
) -> dict:
    require_permission(context, Permission.RUNTIME_OPERATE)
    if not isinstance(message, str) or not message.strip() or len(message) > 100_000:
        raise ValueError('message must contain 1..100000 characters')
    if session_type not in ('person', 'group'):
        raise ValueError('session_type must be person or group')
    execution_context = ExecutionContext.from_request(context)
    runtime = WorkflowRuntime(execution_context)
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
    error = None
    try:
        execution_uuid, runtime = await ap.workflow_service.execute_workflow(
            execution_context,
            workflow_uuid,
            trigger_type='message',
            trigger_data={'message': message},
            message_context=message_context,
            session_id=session_id,
            user_id='manual',
            runtime=runtime,
        )
        status = 'completed'
    except WorkflowExecutionFailedError as exc:
        execution_uuid, status, error = exc.execution_id, 'failed', exc.message
    return {
        'execution_uuid': execution_uuid,
        'status': status,
        'error': error,
        'replies': [''.join(part.text for part in chain if isinstance(part, Plain)) for chain in runtime.replies],
    }
