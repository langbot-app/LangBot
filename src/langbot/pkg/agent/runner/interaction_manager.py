"""Host validation, persistence, and delivery for structured interactions."""

from __future__ import annotations

import copy
import asyncio
import json
import time
import typing

import pydantic

from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.runner.interaction import (
    InteractionDeliveryCapabilities,
    InteractionHandle,
    InteractionRequest,
    InteractionSubmission,
)

from .errors import RunnerProtocolError
from .interaction_store import InteractionStore


INTERACTION_PAYLOAD_MAX_BYTES = 256 * 1024
DEFAULT_INTERACTION_TTL_SECONDS = 30 * 60
MAX_INTERACTION_TTL_SECONDS = 24 * 60 * 60


class HostInteractionOption(pydantic.BaseModel):
    """Host-validated selectable interaction value."""

    value: str = pydantic.Field(min_length=1, max_length=512)
    label: str = pydantic.Field(min_length=1, max_length=512)
    description: str | None = pydantic.Field(default=None, max_length=2000)

    model_config = pydantic.ConfigDict(extra='forbid')


class HostInteractionField(pydantic.BaseModel):
    """Host-validated structured interaction field."""

    id: str = pydantic.Field(min_length=1, max_length=128)
    label: str = pydantic.Field(min_length=1, max_length=512)
    type: typing.Literal['text', 'textarea', 'select', 'multiselect', 'number', 'boolean', 'file']
    required: bool = False
    options: list[HostInteractionOption] = pydantic.Field(default_factory=list, max_length=100)
    placeholder: str | None = pydantic.Field(default=None, max_length=2000)
    default: typing.Any = None

    model_config = pydantic.ConfigDict(extra='forbid')


class HostInteractionAction(pydantic.BaseModel):
    """Host-validated interaction submit action."""

    id: str = pydantic.Field(min_length=1, max_length=128)
    label: str = pydantic.Field(min_length=1, max_length=512)
    style: typing.Literal['default', 'primary', 'danger'] = 'default'

    model_config = pydantic.ConfigDict(extra='forbid')


class HostInteractionRequest(pydantic.BaseModel):
    """Defensive Host projection of the SDK interaction request contract."""

    interaction_id: str = pydantic.Field(min_length=1, max_length=255)
    kind: typing.Literal['form', 'confirmation', 'choice'] = 'form'
    title: str = pydantic.Field(min_length=1, max_length=1000)
    description: str | None = pydantic.Field(default=None, max_length=10000)
    fields: list[HostInteractionField] = pydantic.Field(default_factory=list, max_length=50)
    actions: list[HostInteractionAction] = pydantic.Field(default_factory=list, max_length=20)
    expires_at: int | None = None
    fallback_text: str | None = pydantic.Field(default=None, min_length=1, max_length=20000)

    model_config = pydantic.ConfigDict(extra='forbid')


class HostInteractionSubmission(pydantic.BaseModel):
    """Host-normalized platform callback payload."""

    interaction_id: str = pydantic.Field(min_length=1, max_length=255)
    action_id: str | None = pydantic.Field(default=None, max_length=128)
    values: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    submitted_at: int | None = None
    label: str | None = None

    model_config = pydantic.ConfigDict(extra='forbid')


