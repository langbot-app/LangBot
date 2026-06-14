"""Agent runner modules."""
from __future__ import annotations

from .descriptor import AgentRunnerDescriptor
from .id import parse_runner_id, format_runner_id, RunnerIdParts
from .errors import (
    AgentRunnerError,
    RunnerNotFoundError,
    RunnerNotAuthorizedError,
    RunnerProtocolError,
    RunnerExecutionError,
)
from .registry import AgentRunnerRegistry
from .context_builder import AgentRunContextBuilder
from .resource_builder import AgentResourceBuilder
from .result_normalizer import AgentResultNormalizer
from .orchestrator import AgentRunOrchestrator
from .config_migration import ConfigMigration
from .default_config import AgentRunnerDefaultConfigService
from .binding_resolver import AgentBindingResolver, AgentBindingResolutionError
from .session_registry import (
    AgentRunSessionRegistry,
    AgentRunSession,
    RunAuthorizationSnapshot,
    get_session_registry,
)
from .events import (
    MESSAGE_RECEIVED,
    MESSAGE_RECALLED,
    GROUP_MEMBER_JOINED,
    FRIEND_REQUEST_RECEIVED,
    RESERVED_EVENT_TYPES,
)

__all__ = [
    'AgentRunnerDescriptor',
    'parse_runner_id',
    'format_runner_id',
    'RunnerIdParts',
    'AgentRunnerError',
    'RunnerNotFoundError',
    'RunnerNotAuthorizedError',
    'RunnerProtocolError',
    'RunnerExecutionError',
    'AgentRunnerRegistry',
    'AgentRunContextBuilder',
    'AgentResourceBuilder',
    'AgentResultNormalizer',
    'AgentRunOrchestrator',
    'ConfigMigration',
    'AgentRunnerDefaultConfigService',
    'AgentBindingResolver',
    'AgentBindingResolutionError',
    'AgentRunSessionRegistry',
    'AgentRunSession',
    'RunAuthorizationSnapshot',
    'get_session_registry',
    'MESSAGE_RECEIVED',
    'MESSAGE_RECALLED',
    'GROUP_MEMBER_JOINED',
    'FRIEND_REQUEST_RECEIVED',
    'RESERVED_EVENT_TYPES',
]
