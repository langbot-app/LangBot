"""Transport-neutral plugin and run operations over the existing secured Host actions.

Installation contexts are capabilities supplied by trusted Host code, never by a
request body. A run context cannot fall back to legacy plugin-wide privileges.
The existing runtime consumers are deliberately not routed through this facade.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.resp import ActionResponse
from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel, TypeAdapter, ValidationError, create_model

from .contracts import ApplicationAPIError, ApplicationAPIException, Input
from .streaming import isolated_stream

Text = Annotated[str, Field(min_length=1)]
Positive = Annotated[int, Field(gt=0)]
Nonnegative = Annotated[int, Field(ge=0)]
Object = dict[str, JsonValue]
QueryID = str | int


class JSONOutput(RootModel[Object]):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)


class Output(BaseModel):
    model_config = ConfigDict(extra='allow', strict=True, allow_inf_nan=False)
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)


def _input(name: str, **fields: Any) -> type[Input]:
    return create_model(name, __base__=Input, **fields)


def _output(name: str, **fields: Any) -> type[Output]:
    return create_model(name, __base__=Output, **fields)


@dataclass(frozen=True, slots=True)
class ExecutionAPIContext:
    binding: InstallationBinding
    run_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionOperation:
    action: str
    input_type: type[Input]
    output_type: Any
    scope: Literal['plugin', 'run', 'plugin_or_run', 'runner_admin'] = 'plugin'
    side_effect: bool = False
    streaming: bool = False

    @property
    def operation_id(self) -> str:
        return f'execution.{self.action}'

    def as_dict(self) -> dict[str, Any]:
        return {
            'id': self.operation_id,
            'version': '1',
            'scope': self.scope,
            'authorization': 'installation_binding_and_existing_host_capabilities',
            'side_effect': self.side_effect,
            'streaming': self.streaming,
            'input_schema': self.input_type.model_json_schema(),
            'output_schema': TypeAdapter(self.output_type).json_schema(),
        }


# Only reviewed business actions are public; runtime setup/chunks/ping stay internal.
Empty = _input('ExecutionEmptyInput')
Query = _input('ExecutionQueryInput', query_id=(QueryID, ...))
QueryKey = _input('ExecutionQueryKeyInput', query_id=(QueryID, ...), key=(Text, ...))
ModelCall = _input(
    'ExecutionModelInput',
    llm_model_uuid=(Text, ...),
    messages=(list[Object], ...),
    funcs=(list[Object], []),
    extra_args=(Object, {}),
    reasoning_level=(str | None, None),
    remove_think=(bool, False),
    query_id=(QueryID | None, None),
)
Retrieval = _input(
    'ExecutionRetrievalInput',
    kb_id=(Text, ...),
    query_text=(str, ...),
    top_k=(Positive, 5),
    filters=(Object | None, None),
)
Storage = _input('ExecutionStorageInput', owner_type=(Literal['plugin', 'workspace'], ...), key=(Text, ...))
State = _input('ExecutionStateInput', scope=(Text, ...), key=(Text, ...))
TargetRun = _input('ExecutionTargetRunInput', target_run_id=(Text | None, None))
Page = _input(
    'ExecutionPageInput',
    conversation_id=(Text | None, None),
    before_cursor=(str | None, None),
    after_cursor=(str | None, None),
    limit=(Positive, 50),
    direction=(Literal['forward', 'backward'], 'backward'),
    include_attachments=(bool, False),
)
TargetPage = _input(
    'ExecutionTargetPageInput',
    target_run_id=(Text | None, None),
    before_cursor=(str | None, None),
    after_cursor=(str | None, None),
    limit=(Positive, 50),
    direction=(Literal['forward', 'backward'], 'forward'),
)
ClaimFields = {'runtime_id': (Text, ...), 'claim_token': (Text, ...), 'target_run_id': (Text | None, None)}
RuntimeFields = {
    'runtime_id': (Text, ...),
    'status': (Text | None, None),
    'capabilities': (Object | None, None),
    'labels': (Object | None, None),
    'metadata': (Object | None, None),
    'heartbeat_deadline_at': (float | int | None, None),
    'heartbeat_ttl_seconds': (Positive, 60),
}

EmptyOutput = _output('ExecutionEmptyOutput')
ValueOutput = _output('ExecutionValueOutput', value=(JsonValue, ...))
ResultOutput = _output('ExecutionResultOutput', result=(JsonValue, ...))
ItemsOutput = _output('ExecutionItemsOutput', items=(list[JsonValue], ...))
ResultsOutput = _output('ExecutionResultsOutput', results=(list[JsonValue], ...))
KeysOutput = _output('ExecutionKeysOutput', keys=(list[str], ...))
PageOutput = _output(
    'ExecutionPageOutput',
    items=(list[JsonValue], ...),
    next_cursor=(str | None, ...),
    prev_cursor=(str | None, ...),
    has_more=(bool, ...),
)
RunOutput = _output('ExecutionRunOutput', run_id=(str, ...), status=(str, ...))
RuntimeOutput = _output('ExecutionRuntimeOutput', runtime_id=(str, ...))
EventOutput = _output('ExecutionEventOutput', event_id=(str, ...))
SuccessOutput = _output('ExecutionSuccessOutput', success=(bool, ...))
ToolOutput = _output('ExecutionToolResultOutput', tool_response=(JsonValue, ...)) | ResultOutput
StreamOutput = _output('ExecutionModelChunkOutput', chunk=(Object, ...)) | _output(
    'ExecutionModelUsageOutput', usage=(Object, ...)
)

EXECUTION_OPERATIONS = (
    ExecutionOperation(
        'reply_message',
        _input(
            'ExecutionReplyInput', query_id=(QueryID, ...), message_chain=(list[Object], ...), quote_origin=(bool, ...)
        ),
        EmptyOutput,
        side_effect=True,
    ),
    ExecutionOperation('get_bot_uuid', Query, _output('ExecutionBotIDOutput', bot_uuid=(str, ...))),
    ExecutionOperation(
        'set_query_var',
        _input('ExecutionSetQueryVariableInput', query_id=(QueryID, ...), key=(Text, ...), value=(JsonValue, ...)),
        EmptyOutput,
        side_effect=True,
    ),
    ExecutionOperation('get_query_var', QueryKey, ValueOutput),
    ExecutionOperation('get_query_vars', Query, _output('ExecutionVariablesOutput', vars=(Object, ...))),
    ExecutionOperation('create_new_conversation', Query, EmptyOutput, side_effect=True),
    ExecutionOperation(
        'get_langbot_version', Empty, _output('ExecutionVersionOutput', version=(str, ...)), 'plugin_or_run'
    ),
    ExecutionOperation('get_bots', Empty, _output('ExecutionBotsOutput', bots=(list[JsonValue], ...))),
    ExecutionOperation(
        'get_bot_info',
        _input('ExecutionBotInput', bot_uuid=(Text, ...)),
        _output('ExecutionBotOutput', bot=(Object, ...)),
    ),
    ExecutionOperation(
        'send_message',
        _input(
            'ExecutionSendInput',
            bot_uuid=(Text, ...),
            target_type=(Literal['person', 'group'], ...),
            target_id=(Text, ...),
            message_chain=(list[Object], ...),
        ),
        ResultOutput,
        'plugin_or_run',
        True,
    ),
    ExecutionOperation(
        'call_platform_api',
        _input(
            'ExecutionPlatformInput',
            bot_uuid=(Text | None, None),
            action=(Text, ...),
            params=(Object, {}),
            context_tool=(str | None, None),
            file_ids=(list[str] | None, None),
        ),
        ResultOutput,
        'plugin_or_run',
        True,
    ),
    ExecutionOperation(
        'reply_stream',
        _input(
            'ExecutionReplyStreamInput',
            stream_id=(Text, ...),
            operation=(Literal['update', 'finish', 'abort'], ...),
            text=(str, ...),
        ),
        ResultOutput,
        'run',
        True,
    ),
    ExecutionOperation('get_llm_models', Empty, _output('ExecutionModelsOutput', llm_models=(list[str], ...))),
    ExecutionOperation('count_tokens', ModelCall, _output('ExecutionTokensOutput', tokens=(int, ...)), 'plugin_or_run'),
    ExecutionOperation(
        'invoke_llm', ModelCall, _output('ExecutionModelOutput', message=(Object, ...)), 'plugin_or_run', True
    ),
    ExecutionOperation('invoke_llm_stream', ModelCall, StreamOutput, 'plugin_or_run', True, True),
    ExecutionOperation(
        'call_tool',
        _input(
            'ExecutionCallToolInput',
            tool_name=(Text, ...),
            parameters=(Object, {}),
            tool_parameters=(Object | None, None),
        ),
        ToolOutput,
        'plugin_or_run',
        True,
    ),
    ExecutionOperation(
        'get_tool_detail',
        _input('ExecutionToolInput', tool_name=(Text, ...)),
        _output('ExecutionToolOutput', tool=(Object, ...)),
        'plugin_or_run',
    ),
    ExecutionOperation(
        'set_binary_storage',
        _input(
            'ExecutionSetStorageInput',
            owner_type=(Literal['plugin', 'workspace'], ...),
            key=(Text, ...),
            value_base64=(str, ...),
        ),
        EmptyOutput,
        'plugin_or_run',
        True,
    ),
    ExecutionOperation(
        'get_binary_storage', Storage, _output('ExecutionStorageOutput', value_base64=(str, ...)), 'plugin_or_run'
    ),
    ExecutionOperation('delete_binary_storage', Storage, EmptyOutput, 'plugin_or_run', True),
    ExecutionOperation(
        'get_binary_storage_keys',
        _input('ExecutionStorageKeysInput', owner_type=(Literal['plugin', 'workspace'], ...)),
        KeysOutput,
        'plugin_or_run',
    ),
    ExecutionOperation(
        'get_config_file',
        _input('ExecutionConfigFileInput', file_key=(Text, ...)),
        _output('ExecutionConfigFileOutput', file_base64=(str, ...)),
    ),
    ExecutionOperation(
        'invoke_embedding',
        _input('ExecutionEmbeddingInput', embedding_model_uuid=(Text, ...), texts=(list[str], ...)),
        _output('ExecutionEmbeddingOutput', vectors=(list[list[float]], ...)),
        'plugin_or_run',
        True,
    ),
    ExecutionOperation(
        'invoke_rerank',
        _input(
            'ExecutionRerankInput',
            rerank_model_uuid=(Text, ...),
            query=(str, ...),
            documents=(list[str], ...),
            top_k=(Positive | None, None),
            extra_args=(Object, {}),
        ),
        ResultsOutput,
        'plugin_or_run',
        True,
    ),
    ExecutionOperation(
        'vector_upsert',
        _input(
            'ExecutionVectorUpsertInput',
            collection_id=(Text, ...),
            ids=(list[str], ...),
            vectors=(list[list[float]], ...),
            documents=(list[str] | None, None),
            metadata=(list[Object] | None, None),
        ),
        EmptyOutput,
        side_effect=True,
    ),
    ExecutionOperation(
        'vector_search',
        _input(
            'ExecutionVectorSearchInput',
            collection_id=(Text, ...),
            query_vector=(list[float], ...),
            top_k=(Positive, ...),
            filters=(Object | None, None),
            query_text=(str, ''),
            search_type=(str, 'vector'),
            vector_weight=(float, 0.5),
        ),
        ResultsOutput,
    ),
    ExecutionOperation(
        'vector_delete',
        _input(
            'ExecutionVectorDeleteInput',
            collection_id=(Text, ...),
            file_ids=(list[str] | None, None),
            filters=(Object | None, None),
        ),
        _output('ExecutionVectorDeleteOutput', count=(int, ...)),
        side_effect=True,
    ),
    ExecutionOperation(
        'vector_list',
        _input(
            'ExecutionVectorListInput',
            collection_id=(Text, ...),
            filters=(Object | None, None),
            limit=(Positive, 20),
            offset=(Nonnegative, 0),
        ),
        _output('ExecutionVectorListOutput', items=(list[JsonValue], ...), total=(int, ...)),
    ),
    ExecutionOperation(
        'get_knowledge_file_stream',
        _input('ExecutionKnowledgeFileInput', storage_path=(Text, ...)),
        _output('ExecutionKnowledgeFileOutput', file_key=(str, ...)),
        side_effect=True,
    ),
    ExecutionOperation(
        'list_parsers',
        _input('ExecutionParsersInput', mime_type=(str | None, None)),
        _output('ExecutionParsersOutput', parsers=(list[JsonValue], ...)),
    ),
    ExecutionOperation(
        'invoke_parser',
        _input(
            'ExecutionParserInput',
            plugin_author=(Text, ...),
            plugin_name=(Text, ...),
            storage_path=(Text, ...),
            filename=(str, ''),
            mime_type=(str, 'application/octet-stream'),
            metadata=(Object, {}),
        ),
        JSONOutput,
        side_effect=True,
    ),
    ExecutionOperation(
        'list_knowledge_bases', Empty, _output('ExecutionKnowledgeBasesOutput', knowledge_bases=(list[JsonValue], ...))
    ),
    ExecutionOperation('retrieve_knowledge', Retrieval, ResultsOutput, 'plugin_or_run'),
    ExecutionOperation(
        'list_pipeline_knowledge_bases',
        Query,
        _output('ExecutionPipelineKnowledgeBasesOutput', knowledge_bases=(list[JsonValue], ...)),
    ),
    ExecutionOperation(
        'retrieve_knowledge_base',
        _input(
            'ExecutionPipelineRetrievalInput',
            kb_id=(Text, ...),
            query_text=(str, ...),
            query_id=(QueryID | None, None),
            top_k=(Positive, 5),
            filters=(Object | None, None),
        ),
        ResultsOutput,
        'plugin_or_run',
    ),
    ExecutionOperation('get_prompt', Empty, _output('ExecutionPromptOutput', prompt=(list[Object], ...)), 'run'),
    ExecutionOperation('history_page', Page, PageOutput, 'run'),
    ExecutionOperation(
        'history_search',
        _input('ExecutionHistorySearchInput', query=(str, ''), filters=(Object | None, None), top_k=(Positive, 10)),
        _output('ExecutionHistorySearchOutput', items=(list[JsonValue], ...), total_count=(int, ...), query=(str, ...)),
        'run',
    ),
    ExecutionOperation('event_get', _input('ExecutionEventInput', event_id=(Text, ...)), EventOutput, 'run'),
    ExecutionOperation(
        'event_page',
        _input(
            'ExecutionEventPageInput',
            conversation_id=(Text | None, None),
            before_cursor=(str | None, None),
            event_types=(list[str] | None, None),
            limit=(Positive, 50),
        ),
        PageOutput,
        'run',
    ),
    ExecutionOperation(
        'steering_pull',
        _input('ExecutionSteeringInput', mode=(str, 'all'), limit=(Positive | None, None)),
        ItemsOutput,
        'run',
        True,
    ),
    ExecutionOperation('state_get', State, ValueOutput, 'run'),
    ExecutionOperation(
        'state_set',
        _input('ExecutionSetStateInput', scope=(Text, ...), key=(Text, ...), value=(JsonValue, ...)),
        SuccessOutput,
        'run',
        True,
    ),
    ExecutionOperation('state_delete', State, SuccessOutput, 'run', True),
    ExecutionOperation(
        'state_list',
        _input('ExecutionStateListInput', scope=(Text, ...), prefix=(str | None, None), limit=(Positive, 100)),
        _output('ExecutionStateKeysOutput', keys=(list[str], ...), has_more=(bool, ...)),
        'run',
    ),
    ExecutionOperation(
        'get_box_status',
        Empty,
        _output('ExecutionBoxStatusOutput', available=(bool, ...), enabled=(bool, ...)),
        'plugin_or_run',
    ),
    ExecutionOperation('list_boxes', Empty, ItemsOutput, 'plugin_or_run'),
    ExecutionOperation(
        'acquire_box',
        _input('ExecutionAcquireBoxInput', reuse_key=(Text, ...), options=(Object, {})),
        _output('ExecutionBoxOutput', id=(str, ...), status=(str, ...)),
        'plugin_or_run',
        True,
    ),
    ExecutionOperation(
        'bind_box',
        _input('ExecutionBindBoxInput', box_id=(Text, ...)),
        _output('ExecutionBoxBindingOutput', box_id=(str, ...), outbox=(str, ...)),
        'run',
        True,
    ),
    ExecutionOperation(
        'import_box_attachments',
        _input('ExecutionImportAttachmentsInput', attachment_ids=(list[str] | None, None)),
        ItemsOutput,
        'run',
        True,
    ),
    ExecutionOperation(
        'export_box_files', _input('ExecutionExportBoxInput', paths=(list[str] | None, None)), ItemsOutput, 'run', True
    ),
    ExecutionOperation('run_get', TargetRun, RunOutput, 'runner_admin'),
    ExecutionOperation(
        'run_list',
        _input(
            'ExecutionRunsInput',
            conversation_id=(Text | None, None),
            statuses=(list[str] | None, None),
            before_cursor=(str | None, None),
            limit=(Positive, 50),
        ),
        PageOutput,
        'runner_admin',
    ),
    ExecutionOperation('run_events_page', TargetPage, PageOutput, 'runner_admin'),
    ExecutionOperation(
        'run_cancel',
        _input(
            'ExecutionCancelRunInput',
            target_run_id=(Text | None, None),
            reason=(str | None, None),
            status_reason=(str | None, None),
        ),
        RunOutput,
        'runner_admin',
        True,
    ),
    ExecutionOperation(
        'run_append_result',
        _input(
            'ExecutionAppendResultInput',
            target_run_id=(Text | None, None),
            sequence=(Positive | None, None),
            event_type=(str | None, None),
            type=(str | None, None),
            data=(Object | None, None),
            result=(Object | None, None),
            usage=(Object | None, None),
            metadata=(Object | None, None),
            source=(str | None, None),
            runtime_id=(str | None, None),
            claim_token=(str | None, None),
        ),
        JSONOutput,
        'runner_admin',
        True,
    ),
    ExecutionOperation(
        'run_finalize',
        _input(
            'ExecutionFinalizeRunInput',
            target_run_id=(Text | None, None),
            status=(Text, ...),
            reason=(str | None, None),
            status_reason=(str | None, None),
            usage=(Object | None, None),
            cost=(Object | None, None),
            metadata=(Object | None, None),
            runtime_id=(str | None, None),
            claim_token=(str | None, None),
        ),
        RunOutput,
        'runner_admin',
        True,
    ),
    ExecutionOperation(
        'runner_list',
        _input('ExecutionRunnersInput', include_plugins=(list[str] | None, None), use_cache=(bool, True)),
        ItemsOutput,
        'runner_admin',
    ),
    ExecutionOperation(
        'runtime_register',
        _input(
            'ExecutionRegisterRuntimeInput',
            **RuntimeFields,
            display_name=(str | None, None),
            endpoint=(str | None, None),
            version=(str | None, None),
        ),
        RuntimeOutput,
        'runner_admin',
        True,
    ),
    ExecutionOperation(
        'runtime_heartbeat',
        _input('ExecutionRuntimeHeartbeatInput', **RuntimeFields),
        RuntimeOutput,
        'runner_admin',
        True,
    ),
    ExecutionOperation(
        'runtime_list',
        _input(
            'ExecutionRuntimesInput',
            statuses=(list[str] | None, None),
            labels=(Object | None, None),
            limit=(Positive, 50),
        ),
        PageOutput,
        'runner_admin',
    ),
    ExecutionOperation(
        'runtime_reconcile',
        _input('ExecutionRuntimeReconcileInput', stale_after_seconds=(Positive, 60)),
        JSONOutput,
        'runner_admin',
        True,
    ),
    ExecutionOperation(
        'run_stats',
        _input(
            'ExecutionRunStatsInput',
            runner_id=(str | None, None),
            start_time=(int | float | None, None),
            end_time=(int | float | None, None),
        ),
        JSONOutput,
        'runner_admin',
    ),
    ExecutionOperation('runtime_stats', Empty, JSONOutput, 'runner_admin'),
    ExecutionOperation(
        'runner_stats',
        _input(
            'ExecutionRunnerStatsInput',
            start_time=(int | float | None, None),
            end_time=(int | float | None, None),
            limit=(Positive, 50),
        ),
        ItemsOutput,
        'runner_admin',
    ),
    ExecutionOperation(
        'run_claim',
        _input(
            'ExecutionClaimRunInput',
            runtime_id=(Text, ...),
            lease_seconds=(Positive, 60),
            queue_name=(str | None, None),
            runner_ids=(list[str] | None, None),
        ),
        JSONOutput,
        'runner_admin',
        True,
    ),
    ExecutionOperation(
        'run_renew_claim',
        _input('ExecutionRenewClaimInput', **ClaimFields, lease_seconds=(Positive, 60)),
        RunOutput,
        'runner_admin',
        True,
    ),
    ExecutionOperation(
        'run_release_claim',
        _input(
            'ExecutionReleaseClaimInput',
            **ClaimFields,
            reason=(str | None, None),
            status_reason=(str | None, None),
            status=(Text, 'queued'),
        ),
        RunOutput,
        'runner_admin',
        True,
    ),
)
_BY_ID = {operation.operation_id: operation for operation in EXECUTION_OPERATIONS}


def _fail(code: str, message: str, status: int = 400) -> None:
    raise ApplicationAPIException(ApplicationAPIError(code, message, status))


class ExecutionAPI:
    """Invoke Host APIs with trusted installation/run capabilities, without a transport."""

    def __init__(self, ap: Any):
        self.ap = ap

    def operations(self) -> tuple[ExecutionOperation, ...]:
        return EXECUTION_OPERATIONS

    def catalog(self) -> list[dict[str, Any]]:
        return [operation.as_dict() for operation in self.operations()]

    @contextlib.asynccontextmanager
    async def _invocation(self, operation_id: str, context: ExecutionAPIContext, payload: dict, *, streaming: bool):
        operation = _BY_ID.get(operation_id)
        if operation is None:
            _fail('unknown_operation', f'Unknown execution operation: {operation_id}', 404)
        if operation.streaming != streaming:
            _fail('invalid_input', 'Use stream for streaming operations and invoke for unary operations')
        if not isinstance(context, ExecutionAPIContext) or not isinstance(context.binding, InstallationBinding):
            _fail('invalid_authentication', 'A trusted installation binding is required', 401)
        if context.run_id is not None and (not isinstance(context.run_id, str) or not context.run_id.strip()):
            _fail('invalid_authentication', 'The trusted run ID is invalid', 401)
        if context.run_id is None and operation.scope == 'run':
            _fail('permission_denied', 'This operation requires a trusted run context', 403)
        if context.run_id is not None and operation.scope == 'plugin':
            _fail('permission_denied', 'A run cannot use legacy plugin-wide operations', 403)
        try:
            data = operation.input_type.model_validate(payload).model_dump(exclude_unset=True)
        except ValidationError:
            _fail('invalid_input', f'Input does not match {operation.input_type.__name__}')
        if operation.action == 'call_platform_api' and context.run_id is None and not data.get('bot_uuid'):
            _fail('invalid_input', 'bot_uuid is required outside a run')
        if operation.action == 'call_tool':
            if context.run_id is not None:
                if 'tool_parameters' in data:
                    _fail('invalid_input', 'Run tool calls use parameters')
                data.setdefault('parameters', {})
            elif 'parameters' in data:
                if 'tool_parameters' in data:
                    _fail('invalid_input', 'Supply either parameters or tool_parameters')
                data['tool_parameters'] = data.pop('parameters')
        handler = getattr(getattr(self.ap, 'plugin_connector', None), 'handler', None)
        if handler is None or operation.action not in handler.actions:
            _fail('application_error', 'The execution Host does not provide this operation', 503)
        try:
            handler.validate_inbound_action_context(operation.action, context.binding)
        except (TypeError, ValueError):
            _fail('invalid_authentication', 'Invalid installation binding', 401)
        token = handler._current_action_context.set(context.binding)
        try:
            async with handler._tenant_action_scope(context.binding):
                try:
                    _, identity = await handler._require_plugin_action_context()
                    await handler._require_active_action_context(context.binding)
                except (TypeError, ValueError):
                    _fail('permission_denied', 'Installation binding is invalid or stale', 403)
                if context.run_id is not None:
                    if 'query_id' in data:
                        _fail('invalid_input', 'A run context supplies its own query identity')
                    from ...agent.runner.session_registry import get_session_registry
                    from ...plugin.agent_run_support import _load_persistent_agent_run_session

                    session = await get_session_registry().get(context.run_id)
                    if session is None and operation.scope == 'runner_admin':
                        session = await _load_persistent_agent_run_session(context.run_id, self.ap, operation.action)
                    if (
                        session is None
                        or session['authorization'].get('workspace_id') != context.binding.workspace_uuid
                        or session.get('plugin_identity') != f'{identity.plugin_author}/{identity.plugin_name}'
                    ):
                        _fail('permission_denied', 'Run does not belong to this installation Workspace', 403)
                    data['run_id'] = context.run_id
                yield operation, handler.actions[operation.action], data
        finally:
            handler._current_action_context.reset(token)

    @staticmethod
    def _result(operation: ExecutionOperation, response: Any) -> dict:
        if not isinstance(response, ActionResponse):
            _fail('invalid_output', 'Execution Host returned an invalid response', 500)
        if response.code != 0:
            # The Host exposes structured Box export failures as a public error contract.
            from langbot_plugin.api.entities.builtin.runner.errors import AgentAPIError

            details = None
            if operation.action == 'export_box_files' and 'error' in response.data:
                try:
                    details = {'error': AgentAPIError.model_validate(response.data['error']).model_dump(mode='json')}
                except ValidationError:
                    _fail('invalid_output', 'Invalid Box export error details', 500)
            raise ApplicationAPIException(ApplicationAPIError('application_error', response.message, 400, details))
        try:
            result = TypeAdapter(operation.output_type).validate_python(response.data, strict=True)
            return result.model_dump(mode='json')
        except ValidationError:
            _fail('invalid_output', f'Output does not match {operation.action}', 500)

    async def invoke(self, operation_id: str, context: ExecutionAPIContext, payload: dict | None = None) -> dict:
        try:
            async with self._invocation(
                operation_id, context, {} if payload is None else payload, streaming=False
            ) as call:
                operation, action, data = call
                return self._result(operation, await action(data))
        except ApplicationAPIException:
            raise
        except Exception:
            _fail('application_error', 'Execution operation failed', 500)

    async def stream(self, operation_id: str, context: ExecutionAPIContext, payload: dict | None = None):
        async def produce():
            try:
                async with self._invocation(
                    operation_id, context, {} if payload is None else payload, streaming=True
                ) as call:
                    operation, action, data = call
                    async with contextlib.aclosing(action(data)) as responses:
                        async for response in responses:
                            yield self._result(operation, response)
            except ApplicationAPIException:
                raise
            except Exception:
                _fail('application_error', 'Execution stream failed', 500)

        async with contextlib.aclosing(isolated_stream(produce())) as responses:
            async for response in responses:
                yield response
