"""Agent result normalizer for converting SDK v1 AgentRunResult to Pipeline messages."""
from __future__ import annotations

import typing

from langbot_plugin.api.entities.builtin.provider import message as provider_message

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .errors import RunnerExecutionError, RunnerProtocolError


# Maximum size for a single result payload (prevent memory exhaustion)
MAX_RESULT_SIZE_BYTES = 1024 * 1024  # 1 MB


class AgentResultNormalizer:
    """Normalizer for converting SDK v1 AgentRunResult to Pipeline messages.

    Responsibilities:
    - Accept only SDK v1 result types (message.delta, message.completed, etc.)
    - Map message.delta -> MessageChunk
    - Map message.completed -> Message
    - Map run.completed (with message) -> Message
    - Handle run.failed as controlled error
    - Ignore unknown types with warning
    - Validate result size
    - Validate message schema

    Per PROTOCOL_V1.md, accepted types:
    - message.delta
    - message.completed
    - tool.call.started
    - tool.call.completed
    - state.updated
    - run.completed
    - run.failed
    - action.requested (log only, don't execute)
    """

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def normalize(
        self,
        result_dict: dict[str, typing.Any],
        descriptor: AgentRunnerDescriptor,
    ) -> provider_message.Message | provider_message.MessageChunk | None:
        """Normalize AgentRunResult to Message or MessageChunk.

        Args:
            result_dict: Raw result dict from plugin runtime
            descriptor: Runner descriptor for error context

        Returns:
            Message, MessageChunk, or None (for non-message events)

        Raises:
            RunnerExecutionError: On run.failed
            RunnerProtocolError: On invalid result format
        """
        # Validate result type
        result_type = result_dict.get('type')
        if not result_type:
            raise RunnerProtocolError(descriptor.id, 'Missing result type')

        # Validate result size
        try:
            import json
            result_json = json.dumps(result_dict)
            if len(result_json) > MAX_RESULT_SIZE_BYTES:
                self.ap.logger.warning(
                    f'Runner {descriptor.id} result too large ({len(result_json)} bytes), truncating'
                )
                # Truncate content if possible
                data = result_dict.get('data', {})
                if 'chunk' in data or 'message' in data:
                    content = data.get('chunk', {}).get('content', '') or data.get('message', {}).get('content', '')
                    if isinstance(content, str) and len(content) > 10000:
                        # Keep reasonable length
                        data['chunk'] = {'role': 'assistant', 'content': content[:10000] + '...[truncated]'}
        except Exception as e:
            self.ap.logger.warning(f'Failed to validate runner {descriptor.id} result size: {e}')

        # Handle each result type
        data = result_dict.get('data', {})

        if result_type == 'message.delta':
            return self._normalize_message_delta(data, descriptor)

        elif result_type == 'message.completed':
            return self._normalize_message_completed(data, descriptor)

        elif result_type == 'tool.call.started':
            # Log only, don't yield to pipeline
            self.ap.logger.debug(
                f'Runner {descriptor.id} tool call started: {data.get("tool_name", "unknown")}'
            )
            return None

        elif result_type == 'tool.call.completed':
            # Log only, don't yield to pipeline
            self.ap.logger.debug(
                f'Runner {descriptor.id} tool call completed: {data.get("tool_name", "unknown")}'
            )
            return None

        elif result_type == 'state.updated':
            # Log for telemetry, don't yield to pipeline
            # Orchestrator already handles the actual state_store.apply_update
            scope = data.get('scope', 'conversation')  # Default for backward compat
            key = data.get('key', 'unknown')
            value_repr = repr(data.get('value', '...'))[:100]  # Truncate for log
            self.ap.logger.debug(
                f'Runner {descriptor.id} state.updated logged: scope={scope}, key={key}, value={value_repr}'
            )
            return None

        elif result_type == 'run.completed':
            # May include final message
            if 'message' in data:
                return self._normalize_message_completed(data, descriptor)
            # If no message, it's just completion signal
            return None

        elif result_type == 'run.failed':
            error_msg = data.get('error', 'Unknown error')
            error_code = data.get('code', 'unknown')
            retryable = data.get('retryable', False)
            raise RunnerExecutionError(
                descriptor.id,
                f'{error_msg} (code: {error_code})',
                retryable=retryable,
            )

        elif result_type == 'action.requested':
            # Reserved for EBA - log only, don't execute
            self.ap.logger.info(
                f'Runner {descriptor.id} requested action (not executed in current phase): '
                f'{data.get("action", "unknown")}'
            )
            return None

        else:
            # Unknown type - warn and ignore (SDK v1 only)
            self.ap.logger.warning(
                f'Runner {descriptor.id} returned unknown result type: {result_type}. '
                f'Expected SDK v1 types (message.delta, message.completed, run.completed, run.failed, etc.)'
            )
            return None

    def _normalize_message_delta(
        self,
        data: dict[str, typing.Any],
        descriptor: AgentRunnerDescriptor,
    ) -> provider_message.MessageChunk:
        """Normalize message.delta to MessageChunk."""
        chunk_data = data.get('chunk', {})
        if not chunk_data:
            raise RunnerProtocolError(descriptor.id, 'message.delta missing chunk data')

        try:
            chunk = provider_message.MessageChunk.model_validate(chunk_data)
            return chunk
        except Exception as e:
            raise RunnerProtocolError(descriptor.id, f'Invalid chunk schema: {e}')

    def _normalize_message_completed(
        self,
        data: dict[str, typing.Any],
        descriptor: AgentRunnerDescriptor,
    ) -> provider_message.Message:
        """Normalize message.completed to Message."""
        message_data = data.get('message', {})
        if not message_data:
            raise RunnerProtocolError(descriptor.id, 'message.completed missing message data')

        try:
            msg = provider_message.Message.model_validate(message_data)
            return msg
        except Exception as e:
            raise RunnerProtocolError(descriptor.id, f'Invalid message schema: {e}')
