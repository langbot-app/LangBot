"""Workflow node metadata loading and validation.

This module makes YAML files under ``templates/metadata/nodes`` the backend
source of truth for workflow node metadata. Python node classes still provide
execution logic, but UI-facing metadata is loaded from YAML.
"""

from __future__ import annotations

import copy
import logging
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

logger = logging.getLogger(__name__)


class MetadataLoadError(Exception):
    """Raised when a workflow node metadata file cannot be loaded."""


class MetadataValidationError(Exception):
    """Raised when workflow node metadata does not match the expected shape."""


class NodeMetadataValidator:
    """Validate workflow node metadata loaded from YAML files.

    The validator is intentionally strict about the structural fields that the
    editor needs, but tolerant of legacy YAML details such as missing top-level
    ``label`` or additional frontend field types.
    """

    REQUIRED_FIELDS = ('name', 'category', 'inputs', 'outputs', 'config')
    VALID_CATEGORIES = {'trigger', 'process', 'control', 'action', 'integration', 'misc'}
    VALID_PORT_TYPES = {'any', 'string', 'number', 'integer', 'boolean', 'object', 'array', 'datetime', 'null'}
    VALID_CONFIG_TYPES = {
        'string',
        'integer',
        'number',
        'float',
        'boolean',
        'select',
        'json',
        'textarea',
        'text',
        'secret',
        'array[string]',
        'file',
        'array[file]',
        'llm-model-selector',
        'embedding-model-selector',
        'rerank-model-selector',
        'pipeline-selector',
        'knowledge-base-selector',
        'knowledge-base-multi-selector',
        'bot-selector',
        'tools-selector',
        'model-fallback-selector',
        'prompt-editor',
        'plugin-selector',
        'webhook-url',
        'embed-code',
        'workflow-selector',
    }

    def validate(self, metadata: dict[str, Any]) -> list[str]:
        """Return validation errors. An empty list means the metadata is valid."""
        errors: list[str] = []

        if not isinstance(metadata, dict):
            return ['metadata root must be a mapping']

        for field in self.REQUIRED_FIELDS:
            if field not in metadata:
                errors.append(f'missing required field: {field}')

        if errors:
            return errors

        name = metadata.get('name')
        if not isinstance(name, str) or not name.strip():
            errors.append('field "name" must be a non-empty string')

        category = metadata.get('category')
        if category not in self.VALID_CATEGORIES:
            errors.append(f'invalid category: {category}')

        errors.extend(self._validate_ports(metadata.get('inputs'), 'inputs'))
        errors.extend(self._validate_ports(metadata.get('outputs'), 'outputs'))
        errors.extend(self._validate_config(metadata.get('config')))

        return errors

    def validate_or_raise(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Validate metadata and raise ``MetadataValidationError`` on failure."""
        errors = self.validate(metadata)
        if errors:
            node_name = metadata.get('name', 'unknown') if isinstance(metadata, dict) else 'unknown'
            raise MetadataValidationError(f'invalid metadata for {node_name}: {errors}')
        return metadata

    def _validate_ports(self, ports: Any, field_name: str) -> list[str]:
        errors: list[str] = []
        if not isinstance(ports, list):
            return [f'{field_name} must be a list']

        seen_names: set[str] = set()
        for index, port in enumerate(ports):
            path = f'{field_name}[{index}]'
            if not isinstance(port, dict):
                errors.append(f'{path} must be a mapping')
                continue

            name = port.get('name')
            if not isinstance(name, str) or not name:
                errors.append(f'{path}.name must be a non-empty string')
                continue

            if name in seen_names:
                errors.append(f'{path}.name duplicates "{name}"')
            seen_names.add(name)

            port_type = port.get('type', 'any')
            if port_type not in self.VALID_PORT_TYPES:
                errors.append(f'{path}.type has unsupported value "{port_type}"')

        return errors

    def _validate_config(self, config: Any) -> list[str]:
        errors: list[str] = []
        if not isinstance(config, list):
            return ['config must be a list']

        seen_names: set[str] = set()
        for index, item in enumerate(config):
            path = f'config[{index}]'
            if not isinstance(item, dict):
                errors.append(f'{path} must be a mapping')
                continue

            name = item.get('name')
            if not isinstance(name, str) or not name:
                errors.append(f'{path}.name must be a non-empty string')
                continue

            if name in seen_names:
                errors.append(f'{path}.name duplicates "{name}"')
            seen_names.add(name)

            item_type = item.get('type', 'string')
            if item_type not in self.VALID_CONFIG_TYPES:
                errors.append(f'{path}.type has unsupported value "{item_type}"')

            min_value = item.get('min_value')
            max_value = item.get('max_value')
            if isinstance(min_value, (int, float)) and isinstance(max_value, (int, float)) and min_value > max_value:
                errors.append(f'{path}.min_value must be <= max_value')

        return errors


class NodeMetadataLoader:
    """Load and cache workflow node metadata from YAML files."""

    def __init__(self, validator: Optional[NodeMetadataValidator] = None) -> None:
        self._validator = validator or NodeMetadataValidator()
        self._metadata: dict[str, dict[str, Any]] = {}
        self._sources: dict[str, str] = {}
        self._load_errors: list[dict[str, str]] = []

    async def load_core_metadata(self, resource_dir: str = 'metadata/nodes') -> int:
        """Load all core node metadata from the ``langbot.templates`` package."""
        return await self.load_package_directory('langbot.templates', resource_dir, source='core')

    async def load_package_directory(self, package: str, resource_dir: str, source: str = 'core') -> int:
        """Load YAML files from a package resource directory."""
        try:
            root = resources.files(package).joinpath(resource_dir)
            yaml_files = sorted(
                (item for item in root.iterdir() if item.is_file() and item.name.endswith(('.yaml', '.yml'))),
                key=lambda item: item.name,
            )
        except Exception as exc:
            raise MetadataLoadError(f'failed to scan package directory {package}:{resource_dir}: {exc}') from exc

        return self._load_files(yaml_files, source=source)

    async def load_directory(self, directory: str | Path, source: str) -> int:
        """Load YAML files from an external filesystem directory, e.g. a plugin."""
        directory_path = Path(directory)
        if not directory_path.exists():
            logger.warning('Workflow metadata directory does not exist: %s', directory_path)
            return 0
        if not directory_path.is_dir():
            raise MetadataLoadError(f'workflow metadata path is not a directory: {directory_path}')

        yaml_files = sorted(directory_path.glob('*.yml')) + sorted(directory_path.glob('*.yaml'))
        return self._load_files(yaml_files, source=source)

    def get_metadata(self, node_type: str) -> Optional[dict[str, Any]]:
        """Return metadata by full type or short node name."""
        if node_type in self._metadata:
            return copy.deepcopy(self._metadata[node_type])

        short_name = node_type.split('.')[-1]
        for registered_type, metadata in self._metadata.items():
            if registered_type.split('.')[-1] == short_name or metadata.get('name') == short_name:
                return copy.deepcopy(metadata)

        return None

    def get_all_metadata(self) -> dict[str, dict[str, Any]]:
        """Return a deep copy of all loaded metadata keyed by canonical node type."""
        return copy.deepcopy(self._metadata)

    def get_load_errors(self) -> list[dict[str, str]]:
        """Return metadata files that failed to load or validate."""
        return copy.deepcopy(self._load_errors)

    def clear(self) -> None:
        """Clear all cached metadata and errors."""
        self._metadata.clear()
        self._sources.clear()
        self._load_errors.clear()

    def _load_files(self, yaml_files: Iterable[Any], source: str) -> int:
        count = 0
        for yaml_file in yaml_files:
            file_name = getattr(yaml_file, 'name', str(yaml_file))
            try:
                metadata = self._load_yaml(yaml_file)
                self._validator.validate_or_raise(metadata)
                node_type = build_node_type(metadata)

                if node_type in self._metadata:
                    existing_source = self._sources.get(node_type, 'unknown')
                    if existing_source == 'core' and source != 'core':
                        raise MetadataLoadError(
                            f'plugin source "{source}" attempted to override core node "{node_type}"'
                        )
                    logger.warning(
                        'Workflow node metadata %s from %s overrides previous source %s',
                        node_type,
                        source,
                        existing_source,
                    )

                cached_metadata = copy.deepcopy(metadata)
                cached_metadata['_source'] = source
                cached_metadata['_file'] = file_name
                self._metadata[node_type] = cached_metadata
                self._sources[node_type] = source
                count += 1
            except Exception as exc:
                self._load_errors.append({'file': file_name, 'source': source, 'error': str(exc)})
                logger.error('Failed to load workflow node metadata %s: %s', file_name, exc)

        return count

    def _load_yaml(self, yaml_file: Any) -> dict[str, Any]:
        try:
            if hasattr(yaml_file, 'open'):
                with yaml_file.open('r', encoding='utf-8') as file:
                    data = yaml.load(file, Loader=yaml.FullLoader)
            else:
                with open(yaml_file, 'r', encoding='utf-8') as file:
                    data = yaml.load(file, Loader=yaml.FullLoader)
        except Exception as exc:
            raise MetadataLoadError(f'failed to parse YAML: {exc}') from exc

        if not isinstance(data, dict):
            raise MetadataLoadError('YAML root must be a mapping')
        return data


def build_node_type(metadata: dict[str, Any]) -> str:
    """Build canonical ``category.name`` node type from metadata."""
    category = metadata.get('category') or 'misc'
    name = metadata.get('name') or ''
    return f'{category}.{name}'
