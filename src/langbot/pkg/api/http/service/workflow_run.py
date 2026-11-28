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
    triggers: list | None = None,
    event: dict | None = None,
) -> dict:
    require_permission(context, Permission.RUNTIME_OPERATE)
    if graph is not None:
        require_permission(context, Permission.RESOURCE_MANAGE)
        if not isinstance(graph, dict):
            raise ValueError('graph must be an object')
    if event is not None:
        message = message or ''
    if not isinstance(message, str) or (event is None and not message.strip()) or len(message) > 100_000:
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
    event_data = None
    if event is not None:
        event_data, message_context, platform_context = _test_event(event, message, session_id)
    else:
        platform_context = {
            'event_type': 'message.received',
            'data': {'message_id': message_context.message_id, 'text': message},
            'actor': {'actor_type': 'user', 'actor_id': 'manual', 'actor_name': 'Manual run'},
            'subject': None,
            'delivery': {
                'reply_target': {
                    'target_type': session_type,
                    'target_id': session_id,
                    'message_id': message_context.message_id,
                    **({'group_id': session_id} if session_type == 'group' else {}),
                }
            },
        }
    runtime.platform_session = _mock_session(platform_context)

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
    args = None if event is not None else await _command_args(ap, execution_context, workflow_uuid, message, triggers)
    error = None
    try:
        execution_uuid, runtime = await ap.workflow_service.execute_workflow(
            execution_context,
            workflow_uuid,
            trigger_type='test',
            graph=graph,
            trigger_data={
                'message': message,
                **({'args': args} if args is not None else {}),
                **({'event': event_data} if event_data is not None else {}),
            },
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


async def _command_args(ap, execution_context, workflow_uuid, message, triggers):
    """Parse `/name args` like the bot would when the text calls one of this workflow's commands."""
    from ....workflow.triggers import parse_command_args

    body = message.strip()
    if not body.startswith('/'):
        return None
    if triggers is None:
        workflow = await ap.workflow_service.get_workflow(execution_context, workflow_uuid)
        triggers = (workflow or {}).get('triggers') or []
    name, _, rest = body[1:].partition(' ')
    for trigger in triggers if isinstance(triggers, list) else []:
        if not isinstance(trigger, dict) or trigger.get('type') != 'command':
            continue
        if name in (trigger.get('name'), *(trigger.get('aliases') or [])):
            return parse_command_args(trigger, rest.strip())[0]
    return None


def _mock_session(platform_context):
    """Simulate platform and event actions exactly like an Agent debug run: nothing reaches a bot."""
    from ....agent.runner.platform_tools import PLATFORM_TOOL_DEFINITIONS
    from ....workflow.operations import platform_session

    delivery = platform_context.setdefault('delivery', {})
    delivery['surface'] = 'webui'
    delivery['platform_capabilities'] = {
        'event_type': platform_context.get('event_type'),
        'debug': True,
        'debug_mock': True,
        'supported_apis': sorted({tool.api for tool in PLATFORM_TOOL_DEFINITIONS}),
        'mock_options': {},
    }
    return platform_session(context=platform_context)


def _test_event(event, message, session_id):
    """Build a simulated platform event the way a bot would deliver it."""
    import json

    from langbot_plugin.api.entities.builtin.platform import events as platform_events
    from ....platform.botmgr import RuntimeBot

    if not isinstance(event, dict) or not isinstance(event.get('type'), str) or not event['type'].strip():
        raise ValueError('event.type is required')
    event_type = event['type'].strip()
    if event_type == 'message.received':
        raise ValueError('Test received messages with text instead of an event')
    data = event.get('data') if event.get('data') is not None else {}
    if not isinstance(data, dict) or len(json.dumps(data, ensure_ascii=False)) > 64_000:
        raise ValueError('event.data must be an object under 64 KB')
    try:
        typed = platform_events.parse_eba_event({**data, 'type': event_type})
    except Exception:
        typed = platform_events.PlatformSpecificEvent(action=event_type, data=data)
        typed.type = event_type
    dumped = typed.model_dump(mode='json', exclude={'source_platform_object'})
    target_type, target_id, metadata = RuntimeBot._infer_reply_target(typed)
    person = getattr(typed, 'user', None) or getattr(typed, 'user_id', None)
    if not target_id and person:
        target_type, target_id = 'person', str(getattr(person, 'id', person))
    actor = RuntimeBot._infer_actor_context(typed)
    sender = next(
        (
            getattr(typed, name)
            for name in ('member', 'user', 'editor', 'operator', 'inviter')
            if getattr(typed, name, None)
        ),
        None,
    )
    message_id = str(getattr(typed, 'message_id', '') or '')
    message_context = MessageContext(
        message_id=message_id,
        message_content=message
        or ''.join(part.text for part in getattr(typed, 'new_content', None) or [] if isinstance(part, Plain)),
        sender_id=str(getattr(sender, 'id', '') or getattr(typed, 'user_id', '') or ''),
        sender_name=getattr(sender, 'nickname', '') or '',
        platform='manual',
        conversation_id=target_id or session_id,
        is_group=target_type == 'group',
        group_id=target_id if target_type == 'group' else None,
    )
    platform_context = {
        'event_type': event_type,
        'data': {key: value for key, value in dumped.items() if value is not None},
        'actor': actor.model_dump(mode='json') if actor else None,
        'subject': RuntimeBot._infer_subject_context(typed).model_dump(mode='json'),
        'delivery': {
            'reply_target': {
                'target_type': target_type,
                'target_id': target_id,
                'message_id': message_id or None,
                **metadata,
            }
        },
    }
    return dumped, message_context, platform_context
