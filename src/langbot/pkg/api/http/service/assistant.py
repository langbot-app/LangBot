"""In-process management assistant using the existing model and resource services."""

import asyncio
import contextlib
import json
import uuid

import sqlalchemy as sa
from langbot_plugin.api.entities.builtin.provider.message import Message

from ....entity.persistence.assistant import AssistantConversation as Conversation
from ....provider.modelmgr.errors import RequesterError
from ...application.operation_docs import get_operation_doc
from ..authz import Permission, require_permission
from ..context import ExecutionContext, PrincipalType
from .assistant_disclosure import PresentSetupPlan, build_system_prompt, is_write
from .assistant_context import model_context
from .assistant_tools import execute_tool, tool_definitions, validate_call
from .secrets import redact_secrets


SYSTEM_PROMPT = build_system_prompt()


class AssistantError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code = code
        self.status = status
        super().__init__(code)


class AssistantService:
    def __init__(self, ap):
        self.ap = ap
        # ponytail: per-process admission; shared quotas if multiple workers need a global ceiling.
        self._slots = asyncio.Semaphore(4)
        self._runs = {}

    async def list_conversations(self, context):
        self._scope(context, '')
        result = await self.ap.persistence_mgr.execute_async(
            sa.select(Conversation)
            .where(
                Conversation.workspace_uuid == context.workspace_uuid,
                Conversation.account_uuid == context.account_uuid,
            )
            .order_by(Conversation.updated_at.desc(), Conversation.uuid)
            .limit(100)
        )
        return [
            dict(
                uuid=row['uuid'],
                status=row['status'],
                revision=row['revision'],
                title=next(
                    (
                        m.get('content', '')[:80]
                        for m in row['messages']
                        if m['role'] == 'user' and isinstance(m.get('content'), str)
                    ),
                    '',
                ),
            )
            for row in result.mappings()
        ]

    async def progress(self, context, conversation_id):
        conversation = await self.get(context, conversation_id)
        run = self._runs.get(conversation_id)
        if run:
            return {**(run['snapshot'] or self.public_view(conversation)), 'progress': run['progress']}
        return self.public_view(conversation)

    def start_run(self, context, conversation_id, body):
        """Own execution independently of any HTTP subscriber; never block on a slow browser."""
        if conversation_id in self._runs:
            raise AssistantError('stale_turn')
        if len(self._runs) >= 4:
            raise AssistantError('busy', 429)
        queue = asyncio.Queue(maxsize=32)
        run = {
            'queue': queue,
            'snapshot': None,
            'progress': {},
            'stopping': False,
            'revision': body.revision + 1,
            'started': asyncio.Event(),
        }
        self._runs[conversation_id] = run

        async def emit(frame):
            if frame['kind'] == 'snapshot':
                run['snapshot'] = frame['data']
                run['progress'] = {}
            elif frame['kind'] == 'text':
                run['progress']['text'] = frame['data']['text']
            elif frame['kind'] == 'phase':
                run['progress'].update(frame['data'])
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(frame)

        async def execute():
            run['started'].set()
            tenant_scope = getattr(self.ap.persistence_mgr, 'tenant_scope', None)
            scope = tenant_scope(context.workspace_uuid) if callable(tenant_scope) else contextlib.nullcontext()
            try:
                async with scope:
                    try:
                        conversation = await self.turn(
                            context,
                            conversation_id,
                            body.revision,
                            body.text,
                            body.approved,
                            str(body.model_uuid) if body.model_uuid else None,
                            on_event=emit,
                            choices=body.choices,
                            continue_run=body.continue_run is True,
                        )
                    except asyncio.CancelledError:
                        conversation = await self.get(context, conversation_id)
                        # Preserve interrupted tool outcomes; stopping cannot undo an external write.
                        if run['stopping'] and (
                            conversation['error'] == 'result_unknown'
                            or (conversation['status'] == 'running' and conversation['revision'] == run['revision'])
                        ):
                            await self._save(context, conversation, 'failed', 'stopped')
                    await emit({'kind': 'completed', 'data': self.public_view(conversation)})
            except AssistantError as exc:
                await emit({'kind': 'error', 'code': exc.code})
            except Exception:
                self.ap.logger.exception('Assistant background run failed')
                await emit({'kind': 'error', 'code': 'turn_failed'})
            finally:
                self._runs.pop(conversation_id, None)

        run['task'] = asyncio.create_task(execute())
        return queue

    async def stop(self, context, conversation_id, revision):
        require_permission(context, Permission.RUNTIME_OPERATE)
        conversation = await self.get(context, conversation_id)
        run = self._runs.get(conversation_id)
        if run and run['revision'] != revision:
            raise AssistantError('stale_turn')
        if not run:
            if conversation['revision'] != revision:
                raise AssistantError('stale_turn')
            return self.public_view(conversation)
        await run['started'].wait()
        if not run['stopping']:
            run['stopping'] = True
            run['task'].cancel()
        await asyncio.shield(run['task'])
        return self.public_view(await self.get(context, conversation_id))

    async def recommended_model(self, context):
        require_permission(context, Permission.RUNTIME_OPERATE)
        try:
            recommended = await self.ap.space_service.get_recommended_assistant_model(context)
            model = await self.ap.model_mgr.get_model_by_uuid(
                ExecutionContext.from_request(context), recommended['uuid']
            )
            if 'func_call' not in (model.model_entity.abilities or []):
                raise ValueError('Recommended model does not support tools')
            return {'uuid': recommended['uuid'], 'name': model.model_entity.name}
        except Exception as exc:
            raise AssistantError('model_unavailable', 503) from exc

    async def _invoke(self, model, kwargs, on_event):
        if on_event is None:
            return await model.provider.invoke_llm(**kwargs)
        message = {'role': 'assistant', 'content': ''}
        calls = {}
        finished = False
        async for chunk in model.provider.invoke_llm_stream(**kwargs):
            finished = finished or chunk.is_final
            content = chunk.content or ''
            if isinstance(content, list):
                content = ''.join(item.text or '' for item in content if item.type == 'text')
            if chunk.all_content is not None:
                message['content'] = chunk.all_content
            else:
                message['content'] += content
            for field in ('resp_message_id', 'provider_specific_fields'):
                value = getattr(chunk, field, None)
                if value is not None:
                    if field == 'provider_specific_fields':
                        message[field] = {**message.get(field, {}), **value}
                    else:
                        message[field] = value
            for call in chunk.tool_calls or []:
                value = call.model_dump(mode='json')
                if call.id in calls:
                    saved = calls[call.id]
                    saved['function']['arguments'] += call.function.arguments or ''
                    if call.function.name:
                        saved['function']['name'] = call.function.name
                    if value.get('provider_specific_fields'):
                        saved['provider_specific_fields'] = {
                            **(saved.get('provider_specific_fields') or {}),
                            **value['provider_specific_fields'],
                        }
                else:
                    calls[call.id] = value
            if len(calls) > 32 or len(json.dumps(message, ensure_ascii=False)) + len(json.dumps(calls)) > 128000:
                raise AssistantError('response_too_large')
            if content or chunk.all_content is not None:
                await on_event({'kind': 'text', 'data': {'text': message['content']}})
        if not finished:
            raise AssistantError('stream_interrupted')
        if calls:
            message['tool_calls'] = list(calls.values())
        return Message.model_validate(message)

    async def _snapshot(self, conversation, on_event):
        if on_event is not None:
            await on_event({'kind': 'snapshot', 'data': self.public_view(conversation)})

    @staticmethod
    def _scope(context, conversation_id):
        if context.principal.principal_type != PrincipalType.ACCOUNT or not context.account_uuid:
            raise AssistantError('account_required', 403)
        require_permission(context, Permission.RESOURCE_VIEW)
        return (
            Conversation.uuid == conversation_id,
            Conversation.workspace_uuid == context.workspace_uuid,
            Conversation.account_uuid == context.account_uuid,
        )

    async def create(self, context):
        conversation_id = str(uuid.uuid4())
        self._scope(context, conversation_id)
        await self.ap.persistence_mgr.execute_async(
            sa.insert(Conversation).values(
                uuid=conversation_id,
                workspace_uuid=context.workspace_uuid,
                account_uuid=context.account_uuid,
                revision=0,
                status='ready',
                messages=[],
            )
        )
        return await self.get(context, conversation_id)

    async def get(self, context, conversation_id):
        result = await self.ap.persistence_mgr.execute_async(
            sa.select(Conversation).where(*self._scope(context, conversation_id))
        )
        row = result.mappings().first()
        if row is None:
            raise AssistantError('conversation_not_found', 404)
        return dict(row)

    @staticmethod
    def _calls(message):
        calls = message.get('tool_calls') or []
        if len(calls) > 8:
            raise ValueError('Too many tool calls')
        return calls

    @staticmethod
    def public_view(conversation):
        messages = []
        calls = {}
        for message in conversation['messages']:
            calls.update({call['id']: call['function'] for call in message.get('tool_calls') or []})
            content = message.get('content') or ''
            if isinstance(content, list):
                content = '\n'.join(item.get('text') or '' for item in content if item.get('type') == 'text')
            if content:
                visible = {'role': message['role'], 'content': content}
                if message['role'] == 'tool':
                    function = calls.get(message.get('tool_call_id'), {})
                    try:
                        arguments = json.loads(function.get('arguments') or '{}')
                    except json.JSONDecodeError:
                        arguments = {'unparsed': function['arguments']}
                    visible['tool'] = {
                        'name': function.get('name', ''),
                        'arguments': arguments,
                        'result': json.loads(content),
                    }
                messages.append(visible)
        pending = []
        choice_plan = None
        if conversation['status'] == 'approval':
            for call in conversation['messages'][-1].get('tool_calls') or []:
                function = call['function']
                name = function['name']
                arguments = json.loads(function['arguments'] or '{}')
                item = {
                    'name': name,
                    'arguments': arguments,
                }
                if name == 'workspace_call':
                    op_id = arguments.get('operation_id')
                    if op_id and isinstance(op_id, str):
                        doc = get_operation_doc(op_id)
                        item['operation'] = {
                            'id': op_id,
                            'label': doc.label,
                            'risk': doc.risk,
                            'summary': doc.summary,
                        }
                pending.append(item)
        elif conversation['status'] == 'choice':
            call = conversation['messages'][-1]['tool_calls'][0]
            choice_plan = PresentSetupPlan.model_validate_json(call['function']['arguments']).model_dump()
        return {
            'uuid': conversation['uuid'],
            'revision': conversation['revision'],
            'status': conversation['status'],
            'messages': messages,
            'pending': pending,
            'choice_plan': choice_plan,
            'error': conversation['error'],
            'model_name': conversation['model_name'],
            'model_uuid': conversation['model_uuid'],
        }

    async def _save(self, context, conversation, status, error=None):
        result = await self.ap.persistence_mgr.execute_async(
            sa.update(Conversation)
            .where(
                *self._scope(context, conversation['uuid']),
                Conversation.revision == conversation['revision'],
            )
            .values(
                messages=conversation['messages'],
                status=status,
                error=error,
                model_name=conversation['model_name'],
                model_uuid=conversation['model_uuid'],
                updated_at=sa.func.now(),
            )
        )
        if result.rowcount != 1:
            raise AssistantError('stale_turn')
        conversation.update(status=status, error=error)

    async def turn(
        self,
        context,
        conversation_id,
        revision,
        text=None,
        approved=None,
        model_uuid=None,
        on_event=None,
        choices=None,
        continue_run=False,
    ):
        require_permission(context, Permission.RUNTIME_OPERATE)
        if model_uuid is not None and text is None and not continue_run:
            raise AssistantError('invalid_input', 400)
        if self._slots.locked():
            raise AssistantError('busy', 429)
        async with self._slots:
            conversation = await self.get(context, conversation_id)
            investigation_paused = conversation['error'] in {'round_limit', 'no_progress', 'time_budget'}
            model_error = conversation['error'] in {
                'model_quota_exceeded',
                'model_auth_failed',
                'model_permission_denied',
                'model_request_failed',
                'model_unavailable',
            }
            resumable = (investigation_paused or model_error) and conversation['status'] in {'paused', 'failed'}
            expected_status = 'approval' if approved is not None else 'choice' if choices is not None else None
            if continue_run:
                expected_status = conversation['status'] if resumable else None
            if text is not None:
                expected_status = conversation['status'] if conversation['status'] == 'choice' or resumable else 'ready'
            if conversation['status'] != expected_status or conversation['revision'] != revision:
                raise AssistantError('stale_turn')
            if expected_status == 'choice' and choices is not None:
                plan = PresentSetupPlan.model_validate_json(
                    conversation['messages'][-1]['tool_calls'][0]['function']['arguments']
                )
                valid = {field.key: {option.id for option in field.options} for field in plan.fields}
                if set(choices) != set(valid) or any(value not in valid[key] for key, value in choices.items()):
                    raise AssistantError('invalid_input', 400)
            selected_model = None
            if model_uuid is not None:
                try:
                    selected_model = await self.ap.model_mgr.get_model_by_uuid(
                        ExecutionContext.from_request(context), model_uuid
                    )
                    if 'func_call' not in (selected_model.model_entity.abilities or []):
                        raise ValueError('Model does not support tool calls')
                except Exception as exc:
                    raise AssistantError('model_unavailable', 400) from exc
            result = await self.ap.persistence_mgr.execute_async(
                sa.update(Conversation)
                .where(
                    *self._scope(context, conversation_id),
                    Conversation.revision == revision,
                    Conversation.status == expected_status,
                )
                .values(status='running', revision=revision + 1, error=None, updated_at=sa.func.now())
            )
            if result.rowcount != 1:
                raise AssistantError('stale_turn')
            conversation['revision'] += 1
            uncertain_write = False
            try:
                async with asyncio.timeout(600):
                    if model_uuid is not None and model_uuid != conversation['model_uuid']:
                        # Provider signatures and response IDs belong to the previous model.
                        for message in conversation['messages']:
                            message['provider_specific_fields'] = None
                            message['resp_message_id'] = None
                            for call in message.get('tool_calls') or []:
                                call['provider_specific_fields'] = None
                        conversation['model_uuid'] = model_uuid
                        conversation['model_name'] = selected_model.model_entity.name
                    if expected_status == 'choice':
                        call = conversation['messages'][-1]['tool_calls'][0]
                        self._append_result(
                            conversation,
                            call,
                            {'selected': choices} if choices is not None else {'status': 'revised'},
                        )
                    if text is not None:
                        conversation['messages'].append(Message(role='user', content=text).model_dump(mode='json'))
                    await self._save(context, conversation, 'running')
                    try:
                        if not conversation['model_uuid']:
                            recommended = await self.recommended_model(context)
                            conversation['model_uuid'] = recommended['uuid']
                        execution = ExecutionContext.from_request(context)
                        model = selected_model or await self.ap.model_mgr.get_model_by_uuid(
                            execution, conversation['model_uuid']
                        )
                        if 'func_call' not in (model.model_entity.abilities or []):
                            raise ValueError('Recommended model does not support tool calls')
                        conversation['model_name'] = model.model_entity.name
                    except Exception:
                        await self._save(context, conversation, 'failed', 'model_unavailable')
                        return conversation
                    if approved is not None:
                        calls = self._calls(conversation['messages'][-1])
                        uncertain_write = any(
                            is_write(call['function']['name'], json.loads(call['function']['arguments'] or '{}'))
                            for call in calls
                        )
                        await self._execute(context, conversation, calls, approved, on_event)
                        uncertain_write = False
                    round_index = 0
                    repeated_call = None
                    repeated_count = 0
                    while True:
                        round_index += 1
                        await self._snapshot(conversation, on_event)
                        if on_event is not None:
                            await on_event({'kind': 'phase', 'data': {'phase': 'thinking', 'round': round_index}})
                        invocation_messages = [Message(role='system', content=build_system_prompt(self.ap, context))]
                        if investigation_paused:
                            invocation_messages.append(
                                Message(
                                    role='system',
                                    content=(
                                        'This conversation paused after repeated investigation. '
                                        'Use the saved findings. Do not repeat completed searches or reads. '
                                        'Present a setup plan, propose the next action, or explain a real blocker.'
                                    ),
                                )
                            )
                        response = await self._invoke(
                            model,
                            dict(
                                query=None,
                                model=model,
                                messages=invocation_messages + model_context(conversation['messages']),
                                funcs=tool_definitions(context),
                                extra_args=model.model_entity.extra_args or {},
                                remove_think=True,
                                execution_context=execution,
                            ),
                            on_event,
                        )
                        message = response.model_dump(mode='json')
                        if len(json.dumps(message, ensure_ascii=False)) > 128000:
                            raise AssistantError('response_too_large')
                        conversation['messages'].append(message)
                        await self._snapshot(conversation, on_event)
                        calls = self._calls(message)
                        if not calls:
                            await self._save(context, conversation, 'ready')
                            return conversation
                        fingerprint = json.dumps(
                            [(call['function']['name'], call['function']['arguments']) for call in calls],
                            ensure_ascii=False,
                        )
                        repeated_count = repeated_count + 1 if fingerprint == repeated_call else 1
                        repeated_call = fingerprint
                        invalid_calls = {}
                        valid_calls = []
                        for call in calls:
                            function = call['function']
                            try:
                                validate_call(context, function['name'], json.loads(function['arguments'] or '{}'))
                                valid_calls.append(call)
                            except Exception:
                                invalid_calls[call['id']] = {'error': 'Invalid or unauthorized tool arguments.'}
                        if invalid_calls and not valid_calls:
                            for call in calls:
                                self._append_result(
                                    conversation, call, {'error': 'Invalid or unauthorized tool arguments.'}
                                )
                            stalled = repeated_count >= 3
                            await self._save(
                                context,
                                conversation,
                                'paused' if stalled else 'running',
                                'no_progress' if stalled else None,
                            )
                            if stalled:
                                return conversation
                            continue
                        if invalid_calls:
                            for call in calls:
                                if call['id'] in invalid_calls:
                                    self._append_result(conversation, call, invalid_calls[call['id']])
                        if any(call['function']['name'] == 'present_setup_plan' for call in valid_calls):
                            if len(calls) == 1:
                                await self._save(context, conversation, 'choice')
                                return conversation
                            for call in valid_calls:
                                self._append_result(
                                    conversation, call, {'error': 'Present the setup plan in a separate tool call.'}
                                )
                            stalled = repeated_count >= 3
                            await self._save(
                                context,
                                conversation,
                                'paused' if stalled else 'running',
                                'no_progress' if stalled else None,
                            )
                            if stalled:
                                return conversation
                            continue
                        if any(
                            is_write(
                                call['function']['name'],
                                json.loads(call['function']['arguments'] or '{}'),
                            )
                            for call in valid_calls
                        ):
                            await self._save(context, conversation, 'approval')
                            return conversation
                        await self._execute(context, conversation, valid_calls, True, on_event)
                        if repeated_count >= 3:
                            await self._save(context, conversation, 'paused', 'no_progress')
                            return conversation
            except asyncio.CancelledError:
                partial = self._runs.get(conversation_id, {}).get('progress', {}).get('text')
                if partial:
                    conversation['messages'].append(Message(role='assistant', content=partial).model_dump(mode='json'))
                await asyncio.shield(self._save(context, conversation, 'failed', 'result_unknown'))
                raise
            except TimeoutError:
                if uncertain_write:
                    await self._save(context, conversation, 'failed', 'result_unknown')
                else:
                    for index in range(len(conversation['messages']) - 1, -1, -1):
                        message = conversation['messages'][index]
                        if message.get('role') == 'assistant' and message.get('tool_calls'):
                            completed = {
                                item.get('tool_call_id')
                                for item in conversation['messages'][index + 1 :]
                                if item.get('role') == 'tool'
                            }
                            for call in message['tool_calls']:
                                if call['id'] not in completed:
                                    self._append_result(conversation, call, {'error': 'read_timeout'})
                            break
                    await self._save(context, conversation, 'paused', 'time_budget')
            except AssistantError as exc:
                await self._save(context, conversation, 'failed', exc.code)
            except RequesterError as exc:
                self.ap.logger.warning(
                    'Management assistant model request failed; conversation=%s code=%s status=%s request_id=%s',
                    conversation_id,
                    exc.code,
                    exc.status_code,
                    exc.request_id,
                )
                if exc.code == 'quota_exceeded':
                    error = 'model_quota_exceeded'
                elif exc.code in {'authentication', 'invalid_key'} or exc.status_code == 401:
                    error = 'model_auth_failed'
                elif exc.code == 'permission_denied' or exc.status_code == 403:
                    error = 'model_permission_denied'
                else:
                    error = 'model_request_failed'
                await self._save(context, conversation, 'failed', error)
            except Exception as exc:
                self.ap.logger.warning(
                    'Management assistant turn failed (%s); conversation=%s',
                    type(exc).__name__,
                    conversation_id,
                )
                await self._save(context, conversation, 'failed', 'turn_failed')
            return conversation

    @staticmethod
    def _append_result(conversation, call, result):
        content = json.dumps(redact_secrets(result), ensure_ascii=False, default=str)
        if len(content) > 16000:
            content = json.dumps({'truncated': True, 'preview': content[:16000]}, ensure_ascii=False)
        conversation['messages'].append(
            Message(
                role='tool',
                content=content,
                tool_call_id=call['id'],
            ).model_dump(mode='json')
        )

    async def _execute(self, context, conversation, calls, approved, on_event=None):
        # Validate the complete saved batch before any write, including after approval.
        read_only_batch = not any(
            is_write(call['function']['name'], json.loads(call['function']['arguments'] or '{}')) for call in calls
        )
        if approved:
            for call in calls:
                func = call['function']
                validate_call(context, func['name'], json.loads(func['arguments'] or '{}'))
        for call in calls:
            func = call['function']
            if not approved:
                result = {'status': 'denied', 'message': 'User declined this batch; nothing executed.'}
            else:
                # Persist before effects. A crash leaves a running/unknown operation, never a replayable approval.
                await self._save(context, conversation, 'running')
                if on_event is not None:
                    await on_event(
                        {
                            'kind': 'phase',
                            'data': {
                                'phase': 'tool',
                                'tool': {
                                    'name': func['name'],
                                    'arguments': redact_secrets(json.loads(func['arguments'] or '{}')),
                                },
                            },
                        }
                    )
                try:
                    result = await execute_tool(self.ap, context, func['name'], json.loads(func['arguments'] or '{}'))
                except Exception as exc:
                    self.ap.logger.warning('Management assistant tool %s failed (%s)', func['name'], type(exc).__name__)
                    if read_only_batch:
                        self._append_result(conversation, call, {'error': 'read_failed'})
                        await self._save(context, conversation, 'running')
                        await self._snapshot(conversation, on_event)
                        continue
                    self._append_result(
                        conversation,
                        call,
                        {
                            'error': 'Tool failed. Inspect the resource before retrying; the write outcome may be unknown.',
                        },
                    )
                    await self._save(context, conversation, 'failed', 'tool_failed')
                    raise AssistantError('tool_failed')
            self._append_result(conversation, call, result)
            await self._save(context, conversation, 'running')
            await self._snapshot(conversation, on_event)
