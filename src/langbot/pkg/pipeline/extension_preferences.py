"""Validation and fail-closed reads for Pipeline extension preferences."""

from __future__ import annotations

import typing


_BOOLEAN_FIELDS = (
    'enable_all_plugins',
    'enable_all_mcp_servers',
    'enable_all_skills',
    'mcp_resource_agent_read_enabled',
)


def _valid_plugin_binding(value: typing.Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get('author'), str)
        and bool(value['author'])
        and isinstance(value.get('name'), str)
        and bool(value['name'])
    )


def _valid_name(value: typing.Any) -> bool:
    return isinstance(value, str) and bool(value)


def normalize_extension_preferences(value: typing.Any) -> dict[str, typing.Any]:
    """Return a safe runtime view of persisted extension preferences.

    Missing fields in a valid object retain the established defaults. A
    malformed root is treated as an empty allowlist with every extension
    capability disabled.
    """
    if not isinstance(value, dict):
        return {
            'enable_all_plugins': False,
            'enable_all_mcp_servers': False,
            'enable_all_skills': False,
            'mcp_resource_agent_read_enabled': False,
            'plugins': [],
            'mcp_servers': [],
            'skills': [],
            'mcp_resources': [],
        }

    normalized = dict(value)
    normalized['enable_all_plugins'] = value.get('enable_all_plugins', True) is True
    normalized['enable_all_mcp_servers'] = value.get('enable_all_mcp_servers', True) is True
    normalized['enable_all_skills'] = value.get('enable_all_skills', True) is True
    normalized['mcp_resource_agent_read_enabled'] = (
        value.get('mcp_resource_agent_read_enabled', True) is True
    )

    plugins = value.get('plugins', [])
    plugins_are_valid = isinstance(plugins, list) and all(
        _valid_plugin_binding(plugin) for plugin in plugins
    )
    normalized['plugins'] = list(plugins) if plugins_are_valid else []
    if not plugins_are_valid:
        normalized['enable_all_plugins'] = False

    mcp_servers = value.get('mcp_servers', [])
    mcp_servers_are_valid = isinstance(mcp_servers, list) and all(
        _valid_name(server) for server in mcp_servers
    )
    normalized['mcp_servers'] = list(mcp_servers) if mcp_servers_are_valid else []
    if not mcp_servers_are_valid:
        normalized['enable_all_mcp_servers'] = False

    skills = value.get('skills', [])
    skills_are_valid = isinstance(skills, list) and all(_valid_name(skill) for skill in skills)
    normalized['skills'] = list(skills) if skills_are_valid else []
    if not skills_are_valid:
        normalized['enable_all_skills'] = False

    mcp_resources = value.get('mcp_resources', [])
    mcp_resources_are_valid = isinstance(mcp_resources, list) and all(
        isinstance(resource, dict) for resource in mcp_resources
    )
    normalized['mcp_resources'] = list(mcp_resources) if mcp_resources_are_valid else []
    if not mcp_resources_are_valid:
        normalized['mcp_resource_agent_read_enabled'] = False
    return normalized


def validate_extension_preferences(
    value: typing.Any,
    *,
    context: str = 'Pipeline extensions_preferences',
    field_aliases: typing.Mapping[str, str] | None = None,
) -> dict[str, typing.Any]:
    """Reject extension preferences that cannot be consumed unambiguously."""
    if not isinstance(value, dict):
        raise ValueError(f'{context} must be an object')

    for field_name in _BOOLEAN_FIELDS:
        if field_name in value and not isinstance(value[field_name], bool):
            raise ValueError(f"{context} field '{field_name}' must be a boolean")

    aliases = field_aliases or {}
    _validate_list_field(
        value,
        'plugins',
        aliases.get('plugins', 'plugins'),
        _valid_plugin_binding,
        'a plugin object with non-empty author and name',
        context,
    )
    _validate_list_field(
        value,
        'mcp_servers',
        aliases.get('mcp_servers', 'mcp_servers'),
        _valid_name,
        'a non-empty string',
        context,
    )
    _validate_list_field(
        value,
        'skills',
        aliases.get('skills', 'skills'),
        _valid_name,
        'a non-empty string',
        context,
    )
    _validate_list_field(
        value,
        'mcp_resources',
        aliases.get('mcp_resources', 'mcp_resources'),
        lambda item: isinstance(item, dict),
        'an object',
        context,
    )
    return value


def _validate_list_field(
    value: dict[str, typing.Any],
    field_name: str,
    field_label: str,
    item_validator: typing.Callable[[typing.Any], bool],
    item_description: str,
    context: str,
) -> None:
    if field_name not in value:
        return
    items = value[field_name]
    if not isinstance(items, list):
        raise ValueError(f"{context} field '{field_label}' must be a list")
    for index, item in enumerate(items):
        if not item_validator(item):
            raise ValueError(
                f"{context} field '{field_label}[{index}]' must be {item_description}"
            )
