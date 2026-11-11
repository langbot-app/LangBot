"""Typed Workspace Application API domains.

Regenerate with LangBot/scripts/generate_plugin_workspace_api.py; requires Core
only at generation time. Calls preserve workspace.call()'s ok/result/error envelope
and authorization. No run_id is required to construct or use these domains.
Python keywords gain a trailing underscore (e.g. import_); non-identifier
characters become underscores. Parameter aliases are documented on each method
and always forwarded using the original schema keys.
An omitted optional field without a schema default is not sent. Open JSON objects
use JSONValue; declared object properties use TypedDict. JSON arrays, including
fixed-length arrays, remain lists on the wire.
"""

import builtins
from typing import TYPE_CHECKING, Generic, Literal, TypeVar, Union, cast

from typing_extensions import NotRequired, TypedDict

if TYPE_CHECKING:
    from .workspace import WorkspaceOperationsProxy

JSONValue = Union[None, bool, int, float, str, list["JSONValue"], dict[str, "JSONValue"]]
Result = TypeVar("Result")


class OperationError(TypedDict):
    code: str
    message: str
    details: NotRequired[JSONValue]


class OperationSuccess(TypedDict, Generic[Result]):
    ok: Literal[True]
    result: Result
    operation: NotRequired[dict[str, JSONValue]]


class OperationFailure(TypedDict):
    ok: Literal[False]
    error: OperationError
    operation: NotRequired[dict[str, JSONValue]]


OperationResult = Union[OperationSuccess[Result], OperationFailure]


class _Unset:
    pass


_UNSET = _Unset()


ModelLlmStarredSetArguments = TypedDict('ModelLlmStarredSetArguments', {
    'model_uuid': Union[str, None],
})

AgentRunsEventsArguments = TypedDict('AgentRunsEventsArguments', {
    'after_sequence': NotRequired[Union[int, None]],
    'processor_id': str,
    'run_id': str,
})

AgentRunsListArguments = TypedDict('AgentRunsListArguments', {
    'before_id': NotRequired[Union[int, None]],
    'processor_id': str,
})

BotAdminsListArguments = TypedDict('BotAdminsListArguments', {
    'bot_uuid': str,
})

BotGroupFilterApplyArguments = TypedDict('BotGroupFilterApplyArguments', {
    'bot_uuid': str,
    'disable_pipeline_at_bot': NotRequired[bool],
})

BotGroupFilterPreviewArguments = TypedDict('BotGroupFilterPreviewArguments', {
    'bot_uuid': str,
})

BotMessageSendArguments = TypedDict('BotMessageSendArguments', {
    'bot_uuid': str,
    'message_chain_data': dict[str, JSONValue],
    'target_id': str,
    'target_type': str,
})

BotMessageTestArguments = TypedDict('BotMessageTestArguments', {
    'bot_uuid': str,
    'message': str,
})

BotRoutesPreviewArguments = TypedDict('BotRoutesPreviewArguments', {
    'bot_uuid': str,
    'event_bindings': NotRequired[Union[builtins.list[dict[str, JSONValue]], None]],
    'event_context': NotRequired[Union[dict[str, JSONValue], None]],
    'event_data': NotRequired[Union[dict[str, JSONValue], None]],
    'event_type': str,
})

BotRoutesStatusArguments = TypedDict('BotRoutesStatusArguments', {
    'bot_uuid': str,
})

BotRuntimeGetArguments = TypedDict('BotRuntimeGetArguments', {
    'bot_uuid': str,
    'include_secret': NotRequired[bool],
})

KnowledgeBaseCreateArguments = TypedDict('KnowledgeBaseCreateArguments', {
    'kb_data': dict[str, JSONValue],
})

KnowledgeBaseDeleteArguments = TypedDict('KnowledgeBaseDeleteArguments', {
    'kb_uuid': str,
})

KnowledgeBaseGetArguments = TypedDict('KnowledgeBaseGetArguments', {
    'include_secret': NotRequired[bool],
    'kb_uuid': str,
})

KnowledgeBaseListArguments = TypedDict('KnowledgeBaseListArguments', {
    'include_secret': NotRequired[bool],
})

KnowledgeBaseRetrieveArguments = TypedDict('KnowledgeBaseRetrieveArguments', {
    'kb_uuid': str,
    'query': str,
    'retrieval_settings': NotRequired[Union[dict[str, JSONValue], None]],
})

KnowledgeBaseUpdateArguments = TypedDict('KnowledgeBaseUpdateArguments', {
    'kb_data': dict[str, JSONValue],
    'kb_uuid': str,
})

KnowledgeEngineCreationSchemaArguments = TypedDict('KnowledgeEngineCreationSchemaArguments', {
    'plugin_id': str,
})

KnowledgeEngineRetrievalSchemaArguments = TypedDict('KnowledgeEngineRetrievalSchemaArguments', {
    'plugin_id': str,
})

KnowledgeFileDeleteArguments = TypedDict('KnowledgeFileDeleteArguments', {
    'file_id': str,
    'kb_uuid': str,
})

KnowledgeFileListArguments = TypedDict('KnowledgeFileListArguments', {
    'kb_uuid': str,
})

KnowledgeFileStoreArguments = TypedDict('KnowledgeFileStoreArguments', {
    'file_id': str,
    'kb_uuid': str,
    'parser_plugin_id': NotRequired[Union[str, None]],
})

KnowledgeParserListArguments = TypedDict('KnowledgeParserListArguments', {
    'mime_type': NotRequired[Union[str, None]],
})

McpResourceListArguments = TypedDict('McpResourceListArguments', {
    'server_name': str,
})

McpResourceReadArguments = TypedDict('McpResourceReadArguments', {
    'include_blob': NotRequired[bool],
    'max_bytes': NotRequired[Union[int, None]],
    'server_name': str,
    'uri': str,
})

McpResourceTemplatesArguments = TypedDict('McpResourceTemplatesArguments', {
    'server_name': str,
})

McpServerDeleteArguments = TypedDict('McpServerDeleteArguments', {
    'server_uuid': str,
})

McpServerGetArguments = TypedDict('McpServerGetArguments', {
    'server_name': str,
})

McpServerListArguments = TypedDict('McpServerListArguments', {
    'contain_runtime_info': NotRequired[bool],
})

McpServerLogsArguments = TypedDict('McpServerLogsArguments', {
    'level': NotRequired[Union[str, None]],
    'limit': NotRequired[int],
    'server_name': str,
})

McpServerRuntimeArguments = TypedDict('McpServerRuntimeArguments', {
    'server_name': str,
})

McpServerTestArguments = TypedDict('McpServerTestArguments', {
    'server_data': dict[str, JSONValue],
    'server_name': str,
})

ModelEmbeddingCreateArguments = TypedDict('ModelEmbeddingCreateArguments', {
    'model_data': dict[str, JSONValue],
})

ModelEmbeddingDeleteArguments = TypedDict('ModelEmbeddingDeleteArguments', {
    'model_uuid': str,
})

ModelEmbeddingGetArguments = TypedDict('ModelEmbeddingGetArguments', {
    'include_secret': NotRequired[bool],
    'model_uuid': str,
})

ModelEmbeddingListArguments = TypedDict('ModelEmbeddingListArguments', {
    'include_secret': NotRequired[bool],
})

ModelEmbeddingListByProviderArguments = TypedDict('ModelEmbeddingListByProviderArguments', {
    'include_secret': NotRequired[bool],
    'provider_uuid': str,
})

ModelEmbeddingTestArguments = TypedDict('ModelEmbeddingTestArguments', {
    'model_data': dict[str, JSONValue],
    'model_uuid': str,
})

ModelEmbeddingUpdateArguments = TypedDict('ModelEmbeddingUpdateArguments', {
    'model_data': dict[str, JSONValue],
    'model_uuid': str,
})

ModelLlmCreateArguments = TypedDict('ModelLlmCreateArguments', {
    'auto_set_to_default_pipeline': NotRequired[bool],
    'model_data': dict[str, JSONValue],
})

ModelLlmDeleteArguments = TypedDict('ModelLlmDeleteArguments', {
    'model_uuid': str,
})

ModelLlmGetArguments = TypedDict('ModelLlmGetArguments', {
    'include_secret': NotRequired[bool],
    'model_uuid': str,
})

ModelLlmListArguments = TypedDict('ModelLlmListArguments', {
    'include_secret': NotRequired[bool],
})

ModelLlmListByProviderArguments = TypedDict('ModelLlmListByProviderArguments', {
    'include_secret': NotRequired[bool],
    'provider_uuid': str,
})

ModelLlmTestArguments = TypedDict('ModelLlmTestArguments', {
    'model_data': dict[str, JSONValue],
    'model_uuid': str,
})

ModelLlmUpdateArguments = TypedDict('ModelLlmUpdateArguments', {
    'model_data': dict[str, JSONValue],
    'model_uuid': str,
})

ModelRerankCreateArguments = TypedDict('ModelRerankCreateArguments', {
    'model_data': dict[str, JSONValue],
})

ModelRerankDeleteArguments = TypedDict('ModelRerankDeleteArguments', {
    'model_uuid': str,
})

ModelRerankGetArguments = TypedDict('ModelRerankGetArguments', {
    'include_secret': NotRequired[bool],
    'model_uuid': str,
})

ModelRerankListArguments = TypedDict('ModelRerankListArguments', {
    'include_secret': NotRequired[bool],
})

ModelRerankListByProviderArguments = TypedDict('ModelRerankListByProviderArguments', {
    'include_secret': NotRequired[bool],
    'provider_uuid': str,
})

ModelRerankTestArguments = TypedDict('ModelRerankTestArguments', {
    'model_data': dict[str, JSONValue],
    'model_uuid': str,
})

ModelRerankUpdateArguments = TypedDict('ModelRerankUpdateArguments', {
    'model_data': dict[str, JSONValue],
    'model_uuid': str,
})

MonitoringExecutionDetailArguments = TypedDict('MonitoringExecutionDetailArguments', {
    'execution_id': str,
    'limit': NotRequired[int],
    'offset': NotRequired[int],
    'section': NotRequired[Union[str, None]],
    'source': str,
})

MonitoringFeedbackListArguments = TypedDict('MonitoringFeedbackListArguments', {
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'end_time': NotRequired[Union[str, None]],
    'execution_statuses': NotRequired[Union[builtins.list[str], None]],
    'feedback_type': NotRequired[Union[int, None]],
    'limit': NotRequired[int],
    'mode': NotRequired[str],
    'offset': NotRequired[int],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'start_time': NotRequired[Union[str, None]],
})

MonitoringFeedbackStatsArguments = TypedDict('MonitoringFeedbackStatsArguments', {
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'end_time': NotRequired[Union[str, None]],
    'execution_statuses': NotRequired[Union[builtins.list[str], None]],
    'mode': NotRequired[str],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'start_time': NotRequired[Union[str, None]],
})

MonitoringMessageDetailArguments = TypedDict('MonitoringMessageDetailArguments', {
    'message_id': str,
})

MonitoringSessionAnalysisArguments = TypedDict('MonitoringSessionAnalysisArguments', {
    'bot_id': NotRequired[Union[str, None]],
    'end_time': NotRequired[Union[str, None]],
    'session_id': str,
    'start_time': NotRequired[Union[str, None]],
})

MonitoringSessionResetArguments = TypedDict('MonitoringSessionResetArguments', {
    'bot_id': str,
    'session_id': str,
})

PipelineChatBroadcastArguments = TypedDict('PipelineChatBroadcastArguments', {
    'message': str,
    'pipeline_uuid': str,
})

PipelineChatConnectionsArguments = TypedDict('PipelineChatConnectionsArguments', {
    'pipeline_uuid': str,
})

PipelineChatHistoryArguments = TypedDict('PipelineChatHistoryArguments', {
    'pipeline_uuid': str,
    'session_type': Literal['person', 'group'],
})

PipelineChatResetArguments = TypedDict('PipelineChatResetArguments', {
    'pipeline_uuid': str,
    'session_type': Literal['person', 'group'],
})

PipelineExtensionsGetArguments = TypedDict('PipelineExtensionsGetArguments', {
    'pipeline_uuid': str,
})

PipelineExtensionsUpdateArguments = TypedDict('PipelineExtensionsUpdateArguments', {
    'allowed_platform_tools': NotRequired[Union[builtins.list[str], None]],
    'bound_mcp_resources': NotRequired[Union[builtins.list[dict[str, JSONValue]], None]],
    'bound_mcp_servers': NotRequired[Union[builtins.list[str], None]],
    'bound_plugins': builtins.list[dict[str, JSONValue]],
    'bound_skills': NotRequired[Union[builtins.list[str], None]],
    'enable_all_mcp_servers': NotRequired[bool],
    'enable_all_plugins': NotRequired[bool],
    'enable_all_skills': NotRequired[bool],
    'mcp_resource_agent_read_enabled': NotRequired[Union[bool, None]],
    'pipeline_uuid': str,
    'workspace_operations': NotRequired[Union[builtins.list[str], None]],
})

