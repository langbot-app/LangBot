"""Workflow package for LangBot

This package provides a visual workflow system for LangBot, including:
- Workflow definition models
- Execution engine
- Node types (trigger, process, control, action, integration)
- Trigger system for automation
"""

from .entities import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    Position,
    PortDefinition,
    TriggerDefinition,
    WorkflowSettings,
    ExecutionContext,
    NodeState,
    ExecutionStatus,
    NodeStatus,
)

from .node import WorkflowNode, NodePort, NodeConfig, workflow_node
from .registry import NodeTypeRegistry
from .executor import WorkflowExecutor

# Import nodes module to trigger node registration
from . import nodes as nodes

__all__ = [
    # Entities
    'WorkflowDefinition',
    'NodeDefinition',
    'EdgeDefinition',
    'Position',
    'PortDefinition',
    'TriggerDefinition',
    'WorkflowSettings',
    'ExecutionContext',
    'NodeState',
    'ExecutionStatus',
    'NodeStatus',
    # Node
    'WorkflowNode',
    'NodePort',
    'NodeConfig',
    'workflow_node',
    # Registry
    'NodeTypeRegistry',
    # Executor
    'WorkflowExecutor',
]
