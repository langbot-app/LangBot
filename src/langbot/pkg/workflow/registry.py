"""Workflow node type registry."""

from __future__ import annotations

import copy
import logging
from typing import Any, Optional, TYPE_CHECKING

from .metadata import build_node_type
from .node import WorkflowNode

if TYPE_CHECKING:
    from langbot.pkg.discover.engine import ComponentDiscoveryEngine

logger = logging.getLogger(__name__)


class NodeConflictError(Exception):
    """Raised when two workflow node metadata definitions conflict."""


class NodeTypeRegistry:
    """
    Central registry for workflow node types.

    YAML metadata is the UI-facing source of truth. Python node classes are
    registered separately and provide execution logic only.
    """

    _instance: Optional['NodeTypeRegistry'] = None

    def __init__(self):
        self._nodes: dict[str, type[WorkflowNode]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        self._metadata_sources: dict[str, str] = {}
        self._categories: dict[str, list[str]] = {
            'trigger': [],
            'process': [],
            'control': [],
            'action': [],
            'integration': [],
            'misc': [],
        }
        self._conflicts: list[dict[str, str]] = []

    @classmethod
    def instance(cls) -> 'NodeTypeRegistry':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_metadata(self, metadata: dict[str, Any], source: str = 'core') -> bool:
        """Register YAML metadata for a workflow node type.

        Core metadata cannot be overridden by plugin metadata. Plugin-plugin
        conflicts are allowed with a warning so hot-reload/development flows can
        replace plugin definitions.
        """
        node_type = build_node_type(metadata)
        existing_source = self._metadata_sources.get(node_type)

        if existing_source:
            conflict = {'type': node_type, 'existing_source': existing_source, 'new_source': source}
            if existing_source == 'core' and source != 'core':
                self._conflicts.append(conflict)
                logger.error('Plugin source %s attempted to override core workflow node %s', source, node_type)
                return False
            logger.warning(
                'Workflow node metadata %s from %s overrides previous source %s', node_type, source, existing_source
            )

        cached_metadata = copy.deepcopy(metadata)
        cached_metadata['_source'] = source
        self._metadata[node_type] = cached_metadata
        self._metadata_sources[node_type] = source
        self._add_to_category(metadata.get('category', 'misc'), node_type)
        return True

    def register(self, node_type: str, node_class: type[WorkflowNode]):
        """Register a Python workflow node implementation class."""
        canonical_type = self._canonical_type_for_class(node_type, node_class)
        self._nodes[canonical_type] = node_class

        metadata = self.get_metadata(canonical_type)
        if metadata:
            category = metadata.get('category', getattr(node_class, 'category', 'misc'))
        else:
            category = getattr(node_class, 'category', 'misc')
            logger.warning('Workflow node implementation %s has no YAML metadata', canonical_type)

        self._add_to_category(category, canonical_type)

    def unregister(self, node_type: str):
        """Unregister a Python workflow node implementation."""
        canonical_type = self._resolve_registered_node_key(node_type)
        if canonical_type is None:
            return

        node_class = self._nodes[canonical_type]
        metadata = self.get_metadata(canonical_type)
        category = metadata.get('category') if metadata else getattr(node_class, 'category', 'misc')
        self._remove_from_category(category or 'misc', canonical_type)
        del self._nodes[canonical_type]

    def unregister_metadata(self, node_type: str):
        """Unregister YAML metadata for a node type, primarily for plugin unload."""
        canonical_type = self._resolve_metadata_key(node_type)
        if canonical_type is None:
            return

        metadata = self._metadata[canonical_type]
        self._remove_from_category(metadata.get('category', 'misc'), canonical_type)
        del self._metadata[canonical_type]
        self._metadata_sources.pop(canonical_type, None)

    def get(self, node_type: str) -> Optional[type[WorkflowNode]]:
        """Get node class by type. Supports both ``category.name`` and short names."""
        canonical_type = self._resolve_registered_node_key(node_type)
        if canonical_type:
            return self._nodes[canonical_type]
        return None

    def get_metadata(self, node_type: str) -> Optional[dict[str, Any]]:
        """Get YAML metadata by full type or short node name."""
        canonical_type = self._resolve_metadata_key(node_type)
        if canonical_type:
            return copy.deepcopy(self._metadata[canonical_type])
        return None

    def create_instance(
        self, node_type: str, node_id: str, config: dict[str, Any], ap: Optional['app.Application'] = None
    ) -> Optional[WorkflowNode]:
        """Create a node instance. Supports both ``category.name`` and short names."""
        node_class = self.get(node_type)
        if node_class:
            return node_class(node_id, config, ap=ap)
        logger.warning('No workflow node implementation registered for type: %s', node_type)
        return None

    def get_merged_schema(self, node_type: str) -> Optional[dict[str, Any]]:
        """Get frontend schema from YAML metadata.

        Python node classes no longer carry UI metadata. If a node class is
        registered but has no YAML metadata, a minimal schema is generated
        from the class attributes (category, type_name) so it still appears
        in the editor.
        """
        metadata = self.get_metadata(node_type)
        node_class = self.get(node_type)

        if metadata:
            schema = self._metadata_to_schema(metadata)
            if node_class:
                # Supplement pipeline config reuse fields from Python class
                for key in ('config_schema_source', 'config_stages'):
                    if not schema.get(key) and getattr(node_class, key, None):
                        schema[key] = getattr(node_class, key)
            return schema

        if node_class:
            # Fallback: node has Python class but no YAML metadata
            short_name = getattr(node_class, 'type_name', '') or node_type.split('.')[-1]
            category = getattr(node_class, 'category', 'misc')
            return {
                'type': f'{category}.{short_name}',
                'name': short_name,
                'label': self._normalize_i18n(None, self._prettify_name(short_name)),
                'description': self._normalize_i18n(None, ''),
                'category': category,
                'icon': '',
                'color': '',
                'inputs': [],
                'outputs': [],
                'config_schema': [],
                'config_schema_source': getattr(node_class, 'config_schema_source', None),
                'config_stages': getattr(node_class, 'config_stages', []),
                'source': 'python-only',
            }

        return None

    def list_all(self) -> list[dict[str, Any]]:
        """Get all registered node type schemas, including metadata-only nodes."""
        node_types = self._ordered_node_types(set(self._metadata.keys()) | set(self._nodes.keys()))
        return [schema for node_type in node_types if (schema := self.get_merged_schema(node_type)) is not None]

    def list_by_category(self, category: str) -> list[dict[str, Any]]:
        """Get node type schemas by category."""
        if category not in self._categories:
            return []
        return [schema for node_type in self._categories[category] if (schema := self.get_merged_schema(node_type)) is not None]

    def get_categories(self) -> dict[str, list[dict[str, Any]]]:
        """Get all nodes organized by category."""
        return {category: self.list_by_category(category) for category in self._categories.keys()}

    def has_type(self, node_type: str) -> bool:
        """Check whether a node has metadata or an implementation registered."""
        return self.get_metadata(node_type) is not None or self.get(node_type) is not None

    def discover_nodes(self, discover_engine: 'ComponentDiscoveryEngine', nodes_dir: str = 'pkg/workflow/nodes/'):
        """Discover and register workflow nodes from the discovery engine.
        
        This method uses the ComponentDiscoveryEngine to find all WorkflowNode
        subclasses in the specified directory and registers them automatically,
        replacing the old decorator-based registration mechanism.
        
        Args:
            discover_engine: The ComponentDiscoveryEngine instance
            nodes_dir: Directory path to scan for workflow nodes
        """
        node_classes = discover_engine.discover_workflow_nodes(nodes_dir)
        for node_class in node_classes:
            type_name = getattr(node_class, 'type_name', '')
            if type_name:
                self.register(type_name, node_class)
                logger.debug(f'Auto-registered workflow node: {type_name}')
            else:
                logger.warning(f'Workflow node class {node_class.__name__} missing type_name attribute')

    def count(self) -> int:
        """Get total number of node types exposed by metadata or implementation."""
        return len(set(self._metadata.keys()) | set(self._nodes.keys()))

    def metadata_count(self) -> int:
        """Get number of registered YAML metadata definitions."""
        return len(self._metadata)

    def get_conflicts(self) -> list[dict[str, str]]:
        """Return metadata registration conflicts."""
        return copy.deepcopy(self._conflicts)

    def clear(self):
        """Clear all registrations (for testing)."""
        self._nodes.clear()
        self._metadata.clear()
        self._metadata_sources.clear()
        self._conflicts.clear()
        for category in self._categories:
            self._categories[category] = []

    def _canonical_type_for_class(self, node_type: str, node_class: type[WorkflowNode]) -> str:
        short_name = node_type.split('.')[-1]
        metadata_key = self._resolve_metadata_key(node_type) or self._resolve_metadata_key(short_name)
        if metadata_key:
            return metadata_key

        category = getattr(node_class, 'category', 'misc')
        return node_type if '.' in node_type else f'{category}.{short_name}'

    def _resolve_registered_node_key(self, node_type: str) -> Optional[str]:
        if node_type in self._nodes:
            return node_type

        short_name = node_type.split('.')[-1]
        for registered_type, node_class in self._nodes.items():
            if registered_type.split('.')[-1] == short_name or getattr(node_class, 'type_name', None) == short_name:
                return registered_type

        return None

    def _resolve_metadata_key(self, node_type: str) -> Optional[str]:
        if node_type in self._metadata:
            return node_type

        short_name = node_type.split('.')[-1]
        for registered_type, metadata in self._metadata.items():
            if registered_type.split('.')[-1] == short_name or metadata.get('name') == short_name:
                return registered_type

        return None

    def _ordered_node_types(self, node_types: set[str]) -> list[str]:
        ordered: list[str] = []
        for category in self._categories:
            for node_type in self._categories[category]:
                if node_type in node_types and node_type not in ordered:
                    ordered.append(node_type)

        for node_type in sorted(node_types):
            if node_type not in ordered:
                ordered.append(node_type)

        return ordered

    def _add_to_category(self, category: str, node_type: str) -> None:
        if category not in self._categories:
            self._categories[category] = []
        if node_type not in self._categories[category]:
            self._categories[category].append(node_type)

    def _remove_from_category(self, category: str, node_type: str) -> None:
        if category in self._categories and node_type in self._categories[category]:
            self._categories[category].remove(node_type)

    def _metadata_to_schema(self, metadata: dict[str, Any]) -> dict[str, Any]:
        node_type = build_node_type(metadata)
        node_name = metadata.get('name', node_type.split('.')[-1])
        return {
            'type': node_type,
            'name': node_name,
            'label': self._normalize_i18n(metadata.get('label'), self._prettify_name(node_name)),
            'description': self._normalize_i18n(metadata.get('description'), ''),
            'category': metadata.get('category', 'misc'),
            'icon': metadata.get('icon', ''),
            'color': metadata.get('color', ''),
            'inputs': [self._normalize_port_item(item) for item in metadata.get('inputs', [])],
            'outputs': [self._normalize_port_item(item) for item in metadata.get('outputs', [])],
            'config_schema': [self._normalize_config_item(item) for item in metadata.get('config', [])],
            'config_schema_source': metadata.get('config_schema_source'),
            'config_stages': metadata.get('config_stages', []),
            'source': metadata.get('_source', 'core'),
        }

    def _merge_missing_schema_fields(self, yaml_schema: dict[str, Any], python_schema: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(yaml_schema)
        for key in ('config_schema_source', 'config_stages'):
            if not result.get(key) and python_schema.get(key):
                result[key] = python_schema[key]
        return result

    def _normalize_port_item(self, port: dict[str, Any]) -> dict[str, Any]:
        item = copy.deepcopy(port)
        name = item.get('name', '')
        item['label'] = self._normalize_i18n(item.get('label'), self._prettify_name(name))
        item['description'] = self._normalize_i18n(item.get('description'), '')
        item.setdefault('type', 'any')
        item.setdefault('required', True)
        return item

    def _normalize_config_item(self, config: dict[str, Any]) -> dict[str, Any]:
        item = copy.deepcopy(config)
        name = item.get('name', '')
        frontend_type = self._normalize_config_type(item.get('type', 'string'))

        item['id'] = item.get('id') or name
        item['type'] = frontend_type
        item['label'] = self._normalize_i18n(item.get('label'), self._prettify_name(name))
        item['description'] = self._normalize_i18n(item.get('description'), '')
        item['required'] = bool(item.get('required', False))
        item['default'] = item.get('default', self._default_value_for_type(frontend_type))

        if 'options' in item:
            item['options'] = self._normalize_options(item.get('options'), name)

        return item

    def _normalize_options(self, options: Any, field_name: str) -> list[dict[str, Any]]:
        if not isinstance(options, list):
            return []

        normalized: list[dict[str, Any]] = []
        for option in options:
            if isinstance(option, dict):
                option_item = copy.deepcopy(option)
                option_name = option_item.get('name', option_item.get('value', ''))
                option_item['name'] = str(option_name)
                option_item['label'] = self._normalize_i18n(option_item.get('label'), str(option_name))
                normalized.append(option_item)
            else:
                option_name = str(option)
                normalized.append({'name': option_name, 'label': self._normalize_i18n(None, option_name)})

        return normalized

    def _normalize_i18n(self, value: Any, fallback: str) -> dict[str, str]:
        if isinstance(value, dict):
            en_value = (
                value.get('en_US')
                or value.get('en-US')
                or value.get('en')
                or value.get('en_US'.replace('_', '-'))
                or fallback
            )
            zh_value = value.get('zh_Hans') or value.get('zh-Hans') or value.get('zh-CN') or value.get('zh') or en_value
            return {
                'en_US': str(en_value),
                'en': str(en_value),
                'en-US': str(en_value),
                'zh_Hans': str(zh_value),
                'zh-Hans': str(zh_value),
                'zh-CN': str(zh_value),
            }

        if isinstance(value, str) and value:
            return {
                'en_US': value,
                'en': value,
                'en-US': value,
                'zh_Hans': value,
                'zh-Hans': value,
                'zh-CN': value,
            }

        return {
            'en_US': fallback,
            'en': fallback,
            'en-US': fallback,
            'zh_Hans': fallback,
            'zh-Hans': fallback,
            'zh-CN': fallback,
        }

    def _normalize_config_type(self, field_type: str) -> str:
        type_map = {
            'number': 'float',
            'json': 'text',
            'textarea': 'text',
        }
        return type_map.get(field_type, field_type)

    def _default_value_for_type(self, field_type: str) -> Any:
        if field_type == 'boolean':
            return False
        if field_type in {'integer', 'float'}:
            return 0
        if field_type in {'array[string]', 'knowledge-base-multi-selector', 'tools-selector'}:
            return []
        if field_type == 'model-fallback-selector':
            return {'primary': '', 'fallbacks': []}
        if field_type == 'prompt-editor':
            return [{'role': 'system', 'content': ''}]
        return ''

    def _prettify_name(self, name: str) -> str:
        return ' '.join(part.capitalize() for part in str(name).replace('-', '_').split('_') if part)


# Convenience functions for module-level access
def register_node(node_type: str, node_class: type[WorkflowNode]):
    """Register a node type to the global registry."""
    NodeTypeRegistry.instance().register(node_type, node_class)


def get_node_class(node_type: str) -> Optional[type[WorkflowNode]]:
    """Get a node class from the global registry."""
    return NodeTypeRegistry.instance().get(node_type)


def list_node_types() -> list[dict[str, Any]]:
    """List all registered node types."""
    return NodeTypeRegistry.instance().list_all()