class InteractionManager:
    """Consume the interaction action whitelist for one Host application."""

    def __init__(self, ap: typing.Any, store: InteractionStore | None = None):
        self.ap = ap
        self.store = store or InteractionStore(ap.persistence_mgr.get_db_engine())
        self._waiters: dict[tuple[str, str], asyncio.Future[dict[str, typing.Any]]] = {}
        self._waiter_scopes: dict[tuple[str, str], tuple[str, str]] = {}
        self._responders: dict[tuple[str, str], str | list[str]] = {}
        self._callback_contexts: dict[tuple[str, str], dict[str, typing.Any]] = {}
        self._text_waiters: dict[tuple[str, str], tuple[str, str, str, str, InteractionRequest]] = {}

    async def request_interaction(
        self,
        *,
        session: typing.Mapping[str, typing.Any],
        adapter: typing.Any,
        request_payload: dict[str, typing.Any],
        timeout: float,
        on_unsupported: str,
        responders: str | list[str],
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> dict[str, typing.Any]:
        """Deliver an interaction and wait for its validated callback in this run."""
        authorization = session['authorization']
        if not authorization.get('interactions_enabled') or not authorization.get('interactions_authorized'):
            raise ValueError('Runner did not declare interaction capability and permission')
        if not 0 < timeout <= MAX_INTERACTION_TTL_SECONDS:
            raise ValueError('Interaction timeout must be within 24 hours')
        if on_unsupported not in {'error', 'degrade'}:
            raise ValueError('Invalid interaction fallback policy')
        valid_responders = (
            responders in {'actor', 'any'}
            if isinstance(responders, str)
            else (
                isinstance(responders, list)
                and bool(responders)
                and all(isinstance(item, str) and item for item in responders)
            )
        )
        if not valid_responders:
            raise ValueError('Invalid interaction responders')

        request = InteractionRequest.model_validate(request_payload)
        if request.fields and request.actions:
            raise ValueError('Interaction cannot combine fields and actions')
        self._validate_request_identity(
            HostInteractionRequest.model_validate(request.model_dump(mode='json')), session['runner_id']
        )
        run_id = session['run_id']
        key = (run_id, request.interaction_id)
        bot_id = authorization.get('bot_id')
        workspace_id = authorization.get('workspace_id')
        workspace_waiters = sum(scope[0] == workspace_id for scope in self._waiter_scopes.values())
        bot_waiters = sum(scope == (workspace_id, bot_id) for scope in self._waiter_scopes.values())
        if workspace_waiters >= 256 or bot_waiters >= 32:
            raise ValueError('Too many pending interactions')
        if key in self._waiters:
            raise ValueError('Interaction is already waiting')
        platform_context = authorization.get('platform_context') or {}
        delivery = platform_context.get('delivery') or {}
        reply_target = delivery.get('reply_target') or {}
        selected_type = target_type or reply_target.get('target_type')
        selected_id = target_id or reply_target.get('target_id')
        if not selected_type or not selected_id:
            raise ValueError('Interaction has no delivery target')
        if target_type is not None and (target_type, target_id) != (
            reply_target.get('target_type'),
            reply_target.get('target_id'),
        ):
            from .platform_tools import resolve_platform_api_call

            resolve_platform_api_call(
                session,
                bot_id,
                'send_message',
                {
                    'target_type': target_type,
                    'target_id': target_id,
                    'message': platform_message.MessageChain(
                        [platform_message.Plain(text='Interaction request')]
                    ).model_dump(mode='json'),
                },
            )
        actor = platform_context.get('actor') or {}
        actor_id = actor.get('actor_id')
        if responders == 'actor' and not actor_id:
            raise ValueError('Interaction has no actor')
        capabilities = adapter.get_interaction_capabilities()
        if not isinstance(capabilities, InteractionDeliveryCapabilities):
            capabilities = InteractionDeliveryCapabilities.model_validate(capabilities)
        supported_apis = adapter.get_supported_apis() if callable(getattr(adapter, 'get_supported_apis', None)) else []
        if supported_apis and 'send_interaction' not in supported_apis:
            capabilities = InteractionDeliveryCapabilities(text_fallback=capabilities.text_fallback)
        if supported_apis and 'update_interaction' not in supported_apis:
            capabilities.supports_updates = False
        normalized, degraded, use_text, issues = self._normalize_request(request, capabilities, on_unsupported)
        if issues:
            return {'unsupported': issues}
        request_data = normalized.model_dump(mode='json')
        request_data['expires_at'] = int(time.time() + timeout + 1)
        if len(json.dumps(request_data, ensure_ascii=False).encode('utf-8')) > INTERACTION_PAYLOAD_MAX_BYTES:
            raise ValueError('Interaction request exceeds 256 KiB')
        conversation_id = f'{selected_type}_{selected_id}'
        _, callback_token = await self.store.create_request(
            interaction_id=request.interaction_id,
            run_id=run_id,
            binding_id=authorization['binding_id'],
            runner_id=session['runner_id'],
            processor_type=authorization['processor_type'],
            processor_id=authorization['processor_id'],
            request=request_data,
            delivery_target={'target_type': selected_type, 'target_id': selected_id},
            bot_id=bot_id,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            thread_id=authorization.get('thread_id'),
            actor_id=actor_id if responders == 'actor' else None,
            expires_at=request_data['expires_at'],
            blocking=True,
            **self._pipeline_tool_admission(session, authorization, session['runner_id']),
        )
        future = asyncio.get_running_loop().create_future()
        self._waiters[key] = future
        self._responders[key] = responders
        self._waiter_scopes[key] = (workspace_id, bot_id)
        if use_text:
            self._text_waiters[key] = (workspace_id, bot_id, conversation_id, callback_token, normalized)
        runtime = session.get('runtime_context')
        original_deadline = runtime.get('deadline_at') if isinstance(runtime, dict) else None
        started_at = time.time()
        if original_deadline is not None:
            runtime['deadline_at'] = float(original_deadline) + timeout + 30
        handle = None
        terminal = None
        try:
            if use_text:
                await adapter.send_message(
                    str(selected_type),
                    str(selected_id),
                    platform_message.MessageChain(
                        [platform_message.Plain(text=normalized.fallback_text or normalized.title)]
                    ),
                )
            else:
                handle = await adapter.send_interaction(
                    str(selected_type),
                    str(selected_id),
                    normalized,
                    callback_token,
                    reply_to=reply_target.get('message_id'),
                )
                if isinstance(handle, dict):
                    handle = InteractionHandle.model_validate(handle)
                await self.store.record_delivery_success(run_id, request.interaction_id, handle.model_dump(mode='json'))
            try:
                submission = await asyncio.wait_for(future, timeout=timeout)
                terminal = 'submitted'
            except asyncio.TimeoutError:
                terminal = 'expired'
                await self.store.mark_terminal(run_id, request.interaction_id, terminal)
                submission = None
            if handle is not None and capabilities.supports_updates:
                handle.context['callback_context'] = self._callback_contexts.get(key, {})
                try:
                    await adapter.update_interaction(
                        handle,
                        terminal,
                        InteractionSubmission.model_validate(submission) if submission else None,
                    )
                except Exception as exc:
                    self._warning(f'Failed to update interaction card: {exc}')
            if original_deadline is not None:
                runtime['deadline_at'] = float(original_deadline) + (time.time() - started_at)
            return {
                'status': 'timeout' if terminal == 'expired' else 'submitted',
                'submission': submission,
                'degraded': degraded,
                'deadline_at': runtime.get('deadline_at') if isinstance(runtime, dict) else None,
            }
        except asyncio.CancelledError:
            terminal = 'cancelled'
            await self.store.mark_terminal(run_id, request.interaction_id, terminal)
            if handle is not None and capabilities.supports_updates:
                try:
                    await adapter.update_interaction(handle, terminal)
                except Exception as exc:
                    self._warning(f'Failed to cancel interaction card: {exc}')
            raise
        except Exception as exc:
            if terminal is None:
                await self.store.mark_delivery_failed(run_id, request.interaction_id, str(exc))
            raise
        finally:
            if original_deadline is not None:
                runtime['deadline_at'] = float(original_deadline) + (time.time() - started_at)
            self._waiters.pop(key, None)
            self._responders.pop(key, None)
            self._callback_contexts.pop(key, None)
            self._text_waiters.pop(key, None)
            self._waiter_scopes.pop(key, None)

    @staticmethod
    def _normalize_request(request, capabilities, policy):
        normalized = request.model_copy(deep=True)
        issues = []
        degraded = []
        native = bool(capabilities.field_types or capabilities.max_actions or capabilities.action_styles)
        if not native:
            issues.append({'path': 'platform', 'reason': 'native_interactions_unavailable'})
        for index, field in enumerate(request.fields):
            if field.type not in capabilities.field_types:
                issues.append({'path': f'fields[{index}].type', 'reason': 'unsupported_field_type'})
            if capabilities.max_options is not None and len(field.options) > capabilities.max_options:
                issues.append({'path': f'fields[{index}].options', 'reason': 'too_many_options'})
            if field.placeholder:
                degraded.append(
                    {'path': f'fields[{index}].placeholder', 'reason': 'unsupported_placeholder', 'applied': 'omit'}
                )
                normalized.fields[index].placeholder = None
            if field.default is not None:
                degraded.append(
                    {'path': f'fields[{index}].default', 'reason': 'unsupported_default', 'applied': 'omit'}
                )
                normalized.fields[index].default = None
        if capabilities.max_fields is not None and len(request.fields) > capabilities.max_fields:
            issues.append({'path': 'fields', 'reason': 'too_many_fields'})
        if capabilities.max_actions is not None and len(request.actions) > capabilities.max_actions:
            issues.append({'path': 'actions', 'reason': 'too_many_actions'})
        for index, action in enumerate(request.actions):
            if action.style not in capabilities.action_styles:
                degraded.append(
                    {'path': f'actions[{index}].style', 'reason': 'unsupported_style', 'applied': 'default'}
                )
                normalized.actions[index].style = 'default'
        if request.description and not capabilities.supports_markdown:
            degraded.append({'path': 'description', 'reason': 'unsupported_markdown', 'applied': 'literal_text'})
        if issues and policy == 'error':
            return normalized, degraded, False, issues
        if issues and (
            not capabilities.text_fallback
            or len(request.fields) > 1
            or any(field.type in {'file', 'multiselect'} for field in request.fields)
        ):
            return normalized, degraded, False, issues
        use_text = bool(issues)
        fallback_text = request.fallback_text or request.title
        if use_text and request.actions:
            choices = ' / '.join(f'{index + 1} {action.label}' for index, action in enumerate(request.actions))
            fallback_text = f'{fallback_text}\n{choices}'
        elif use_text and request.fields:
            field = request.fields[0]
            fallback_text = f'{fallback_text}\n{field.label}'
            if field.type == 'select':
                fallback_text += '\n' + ' / '.join(
                    f'{index + 1} {option.label}' for index, option in enumerate(field.options)
                )
        normalized.fallback_text = fallback_text
        return (
            normalized,
            degraded
            + (
                [{'path': 'platform', 'reason': 'unsupported_structure', 'applied': 'text_fallback'}]
                if use_text
                else []
            ),
            use_text,
            [],
        )

    def wake_waiter(
        self,
        record: dict[str, typing.Any],
        actor_id: str | None,
        callback_context: dict[str, typing.Any] | None = None,
    ) -> bool:
        key = (record['run_id'], record['interaction_id'])
        future = self._waiters.get(key)
        if future is None or future.done():
            return False
        responders = self._responders[key]
        if isinstance(responders, list) and actor_id not in responders:
            raise ValueError('Interaction actor is not an allowed responder')
        self._callback_contexts[key] = callback_context or {}
        future.set_result(record['submission'])
        return True

    def waiting_run_ids(self) -> set[str]:
        return {run_id for (run_id, _), future in self._waiters.items() if not future.done()}

    async def consume_text_message(
        self,
        *,
        workspace_id: str,
        bot_id: str,
        conversation_id: str,
        actor_id: str,
        text: str,
    ) -> bool:
        answer = text.strip()
        if not answer or len(answer) > 20000:
            return False
        for key, (workspace, bot, conversation, token, request) in reversed(list(self._text_waiters.items())):
            if (workspace, bot, conversation) != (workspace_id, bot_id, conversation_id):
                continue
            responders = self._responders.get(key)
            if responders == 'actor':
                pending = await self.store.get_by_callback_token(token)
                if pending is None or pending.get('actor_id') != actor_id:
                    continue
            elif isinstance(responders, list) and actor_id not in responders:
                continue
            submission: dict[str, typing.Any] = {'interaction_id': request.interaction_id, 'values': {}}
            if request.actions:
                if not answer.isdigit() or not 1 <= int(answer) <= len(request.actions):
                    return False
                submission['action_id'] = request.actions[int(answer) - 1].id
                submission['label'] = request.actions[int(answer) - 1].label
            elif request.fields:
                field = request.fields[0]
                value: typing.Any = answer
                if field.type == 'number':
                    try:
                        value = float(answer)
                    except ValueError:
                        return False
                elif field.type == 'boolean':
                    if answer.lower() not in {'yes', 'no', 'true', 'false', '1', '0'}:
                        return False
                    value = answer.lower() in {'yes', 'true', '1'}
                elif field.type == 'select':
                    options = field.options
                    if answer.isdigit() and 1 <= int(answer) <= len(options):
                        value = options[int(answer) - 1].value
                    elif answer not in {option.value for option in options}:
                        return False
                submission['values'] = {field.id: value}
            record = await self.consume_callback(
                callback_token=token,
                submission=submission,
                bot_id=bot_id,
                conversation_id=conversation_id,
                actor_id=actor_id,
            )
            return self.wake_waiter(record, actor_id)
        return False

    @staticmethod
    def _pipeline_tool_admission(session, authorization, runner_id):
        if authorization.get('processor_type') != 'pipeline':
            return {}

        query = session.get('execution_query')
        expected = copy.deepcopy(getattr(query, 'pipeline_config', None))
        query_session = getattr(query, 'session', None)
        conversation = getattr(query_session, 'using_conversation', None)
        processor_id = str(authorization.get('processor_id') or '').strip()

        def authority():
            from .config_resolver import RunnerConfigResolver

            current_config = getattr(query, 'pipeline_config', None)
            return (
                query is not None
                and query_session is not None
                and conversation is not None
                and isinstance(expected, dict)
                and query_session.using_conversation is conversation
                and getattr(query, 'pipeline_uuid', None) == processor_id
                and current_config == expected
                and RunnerConfigResolver.resolve_runner_id(expected) == runner_id
            )

        return {'expected_config': expected, 'authority_check': authority}

    @staticmethod
    def _validate_request_identity(request: HostInteractionRequest, runner_id: str) -> None:
        field_ids = [field.id for field in request.fields]
        action_ids = [action.id for action in request.actions]
        if len(field_ids) != len(set(field_ids)):
            raise RunnerProtocolError(runner_id, 'interaction request has duplicate field IDs')
        if len(action_ids) != len(set(action_ids)):
            raise RunnerProtocolError(runner_id, 'interaction request has duplicate action IDs')
        for field in request.fields:
            if field.type in {'select', 'multiselect'} and not field.options:
                raise RunnerProtocolError(
                    runner_id,
                    f'interaction field {field.id} requires at least one option',
                )
            option_values = [option.value for option in field.options]
            if len(option_values) != len(set(option_values)):
                raise RunnerProtocolError(
                    runner_id,
                    f'interaction field {field.id} has duplicate option values',
                )

    async def consume_callback(
        self,
        *,
        callback_token: str,
        submission: dict[str, typing.Any],
        bot_id: str | None,
        conversation_id: str | None,
        actor_id: str | None,
    ) -> dict[str, typing.Any]:
        """Validate a platform callback and return the persisted resume target."""
        pending = await self.store.get_by_callback_token(callback_token)
        if pending is None:
            from .interaction_store import InteractionNotFoundError

            raise InteractionNotFoundError('Unknown interaction callback token')
        responders = self._responders.get((pending['run_id'], pending['interaction_id']))
        if isinstance(responders, list) and actor_id not in responders:
            raise ValueError('Interaction actor is not an allowed responder')
        normalized_submission = self._resolve_submission_refs(pending, submission)
        try:
            normalized = HostInteractionSubmission.model_validate(normalized_submission)
        except pydantic.ValidationError as exc:
            raise ValueError(f'invalid interaction submission: {exc}') from exc
        self._validate_submission(pending, normalized)
        submission_data = normalized.model_dump(mode='json')
        submission_data['submitted_at'] = int(time.time())
        if len(json.dumps(submission_data, ensure_ascii=False).encode('utf-8')) > 256 * 1024:
            raise ValueError('interaction submission exceeds 256 KiB')
        return await self.store.consume_submission(
            callback_token=callback_token,
            submission=submission_data,
            bot_id=bot_id,
            conversation_id=conversation_id,
            actor_id=actor_id,
            submitted_at=submission_data['submitted_at'],
        )

    @staticmethod
    def _resolve_submission_refs(
        pending: dict[str, typing.Any],
        submission: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        """Resolve compact platform indexes against the persisted request."""
        resolved = dict(submission)
        resolved['interaction_id'] = pending['interaction_id']
        request = pending.get('request') if isinstance(pending.get('request'), dict) else {}

        action_ref = resolved.pop('action_ref', None)
        if action_ref is not None:
            actions = request.get('actions') if isinstance(request.get('actions'), list) else []
            try:
                action = actions[InteractionManager._callback_index(action_ref, 'action')]
            except (IndexError, TypeError, ValueError) as exc:
                raise ValueError('interaction action reference is invalid') from exc
            if not isinstance(action, dict) or not action.get('id'):
                raise ValueError('interaction action reference has no action ID')
            resolved['action_id'] = str(action['id'])

        field_ref = resolved.pop('field_ref', None)
        option_ref = resolved.pop('option_ref', None)
        if field_ref is not None or option_ref is not None:
            fields = request.get('fields') if isinstance(request.get('fields'), list) else []
            try:
                field = fields[InteractionManager._callback_index(field_ref, 'field')]
                option = field['options'][InteractionManager._callback_index(option_ref, 'option')]
            except (IndexError, KeyError, TypeError, ValueError) as exc:
                raise ValueError('interaction field option reference is invalid') from exc
            if not isinstance(field, dict) or not field.get('id') or not isinstance(option, dict):
                raise ValueError('interaction field option reference is malformed')
            resolved['values'] = {str(field['id']): option.get('value')}

        return resolved

    @staticmethod
    def _callback_index(value: typing.Any, label: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f'interaction {label} reference is not an integer')
        if isinstance(value, int):
            index = value
        elif isinstance(value, str) and value.isdigit():
            index = int(value)
        else:
            raise ValueError(f'interaction {label} reference is not an integer')
        if index < 0:
            raise ValueError(f'interaction {label} reference is negative')
        return index

    @staticmethod
    def _validate_submission(
        pending: dict[str, typing.Any],
        submission: HostInteractionSubmission,
    ) -> None:
        request = pending.get('request') if isinstance(pending.get('request'), dict) else {}
        actions = request.get('actions') if isinstance(request.get('actions'), list) else []
        action_ids = {str(action.get('id')) for action in actions if isinstance(action, dict) and action.get('id')}
        if submission.action_id is not None and submission.action_id not in action_ids:
            raise ValueError('interaction submission action is not present in the request')

        fields = request.get('fields') if isinstance(request.get('fields'), list) else []
        fields_by_id = {str(field.get('id')): field for field in fields if isinstance(field, dict) and field.get('id')}
        for field_id, value in submission.values.items():
            field = fields_by_id.get(field_id)
            if field is None:
                raise ValueError(f'interaction submission field is not present in the request: {field_id}')
            field_type = field.get('type')
            if field_type not in {'select', 'multiselect'}:
                continue
            options = field.get('options') if isinstance(field.get('options'), list) else []
            allowed_values = {
                option.get('value')
                for option in options
                if isinstance(option, dict) and option.get('value') is not None
            }
            selected_values = value if field_type == 'multiselect' and isinstance(value, list) else [value]
            if field_type == 'multiselect' and not isinstance(value, list):
                raise ValueError(f'interaction multiselect field requires a list: {field_id}')
            if any(selected not in allowed_values for selected in selected_values):
                raise ValueError(f'interaction submission option is not present in the request: {field_id}')

    def _warning(self, message: str) -> None:
        logger = getattr(self.ap, 'logger', None)
        warning = getattr(logger, 'warning', None)
        if callable(warning):
            warning(message)
