"""Workflow entities and data models"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional
import pydantic


class Position(pydantic.BaseModel):
    """Node position on canvas"""
    x: float = 0
    y: float = 0


class PortDefinition(pydantic.BaseModel):
    """Node port definition"""
    name: str
    type: str = "any"  # any, string, number, boolean, object, array
    description: str = ""
    required: bool = True


class NodeDefinition(pydantic.BaseModel):
    """Workflow node definition"""
    id: str
    type: str
    name: str = ""
    position: Position = Position()
    config: dict[str, Any] = {}
    inputs: list[PortDefinition] = []
    outputs: list[PortDefinition] = []
    
    # UI metadata
    description: str = ""
    comment: str = ""  # User comment/annotation


class EdgeDefinition(pydantic.BaseModel):
    """Workflow edge definition (connection between nodes)"""
    id: str
    source_node: str
    source_port: str = "output"
    target_node: str
    target_port: str = "input"
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
    error_handling: str = "stop"  # stop, continue, retry
    
    # Logging
    log_level: str = "info"
    save_execution_history: bool = True
    
    # Concurrency
    max_concurrent_executions: int = 10


class SafetyConfig(pydantic.BaseModel):
    """Safety configuration (inherited from Pipeline)"""
    content_filter: dict[str, Any] = {
        "enable": False,
        "sensitive_words": [],
        "replace_with": "***"
    }
    rate_limit: dict[str, Any] = {
        "enable": False,
        "requests_per_minute": 60,
        "burst_limit": 10
    }


class OutputConfig(pydantic.BaseModel):
    """Output configuration (inherited from Pipeline)"""
    long_text_processing: dict[str, Any] = {
        "strategy": "split",  # split, truncate, file
        "max_length": 4000,
        "split_separator": "\n\n"
    }
    force_delay: dict[str, Any] = {
        "enable": False,
        "min_delay_ms": 0,
        "max_delay_ms": 0
    }
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
    type: str = "string"  # string, number, boolean, object, array
    description: str = ""
    default_value: Any = None
    max_length: Optional[int] = None  # For strings


class WorkflowDefinition(pydantic.BaseModel):
    """Complete workflow definition"""
    uuid: str
    name: str
    description: str = ""
    emoji: str = "🔄"
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


class ExecutionStatus(enum.Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(enum.Enum):
    """Node execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeState(pydantic.BaseModel):
    """Runtime state of a node during execution"""
    node_id: str
    status: NodeStatus = NodeStatus.PENDING
    inputs: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0


class MessageContext(pydantic.BaseModel):
    """Message context for message-triggered workflows"""
    message_id: str
    message_content: str
    sender_id: str
    sender_name: str = ""
    platform: str = ""
    conversation_id: str = ""
    is_group: bool = False
    group_id: Optional[str] = None
    mentions: list[str] = []
    reply_to: Optional[str] = None
    raw_message: dict[str, Any] = {}


class ExecutionStep(pydantic.BaseModel):
    """Execution history step"""
    timestamp: datetime
    node_id: str
    node_type: str
    status: str
    inputs: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    duration_ms: int = 0
    error: Optional[str] = None


class ExecutionContext(pydantic.BaseModel):
    """Workflow execution context"""
    execution_id: str
    workflow_id: str
    workflow_version: int = 1
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    # Runtime data
    variables: dict[str, Any] = {}
    conversation_variables: dict[str, Any] = {}  # Session-level persistent variables
    node_states: dict[str, NodeState] = {}
    memory: dict[str, Any] = {}  # Workflow memory for storing/retrieving data
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Error
    error: Optional[str] = None
    
    # Message context (if triggered by message)
    message_context: Optional[MessageContext] = None
    
    # Trigger info
    trigger_type: Optional[str] = None
    trigger_data: dict[str, Any] = {}
    
    # Execution history
    history: list[ExecutionStep] = []
    
    # Session info
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    bot_id: Optional[str] = None
    
    def get_node_output(self, node_id: str, output_name: str = "output") -> Any:
        """Get output from a specific node"""
        if node_id in self.node_states:
            return self.node_states[node_id].outputs.get(output_name)
        return None
    
    def set_variable(self, name: str, value: Any):
        """Set a workflow variable"""
        self.variables[name] = value
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a workflow variable"""
        return self.variables.get(name, default)
    
    def set_conversation_variable(self, name: str, value: Any):
        """Set a conversation-level variable (persisted across executions)"""
        self.conversation_variables[name] = value
    
    def get_conversation_variable(self, name: str, default: Any = None) -> Any:
        """Get a conversation-level variable"""
        return self.conversation_variables.get(name, default)
