"""Workflow node base class and decorators"""
from __future__ import annotations

import abc
from typing import Any, Callable, Optional, TYPE_CHECKING

import pydantic

if TYPE_CHECKING:
    from .entities import ExecutionContext
    from ..core import app


class NodePort(pydantic.BaseModel):
    """Node port definition"""
    name: str
    type: str = "any"  # any, string, number, boolean, object, array
    description: str = ""
    required: bool = True


class NodeConfig(pydantic.BaseModel):
    """Node configuration field definition"""
    name: str
    type: str  # string, integer, number, boolean, select, json, secret, etc.
    required: bool = False
    default: Any = None
    description: str = ""
    options: Optional[list[str]] = None  # For select type
    
    # Validation
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern
    
    # UI hints
    placeholder: str = ""
    show_if: Optional[dict] = None  # Conditional display
    
    # Pipeline config source (for reusing Pipeline config metadata)
    pipeline_config_source: Optional[str] = None  # e.g., "pipeline:trigger"
    
    # i18n support for label
    label: Optional[dict[str, str]] = None  # e.g., {"en_US": "Name", "zh_Hans": "名称"}
    label_zh: Optional[str] = None  # Chinese label
    label_en: Optional[str] = None  # English label


class WorkflowNode(abc.ABC):
    """Base class for all workflow nodes"""
    
    # Node metadata
    type_name: str = ""
    name: str = ""
    description: str = ""
    category: str = "misc"  # trigger, process, control, action, integration
    icon: str = ""
    
    # Port definitions
    inputs: list[NodePort] = []
    outputs: list[NodePort] = []
    
    # Configuration schema
    config_schema: list[NodeConfig] = []
    
    # Pipeline config reuse
    config_schema_source: Optional[str] = None  # e.g., "pipeline:ai"
    config_stages: list[str] = []  # Specific stages to reuse
    
    def __init__(self, node_id: str, config: dict[str, Any], ap: Optional['app.Application'] = None):
        """Initialize node with ID and configuration"""
        self.node_id = node_id
        self.config = config
        self.ap = ap  # Reference to the application instance for accessing services
    
    @abc.abstractmethod
    async def execute(
        self, 
        inputs: dict[str, Any], 
        context: ExecutionContext
    ) -> dict[str, Any]:
        """
        Execute the node logic.
        
        Args:
            inputs: Input data from connected nodes
            context: Execution context with workflow state
            
        Returns:
            Dictionary of output values
        """
        pass
    
    async def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """
        Validate input data against port definitions.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        for port in self.inputs:
            if port.required and port.name not in inputs:
                errors.append(f"Missing required input: {port.name}")
        return errors
    
    async def validate_config(self) -> list[str]:
        """
        Validate node configuration.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        for cfg in self.config_schema:
            if cfg.required and cfg.name not in self.config:
                errors.append(f"Missing required config: {cfg.name}")
            elif cfg.name in self.config:
                value = self.config[cfg.name]
                # Type validation
                if cfg.type == "integer" and not isinstance(value, int):
                    errors.append(f"Config {cfg.name} must be an integer")
                elif cfg.type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Config {cfg.name} must be a number")
                elif cfg.type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Config {cfg.name} must be a boolean")
                # Range validation
                if cfg.min_value is not None and isinstance(value, (int, float)):
                    if value < cfg.min_value:
                        errors.append(f"Config {cfg.name} must be >= {cfg.min_value}")
                if cfg.max_value is not None and isinstance(value, (int, float)):
                    if value > cfg.max_value:
                        errors.append(f"Config {cfg.name} must be <= {cfg.max_value}")
        return errors
    
    # Type mapping from backend to frontend DynamicFormItemType
    _TYPE_MAP = {
        'string': 'string',
        'integer': 'integer',
        'number': 'float',
        'boolean': 'boolean',
        'select': 'select',
        'json': 'text',
        'textarea': 'text',
        'secret': 'secret',
        'llm-model-selector': 'llm-model-selector',
        'embedding-model-selector': 'embedding-model-selector',
        'rerank-model-selector': 'rerank-model-selector',
        'knowledge-base-selector': 'knowledge-base-selector',
        'knowledge-base-multi-selector': 'knowledge-base-multi-selector',
        'bot-selector': 'bot-selector',
        'tools-selector': 'tools-selector',
        'model-fallback-selector': 'model-fallback-selector',
        'prompt-editor': 'prompt-editor',
    }

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default"""
        return self.config.get(key, default)
    
    @classmethod
    def _config_to_schema_item(cls, cfg: NodeConfig) -> dict[str, Any]:
        """Convert a NodeConfig to frontend-compatible schema item"""
        # Map type to frontend type
        frontend_type = cls._TYPE_MAP.get(cfg.type, 'string')
        
        # Build i18n label from name
        label = {
            'zh_Hans': cfg.name,
            'en_US': cfg.name,
        }
        
        # Build i18n description
        desc = cfg.description or ''
        description = {
            'zh_Hans': desc,
            'en_US': desc,
        }
        
        result = {
            'id': cfg.name,
            'name': cfg.name,
            'type': frontend_type,
            'label': label,
            'description': description,
            'required': cfg.required,
            'default': cfg.default,
        }
        
        # Add placeholder if present
        if cfg.placeholder:
            result['placeholder'] = cfg.placeholder
        
        # Add options if present
        if cfg.options:
            result['options'] = [
                {
                    'name': opt,
                    'label': {
                        'zh_Hans': opt,
                        'en_US': opt,
                    }
                }
                for opt in cfg.options
            ]
        
        # Add show_if if present
        if cfg.show_if:
            result['show_if'] = cfg.show_if
        
        return result

    @classmethod
    def to_schema(cls) -> dict[str, Any]:
        """
        Convert node class to JSON schema for frontend.
        
        Returns:
            Node schema dictionary
        """
        # Build label dict for i18n support
        # Use underscore format to match frontend I18nObject interface
        name_zh = getattr(cls, 'name_zh', None) or cls.name
        name_en = getattr(cls, 'name_en', None) or cls.name
        desc_zh = getattr(cls, 'description_zh', None) or cls.description
        desc_en = getattr(cls, 'description_en', None) or cls.description
        label = {
            'zh_Hans': name_zh,
            'en_US': name_en,
        }
        description = {
            'zh_Hans': desc_zh,
            'en_US': desc_en,
        }
        
        return {
            'type': f'{cls.category}.{cls.type_name}',
            'name': cls.name,
            'label': label,
            'description': description,
            'category': cls.category,
            'icon': cls.icon,
            'inputs': [port.model_dump() for port in cls.inputs],
            'outputs': [port.model_dump() for port in cls.outputs],
            'config_schema': [cls._config_to_schema_item(cfg) for cfg in cls.config_schema],
            'config_schema_source': cls.config_schema_source,
            'config_stages': cls.config_stages,
        }


# Registry for node type decorator
_pending_registrations: list[tuple[str, type[WorkflowNode]]] = []


def workflow_node(type_name: str) -> Callable[[type[WorkflowNode]], type[WorkflowNode]]:
    """
    Decorator to register a workflow node type.
    
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
