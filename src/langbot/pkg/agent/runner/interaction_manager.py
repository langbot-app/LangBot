"""Host validation, persistence, and delivery for structured interactions."""

from __future__ import annotations

import json
import time
import typing

import pydantic

from langbot_plugin.api.entities.builtin.platform import message as platform_message

from .descriptor import AgentRunnerDescriptor
from .errors import RunnerProtocolError
from .host_models import AgentBinding, AgentEventEnvelope
from .interaction_store import InteractionStore


INTERACTION_REQUESTED_ACTION = 'interaction.requested'
INTERACTION_DELIVERY_API = 'interaction.request'
INTERACTION_ACKNOWLEDGE_API = 'interaction.acknowledge'
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
    fallback_text: str = pydantic.Field(min_length=1, max_length=20000)

    model_config = pydantic.ConfigDict(extra='forbid')


class HostInteractionSubmission(pydantic.BaseModel):
    """Host-normalized platform callback payload."""

    interaction_id: str = pydantic.Field(min_length=1, max_length=255)
    action_id: str | None = pydantic.Field(default=None, max_length=128)
    values: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    submitted_at: int | None = None

    model_config = pydantic.ConfigDict(extra='forbid')


class InteractionManager:
    """Consume the interaction action whitelist for one Host application."""

    def __init__(self, ap: typing.Any, store: InteractionStore | None = None):
        self.ap = ap
        self.store = store or InteractionStore(ap.persistence_mgr.get_db_engine())

    async def handle_result(
        self,
        *,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
        run_id: str,
        adapter_context: dict[str, typing.Any] | None,
    ) -> bool:
        """Execute an authorized interaction request; return whether it was consumed."""
        data = result_dict.get('data')
        if not isinstance(data, dict) or data.get('action') != INTERACTION_REQUESTED_ACTION:
            return False

        self._authorize(descriptor, binding)
        payload = data.get('payload')
        try:
            request = HostInteractionRequest.model_validate(payload)
        except pydantic.ValidationError as exc:
            raise RunnerProtocolError(descriptor.id, f'invalid interaction request: {exc}') from exc

        processor_id = binding.processor_id or binding.agent_id
        if not processor_id:
            raise RunnerProtocolError(descriptor.id, 'interaction request has no stable processor identity')
        adapter = self._resolve_adapter(adapter_context)
        if adapter is None:
            raise RunnerProtocolError(descriptor.id, 'interaction request has no delivery adapter')

        request_data = request.model_dump(mode='json')
        now = int(time.time())
        expires_at = now + DEFAULT_INTERACTION_TTL_SECONDS if request.expires_at is None else request.expires_at
        if expires_at <= now:
            raise RunnerProtocolError(descriptor.id, 'interaction request is already expired')
        if expires_at > now + MAX_INTERACTION_TTL_SECONDS:
            raise RunnerProtocolError(descriptor.id, 'interaction request expiry exceeds 24 hours')
        request_data['expires_at'] = expires_at
        if len(json.dumps(request_data, ensure_ascii=False).encode('utf-8')) > INTERACTION_PAYLOAD_MAX_BYTES:
            raise RunnerProtocolError(descriptor.id, 'interaction request exceeds 256 KiB')
        self._validate_request_identity(request, descriptor.id)
        reply_target = event.delivery.reply_target or {}
        target_type = reply_target.get('target_type')
        target_id = reply_target.get('target_id')
        callback_conversation_id = f'{target_type}_{target_id}' if target_type and target_id else event.conversation_id
        update_target = await self._find_update_target(
            event=event,
            binding=binding,
            descriptor=descriptor,
            processor_id=processor_id,
            conversation_id=callback_conversation_id,
        )
        _, callback_token = await self.store.create_request(
            interaction_id=request.interaction_id,
            run_id=run_id,
            binding_id=binding.binding_id,
            runner_id=descriptor.id,
            processor_type=binding.processor_type,
            processor_id=processor_id,
            request=request_data,
            delivery_target=reply_target,
            replaces_interaction_id=(update_target or {}).get('interaction_id'),
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            conversation_id=callback_conversation_id,
            thread_id=event.thread_id,
            actor_id=event.actor.actor_id if event.actor else None,
            expires_at=expires_at,
        )

        try:
            if self._supports_interaction_delivery(adapter):
                delivery_params = {
                    'request': request_data,
                    'callback_token': callback_token,
                    'reply_target': event.delivery.reply_target,
                }
                if update_target is not None:
                    delivery_params['update_target'] = update_target.get('delivery_result')
                try:
                    delivery_result = await adapter.call_platform_api(
                        INTERACTION_DELIVERY_API,
                        delivery_params,
                    )
                except Exception as exc:
                    if update_target is None:
                        raise
                    self._warning(f'Interaction update failed; sending a new presentation: {exc}')
                    fallback_params = dict(delivery_params)
                    fallback_params.pop('update_target', None)
                    delivery_result = await adapter.call_platform_api(
                        INTERACTION_DELIVERY_API,
                        fallback_params,
                    )
                if isinstance(delivery_result, dict):
                    try:
                        await self.store.record_delivery_success(
                            run_id,
                            request.interaction_id,
                            delivery_result,
                        )
                    except Exception as exc:
                        self._warning(f'Failed to persist interaction delivery result: {exc}')
            else:
                await self._deliver_fallback(adapter, event, request.fallback_text)
        except Exception as exc:
            await self.store.mark_delivery_failed(run_id, request.interaction_id, str(exc))
            raise
        return True

    async def acknowledge_submission(self, record: dict[str, typing.Any], adapter: typing.Any) -> None:
        """Best-effort transition of submitted controls into a read-only state."""
        delivery_result = record.get('delivery_result')
        if not isinstance(delivery_result, dict) or not self._supports_platform_api(
            adapter, INTERACTION_ACKNOWLEDGE_API
        ):
            return
        try:
            delivery_result = await adapter.call_platform_api(
                INTERACTION_ACKNOWLEDGE_API,
                {
                    'request': record.get('request') or {},
                    'submission': record.get('submission') or {},
                    'update_target': delivery_result,
                },
            )
            if isinstance(delivery_result, dict):
                await self.store.record_delivery_success(
                    record['run_id'],
                    record['interaction_id'],
                    delivery_result,
                )
        except Exception as exc:
            self._warning(f'Failed to acknowledge interaction submission: {exc}')

    async def _find_update_target(
        self,
        *,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
        processor_id: str,
        conversation_id: str | None,
    ) -> dict[str, typing.Any] | None:
        capabilities = getattr(event.delivery, 'interactions', None)
        if not capabilities or not getattr(capabilities, 'supports_updates', False):
            return None
        prior = getattr(event.input, 'interaction', None)
        prior_interaction_id = getattr(prior, 'interaction_id', None)
        if not prior_interaction_id:
            return None
        return await self.store.find_update_target(
            interaction_id=str(prior_interaction_id),
            binding_id=binding.binding_id,
            runner_id=descriptor.id,
            processor_type=binding.processor_type,
            processor_id=processor_id,
            bot_id=event.bot_id,
            conversation_id=conversation_id,
            actor_id=event.actor.actor_id if event.actor else None,
        )

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

    @staticmethod
    def _authorize(descriptor: AgentRunnerDescriptor, binding: AgentBinding) -> None:
        supports_interactions = bool(getattr(descriptor.capabilities, 'interactions', False))
        permissions = set(getattr(descriptor.permissions, 'interactions', []) or [])
        if not supports_interactions or 'request' not in permissions:
            raise RunnerProtocolError(descriptor.id, 'runner did not declare interaction capability and permission')
        if not binding.delivery_policy.enable_interactions:
            raise RunnerProtocolError(descriptor.id, 'binding delivery policy does not allow interactions')

    @staticmethod
    def _resolve_adapter(adapter_context: dict[str, typing.Any] | None) -> typing.Any | None:
        if not adapter_context:
            return None
        query = adapter_context.get('_query')
        if query is not None and getattr(query, 'adapter', None) is not None:
            return query.adapter
        return adapter_context.get('_delivery_adapter')

    @staticmethod
    def _supports_interaction_delivery(adapter: typing.Any) -> bool:
        return InteractionManager._supports_platform_api(adapter, INTERACTION_DELIVERY_API)

    @staticmethod
    def _supports_platform_api(adapter: typing.Any, api_name: str) -> bool:
        get_supported_apis = getattr(adapter, 'get_supported_apis', None)
        if not callable(get_supported_apis):
            return False
        try:
            return api_name in (get_supported_apis() or [])
        except Exception:
            return False

    def _warning(self, message: str) -> None:
        logger = getattr(self.ap, 'logger', None)
        warning = getattr(logger, 'warning', None)
        if callable(warning):
            warning(message)

    @staticmethod
    async def _deliver_fallback(adapter: typing.Any, event: AgentEventEnvelope, text: str) -> None:
        target = event.delivery.reply_target or {}
        target_type = target.get('target_type')
        target_id = target.get('target_id')
        if not target_type or not target_id:
            raise ValueError('interaction fallback has no reply target')
        await adapter.send_message(
            str(target_type),
            str(target_id),
            platform_message.MessageChain([platform_message.Plain(text=text)]),
        )
