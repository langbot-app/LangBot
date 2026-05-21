"""Workflow entities and data models

This module defines workflow entities using SDK standard entities where available,
and local-specific entities for LangBot_copy-specific functionality.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
import pydantic

# Import SDK entities for standard workflow protocol types
from langbot_plugin.api.entities.builtin.workflow import (
    ExecutionContext,
    ExecutionStep,
    ExecutionStatus,
    MessageContext,
    NodeDefinition,
    NodeState,
    NodeStatus,
    PortDefinition,
)


class Position(pydantic.BaseModel):
    """Node position on canvas"""

    x: float = 0
    y: float = 0


class EdgeDefinition(pydantic.BaseModel):
    """Workflow edge definition (connection between nodes)"""

    id: str
    source_node: str
    source_port: str = 'output'
    target_node: str
    target_port: str = 'input'
    condition: Optional[str] = None  # Optional condition expression


class TriggerDefinition(pydantic.BaseModel):
    """Workflow trigger definition"""

    id: str
    type: str  # message, cron, event, webhook
    config: dict[str, Any] = {}
    enabled: bool = True


class WorkflowSettings(pydantic.BaseModel):
    """Workflow settings"""

    # Execution settings
    max_execution_time: int = 300  # seconds
    max_retries: int = 3
    retry_delay: int = 5  # seconds

    # Error handling
    error_handling: str = 'stop'  # stop, continue, retry

    # Logging
    log_level: str = 'info'
    save_execution_history: bool = True

    # Concurrency
    max_concurrent_executions: int = 10


class SafetyConfig(pydantic.BaseModel):
    """Safety configuration (inherited from Pipeline)"""

    content_filter: dict[str, Any] = {'enable': False, 'sensitive_words': [], 'replace_with': '***'}
    rate_limit: dict[str, Any] = {'enable': False, 'requests_per_minute': 60, 'burst_limit': 10}


class OutputConfig(pydantic.BaseModel):
    """Output configuration (inherited from Pipeline)"""

    long_text_processing: dict[str, Any] = {
        'strategy': 'split',  # split, truncate, file
        'max_length': 4000,
        'split_separator': '\n\n',
    }
    force_delay: dict[str, Any] = {'enable': False, 'min_delay_ms': 0, 'max_delay_ms': 0}
    misc: dict[str, Any] = {}


class WorkflowGlobalConfig(pydantic.BaseModel):
    """Workflow global configuration (inherited from Pipeline capabilities)"""

    safety: SafetyConfig = SafetyConfig()
    output: OutputConfig = OutputConfig()


class ExtensionsPreferences(pydantic.BaseModel):
    """Extensions preferences (same as Pipeline)"""

    enable_all_plugins: bool = True
    enable_all_mcp_servers: bool = True
    plugins: list[str] = []
    mcp_servers: list[str] = []


class ConversationVariable(pydantic.BaseModel):
    """Conversation-level variable definition"""

    name: str
    type: str = 'string'  # string, number, boolean, object, array
    description: str = ''
    default_value: Any = None
    max_length: Optional[int] = None  # For strings


class WorkflowDefinition(pydantic.BaseModel):
    """Complete workflow definition"""

    uuid: str
    name: str
    description: str = ''
    emoji: str = '🔄'
    version: int = 1

    # Workflow graph
    nodes: list[NodeDefinition] = []
    edges: list[EdgeDefinition] = []

    # Variables
    variables: dict[str, Any] = {}  # Global variables
    conversation_variables: list[ConversationVariable] = []  # Session-level variables

    # Settings
    settings: WorkflowSettings = WorkflowSettings()

    # Triggers (for automation)
    triggers: list[TriggerDefinition] = []

    # Global configuration (inherited from Pipeline)
    global_config: WorkflowGlobalConfig = WorkflowGlobalConfig()

    # Extensions
    extensions_preferences: ExtensionsPreferences = ExtensionsPreferences()

    # Metadata
    is_enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Source tracking (for imported workflows)
    source: Optional[str] = None  # dify, n8n, langflow, etc.
    source_id: Optional[str] = None
