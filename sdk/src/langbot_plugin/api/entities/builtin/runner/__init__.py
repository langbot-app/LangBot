"""Runner entities for Protocol v1."""

from langbot_plugin.api.entities.builtin.runner.manifest import (
    RunnerCapabilities,
    RunnerManifest,
    RunnerPermissions,
    DynamicFormItemSchema,
    I18nObject,
)
from langbot_plugin.api.entities.builtin.runner.trigger import AgentTrigger
from langbot_plugin.api.entities.builtin.runner.input import (
    AgentInput,
    InputAttachment,
)
from langbot_plugin.api.entities.builtin.runner.resources import (
    AgentResources,
    ModelResource,
    ToolResource,
    KnowledgeBaseResource,
    SkillResource,
    StorageResource,
    WorkspaceOperationResource,
)
from langbot_plugin.api.entities.builtin.runner.runtime import AgentRuntimeContext
from langbot_plugin.api.entities.builtin.runner.state import (
    AgentRunState,
    VALID_STATE_SCOPES,
)
from langbot_plugin.api.entities.builtin.runner.event import (
    ConversationContext,
    AgentEventContext,
    ActorContext,
    SubjectContext,
    RawEventRef,
)
from langbot_plugin.api.entities.builtin.runner.context_access import (
    ContextAccess,
    InlineContextPolicy,
    ContextAPICapabilities,
)
from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.runner.interaction import (
    InteractionAction,
    InteractionActionStyle,
    InteractionDeliveryCapabilities,
    InteractionDegradation,
    InteractionField,
    InteractionFieldType,
    InteractionOption,
    InteractionHandle,
    InteractionNotSupportedError,
    InteractionRequest,
    InteractionResult,
    InteractionSubmission,
    JSONValue,
)
from langbot_plugin.api.entities.builtin.runner.context import (
    RunnerContext,
    AdapterContext,
)
from langbot_plugin.api.entities.builtin.runner.result import (
    ActionRequestedPayload,
    RunnerResult,
    RunnerResultType,
    MessageCompletedPayload,
    MessageDeltaPayload,
    RunCompletedPayload,
    RunFailedPayload,
    StateUpdatedPayload,
    ToolCallCompletedPayload,
    ToolCallStartedPayload,
)
from langbot_plugin.api.entities.builtin.runner.transcript import TranscriptItem
from langbot_plugin.api.entities.builtin.runner.page_results import (
    HistoryPage,
    HistorySearchResult,
    AgentEventRecord,
    EventPage,
)
from langbot_plugin.api.entities.builtin.runner.run_ledger import (
    AgentRun,
    AgentRunEvent,
    AgentRunStatus,
    RunEventPage,
    RunPage,
)
from langbot_plugin.api.entities.builtin.runner.runtime_registry import (
    AgentRuntime,
    RuntimePage,
)
from langbot_plugin.api.entities.builtin.runner.stats import (
    RunnerStats,
    RunnerStatsPage,
    RunStats,
    RuntimeStats,
)
from langbot_plugin.api.entities.builtin.runner.errors import (
    AgentAPIError,
    AgentAPIException,
)
from langbot_plugin.api.entities.builtin.runner.steering import (
    SteeringInputItem,
    SteeringPullResult,
)
from langbot_plugin.api.entities.builtin.provider.message import (
    LLMInvokeResult,
    LLMStreamEvent,
    LLMTokenUsage,
)

__all__ = [
    # Manifest
    "RunnerCapabilities",
    "RunnerManifest",
    "RunnerPermissions",
    "DynamicFormItemSchema",
    "I18nObject",
    # Event and context
    "AgentTrigger",
    "AgentInput",
    "InputAttachment",
    "AgentResources",
    "ModelResource",
    "ToolResource",
    "KnowledgeBaseResource",
    "SkillResource",
    "StorageResource",
    "WorkspaceOperationResource",
    "AgentRuntimeContext",
    "AgentRunState",
    "VALID_STATE_SCOPES",
    "ConversationContext",
    "AgentEventContext",
    "ActorContext",
    "SubjectContext",
    "RawEventRef",
    # Protocol v1 context access
    "ContextAccess",
    "InlineContextPolicy",
    "ContextAPICapabilities",
    "DeliveryContext",
    "InteractionAction",
    "InteractionActionStyle",
    "InteractionDeliveryCapabilities",
    "InteractionDegradation",
    "InteractionField",
    "InteractionFieldType",
    "InteractionOption",
    "InteractionHandle",
    "InteractionNotSupportedError",
    "InteractionRequest",
    "InteractionResult",
    "InteractionSubmission",
    "JSONValue",
    "AdapterContext",
    # Main context and result
    "RunnerContext",
    "ActionRequestedPayload",
    "RunnerResult",
    "RunnerResultType",
    "MessageCompletedPayload",
    "MessageDeltaPayload",
    "RunCompletedPayload",
    "RunFailedPayload",
    "StateUpdatedPayload",
    "ToolCallCompletedPayload",
    "ToolCallStartedPayload",
    # History and Event APIs
    "TranscriptItem",
    "HistoryPage",
    "HistorySearchResult",
    "AgentEventRecord",
    "EventPage",
    # Run Ledger APIs
    "AgentRun",
    "AgentRunEvent",
    "AgentRunStatus",
    "RunEventPage",
    "RunPage",
    # Runtime Registry APIs
    "AgentRuntime",
    "RuntimePage",
    # Admin Stats APIs
    "RunStats",
    "RuntimeStats",
    "RunnerStats",
    "RunnerStatsPage",
    # Steering API
    "SteeringInputItem",
    "SteeringPullResult",
    # Error model
    "AgentAPIError",
    "AgentAPIException",
    # LLM invoke result metadata
    "LLMInvokeResult",
    "LLMStreamEvent",
    "LLMTokenUsage",
]
