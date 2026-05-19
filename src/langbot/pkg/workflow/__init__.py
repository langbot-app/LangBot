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

from importlib import import_module
from typing import Any

from .node import WorkflowNode, workflow_node


def __getattr__(name: str) -> Any:
    """Lazily expose heavier workflow modules.

    Loading workflow metadata should not import the executor or node modules as a
    side effect. Node implementations are imported explicitly during boot after
    YAML metadata has been registered.
    """
    if name == 'NodeTypeRegistry':
        from .registry import NodeTypeRegistry

        return NodeTypeRegistry

    if name == 'WorkflowExecutor':
        from .executor import WorkflowExecutor

        return WorkflowExecutor

    if name in ('DebugWorkflowExecutor', 'DebugExecutionState', 'ExecutionLog'):
        from . import debug

        return getattr(debug, name)

    if name == 'nodes':
        return import_module('.nodes', __name__)

    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')

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
    'workflow_node',
    # Registry
    'NodeTypeRegistry',
    # Executor
    'WorkflowExecutor',
    # Debug
    'DebugWorkflowExecutor',
    'DebugExecutionState',
    'ExecutionLog',
]