PluginConfigGetArguments = TypedDict('PluginConfigGetArguments', {
    'author': str,
    'plugin_name': str,
})

PluginConfigGetOutput = TypedDict('PluginConfigGetOutput', {
    'config': dict[str, JSONValue],
})

PluginGithubAssetsArguments = TypedDict('PluginGithubAssetsArguments', {
    'owner': str,
    'release_id': int,
    'repo': str,
})

PluginGithubReleasesArguments = TypedDict('PluginGithubReleasesArguments', {
    'repo_url': str,
})

PluginInstallMarketplaceArguments = TypedDict('PluginInstallMarketplaceArguments', {
    'auto_confirm_permissions': NotRequired[bool],
    'plugin_author': str,
    'plugin_name': str,
    'plugin_version': NotRequired[Union[str, None]],
})

PluginInstallMarketplaceOutput = TypedDict('PluginInstallMarketplaceOutput', {
    'task_id': int,
})

PluginMarketplaceSearchArguments = TypedDict('PluginMarketplaceSearchArguments', {
    'component_filter': NotRequired[Union[str, None]],
    'page': NotRequired[int],
    'page_size': NotRequired[int],
    'query': NotRequired[str],
    'sort_by': NotRequired[Literal['install_count', 'like_count', 'created_at', 'updated_at']],
    'sort_order': NotRequired[Literal['ASC', 'DESC']],
    'tags_filter': NotRequired[builtins.list[str]],
})

PluginMarketplaceSearchOutput = TypedDict('PluginMarketplaceSearchOutput', {
    'page': int,
    'page_size': int,
    'plugins': builtins.list[dict[str, JSONValue]],
    'total': int,
})

ProviderModelsCountArguments = TypedDict('ProviderModelsCountArguments', {
    'provider_uuid': str,
})

ProviderModelsScanArguments = TypedDict('ProviderModelsScanArguments', {
    'model_type': NotRequired[Union[str, None]],
    'provider_uuid': str,
})

SkillFileListArguments = TypedDict('SkillFileListArguments', {
    'include_hidden': NotRequired[bool],
    'max_entries': NotRequired[int],
    'path': NotRequired[str],
    'skill_name': str,
})

SkillFileReadArguments = TypedDict('SkillFileReadArguments', {
    'path': str,
    'skill_name': str,
})

SkillFileWriteArguments = TypedDict('SkillFileWriteArguments', {
    'base_revision': Union[str, None],
    'content': str,
    'path': str,
    'skill_name': str,
})

SkillGithubPreviewArguments = TypedDict('SkillGithubPreviewArguments', {
    'data': dict[str, JSONValue],
})

AdapterGetArguments = TypedDict('AdapterGetArguments', {
    'adapter_name': str,
})

AgentCreateArguments = TypedDict('AgentCreateArguments', {
    'agent_data': dict[str, JSONValue],
})

AgentDebugArguments = TypedDict('AgentDebugArguments', {
    'agent_uuid': str,
    'payload': dict[str, JSONValue],
})

AgentDeleteArguments = TypedDict('AgentDeleteArguments', {
    'agent_uuid': str,
})

AgentGetArguments = TypedDict('AgentGetArguments', {
    'agent_uuid': str,
})

AgentListArguments = TypedDict('AgentListArguments', {
    'sort_by': NotRequired[str],
    'sort_order': NotRequired[str],
})

AgentUpdateArguments = TypedDict('AgentUpdateArguments', {
    'agent_data': dict[str, JSONValue],
    'agent_uuid': str,
})

BotCreateArgumentsBotData = TypedDict('BotCreateArgumentsBotData', {
    'adapter': str,
    'adapter_config': dict[str, JSONValue],
    'name': str,
})

BotCreateArguments = TypedDict('BotCreateArguments', {
    'bot_data': BotCreateArgumentsBotData,
})

BotCreateBotDataInput = TypedDict('BotCreateBotDataInput', {
    'adapter': str,
    'adapter_config': dict[str, JSONValue],
    'name': str,
})

BotDeleteArguments = TypedDict('BotDeleteArguments', {
    'bot_uuid': str,
})

BotGetArguments = TypedDict('BotGetArguments', {
    'bot_uuid': str,
    'include_secret': NotRequired[bool],
})

BotListArguments = TypedDict('BotListArguments', {
    'include_secret': NotRequired[bool],
})

BotLogsArguments = TypedDict('BotLogsArguments', {
    'bot_uuid': str,
    'from_index': int,
    'max_count': int,
})

BotUpdateArguments = TypedDict('BotUpdateArguments', {
    'bot_data': dict[str, JSONValue],
    'bot_uuid': str,
})

MonitoringEmbeddingCallsArguments = TypedDict('MonitoringEmbeddingCallsArguments', {
    'end_time': NotRequired[Union[str, None]],
    'execution_statuses': NotRequired[Union[builtins.list[str], None]],
    'knowledge_base_id': NotRequired[Union[str, None]],
    'limit': NotRequired[int],
    'mode': NotRequired[str],
    'offset': NotRequired[int],
    'start_time': NotRequired[Union[str, None]],
})

MonitoringErrorsArguments = TypedDict('MonitoringErrorsArguments', {
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'end_time': NotRequired[Union[str, None]],
    'execution_statuses': NotRequired[Union[builtins.list[str], None]],
    'limit': NotRequired[int],
    'mode': NotRequired[str],
    'offset': NotRequired[int],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'start_time': NotRequired[Union[str, None]],
})

MonitoringExecutionsArguments = TypedDict('MonitoringExecutionsArguments', {
    'agent_ids': NotRequired[Union[builtins.list[str], None]],
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'end_time': NotRequired[Union[str, None]],
    'include_summary': NotRequired[bool],
    'limit': NotRequired[int],
    'mode': NotRequired[str],
    'offset': NotRequired[int],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'source': NotRequired[str],
    'start_time': NotRequired[Union[str, None]],
    'statuses': NotRequired[Union[builtins.list[str], None]],
})

MonitoringInflightArguments = TypedDict('MonitoringInflightArguments', {
    'previous': NotRequired[Union[builtins.list[dict[str, JSONValue]], None]],
})

MonitoringLlmCallsArguments = TypedDict('MonitoringLlmCallsArguments', {
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'end_time': NotRequired[Union[str, None]],
    'execution_statuses': NotRequired[Union[builtins.list[str], None]],
    'limit': NotRequired[int],
    'mode': NotRequired[str],
    'offset': NotRequired[int],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'start_time': NotRequired[Union[str, None]],
})

MonitoringMessagesArguments = TypedDict('MonitoringMessagesArguments', {
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'end_time': NotRequired[Union[str, None]],
    'execution_statuses': NotRequired[Union[builtins.list[str], None]],
    'limit': NotRequired[int],
    'mode': NotRequired[str],
    'offset': NotRequired[int],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'session_ids': NotRequired[Union[builtins.list[str], None]],
    'start_time': NotRequired[Union[str, None]],
})

MonitoringOverviewArguments = TypedDict('MonitoringOverviewArguments', {
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'end_time': NotRequired[Union[str, None]],
    'execution_statuses': NotRequired[Union[builtins.list[str], None]],
    'mode': NotRequired[str],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'start_time': NotRequired[Union[str, None]],
})

MonitoringSessionsArguments = TypedDict('MonitoringSessionsArguments', {
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'end_time': NotRequired[Union[str, None]],
    'is_active': NotRequired[Union[bool, None]],
    'limit': NotRequired[int],
    'offset': NotRequired[int],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'start_time': NotRequired[Union[str, None]],
    'user_query': NotRequired[Union[str, None]],
})

MonitoringTokensArguments = TypedDict('MonitoringTokensArguments', {
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'bucket': NotRequired[str],
    'end_time': NotRequired[Union[str, None]],
    'execution_statuses': NotRequired[Union[builtins.list[str], None]],
    'mode': NotRequired[str],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'start_time': NotRequired[Union[str, None]],
})

MonitoringToolCallsArguments = TypedDict('MonitoringToolCallsArguments', {
    'bot_ids': NotRequired[Union[builtins.list[str], None]],
    'end_time': NotRequired[Union[str, None]],
    'execution_statuses': NotRequired[Union[builtins.list[str], None]],
    'limit': NotRequired[int],
    'mode': NotRequired[str],
    'offset': NotRequired[int],
    'pipeline_ids': NotRequired[Union[builtins.list[str], None]],
    'session_ids': NotRequired[Union[builtins.list[str], None]],
    'start_time': NotRequired[Union[str, None]],
})

PipelineCopyArguments = TypedDict('PipelineCopyArguments', {
    'pipeline_uuid': str,
})

PipelineCreateArguments = TypedDict('PipelineCreateArguments', {
    'pipeline_data': dict[str, JSONValue],
    'runner_id': NotRequired[Union[str, None]],
})

PipelineDefaultsArguments = TypedDict('PipelineDefaultsArguments', {
    'runner_id': NotRequired[Union[str, None]],
})

PipelineDeleteArguments = TypedDict('PipelineDeleteArguments', {
    'pipeline_uuid': str,
})

PipelineGetArguments = TypedDict('PipelineGetArguments', {
    'include_secret': NotRequired[bool],
    'pipeline_uuid': str,
})

PipelineListArguments = TypedDict('PipelineListArguments', {
    'include_secret': NotRequired[bool],
    'sort_by': NotRequired[str],
    'sort_order': NotRequired[str],
})

PipelineRunArguments = TypedDict('PipelineRunArguments', {
    'pipeline_uuid': str,
    'text': str,
    'timeout': NotRequired[float],
})

PipelineUpdateArguments = TypedDict('PipelineUpdateArguments', {
    'pipeline_data': dict[str, JSONValue],
    'pipeline_uuid': str,
})

PluginDebugInfoOutput = TypedDict('PluginDebugInfoOutput', {
    'debug_url': str,
    'expires_at': str,
    'plugin_debug_key': str,
})

PluginGetArguments = TypedDict('PluginGetArguments', {
    'author': str,
    'plugin_name': str,
})

PluginGetOutput = TypedDict('PluginGetOutput', {
    'plugin': dict[str, JSONValue],
})

PluginListOutput = TypedDict('PluginListOutput', {
    'plugins': builtins.list[dict[str, JSONValue]],
})

PluginLogsArguments = TypedDict('PluginLogsArguments', {
    'author': str,
    'level': NotRequired[Union[str, None]],
    'limit': NotRequired[int],
    'plugin_name': str,
})

PluginReadmeArguments = TypedDict('PluginReadmeArguments', {
    'author': str,
    'language': NotRequired[str],
    'plugin_name': str,
})

PluginReadmeOutput = TypedDict('PluginReadmeOutput', {
    'readme': str,
})

ProviderCreateArguments = TypedDict('ProviderCreateArguments', {
    'provider_data': dict[str, JSONValue],
})

ProviderDeleteArguments = TypedDict('ProviderDeleteArguments', {
    'cascade': NotRequired[bool],
    'provider_uuid': str,
})

ProviderGetArguments = TypedDict('ProviderGetArguments', {
    'include_secret': NotRequired[bool],
    'provider_uuid': str,
})

ProviderListArguments = TypedDict('ProviderListArguments', {
    'include_secret': NotRequired[bool],
})

ProviderUpdateArguments = TypedDict('ProviderUpdateArguments', {
    'provider_data': dict[str, JSONValue],
    'provider_uuid': str,
})

RequesterGetArguments = TypedDict('RequesterGetArguments', {
    'requester_name': str,
})

RequesterListArguments = TypedDict('RequesterListArguments', {
    'model_type': NotRequired[str],
})

SkillCreateArguments = TypedDict('SkillCreateArguments', {
    'data': dict[str, JSONValue],
})

SkillDeleteArguments = TypedDict('SkillDeleteArguments', {
    'skill_name': str,
})

SkillGetArguments = TypedDict('SkillGetArguments', {
    'skill_name': str,
})

SkillUpdateArguments = TypedDict('SkillUpdateArguments', {
    'data': dict[str, JSONValue],
    'skill_name': str,
})

TaskGetArguments = TypedDict('TaskGetArguments', {
    'task_id': int,
})

ToolGetArguments = TypedDict('ToolGetArguments', {
    'pipeline_uuid': NotRequired[Union[str, None]],
    'tool_name': str,
})

ToolListArguments = TypedDict('ToolListArguments', {
    'pipeline_uuid': NotRequired[Union[str, None]],
})

class ModelLlmDefaultDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self) -> OperationResult[Union[str, None]]:
        'model.llm.default.get: Retrieve the default LLM model configured for new pipelines and agents in the workspace.'
        return cast(OperationResult[Union[str, None]], await self._workspace.call('model.llm.default.get'))

class ModelLlmStarredDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self) -> OperationResult[Union[str, None]]:
        'model.llm.starred.get: Retrieve the favorite/starred LLM model designated for quick selection in the workspace.'
        return cast(OperationResult[Union[str, None]], await self._workspace.call('model.llm.starred.get'))

    async def set(self, *, model_uuid: Union[str, None]) -> OperationResult[None]:
        'model.llm.starred.set: Mark an LLM model as the workspace starred favorite model. Prerequisites: Call model.llm.list to obtain model_uuid. Side effect: Modifies workspace favorite model setting.\nParameters (Python -> wire): model_uuid -> model_uuid.'
        arguments: ModelLlmStarredSetArguments = {'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.llm.starred.set', **arguments))

class AgentRunsDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def events(self, *, after_sequence: Union[int, None] = None, processor_id: str, run_id: str) -> OperationResult[dict[str, JSONValue]]:
        'agent.runs.events: Retrieve incremental trace events, thoughts, and tool calls for a run. Prerequisites: Call agent.runs.list to obtain run_id and processor_id. Use after_sequence to stream.\nParameters (Python -> wire): after_sequence -> after_sequence, processor_id -> processor_id, run_id -> run_id.'
        arguments: AgentRunsEventsArguments = {'after_sequence': after_sequence, 'processor_id': processor_id, 'run_id': run_id}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('agent.runs.events', **arguments))

    async def list(self, *, before_id: Union[int, None] = None, processor_id: str) -> OperationResult[dict[str, JSONValue]]:
        'agent.runs.list: Retrieve execution run records for a processor (agent or pipeline). Prerequisites: Call agent.list to find processor_id. Supports pagination with before_id.\nParameters (Python -> wire): before_id -> before_id, processor_id -> processor_id.'
        arguments: AgentRunsListArguments = {'before_id': before_id, 'processor_id': processor_id}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('agent.runs.list', **arguments))

class BotAdminsDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def list(self, *, bot_uuid: str) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'bot.admins.list: Retrieve the list of designated administrators for a bot. Prerequisites: Call bot.list to obtain bot_uuid.\nParameters (Python -> wire): bot_uuid -> bot_uuid.'
        arguments: BotAdminsListArguments = {'bot_uuid': bot_uuid}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('bot.admins.list', **arguments))

class BotGroupFilterDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def apply(self, *, bot_uuid: str, disable_pipeline_at_bot: bool = True) -> OperationResult[dict[str, JSONValue]]:
        'bot.group_filter.apply: Update group filtering rules for a bot to allow or restrict message handling. Prerequisites: Call bot.list to obtain bot_uuid. Side effect: Modifies group filter policy.\nParameters (Python -> wire): bot_uuid -> bot_uuid, disable_pipeline_at_bot -> disable_pipeline_at_bot.'
        arguments: BotGroupFilterApplyArguments = {'bot_uuid': bot_uuid, 'disable_pipeline_at_bot': disable_pipeline_at_bot}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('bot.group_filter.apply', **arguments))

    async def preview(self, *, bot_uuid: str) -> OperationResult[dict[str, JSONValue]]:
        'bot.group_filter.preview: Inspect effective group chat filter rules and determine which groups are allowed or blocked. Prerequisites: Call bot.list to obtain bot_uuid.\nParameters (Python -> wire): bot_uuid -> bot_uuid.'
        arguments: BotGroupFilterPreviewArguments = {'bot_uuid': bot_uuid}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('bot.group_filter.preview', **arguments))

class BotMessageDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def send(self, *, bot_uuid: str, message_chain_data: dict[str, JSONValue], target_id: str, target_type: str) -> OperationResult[None]:
        'bot.message.send: Send an outbound message to a target user or chat group via the specified bot. Prerequisites: Call bot.list to obtain bot_uuid. Side effect: Delivers external message.\nParameters (Python -> wire): bot_uuid -> bot_uuid, message_chain_data -> message_chain_data, target_id -> target_id, target_type -> target_type.'
        arguments: BotMessageSendArguments = {'bot_uuid': bot_uuid, 'message_chain_data': message_chain_data, 'target_id': target_id, 'target_type': target_type}
        return cast(OperationResult[None], await self._workspace.call('bot.message.send', **arguments))

    async def test(self, *, bot_uuid: str, message: str) -> OperationResult[dict[str, JSONValue]]:
        'bot.message.test: Send a diagnostic test message through the bot to verify adapter credentials and connectivity. Prerequisites: Call bot.list to obtain bot_uuid. Side effect: Sends test message.\nParameters (Python -> wire): bot_uuid -> bot_uuid, message -> message.'
        arguments: BotMessageTestArguments = {'bot_uuid': bot_uuid, 'message': message}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('bot.message.test', **arguments))

class BotRoutesDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def preview(self, *, bot_uuid: str, event_bindings: Union[builtins.list[dict[str, JSONValue]], None] = None, event_context: Union[dict[str, JSONValue], None] = None, event_data: Union[dict[str, JSONValue], None] = None, event_type: str) -> OperationResult[dict[str, JSONValue]]:
        'bot.routes.preview: Simulate how incoming events and messages would be routed by a bot without executing handlers. Prerequisites: Call bot.list to obtain bot_uuid.\nParameters (Python -> wire): bot_uuid -> bot_uuid, event_bindings -> event_bindings, event_context -> event_context, event_data -> event_data, event_type -> event_type.'
        arguments: BotRoutesPreviewArguments = {'bot_uuid': bot_uuid, 'event_bindings': event_bindings, 'event_context': event_context, 'event_data': event_data, 'event_type': event_type}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('bot.routes.preview', **arguments))

    async def status(self, *, bot_uuid: str) -> OperationResult[dict[str, JSONValue]]:
        'bot.routes.status: Inspect message routing table, target pipelines, and active event handlers configured on a bot. Prerequisites: Call bot.list to obtain bot_uuid.\nParameters (Python -> wire): bot_uuid -> bot_uuid.'
        arguments: BotRoutesStatusArguments = {'bot_uuid': bot_uuid}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('bot.routes.status', **arguments))

class BotRuntimeDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self, *, bot_uuid: str, include_secret: bool = False) -> OperationResult[dict[str, JSONValue]]:
        'bot.runtime.get: Inspect live runtime health, connection status, latency, and adapter heartbeat for a bot. Prerequisites: Call bot.list to obtain bot_uuid.\nParameters (Python -> wire): bot_uuid -> bot_uuid, include_secret -> include_secret.'
        arguments: BotRuntimeGetArguments = {'bot_uuid': bot_uuid, 'include_secret': include_secret}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('bot.runtime.get', **arguments))

class KnowledgeBaseDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def create(self, *, kb_data: dict[str, JSONValue]) -> OperationResult[str]:
        'knowledge.base.create: Create and configure a new knowledge base. Specify vector engine, embedding model, and chunking strategy. Side effect: Allocates knowledge base storage.\nParameters (Python -> wire): kb_data -> kb_data.'
        arguments: KnowledgeBaseCreateArguments = {'kb_data': kb_data}
        return cast(OperationResult[str], await self._workspace.call('knowledge.base.create', **arguments))

    async def delete(self, *, kb_uuid: str) -> OperationResult[None]:
        'knowledge.base.delete: Delete a knowledge base and all associated vector embeddings and documents. Prerequisites: Call knowledge.base.list to obtain kb_uuid. Side effect: Irreversible removal of data.\nParameters (Python -> wire): kb_uuid -> kb_uuid.'
        arguments: KnowledgeBaseDeleteArguments = {'kb_uuid': kb_uuid}
        return cast(OperationResult[None], await self._workspace.call('knowledge.base.delete', **arguments))

    async def get(self, *, include_secret: bool = False, kb_uuid: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'knowledge.base.get: Retrieve detailed configuration of a knowledge base including storage engine, chunking parameters, and embedding model. Prerequisites: Call knowledge.base.list to obtain kb_uuid.\nParameters (Python -> wire): include_secret -> include_secret, kb_uuid -> kb_uuid.'
        arguments: KnowledgeBaseGetArguments = {'include_secret': include_secret, 'kb_uuid': kb_uuid}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('knowledge.base.get', **arguments))

    async def list(self, *, include_secret: bool = False) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'knowledge.base.list: Retrieve all knowledge bases in the workspace with vector engine types, parser configurations, and document counts.\nParameters (Python -> wire): include_secret -> include_secret.'
        arguments: KnowledgeBaseListArguments = {'include_secret': include_secret}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('knowledge.base.list', **arguments))

    async def retrieve(self, *, kb_uuid: str, query: str, retrieval_settings: Union[dict[str, JSONValue], None] = None) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'knowledge.base.retrieve: Perform semantic vector and keyword search over a knowledge base to retrieve relevant text chunks and citation metadata. Prerequisites: Call knowledge.base.list to obtain kb_uuid.\nParameters (Python -> wire): kb_uuid -> kb_uuid, query -> query, retrieval_settings -> retrieval_settings.'
        arguments: KnowledgeBaseRetrieveArguments = {'kb_uuid': kb_uuid, 'query': query, 'retrieval_settings': retrieval_settings}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('knowledge.base.retrieve', **arguments))

    async def update(self, *, kb_data: dict[str, JSONValue], kb_uuid: str) -> OperationResult[None]:
        'knowledge.base.update: Modify metadata, description, or search parameters of a knowledge base. Prerequisites: Call knowledge.base.list to obtain kb_uuid. Side effect: Updates knowledge base settings.\nParameters (Python -> wire): kb_data -> kb_data, kb_uuid -> kb_uuid.'
        arguments: KnowledgeBaseUpdateArguments = {'kb_data': kb_data, 'kb_uuid': kb_uuid}
        return cast(OperationResult[None], await self._workspace.call('knowledge.base.update', **arguments))

class KnowledgeEngineDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def creation_schema(self, *, plugin_id: str) -> OperationResult[Union[dict[str, JSONValue], builtins.list[dict[str, JSONValue]]]]:
        'knowledge.engine.creation_schema: Retrieve input schema requirements for initializing a specific storage engine backend.\nParameters (Python -> wire): plugin_id -> plugin_id.'
        arguments: KnowledgeEngineCreationSchemaArguments = {'plugin_id': plugin_id}
        return cast(OperationResult[Union[dict[str, JSONValue], builtins.list[dict[str, JSONValue]]]], await self._workspace.call('knowledge.engine.creation_schema', **arguments))

    async def list(self) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'knowledge.engine.list: Retrieve supported vector database and search engine backends available in the deployment (e.g. pgvector, milvus, seekdb).'
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('knowledge.engine.list'))

    async def retrieval_schema(self, *, plugin_id: str) -> OperationResult[Union[dict[str, JSONValue], builtins.list[dict[str, JSONValue]]]]:
        'knowledge.engine.retrieval_schema: Retrieve query and retrieval parameter schema supported by a specific storage engine.\nParameters (Python -> wire): plugin_id -> plugin_id.'
        arguments: KnowledgeEngineRetrievalSchemaArguments = {'plugin_id': plugin_id}
        return cast(OperationResult[Union[dict[str, JSONValue], builtins.list[dict[str, JSONValue]]]], await self._workspace.call('knowledge.engine.retrieval_schema', **arguments))

class KnowledgeFileDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def delete(self, *, file_id: str, kb_uuid: str) -> OperationResult[None]:
        'knowledge.file.delete: Remove a document and its vector embeddings from a knowledge base. Prerequisites: Call knowledge.file.list to obtain filename and kb_uuid. Side effect: Irreversible document removal.\nParameters (Python -> wire): file_id -> file_id, kb_uuid -> kb_uuid.'
        arguments: KnowledgeFileDeleteArguments = {'file_id': file_id, 'kb_uuid': kb_uuid}
        return cast(OperationResult[None], await self._workspace.call('knowledge.file.delete', **arguments))

    async def list(self, *, kb_uuid: str) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'knowledge.file.list: List files and documents stored in a knowledge base with ingestion status, chunk counts, and error details. Prerequisites: Call knowledge.base.list to obtain kb_uuid.\nParameters (Python -> wire): kb_uuid -> kb_uuid.'
        arguments: KnowledgeFileListArguments = {'kb_uuid': kb_uuid}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('knowledge.file.list', **arguments))

    async def store(self, *, file_id: str, kb_uuid: str, parser_plugin_id: Union[str, None] = None) -> OperationResult[int]:
        'knowledge.file.store: Ingest and index a document into the specified knowledge base. Triggers parsing, chunking, and embedding generation. Prerequisites: Call knowledge.base.list to obtain kb_uuid. Side effect: Stores document data.\nParameters (Python -> wire): file_id -> file_id, kb_uuid -> kb_uuid, parser_plugin_id -> parser_plugin_id.'
        arguments: KnowledgeFileStoreArguments = {'file_id': file_id, 'kb_uuid': kb_uuid, 'parser_plugin_id': parser_plugin_id}
        return cast(OperationResult[int], await self._workspace.call('knowledge.file.store', **arguments))

class KnowledgeParserDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def list(self, *, mime_type: Union[str, None] = None) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'knowledge.parser.list: Retrieve supported file formats (PDF, Markdown, DOCX, HTML) and document parser implementations available for ingestion.\nParameters (Python -> wire): mime_type -> mime_type.'
        arguments: KnowledgeParserListArguments = {'mime_type': mime_type}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('knowledge.parser.list', **arguments))

class McpResourceDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def list(self, *, server_name: str) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'mcp.resource.list: Retrieve resources (files, schemas, system prompts) provided by registered MCP servers. Optionally filter by server_name.\nParameters (Python -> wire): server_name -> server_name.'
        arguments: McpResourceListArguments = {'server_name': server_name}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('mcp.resource.list', **arguments))

    async def read(self, *, include_blob: bool = False, max_bytes: Union[int, None] = None, server_name: str, uri: str) -> OperationResult[dict[str, JSONValue]]:
        'mcp.resource.read: Fetch textual or binary content of an MCP resource by URI. Prerequisites: Call mcp.resource.list to obtain valid uri and server_name.\nParameters (Python -> wire): include_blob -> include_blob, max_bytes -> max_bytes, server_name -> server_name, uri -> uri.'
        arguments: McpResourceReadArguments = {'include_blob': include_blob, 'max_bytes': max_bytes, 'server_name': server_name, 'uri': uri}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('mcp.resource.read', **arguments))

    async def templates(self, *, server_name: str) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'mcp.resource.templates: Retrieve parameterized resource URI templates exposed by MCP servers to construct dynamic resource queries.\nParameters (Python -> wire): server_name -> server_name.'
        arguments: McpResourceTemplatesArguments = {'server_name': server_name}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('mcp.resource.templates', **arguments))

class McpServerDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def delete(self, *, server_uuid: str) -> OperationResult[None]:
        'mcp.server.delete: Remove an MCP server registration and terminate active subprocess or connection. Prerequisites: Call mcp.server.list to obtain server_uuid (note: list returns server objects with uuid; get, logs, runtime, and test use server_name). Side effect: Deletes server registration.\nParameters (Python -> wire): server_uuid -> server_uuid.'
        arguments: McpServerDeleteArguments = {'server_uuid': server_uuid}
        return cast(OperationResult[None], await self._workspace.call('mcp.server.delete', **arguments))

    async def get(self, *, server_name: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'mcp.server.get: Retrieve full configuration of an MCP server including transport command or SSE endpoint. Prerequisites: Call mcp.server.list to obtain server_name.\nParameters (Python -> wire): server_name -> server_name.'
        arguments: McpServerGetArguments = {'server_name': server_name}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('mcp.server.get', **arguments))

    async def list(self, *, contain_runtime_info: bool = False) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'mcp.server.list: Retrieve all configured MCP servers in the workspace with connection types (stdio, sse), status, and capabilities.\nParameters (Python -> wire): contain_runtime_info -> contain_runtime_info.'
        arguments: McpServerListArguments = {'contain_runtime_info': contain_runtime_info}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('mcp.server.list', **arguments))

    async def logs(self, *, level: Union[str, None] = None, limit: int = 200, server_name: str) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'mcp.server.logs: Fetch protocol exchange messages and error output for an active MCP server. Prerequisites: Call mcp.server.list to obtain server_name.\nParameters (Python -> wire): level -> level, limit -> limit, server_name -> server_name.'
        arguments: McpServerLogsArguments = {'level': level, 'limit': limit, 'server_name': server_name}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('mcp.server.logs', **arguments))

    async def runtime(self, *, server_name: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'mcp.server.runtime: Inspect live process or connection health, heartbeat status, and error counters for an MCP server. Prerequisites: Call mcp.server.list to obtain server_name.\nParameters (Python -> wire): server_name -> server_name.'
        arguments: McpServerRuntimeArguments = {'server_name': server_name}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('mcp.server.runtime', **arguments))

    async def test(self, *, server_data: dict[str, JSONValue], server_name: str) -> OperationResult[int]:
        'mcp.server.test: Verify connection and protocol handshake with an MCP server without saving. Side effect: Initiates external network or process connection.\nParameters (Python -> wire): server_data -> server_data, server_name -> server_name.'
        arguments: McpServerTestArguments = {'server_data': server_data, 'server_name': server_name}
        return cast(OperationResult[int], await self._workspace.call('mcp.server.test', **arguments))

class ModelEmbeddingDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def create(self, *, model_data: dict[str, JSONValue]) -> OperationResult[str]:
        'model.embedding.create: Add a new embedding model configuration with dimension and endpoint settings. Side effect: Creates model entity.\nParameters (Python -> wire): model_data -> model_data.'
        arguments: ModelEmbeddingCreateArguments = {'model_data': model_data}
        return cast(OperationResult[str], await self._workspace.call('model.embedding.create', **arguments))

    async def delete(self, *, model_uuid: str) -> OperationResult[None]:
        'model.embedding.delete: Permanently remove an embedding model configuration. Prerequisites: Call model.embedding.list to obtain model_uuid. Side effect: Irreversible removal of model config.\nParameters (Python -> wire): model_uuid -> model_uuid.'
        arguments: ModelEmbeddingDeleteArguments = {'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.embedding.delete', **arguments))

    async def get(self, *, include_secret: bool = False, model_uuid: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'model.embedding.get: Retrieve complete configuration for an embedding model. Prerequisites: Call model.embedding.list to obtain model_uuid. Optionally pass include_secret.\nParameters (Python -> wire): include_secret -> include_secret, model_uuid -> model_uuid.'
        arguments: ModelEmbeddingGetArguments = {'include_secret': include_secret, 'model_uuid': model_uuid}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('model.embedding.get', **arguments))

    async def list(self, *, include_secret: bool = False) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'model.embedding.list: Retrieve configured text embedding models with dimension and provider details. Pass include_secret=True to include credentials.\nParameters (Python -> wire): include_secret -> include_secret.'
        arguments: ModelEmbeddingListArguments = {'include_secret': include_secret}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('model.embedding.list', **arguments))

    async def list_by_provider(self, *, include_secret: bool = False, provider_uuid: str) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'model.embedding.list_by_provider: Retrieve embedding models belonging to a specific provider. Prerequisites: Call provider.list to obtain provider_uuid.\nParameters (Python -> wire): include_secret -> include_secret, provider_uuid -> provider_uuid.'
        arguments: ModelEmbeddingListByProviderArguments = {'include_secret': include_secret, 'provider_uuid': provider_uuid}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('model.embedding.list_by_provider', **arguments))

    async def test(self, *, model_data: dict[str, JSONValue], model_uuid: str) -> OperationResult[None]:
        'model.embedding.test: Send sample text to an embedding model to verify credentials and vector output. Prerequisites: Call model.embedding.list to obtain model_uuid. Side effect: Incurs model API call.\nParameters (Python -> wire): model_data -> model_data, model_uuid -> model_uuid.'
        arguments: ModelEmbeddingTestArguments = {'model_data': model_data, 'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.embedding.test', **arguments))

    async def update(self, *, model_data: dict[str, JSONValue], model_uuid: str) -> OperationResult[None]:
        'model.embedding.update: Modify settings or credentials of an embedding model. Prerequisites: Call model.embedding.list to obtain model_uuid. Side effect: Updates model config.\nParameters (Python -> wire): model_data -> model_data, model_uuid -> model_uuid.'
        arguments: ModelEmbeddingUpdateArguments = {'model_data': model_data, 'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.embedding.update', **arguments))

class ModelLlmDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.default = ModelLlmDefaultDomain(workspace)
        self.starred = ModelLlmStarredDomain(workspace)

    async def create(self, *, auto_set_to_default_pipeline: bool = True, model_data: dict[str, JSONValue]) -> OperationResult[str]:
        'model.llm.create: Add a new LLM model configuration to the workspace with context window and temperature settings. Side effect: Creates model entity.\nParameters (Python -> wire): auto_set_to_default_pipeline -> auto_set_to_default_pipeline, model_data -> model_data.'
        arguments: ModelLlmCreateArguments = {'auto_set_to_default_pipeline': auto_set_to_default_pipeline, 'model_data': model_data}
        return cast(OperationResult[str], await self._workspace.call('model.llm.create', **arguments))

    async def delete(self, *, model_uuid: str) -> OperationResult[None]:
        'model.llm.delete: Permanently remove an LLM model from the workspace. Prerequisites: Call model.llm.list to obtain model_uuid. Side effect: Irreversible removal of model config.\nParameters (Python -> wire): model_uuid -> model_uuid.'
        arguments: ModelLlmDeleteArguments = {'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.llm.delete', **arguments))

    async def get(self, *, include_secret: bool = False, model_uuid: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'model.llm.get: Retrieve complete configuration for an LLM model. Prerequisites: Call model.llm.list to obtain model_uuid. Optionally pass include_secret.\nParameters (Python -> wire): include_secret -> include_secret, model_uuid -> model_uuid.'
        arguments: ModelLlmGetArguments = {'include_secret': include_secret, 'model_uuid': model_uuid}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('model.llm.get', **arguments))

    async def list(self, *, include_secret: bool = False) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'model.llm.list: Retrieve all configured LLM models in the workspace, including context limits and capabilities. Pass include_secret=True to include credentials.\nParameters (Python -> wire): include_secret -> include_secret.'
        arguments: ModelLlmListArguments = {'include_secret': include_secret}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('model.llm.list', **arguments))

    async def list_by_provider(self, *, include_secret: bool = False, provider_uuid: str) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'model.llm.list_by_provider: Retrieve LLM models belonging to a specific provider. Prerequisites: Call provider.list to obtain provider_uuid.\nParameters (Python -> wire): include_secret -> include_secret, provider_uuid -> provider_uuid.'
        arguments: ModelLlmListByProviderArguments = {'include_secret': include_secret, 'provider_uuid': provider_uuid}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('model.llm.list_by_provider', **arguments))

    async def test(self, *, model_data: dict[str, JSONValue], model_uuid: str) -> OperationResult[None]:
        'model.llm.test: Send a test prompt to an LLM model to verify credentials and API availability. Prerequisites: Call model.llm.list to obtain model_uuid. Side effect: Incurs model API call.\nParameters (Python -> wire): model_data -> model_data, model_uuid -> model_uuid.'
        arguments: ModelLlmTestArguments = {'model_data': model_data, 'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.llm.test', **arguments))

    async def update(self, *, model_data: dict[str, JSONValue], model_uuid: str) -> OperationResult[None]:
        'model.llm.update: Modify settings, context parameters, or credentials of an LLM model. Prerequisites: Call model.llm.list to obtain model_uuid. Side effect: Updates model config.\nParameters (Python -> wire): model_data -> model_data, model_uuid -> model_uuid.'
        arguments: ModelLlmUpdateArguments = {'model_data': model_data, 'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.llm.update', **arguments))

class ModelRerankDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def create(self, *, model_data: dict[str, JSONValue]) -> OperationResult[str]:
        'model.rerank.create: Add a new rerank model configuration to the workspace. Side effect: Creates model entity.\nParameters (Python -> wire): model_data -> model_data.'
        arguments: ModelRerankCreateArguments = {'model_data': model_data}
        return cast(OperationResult[str], await self._workspace.call('model.rerank.create', **arguments))

    async def delete(self, *, model_uuid: str) -> OperationResult[None]:
        'model.rerank.delete: Permanently remove a rerank model configuration. Prerequisites: Call model.rerank.list to obtain model_uuid. Side effect: Irreversible removal of model config.\nParameters (Python -> wire): model_uuid -> model_uuid.'
        arguments: ModelRerankDeleteArguments = {'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.rerank.delete', **arguments))

    async def get(self, *, include_secret: bool = False, model_uuid: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'model.rerank.get: Retrieve complete configuration for a rerank model. Prerequisites: Call model.rerank.list to obtain model_uuid. Optionally pass include_secret.\nParameters (Python -> wire): include_secret -> include_secret, model_uuid -> model_uuid.'
        arguments: ModelRerankGetArguments = {'include_secret': include_secret, 'model_uuid': model_uuid}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('model.rerank.get', **arguments))

    async def list(self, *, include_secret: bool = False) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'model.rerank.list: Retrieve configured reranking models used in knowledge base retrieval. Pass include_secret=True to include credentials.\nParameters (Python -> wire): include_secret -> include_secret.'
        arguments: ModelRerankListArguments = {'include_secret': include_secret}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('model.rerank.list', **arguments))

    async def list_by_provider(self, *, include_secret: bool = False, provider_uuid: str) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'model.rerank.list_by_provider: Retrieve rerank models belonging to a specific provider. Prerequisites: Call provider.list to obtain provider_uuid.\nParameters (Python -> wire): include_secret -> include_secret, provider_uuid -> provider_uuid.'
        arguments: ModelRerankListByProviderArguments = {'include_secret': include_secret, 'provider_uuid': provider_uuid}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('model.rerank.list_by_provider', **arguments))

    async def test(self, *, model_data: dict[str, JSONValue], model_uuid: str) -> OperationResult[None]:
        'model.rerank.test: Send sample documents to a rerank model to verify credentials and scoring. Prerequisites: Call model.rerank.list to obtain model_uuid. Side effect: Incurs model API call.\nParameters (Python -> wire): model_data -> model_data, model_uuid -> model_uuid.'
        arguments: ModelRerankTestArguments = {'model_data': model_data, 'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.rerank.test', **arguments))

    async def update(self, *, model_data: dict[str, JSONValue], model_uuid: str) -> OperationResult[None]:
        'model.rerank.update: Modify settings or credentials of a rerank model. Prerequisites: Call model.rerank.list to obtain model_uuid. Side effect: Updates model config.\nParameters (Python -> wire): model_data -> model_data, model_uuid -> model_uuid.'
        arguments: ModelRerankUpdateArguments = {'model_data': model_data, 'model_uuid': model_uuid}
        return cast(OperationResult[None], await self._workspace.call('model.rerank.update', **arguments))

class MonitoringExecutionDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def detail(self, *, execution_id: str, limit: int = 100, offset: int = 0, section: Union[str, None] = None, source: str) -> OperationResult[dict[str, JSONValue]]:
        'monitoring.execution.detail: Retrieve fine-grained execution trace events and step diagnostics. Prerequisites: Call monitoring.executions first to find the execution_id and source. Filter by section or page with offset and limit.\nParameters (Python -> wire): execution_id -> execution_id, limit -> limit, offset -> offset, section -> section, source -> source.'
        arguments: MonitoringExecutionDetailArguments = {'execution_id': execution_id, 'limit': limit, 'offset': offset, 'section': section, 'source': source}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('monitoring.execution.detail', **arguments))

class MonitoringFeedbackDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def list(self, *, bot_ids: Union[builtins.list[str], None] = None, end_time: Union[str, None] = None, execution_statuses: Union[builtins.list[str], None] = None, feedback_type: Union[int, None] = None, limit: int = 100, mode: str = 'all', offset: int = 0, pipeline_ids: Union[builtins.list[str], None] = None, start_time: Union[str, None] = None) -> OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]]:
        'monitoring.feedback.list: Query user feedback and satisfaction ratings on bot responses. Filter by bot_ids, pipeline_ids, feedback_type (upvote/downvote), and time range.\nParameters (Python -> wire): bot_ids -> bot_ids, end_time -> end_time, execution_statuses -> execution_statuses, feedback_type -> feedback_type, limit -> limit, mode -> mode, offset -> offset, pipeline_ids -> pipeline_ids, start_time -> start_time.'
        arguments: MonitoringFeedbackListArguments = {'bot_ids': bot_ids, 'end_time': end_time, 'execution_statuses': execution_statuses, 'feedback_type': feedback_type, 'limit': limit, 'mode': mode, 'offset': offset, 'pipeline_ids': pipeline_ids, 'start_time': start_time}
        return cast(OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]], await self._workspace.call('monitoring.feedback.list', **arguments))

    async def stats(self, *, bot_ids: Union[builtins.list[str], None] = None, end_time: Union[str, None] = None, execution_statuses: Union[builtins.list[str], None] = None, mode: str = 'all', pipeline_ids: Union[builtins.list[str], None] = None, start_time: Union[str, None] = None) -> OperationResult[dict[str, JSONValue]]:
        'monitoring.feedback.stats: Retrieve aggregated user feedback metrics, such as like/dislike ratios, over a specified time window for given bot_ids or pipeline_ids.\nParameters (Python -> wire): bot_ids -> bot_ids, end_time -> end_time, execution_statuses -> execution_statuses, mode -> mode, pipeline_ids -> pipeline_ids, start_time -> start_time.'
        arguments: MonitoringFeedbackStatsArguments = {'bot_ids': bot_ids, 'end_time': end_time, 'execution_statuses': execution_statuses, 'mode': mode, 'pipeline_ids': pipeline_ids, 'start_time': start_time}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('monitoring.feedback.stats', **arguments))

class MonitoringMessageDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def detail(self, *, message_id: str) -> OperationResult[dict[str, JSONValue]]:
        'monitoring.message.detail: Fetch complete message content, routing trace, and execution context for a message. Prerequisites: Call monitoring.messages first to obtain the message_id.\nParameters (Python -> wire): message_id -> message_id.'
        arguments: MonitoringMessageDetailArguments = {'message_id': message_id}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('monitoring.message.detail', **arguments))

class MonitoringSessionDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def analysis(self, *, bot_id: Union[str, None] = None, end_time: Union[str, None] = None, session_id: str, start_time: Union[str, None] = None) -> OperationResult[dict[str, JSONValue]]:
        'monitoring.session.analysis: Retrieve detailed analytics for a chat session including message frequency, turn count, and token usage. Prerequisites: Call monitoring.sessions first to obtain session_id.\nParameters (Python -> wire): bot_id -> bot_id, end_time -> end_time, session_id -> session_id, start_time -> start_time.'
        arguments: MonitoringSessionAnalysisArguments = {'bot_id': bot_id, 'end_time': end_time, 'session_id': session_id, 'start_time': start_time}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('monitoring.session.analysis', **arguments))

    async def reset(self, *, bot_id: str, session_id: str) -> OperationResult[dict[str, JSONValue]]:
        'monitoring.session.reset: Clear context history and reset memory state for a given session. Prerequisites: Call monitoring.sessions to obtain session_id and bot_id. Side effect: Deletes stored session conversation state.\nParameters (Python -> wire): bot_id -> bot_id, session_id -> session_id.'
        arguments: MonitoringSessionResetArguments = {'bot_id': bot_id, 'session_id': session_id}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('monitoring.session.reset', **arguments))

class PipelineChatDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def broadcast(self, *, message: str, pipeline_uuid: str) -> OperationResult[None]:
        'pipeline.chat.broadcast: Broadcast a message payload to all connected test clients in the pipeline debug channel. Prerequisites: Call pipeline.list to obtain pipeline_uuid. Side effect: Sends message to active clients.\nParameters (Python -> wire): message -> message, pipeline_uuid -> pipeline_uuid.'
        arguments: PipelineChatBroadcastArguments = {'message': message, 'pipeline_uuid': pipeline_uuid}
        return cast(OperationResult[None], await self._workspace.call('pipeline.chat.broadcast', **arguments))

    async def connections(self, *, pipeline_uuid: str) -> OperationResult[dict[str, JSONValue]]:
        'pipeline.chat.connections: Inspect active real-time preview websocket clients connected to the pipeline test interface. Prerequisites: Call pipeline.list to obtain pipeline_uuid.\nParameters (Python -> wire): pipeline_uuid -> pipeline_uuid.'
        arguments: PipelineChatConnectionsArguments = {'pipeline_uuid': pipeline_uuid}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('pipeline.chat.connections', **arguments))

    async def history(self, *, pipeline_uuid: str, session_type: Literal['person', 'group']) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'pipeline.chat.history: Fetch recent test messages and interaction logs for a pipeline web preview session. Prerequisites: Call pipeline.list to obtain pipeline_uuid.\nParameters (Python -> wire): pipeline_uuid -> pipeline_uuid, session_type -> session_type.'
        arguments: PipelineChatHistoryArguments = {'pipeline_uuid': pipeline_uuid, 'session_type': session_type}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('pipeline.chat.history', **arguments))

    async def reset(self, *, pipeline_uuid: str, session_type: Literal['person', 'group']) -> OperationResult[None]:
        'pipeline.chat.reset: Reset test chat memory and clear session state for pipeline preview. Prerequisites: Call pipeline.list to obtain pipeline_uuid. Side effect: Deletes stored preview chat context.\nParameters (Python -> wire): pipeline_uuid -> pipeline_uuid, session_type -> session_type.'
        arguments: PipelineChatResetArguments = {'pipeline_uuid': pipeline_uuid, 'session_type': session_type}
        return cast(OperationResult[None], await self._workspace.call('pipeline.chat.reset', **arguments))

class PipelineExtensionsDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self, *, pipeline_uuid: str) -> OperationResult[dict[str, JSONValue]]:
        'pipeline.extensions.get: Inspect extensions, plugins, and MCP connections bound to a specific pipeline. Prerequisites: Call pipeline.list to obtain pipeline_uuid.\nParameters (Python -> wire): pipeline_uuid -> pipeline_uuid.'
        arguments: PipelineExtensionsGetArguments = {'pipeline_uuid': pipeline_uuid}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('pipeline.extensions.get', **arguments))

    async def update(self, *, allowed_platform_tools: Union[builtins.list[str], None] = None, bound_mcp_resources: Union[builtins.list[dict[str, JSONValue]], None] = None, bound_mcp_servers: Union[builtins.list[str], None] = None, bound_plugins: builtins.list[dict[str, JSONValue]], bound_skills: Union[builtins.list[str], None] = None, enable_all_mcp_servers: bool = True, enable_all_plugins: bool = True, enable_all_skills: bool = True, mcp_resource_agent_read_enabled: Union[bool, None] = None, pipeline_uuid: str, workspace_operations: Union[builtins.list[str], None] = None) -> OperationResult[None]:
        'pipeline.extensions.update: Bind or unbind plugins, MCP servers, and tools to a pipeline. Prerequisites: Call pipeline.list to obtain pipeline_uuid. Side effect: Modifies pipeline tool attachments.\nParameters (Python -> wire): allowed_platform_tools -> allowed_platform_tools, bound_mcp_resources -> bound_mcp_resources, bound_mcp_servers -> bound_mcp_servers, bound_plugins -> bound_plugins, bound_skills -> bound_skills, enable_all_mcp_servers -> enable_all_mcp_servers, enable_all_plugins -> enable_all_plugins, enable_all_skills -> enable_all_skills, mcp_resource_agent_read_enabled -> mcp_resource_agent_read_enabled, pipeline_uuid -> pipeline_uuid, workspace_operations -> workspace_operations.'
        arguments: PipelineExtensionsUpdateArguments = {'allowed_platform_tools': allowed_platform_tools, 'bound_mcp_resources': bound_mcp_resources, 'bound_mcp_servers': bound_mcp_servers, 'bound_plugins': bound_plugins, 'bound_skills': bound_skills, 'enable_all_mcp_servers': enable_all_mcp_servers, 'enable_all_plugins': enable_all_plugins, 'enable_all_skills': enable_all_skills, 'mcp_resource_agent_read_enabled': mcp_resource_agent_read_enabled, 'pipeline_uuid': pipeline_uuid, 'workspace_operations': workspace_operations}
        return cast(OperationResult[None], await self._workspace.call('pipeline.extensions.update', **arguments))

class PluginConfigDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self, *, author: str, plugin_name: str) -> OperationResult[PluginConfigGetOutput]:
        'plugin.config.get: Retrieve current configuration values and schema for an installed plugin. Prerequisites: Call plugin.list to obtain author and plugin_name.\nParameters (Python -> wire): author -> author, plugin_name -> plugin_name.'
        arguments: PluginConfigGetArguments = {'author': author, 'plugin_name': plugin_name}
        return cast(OperationResult[PluginConfigGetOutput], await self._workspace.call('plugin.config.get', **arguments))

class PluginGithubDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def assets(self, *, owner: str, release_id: int, repo: str) -> OperationResult[dict[str, JSONValue]]:
        'plugin.github.assets: List downloadable distribution packages for a GitHub release tag of a plugin.\nParameters (Python -> wire): owner -> owner, release_id -> release_id, repo -> repo.'
        arguments: PluginGithubAssetsArguments = {'owner': owner, 'release_id': release_id, 'repo': repo}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('plugin.github.assets', **arguments))

    async def releases(self, *, repo_url: str) -> OperationResult[dict[str, JSONValue]]:
        'plugin.github.releases: Fetch available release versions and tags for a plugin from its GitHub repository URL.\nParameters (Python -> wire): repo_url -> repo_url.'
        arguments: PluginGithubReleasesArguments = {'repo_url': repo_url}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('plugin.github.releases', **arguments))

class PluginInstallDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def marketplace(self, *, auto_confirm_permissions: bool = False, plugin_author: str, plugin_name: str, plugin_version: Union[str, None] = None) -> OperationResult[PluginInstallMarketplaceOutput]:
        'plugin.install.marketplace: Download and install a plugin package from the LangBot Plugin Marketplace. Prerequisites: Call plugin.marketplace.search to find plugin_author and plugin_name. Returns task_id; poll task.get for progress. A new installation stays disabled until a member confirms its permissions. auto_confirm_permissions defaults to false; when true, only an account or support administrator with every declared permission can confirm and activate it. API keys, plugins and Agents cannot grant permissions, and plugins and Agents cannot replace an installed plugin. Side effect: Installs executable code.\nParameters (Python -> wire): auto_confirm_permissions -> auto_confirm_permissions, plugin_author -> plugin_author, plugin_name -> plugin_name, plugin_version -> plugin_version.'
        arguments: PluginInstallMarketplaceArguments = {'auto_confirm_permissions': auto_confirm_permissions, 'plugin_author': plugin_author, 'plugin_name': plugin_name, 'plugin_version': plugin_version}
        return cast(OperationResult[PluginInstallMarketplaceOutput], await self._workspace.call('plugin.install.marketplace', **arguments))

class PluginMarketplaceDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def search(self, *, component_filter: Union[str, None] = None, page: int = 1, page_size: int = 10, query: str = '', sort_by: Literal['install_count', 'like_count', 'created_at', 'updated_at'] = 'install_count', sort_order: Literal['ASC', 'DESC'] = 'DESC', tags_filter: Union[builtins.list[str], _Unset] = _UNSET) -> OperationResult[PluginMarketplaceSearchOutput]:
        'plugin.marketplace.search: Search plugins published on the LangBot Plugin Marketplace by keyword, component type or tags. Returns plugin_id, author, name, latest_version, labels, descriptions and component counts; pass author and name to plugin.install.marketplace. Fails with marketplace_disabled when the instance disables the marketplace.\nParameters (Python -> wire): component_filter -> component_filter, page -> page, page_size -> page_size, query -> query, sort_by -> sort_by, sort_order -> sort_order, tags_filter -> tags_filter.'
        arguments: PluginMarketplaceSearchArguments = {'component_filter': component_filter, 'page': page, 'page_size': page_size, 'query': query, 'sort_by': sort_by, 'sort_order': sort_order}
        if not isinstance(tags_filter, _Unset):
            arguments['tags_filter'] = tags_filter
        return cast(OperationResult[PluginMarketplaceSearchOutput], await self._workspace.call('plugin.marketplace.search', **arguments))

class ProviderModelsDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def count(self, *, provider_uuid: str) -> OperationResult[dict[str, JSONValue]]:
        'provider.models.count: Count total LLM, embedding, and rerank models associated with a provider. Prerequisites: Call provider.list to obtain provider_uuid.\nParameters (Python -> wire): provider_uuid -> provider_uuid.'
        arguments: ProviderModelsCountArguments = {'provider_uuid': provider_uuid}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('provider.models.count', **arguments))

    async def scan(self, *, model_type: Union[str, None] = None, provider_uuid: str) -> OperationResult[dict[str, JSONValue]]:
        'provider.models.scan: Query remote provider API to discover available models for importing. Prerequisites: Call provider.list to obtain provider_uuid. Side effect: Queries remote provider API.\nParameters (Python -> wire): model_type -> model_type, provider_uuid -> provider_uuid.'
        arguments: ProviderModelsScanArguments = {'model_type': model_type, 'provider_uuid': provider_uuid}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('provider.models.scan', **arguments))

class SkillFileDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def list(self, *, include_hidden: bool = False, max_entries: int = 200, path: str = '.', skill_name: str) -> OperationResult[dict[str, JSONValue]]:
        'skill.file.list: Inspect files and subdirectories contained in a skill package. Prerequisites: Call skill.list to obtain skill_name.\nParameters (Python -> wire): include_hidden -> include_hidden, max_entries -> max_entries, path -> path, skill_name -> skill_name.'
        arguments: SkillFileListArguments = {'include_hidden': include_hidden, 'max_entries': max_entries, 'path': path, 'skill_name': skill_name}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('skill.file.list', **arguments))

    async def read(self, *, path: str, skill_name: str) -> OperationResult[dict[str, JSONValue]]:
        'skill.file.read: Retrieve content of a specific source code or config file inside a skill package. Prerequisites: Call skill.file.list to obtain path and skill_name.\nParameters (Python -> wire): path -> path, skill_name -> skill_name.'
        arguments: SkillFileReadArguments = {'path': path, 'skill_name': skill_name}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('skill.file.read', **arguments))

    async def write(self, *, base_revision: Union[str, None], content: str, path: str, skill_name: str) -> OperationResult[dict[str, JSONValue]]:
        'skill.file.write: Write or overwrite a source code file inside a skill package. Prerequisites: Call skill.list to obtain skill_name. Side effect: Overwrites skill file content.\nParameters (Python -> wire): base_revision -> base_revision, content -> content, path -> path, skill_name -> skill_name.'
        arguments: SkillFileWriteArguments = {'base_revision': base_revision, 'content': content, 'path': path, 'skill_name': skill_name}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('skill.file.write', **arguments))

class SkillGithubDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def preview(self, *, data: dict[str, JSONValue]) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'skill.github.preview: Inspect metadata and file contents of a skill hosted on GitHub before installing.\nParameters (Python -> wire): data -> data.'
        arguments: SkillGithubPreviewArguments = {'data': data}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('skill.github.preview', **arguments))

class WorkspaceLanguageDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self) -> OperationResult[dict[str, JSONValue]]:
        "workspace.language.get: Return the Workspace message language (language, for example en_US or zh_Hans) and the supported_languages list. It is independent of any member's personal WebUI language. Use it to localize replies, notices or generated content for this Workspace."
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('workspace.language.get'))

class AdapterDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self, *, adapter_name: str) -> OperationResult[dict[str, JSONValue]]:
        'adapter.get: Retrieve configuration parameters and supported features for an adapter. Prerequisites: Call adapter.list to discover valid adapter_name values.\nParameters (Python -> wire): adapter_name -> adapter_name.'
        arguments: AdapterGetArguments = {'adapter_name': adapter_name}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('adapter.get', **arguments))

    async def list(self) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'adapter.list: List all supported IM platform adapters (e.g. Slack, Discord, OneBot, WeChat) and their availability status in the workspace.'
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('adapter.list'))

class AgentDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.runs = AgentRunsDomain(workspace)

    async def create(self, *, agent_data: dict[str, JSONValue]) -> OperationResult[dict[str, str]]:
        'agent.create: Create and initialize a new AI agent with model, prompts, and tool configurations. Provide agent_data payload. Side effect: Creates a new agent entity.\nParameters (Python -> wire): agent_data -> agent_data.'
        arguments: AgentCreateArguments = {'agent_data': agent_data}
        return cast(OperationResult[dict[str, str]], await self._workspace.call('agent.create', **arguments))

    async def debug(self, *, agent_uuid: str, payload: dict[str, JSONValue]) -> OperationResult[dict[str, JSONValue]]:
        'agent.debug: Send a test input payload to an agent to evaluate prompt execution and tool selection without connecting to chat channels. Prerequisites: Call agent.list to obtain agent_uuid. Side effect: Generates execution trace.\nParameters (Python -> wire): agent_uuid -> agent_uuid, payload -> payload.'
        arguments: AgentDebugArguments = {'agent_uuid': agent_uuid, 'payload': payload}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('agent.debug', **arguments))

    async def delete(self, *, agent_uuid: str) -> OperationResult[None]:
        'agent.delete: Permanently remove an AI agent and its configuration from the workspace. Prerequisites: Call agent.list to obtain agent_uuid. Side effect: Irreversible deletion of agent.\nParameters (Python -> wire): agent_uuid -> agent_uuid.'
        arguments: AgentDeleteArguments = {'agent_uuid': agent_uuid}
        return cast(OperationResult[None], await self._workspace.call('agent.delete', **arguments))

    async def get(self, *, agent_uuid: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'agent.get: Retrieve full agent definition including system prompt, model configuration, and attached skills/tools. Prerequisites: Call agent.list to obtain agent_uuid.\nParameters (Python -> wire): agent_uuid -> agent_uuid.'
        arguments: AgentGetArguments = {'agent_uuid': agent_uuid}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('agent.get', **arguments))

    async def list(self, *, sort_by: str = 'updated_at', sort_order: str = 'DESC') -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'agent.list: Retrieve configured AI agents in the workspace with model selection, prompt settings, and bound tools. Supports sort_by and sort_order.\nParameters (Python -> wire): sort_by -> sort_by, sort_order -> sort_order.'
        arguments: AgentListArguments = {'sort_by': sort_by, 'sort_order': sort_order}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('agent.list', **arguments))

    async def metadata(self) -> OperationResult[dict[str, JSONValue]]:
        'agent.metadata: Retrieve metadata schemas describing supported agent parameters, available memory modes, and execution strategies.'
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('agent.metadata'))

    async def update(self, *, agent_data: dict[str, JSONValue], agent_uuid: str) -> OperationResult[None]:
        'agent.update: Update an agent definition, prompt templates, tool permissions, or model settings. Prerequisites: Call agent.list to obtain agent_uuid. Side effect: Modifies agent settings.\nParameters (Python -> wire): agent_data -> agent_data, agent_uuid -> agent_uuid.'
        arguments: AgentUpdateArguments = {'agent_data': agent_data, 'agent_uuid': agent_uuid}
        return cast(OperationResult[None], await self._workspace.call('agent.update', **arguments))

class BotDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.admins = BotAdminsDomain(workspace)
        self.group_filter = BotGroupFilterDomain(workspace)
        self.message = BotMessageDomain(workspace)
        self.routes = BotRoutesDomain(workspace)
        self.runtime = BotRuntimeDomain(workspace)

    async def create(self, *, bot_data: BotCreateBotDataInput) -> OperationResult[str]:
        'bot.create: Create a chat bot. bot_data requires non-empty name and adapter strings, and an adapter_config object with adapter-specific settings. Optional event_bindings routes events to a pipeline or agent. Side effect: Instantiates a new bot entity.\nParameters (Python -> wire): bot_data -> bot_data.'
        arguments: BotCreateArguments = {'bot_data': bot_data}
        return cast(OperationResult[str], await self._workspace.call('bot.create', **arguments))

    async def delete(self, *, bot_uuid: str) -> OperationResult[None]:
        'bot.delete: Permanently remove a chat bot from the workspace. Prerequisites: Call bot.list to obtain bot_uuid. Side effect: Irreversible removal of bot and its adapter credentials.\nParameters (Python -> wire): bot_uuid -> bot_uuid.'
        arguments: BotDeleteArguments = {'bot_uuid': bot_uuid}
        return cast(OperationResult[None], await self._workspace.call('bot.delete', **arguments))

    async def get(self, *, bot_uuid: str, include_secret: bool = False) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'bot.get: Retrieve full configuration, adapter parameters, and pipeline bindings for a bot. Prerequisites: Call bot.list to find bot_uuid. Optionally pass include_secret.\nParameters (Python -> wire): bot_uuid -> bot_uuid, include_secret -> include_secret.'
        arguments: BotGetArguments = {'bot_uuid': bot_uuid, 'include_secret': include_secret}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('bot.get', **arguments))

    async def list(self, *, include_secret: bool = False) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'bot.list: Retrieve all configured chat bots in the workspace with basic settings, adapter types, and pipeline bindings. Set include_secret=True to include credentials.\nParameters (Python -> wire): include_secret -> include_secret.'
        arguments: BotListArguments = {'include_secret': include_secret}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('bot.list', **arguments))

    async def logs(self, *, bot_uuid: str, from_index: int, max_count: int) -> OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]]:
        'bot.logs: Retrieve connection logs, heartbeat messages, and adapter events for a bot. Prerequisites: Call bot.list to obtain bot_uuid. Paginate with from_index and max_count.\nParameters (Python -> wire): bot_uuid -> bot_uuid, from_index -> from_index, max_count -> max_count.'
        arguments: BotLogsArguments = {'bot_uuid': bot_uuid, 'from_index': from_index, 'max_count': max_count}
        return cast(OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]], await self._workspace.call('bot.logs', **arguments))

    async def update(self, *, bot_data: dict[str, JSONValue], bot_uuid: str) -> OperationResult[None]:
        'bot.update: Modify configuration, adapter parameters, or pipeline bindings for a bot. Prerequisites: Call bot.list to obtain bot_uuid. Side effect: Updates bot configuration.\nParameters (Python -> wire): bot_data -> bot_data, bot_uuid -> bot_uuid.'
        arguments: BotUpdateArguments = {'bot_data': bot_data, 'bot_uuid': bot_uuid}
        return cast(OperationResult[None], await self._workspace.call('bot.update', **arguments))

class ExtensionDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def list(self) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'extension.list: Retrieve a unified list of all active extensions across plugins, MCP servers, and custom skills in the workspace.'
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('extension.list'))

class KnowledgeDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.base = KnowledgeBaseDomain(workspace)
        self.engine = KnowledgeEngineDomain(workspace)
        self.file = KnowledgeFileDomain(workspace)
        self.parser = KnowledgeParserDomain(workspace)

class McpDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.resource = McpResourceDomain(workspace)
        self.server = McpServerDomain(workspace)

class ModelDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.embedding = ModelEmbeddingDomain(workspace)
        self.llm = ModelLlmDomain(workspace)
        self.rerank = ModelRerankDomain(workspace)

class MonitoringDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.execution = MonitoringExecutionDomain(workspace)
        self.feedback = MonitoringFeedbackDomain(workspace)
        self.message = MonitoringMessageDomain(workspace)
        self.session = MonitoringSessionDomain(workspace)

    async def embedding_calls(self, *, end_time: Union[str, None] = None, execution_statuses: Union[builtins.list[str], None] = None, knowledge_base_id: Union[str, None] = None, limit: int = 100, mode: str = 'all', offset: int = 0, start_time: Union[str, None] = None) -> OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]]:
        'monitoring.embedding_calls: Retrieve embedding model call statistics and token counts, optionally filtered by knowledge_base_id and time range.\nParameters (Python -> wire): end_time -> end_time, execution_statuses -> execution_statuses, knowledge_base_id -> knowledge_base_id, limit -> limit, mode -> mode, offset -> offset, start_time -> start_time.'
        arguments: MonitoringEmbeddingCallsArguments = {'end_time': end_time, 'execution_statuses': execution_statuses, 'knowledge_base_id': knowledge_base_id, 'limit': limit, 'mode': mode, 'offset': offset, 'start_time': start_time}
        return cast(OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]], await self._workspace.call('monitoring.embedding_calls', **arguments))

    async def errors(self, *, bot_ids: Union[builtins.list[str], None] = None, end_time: Union[str, None] = None, execution_statuses: Union[builtins.list[str], None] = None, limit: int = 100, mode: str = 'all', offset: int = 0, pipeline_ids: Union[builtins.list[str], None] = None, start_time: Union[str, None] = None) -> OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]]:
        'monitoring.errors: Retrieve error logs and failed execution events. Filter by bot_ids, pipeline_ids, execution_statuses, and time range with limit and offset pagination.\nParameters (Python -> wire): bot_ids -> bot_ids, end_time -> end_time, execution_statuses -> execution_statuses, limit -> limit, mode -> mode, offset -> offset, pipeline_ids -> pipeline_ids, start_time -> start_time.'
        arguments: MonitoringErrorsArguments = {'bot_ids': bot_ids, 'end_time': end_time, 'execution_statuses': execution_statuses, 'limit': limit, 'mode': mode, 'offset': offset, 'pipeline_ids': pipeline_ids, 'start_time': start_time}
        return cast(OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]], await self._workspace.call('monitoring.errors', **arguments))

    async def executions(self, *, agent_ids: Union[builtins.list[str], None] = None, bot_ids: Union[builtins.list[str], None] = None, end_time: Union[str, None] = None, include_summary: bool = True, limit: int = 50, mode: str = 'all', offset: int = 0, pipeline_ids: Union[builtins.list[str], None] = None, source: str = 'all', start_time: Union[str, None] = None, statuses: Union[builtins.list[str], None] = None) -> OperationResult[dict[str, JSONValue]]:
        'monitoring.executions: Query and list pipeline and agent execution runs with status and duration. Filter by bot_ids, pipeline_ids, agent_ids, execution statuses, and time range. Supports pagination with limit and offset.\nParameters (Python -> wire): agent_ids -> agent_ids, bot_ids -> bot_ids, end_time -> end_time, include_summary -> include_summary, limit -> limit, mode -> mode, offset -> offset, pipeline_ids -> pipeline_ids, source -> source, start_time -> start_time, statuses -> statuses.'
        arguments: MonitoringExecutionsArguments = {'agent_ids': agent_ids, 'bot_ids': bot_ids, 'end_time': end_time, 'include_summary': include_summary, 'limit': limit, 'mode': mode, 'offset': offset, 'pipeline_ids': pipeline_ids, 'source': source, 'start_time': start_time, 'statuses': statuses}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('monitoring.executions', **arguments))

    async def inflight(self, *, previous: Union[builtins.list[dict[str, JSONValue]], None] = None) -> OperationResult[dict[str, JSONValue]]:
        'monitoring.inflight: Retrieve real-time snapshot of active in-flight requests and currently executing pipeline steps across the workspace.\nParameters (Python -> wire): previous -> previous.'
        arguments: MonitoringInflightArguments = {'previous': previous}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('monitoring.inflight', **arguments))

    async def llm_calls(self, *, bot_ids: Union[builtins.list[str], None] = None, end_time: Union[str, None] = None, execution_statuses: Union[builtins.list[str], None] = None, limit: int = 100, mode: str = 'all', offset: int = 0, pipeline_ids: Union[builtins.list[str], None] = None, start_time: Union[str, None] = None) -> OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]]:
        'monitoring.llm_calls: Query statistics on LLM invocations including latency distributions, token usage, and status codes. Filter by bot_ids, pipeline_ids, and time range.\nParameters (Python -> wire): bot_ids -> bot_ids, end_time -> end_time, execution_statuses -> execution_statuses, limit -> limit, mode -> mode, offset -> offset, pipeline_ids -> pipeline_ids, start_time -> start_time.'
        arguments: MonitoringLlmCallsArguments = {'bot_ids': bot_ids, 'end_time': end_time, 'execution_statuses': execution_statuses, 'limit': limit, 'mode': mode, 'offset': offset, 'pipeline_ids': pipeline_ids, 'start_time': start_time}
        return cast(OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]], await self._workspace.call('monitoring.llm_calls', **arguments))

    async def messages(self, *, bot_ids: Union[builtins.list[str], None] = None, end_time: Union[str, None] = None, execution_statuses: Union[builtins.list[str], None] = None, limit: int = 100, mode: str = 'all', offset: int = 0, pipeline_ids: Union[builtins.list[str], None] = None, session_ids: Union[builtins.list[str], None] = None, start_time: Union[str, None] = None) -> OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]]:
        'monitoring.messages: Retrieve processed inbound and outbound messages. Supports filtering by bot_ids, pipeline_ids, session_ids, and time range. Paginate with limit and offset.\nParameters (Python -> wire): bot_ids -> bot_ids, end_time -> end_time, execution_statuses -> execution_statuses, limit -> limit, mode -> mode, offset -> offset, pipeline_ids -> pipeline_ids, session_ids -> session_ids, start_time -> start_time.'
        arguments: MonitoringMessagesArguments = {'bot_ids': bot_ids, 'end_time': end_time, 'execution_statuses': execution_statuses, 'limit': limit, 'mode': mode, 'offset': offset, 'pipeline_ids': pipeline_ids, 'session_ids': session_ids, 'start_time': start_time}
        return cast(OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]], await self._workspace.call('monitoring.messages', **arguments))

    async def overview(self, *, bot_ids: Union[builtins.list[str], None] = None, end_time: Union[str, None] = None, execution_statuses: Union[builtins.list[str], None] = None, mode: str = 'all', pipeline_ids: Union[builtins.list[str], None] = None, start_time: Union[str, None] = None) -> OperationResult[dict[str, JSONValue]]:
        'monitoring.overview: Retrieve high-level overview metrics including total message counts, active sessions, and errors across bots and pipelines. Supports optional filtering by bot_ids, pipeline_ids, time range (start_time, end_time), and execution status.\nParameters (Python -> wire): bot_ids -> bot_ids, end_time -> end_time, execution_statuses -> execution_statuses, mode -> mode, pipeline_ids -> pipeline_ids, start_time -> start_time.'
        arguments: MonitoringOverviewArguments = {'bot_ids': bot_ids, 'end_time': end_time, 'execution_statuses': execution_statuses, 'mode': mode, 'pipeline_ids': pipeline_ids, 'start_time': start_time}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('monitoring.overview', **arguments))

    async def sessions(self, *, bot_ids: Union[builtins.list[str], None] = None, end_time: Union[str, None] = None, is_active: Union[bool, None] = None, limit: int = 100, offset: int = 0, pipeline_ids: Union[builtins.list[str], None] = None, start_time: Union[str, None] = None, user_query: Union[str, None] = None) -> OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]]:
        'monitoring.sessions: Query chat sessions filtered by bot_ids, pipeline_ids, active status, user query keyword, and time range. Paginate results with limit and offset.\nParameters (Python -> wire): bot_ids -> bot_ids, end_time -> end_time, is_active -> is_active, limit -> limit, offset -> offset, pipeline_ids -> pipeline_ids, start_time -> start_time, user_query -> user_query.'
        arguments: MonitoringSessionsArguments = {'bot_ids': bot_ids, 'end_time': end_time, 'is_active': is_active, 'limit': limit, 'offset': offset, 'pipeline_ids': pipeline_ids, 'start_time': start_time, 'user_query': user_query}
        return cast(OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]], await self._workspace.call('monitoring.sessions', **arguments))

    async def tokens(self, *, bot_ids: Union[builtins.list[str], None] = None, bucket: str = 'hour', end_time: Union[str, None] = None, execution_statuses: Union[builtins.list[str], None] = None, mode: str = 'all', pipeline_ids: Union[builtins.list[str], None] = None, start_time: Union[str, None] = None) -> OperationResult[dict[str, JSONValue]]:
        'monitoring.tokens: Retrieve prompt and completion token consumption aggregated across bots, pipelines, and models. Configure time bucket granularity (bucket) and time window (start_time, end_time).\nParameters (Python -> wire): bot_ids -> bot_ids, bucket -> bucket, end_time -> end_time, execution_statuses -> execution_statuses, mode -> mode, pipeline_ids -> pipeline_ids, start_time -> start_time.'
        arguments: MonitoringTokensArguments = {'bot_ids': bot_ids, 'bucket': bucket, 'end_time': end_time, 'execution_statuses': execution_statuses, 'mode': mode, 'pipeline_ids': pipeline_ids, 'start_time': start_time}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('monitoring.tokens', **arguments))

    async def tool_calls(self, *, bot_ids: Union[builtins.list[str], None] = None, end_time: Union[str, None] = None, execution_statuses: Union[builtins.list[str], None] = None, limit: int = 100, mode: str = 'all', offset: int = 0, pipeline_ids: Union[builtins.list[str], None] = None, session_ids: Union[builtins.list[str], None] = None, start_time: Union[str, None] = None) -> OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]]:
        'monitoring.tool_calls: Retrieve tool and plugin function call events including execution duration and status. Filter by bot_ids, pipeline_ids, session_ids, and time range.\nParameters (Python -> wire): bot_ids -> bot_ids, end_time -> end_time, execution_statuses -> execution_statuses, limit -> limit, mode -> mode, offset -> offset, pipeline_ids -> pipeline_ids, session_ids -> session_ids, start_time -> start_time.'
        arguments: MonitoringToolCallsArguments = {'bot_ids': bot_ids, 'end_time': end_time, 'execution_statuses': execution_statuses, 'limit': limit, 'mode': mode, 'offset': offset, 'pipeline_ids': pipeline_ids, 'session_ids': session_ids, 'start_time': start_time}
        return cast(OperationResult[builtins.list[Union[builtins.list[dict[str, JSONValue]], int]]], await self._workspace.call('monitoring.tool_calls', **arguments))

class PipelineDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.chat = PipelineChatDomain(workspace)
        self.extensions = PipelineExtensionsDomain(workspace)

    async def copy(self, *, pipeline_uuid: str) -> OperationResult[str]:
        'pipeline.copy: Clone an existing pipeline definition under a new identifier. Prerequisites: Call pipeline.list to obtain source pipeline_uuid. Side effect: Creates duplicate pipeline.\nParameters (Python -> wire): pipeline_uuid -> pipeline_uuid.'
        arguments: PipelineCopyArguments = {'pipeline_uuid': pipeline_uuid}
        return cast(OperationResult[str], await self._workspace.call('pipeline.copy', **arguments))

    async def create(self, *, pipeline_data: dict[str, JSONValue], runner_id: Union[str, None] = None) -> OperationResult[str]:
        'pipeline.create: Create and configure a new message processing pipeline. Provide pipeline_data containing nodes and flow definition. Side effect: Creates a new pipeline entity.\nParameters (Python -> wire): pipeline_data -> pipeline_data, runner_id -> runner_id.'
        arguments: PipelineCreateArguments = {'pipeline_data': pipeline_data, 'runner_id': runner_id}
        return cast(OperationResult[str], await self._workspace.call('pipeline.create', **arguments))

    async def defaults(self, *, runner_id: Union[str, None] = None) -> OperationResult[dict[str, JSONValue]]:
        'pipeline.defaults: Retrieve default pipeline templates and starter configuration presets for creating standard processing workflows.\nParameters (Python -> wire): runner_id -> runner_id.'
        arguments: PipelineDefaultsArguments = {'runner_id': runner_id}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('pipeline.defaults', **arguments))

    async def delete(self, *, pipeline_uuid: str) -> OperationResult[None]:
        'pipeline.delete: Delete a processing pipeline and disconnect it from associated bots. Prerequisites: Call pipeline.list to obtain pipeline_uuid. Side effect: Irreversible removal of pipeline.\nParameters (Python -> wire): pipeline_uuid -> pipeline_uuid.'
        arguments: PipelineDeleteArguments = {'pipeline_uuid': pipeline_uuid}
        return cast(OperationResult[None], await self._workspace.call('pipeline.delete', **arguments))

    async def get(self, *, include_secret: bool = False, pipeline_uuid: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'pipeline.get: Retrieve full pipeline configuration including components, flow nodes, and bound models/tools. Prerequisites: Call pipeline.list to obtain pipeline_uuid.\nParameters (Python -> wire): include_secret -> include_secret, pipeline_uuid -> pipeline_uuid.'
        arguments: PipelineGetArguments = {'include_secret': include_secret, 'pipeline_uuid': pipeline_uuid}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('pipeline.get', **arguments))

    async def list(self, *, include_secret: bool = False, sort_by: str = 'created_at', sort_order: str = 'DESC') -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'pipeline.list: Retrieve all configured pipelines in the workspace, including node configurations and active routing states. Supports sort_by, sort_order, and include_secret.\nParameters (Python -> wire): include_secret -> include_secret, sort_by -> sort_by, sort_order -> sort_order.'
        arguments: PipelineListArguments = {'include_secret': include_secret, 'sort_by': sort_by, 'sort_order': sort_order}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('pipeline.list', **arguments))

    async def metadata(self) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'pipeline.metadata: Retrieve supported pipeline component types, node port contracts, and configuration parameter schemas.'
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('pipeline.metadata'))

    async def run(self, *, pipeline_uuid: str, text: str, timeout: float = 60.0) -> OperationResult[dict[str, JSONValue]]:
        'pipeline.run: Trigger an on-demand execution of a pipeline with provided payload. Prerequisites: Call pipeline.list to obtain pipeline_uuid. Side effect: Executes pipeline logic and consumes compute.\nParameters (Python -> wire): pipeline_uuid -> pipeline_uuid, text -> text, timeout -> timeout.'
        arguments: PipelineRunArguments = {'pipeline_uuid': pipeline_uuid, 'text': text, 'timeout': timeout}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('pipeline.run', **arguments))

    async def update(self, *, pipeline_data: dict[str, JSONValue], pipeline_uuid: str) -> OperationResult[None]:
        'pipeline.update: Modify pipeline settings or name. Call pipeline.get first: config merges top-level sections, preserving omitted sections and replacing each supplied section in full. Supplied sections must be objects. The merged configuration is validated and runtime initialization is checked before persistence. Side effect: Updates pipeline definition.\nParameters (Python -> wire): pipeline_data -> pipeline_data, pipeline_uuid -> pipeline_uuid.'
        arguments: PipelineUpdateArguments = {'pipeline_data': pipeline_data, 'pipeline_uuid': pipeline_uuid}
        return cast(OperationResult[None], await self._workspace.call('pipeline.update', **arguments))

class PluginDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.config = PluginConfigDomain(workspace)
        self.github = PluginGithubDomain(workspace)
        self.install = PluginInstallDomain(workspace)
        self.marketplace = PluginMarketplaceDomain(workspace)

    async def debug_info(self) -> OperationResult[PluginDebugInfoOutput]:
        'plugin.debug_info: Inspect plugin container/process status, memory consumption, and active communication channels across the workspace.'
        return cast(OperationResult[PluginDebugInfoOutput], await self._workspace.call('plugin.debug_info'))

    async def get(self, *, author: str, plugin_name: str) -> OperationResult[PluginGetOutput]:
        'plugin.get: Retrieve manifest, permissions, and configuration options for an installed plugin. Prerequisites: Call plugin.list to obtain author and plugin_name.\nParameters (Python -> wire): author -> author, plugin_name -> plugin_name.'
        arguments: PluginGetArguments = {'author': author, 'plugin_name': plugin_name}
        return cast(OperationResult[PluginGetOutput], await self._workspace.call('plugin.get', **arguments))

    async def list(self) -> OperationResult[PluginListOutput]:
        'plugin.list: Retrieve all installed workspace plugins with version numbers, author details, enablement state, and registered capabilities.'
        return cast(OperationResult[PluginListOutput], await self._workspace.call('plugin.list'))

    async def logs(self, *, author: str, level: Union[str, None] = None, limit: int = 200, plugin_name: str) -> OperationResult[dict[str, JSONValue]]:
        'plugin.logs: Retrieve stdout/stderr logs and diagnostic traces produced by a running plugin. Prerequisites: Call plugin.list to obtain author and plugin_name.\nParameters (Python -> wire): author -> author, level -> level, limit -> limit, plugin_name -> plugin_name.'
        arguments: PluginLogsArguments = {'author': author, 'level': level, 'limit': limit, 'plugin_name': plugin_name}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('plugin.logs', **arguments))

    async def readme(self, *, author: str, language: str = 'en', plugin_name: str) -> OperationResult[PluginReadmeOutput]:
        'plugin.readme: Fetch the README documentation of an installed plugin in the requested language. Prerequisites: Call plugin.list to obtain author and plugin_name.\nParameters (Python -> wire): author -> author, language -> language, plugin_name -> plugin_name.'
        arguments: PluginReadmeArguments = {'author': author, 'language': language, 'plugin_name': plugin_name}
        return cast(OperationResult[PluginReadmeOutput], await self._workspace.call('plugin.readme', **arguments))

class ProviderDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.models = ProviderModelsDomain(workspace)

    async def create(self, *, provider_data: dict[str, JSONValue]) -> OperationResult[str]:
        'provider.create: Register a new model provider with API key and base URL. Side effect: Creates provider entity.\nParameters (Python -> wire): provider_data -> provider_data.'
        arguments: ProviderCreateArguments = {'provider_data': provider_data}
        return cast(OperationResult[str], await self._workspace.call('provider.create', **arguments))

    async def delete(self, *, cascade: bool = False, provider_uuid: str) -> OperationResult[None]:
        'provider.delete: Remove a model provider from the workspace. Prerequisites: Call provider.list to obtain provider_uuid. Set cascade=True to delete associated models. Side effect: Deletes provider.\nParameters (Python -> wire): cascade -> cascade, provider_uuid -> provider_uuid.'
        arguments: ProviderDeleteArguments = {'cascade': cascade, 'provider_uuid': provider_uuid}
        return cast(OperationResult[None], await self._workspace.call('provider.delete', **arguments))

    async def get(self, *, include_secret: bool = False, provider_uuid: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'provider.get: Retrieve detailed configuration for a model provider. Prerequisites: Call provider.list to obtain provider_uuid. Optionally pass include_secret.\nParameters (Python -> wire): include_secret -> include_secret, provider_uuid -> provider_uuid.'
        arguments: ProviderGetArguments = {'include_secret': include_secret, 'provider_uuid': provider_uuid}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('provider.get', **arguments))

    async def list(self, *, include_secret: bool = False) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'provider.list: Retrieve configured model providers (e.g. OpenAI, Anthropic, Ollama) and base URLs. Pass include_secret=True to include credentials.\nParameters (Python -> wire): include_secret -> include_secret.'
        arguments: ProviderListArguments = {'include_secret': include_secret}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('provider.list', **arguments))

    async def update(self, *, provider_data: dict[str, JSONValue], provider_uuid: str) -> OperationResult[None]:
        'provider.update: Modify provider settings, API keys, or custom base URLs. Prerequisites: Call provider.list to obtain provider_uuid. Side effect: Updates provider settings.\nParameters (Python -> wire): provider_data -> provider_data, provider_uuid -> provider_uuid.'
        arguments: ProviderUpdateArguments = {'provider_data': provider_data, 'provider_uuid': provider_uuid}
        return cast(OperationResult[None], await self._workspace.call('provider.update', **arguments))

class RequesterDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self, *, requester_name: str) -> OperationResult[dict[str, JSONValue]]:
        'requester.get: Retrieve configuration details and capabilities of a requester. Prerequisites: Call requester.list to discover valid requester_name values.\nParameters (Python -> wire): requester_name -> requester_name.'
        arguments: RequesterGetArguments = {'requester_name': requester_name}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('requester.get', **arguments))

    async def list(self, *, model_type: str = '') -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'requester.list: Retrieve supported HTTP and API request client implementations (e.g. standard HTTP, streaming client, proxy clients).\nParameters (Python -> wire): model_type -> model_type.'
        arguments: RequesterListArguments = {'model_type': model_type}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('requester.list', **arguments))

class SkillDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.file = SkillFileDomain(workspace)
        self.github = SkillGithubDomain(workspace)

    async def create(self, *, data: dict[str, JSONValue]) -> OperationResult[dict[str, JSONValue]]:
        'skill.create: Create a new skill package with name, description, and initial script files. Side effect: Instantiates a new skill directory.\nParameters (Python -> wire): data -> data.'
        arguments: SkillCreateArguments = {'data': data}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('skill.create', **arguments))

    async def delete(self, *, skill_name: str) -> OperationResult[bool]:
        'skill.delete: Permanently remove a skill and delete its associated script files. Prerequisites: Call skill.list to obtain skill_name. Side effect: Irreversible removal of skill.\nParameters (Python -> wire): skill_name -> skill_name.'
        arguments: SkillDeleteArguments = {'skill_name': skill_name}
        return cast(OperationResult[bool], await self._workspace.call('skill.delete', **arguments))

    async def get(self, *, skill_name: str) -> OperationResult[Union[dict[str, JSONValue], None]]:
        'skill.get: Retrieve complete skill definition, parameter schema, and file structure. Prerequisites: Call skill.list to obtain skill_name.\nParameters (Python -> wire): skill_name -> skill_name.'
        arguments: SkillGetArguments = {'skill_name': skill_name}
        return cast(OperationResult[Union[dict[str, JSONValue], None]], await self._workspace.call('skill.get', **arguments))

    async def list(self) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'skill.list: Retrieve all custom skill packages registered in the workspace, including descriptions, version tags, and entry points.'
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('skill.list'))

    async def reload(self) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'skill.reload: Re-index skill files from disk and re-register executable tools in the workspace runtime. Side effect: Refreshes active skill execution cache.'
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('skill.reload'))

    async def update(self, *, data: dict[str, JSONValue], skill_name: str) -> OperationResult[dict[str, JSONValue]]:
        'skill.update: Update skill description, parameters, or settings. Prerequisites: Call skill.list to obtain skill_name. Side effect: Modifies skill definition.\nParameters (Python -> wire): data -> data, skill_name -> skill_name.'
        arguments: SkillUpdateArguments = {'data': data, 'skill_name': skill_name}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('skill.update', **arguments))

class StatsDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def basic(self) -> OperationResult[dict[str, int]]:
        'stats.basic: Retrieve aggregate workspace statistics including total bot count, active pipelines, configured models, and knowledge bases.'
        return cast(OperationResult[dict[str, int]], await self._workspace.call('stats.basic'))

class TaskDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self, *, task_id: int) -> OperationResult[dict[str, JSONValue]]:
        'task.get: Return the status of a Workspace background task by task_id, for example one returned by plugin.install.marketplace. status is running, succeeded, failed or cancelled; pending_permission_confirmation is true when an installed plugin awaits member confirmation.\nParameters (Python -> wire): task_id -> task_id.'
        arguments: TaskGetArguments = {'task_id': task_id}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('task.get', **arguments))

class ToolDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace

    async def get(self, *, pipeline_uuid: Union[str, None] = None, tool_name: str) -> OperationResult[dict[str, JSONValue]]:
        'tool.get: Retrieve input schema, argument descriptions, and execution requirements for a tool. Prerequisites: Call tool.list to obtain tool_name (and optional pipeline_uuid from pipeline.list).\nParameters (Python -> wire): pipeline_uuid -> pipeline_uuid, tool_name -> tool_name.'
        arguments: ToolGetArguments = {'pipeline_uuid': pipeline_uuid, 'tool_name': tool_name}
        return cast(OperationResult[dict[str, JSONValue]], await self._workspace.call('tool.get', **arguments))

    async def list(self, *, pipeline_uuid: Union[str, None] = None) -> OperationResult[builtins.list[dict[str, JSONValue]]]:
        'tool.list: Retrieve all available executable function tools, including plugin actions, MCP tools, and skill functions. Optionally filter by pipeline_uuid (get it from pipeline.list).\nParameters (Python -> wire): pipeline_uuid -> pipeline_uuid.'
        arguments: ToolListArguments = {'pipeline_uuid': pipeline_uuid}
        return cast(OperationResult[builtins.list[dict[str, JSONValue]]], await self._workspace.call('tool.list', **arguments))

class WorkspaceDomain:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.language = WorkspaceLanguageDomain(workspace)

class WorkspaceDomains:
    def __init__(self, workspace: "WorkspaceOperationsProxy"):
        self._workspace = workspace
        self.adapter = AdapterDomain(workspace)
        self.agent = AgentDomain(workspace)
        self.bot = BotDomain(workspace)
        self.extension = ExtensionDomain(workspace)
        self.knowledge = KnowledgeDomain(workspace)
        self.mcp = McpDomain(workspace)
        self.model = ModelDomain(workspace)
        self.monitoring = MonitoringDomain(workspace)
        self.pipeline = PipelineDomain(workspace)
        self.plugin = PluginDomain(workspace)
        self.provider = ProviderDomain(workspace)
        self.requester = RequesterDomain(workspace)
        self.skill = SkillDomain(workspace)
        self.stats = StatsDomain(workspace)
        self.task = TaskDomain(workspace)
        self.tool = ToolDomain(workspace)
        self.workspace = WorkspaceDomain(workspace)
