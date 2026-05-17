"""Workflow node base class and decorators"""

from __future__ import annotations

import abc
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .entities import ExecutionContext
    from ..core import app


class WorkflowNode(abc.ABC):
    """Base class for all workflow nodes.

    Node metadata (inputs, outputs, config schema, label, icon, etc.) is
    defined exclusively in YAML files under templates/metadata/nodes/.
    Python subclasses only provide execution logic and runtime behaviour.
    """

    # Set by @workflow_node decorator
    type_name: str = ''

    # Category is kept as a fallback for registry when YAML is missing
    category: str = 'misc'

    # Pipeline config reuse (referenced by registry merge logic)
    config_schema_source: Optional[str] = None
    config_stages: list[str] = []

    def __init__(self, node_id: str, config: dict[str, Any], ap: Optional['app.Application'] = None):
        """Initialize node with ID and configuration"""
        self.node_id = node_id
        self.config = config
        self.ap = ap

    @abc.abstractmethod
    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        """Execute the node logic.

        Args:
            inputs: Input data from connected nodes
            context: Execution context with workflow state

        Returns:
            Dictionary of output values
        """
        pass

    # ------------------------------------------------------------------
    # Validation helpers — metadata is resolved from the registry at
    # runtime so that YAML remains the single source of truth.
    # ------------------------------------------------------------------

    async def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate input data against YAML port definitions.

        Returns:
            List of validation error messages (empty if valid)
        """
        metadata = self._get_metadata()
        if metadata is None:
            return []

        errors: list[str] = []
        for port in metadata.get('inputs', []):
            if port.get('required', True) and port.get('name') and port['name'] not in inputs:
                errors.append(f"Missing required input: {port['name']}")
        return errors

    async def validate_config(self) -> list[str]:
        """Validate node configuration against YAML config schema.

        Returns:
            List of validation error messages (empty if valid)
        """
        metadata = self._get_metadata()
        if metadata is None:
            return []

        errors: list[str] = []
        for cfg in metadata.get('config', []):
            name = cfg.get('name', '')
            if not name:
                continue
            required = cfg.get('required', False)
            cfg_type = cfg.get('type', 'string')

            if required and name not in self.config:
                errors.append(f'Missing required config: {name}')
            elif name in self.config:
                value = self.config[name]
                # Type validation
                if cfg_type == 'integer' and not isinstance(value, int):
                    errors.append(f'Config {name} must be an integer')
                elif cfg_type == 'number' and not isinstance(value, (int, float)):
                    errors.append(f'Config {name} must be a number')
                elif cfg_type == 'boolean' and not isinstance(value, bool):
                    errors.append(f'Config {name} must be a boolean')
                # Range validation
                min_val = cfg.get('min_value')
                max_val = cfg.get('max_value')
                if min_val is not None and isinstance(value, (int, float)):
                    if value < min_val:
                        errors.append(f'Config {name} must be >= {min_val}')
                if max_val is not None and isinstance(value, (int, float)):
                    if value > max_val:
                        errors.append(f'Config {name} must be <= {max_val}')
        return errors

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default"""
        return self.config.get(key, default)

    def _get_metadata(self) -> Optional[dict[str, Any]]:
        """Retrieve YAML metadata for this node from the registry."""
        from .registry import NodeTypeRegistry
        registry = NodeTypeRegistry.instance()
        return registry.get_metadata(self.type_name)


# ------------------------------------------------------------------
# Decorator and pending registration helpers
# ------------------------------------------------------------------

_pending_registrations: list[tuple[str, type[WorkflowNode]]] = []


def workflow_node(type_name: str) -> Callable[[type[WorkflowNode]], type[WorkflowNode]]:
    """Decorator to register a workflow node type.

    Usage:
        @workflow_node('llm_call')
        class LLMCallNode(WorkflowNode):
            ...
    """

    def decorator(cls: type[WorkflowNode]) -> type[WorkflowNode]:
        cls.type_name = type_name
        _pending_registrations.append((type_name, cls))
        return cls

    return decorator


def get_pending_registrations() -> list[tuple[str, type[WorkflowNode]]]:
    """Get pending node registrations"""
    return _pending_registrations.copy()


def clear_pending_registrations():
    """Clear pending registrations after they're processed"""
    _pending_registrations.clear()
