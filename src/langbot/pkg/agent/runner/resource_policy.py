"""Project AgentRunner configuration into Host resource policy."""

from __future__ import annotations

import collections.abc
import typing

from .host_models import ResourcePolicy


class ResourcePolicyProjector:
    """Build one generic resource policy for Pipeline and Agent bindings."""

    @classmethod
    def from_runner_config(
        cls,
        runner_config: dict[str, typing.Any] | None,
        *,
        resolved_model_uuids: collections.abc.Iterable[typing.Any] | None = None,
        resolved_tool_names: collections.abc.Iterable[typing.Any] | None = None,
        resolved_tool_sources: typing.Mapping[str, typing.Any] | None = None,
        resolved_kb_uuids: collections.abc.Iterable[typing.Any] | None = None,
        resolved_skill_names: collections.abc.Iterable[typing.Any] | None = None,
    ) -> ResourcePolicy:
        """Project standard resource fields without depending on a runner ID.

        Resolved values are supplied by entry paths that already narrowed the
        available resources, such as Pipeline preprocessing. Independent Agent
        bindings omit them so the Host can resolve an explicit all-tools grant
        against the live tool catalog when the run starts.
        """
        config = runner_config if isinstance(runner_config, dict) else {}
        selected_tool_names = cls.normalize_names(config.get('tools'))
        enable_all_tools = config.get('enable-all-tools', True) is True

        if resolved_tool_names is not None:
            available_tool_names = cls.normalize_names(resolved_tool_names)
            if enable_all_tools:
                allowed_tool_names = available_tool_names
            else:
                selected = set(selected_tool_names)
                allowed_tool_names = [name for name in available_tool_names if name in selected]
            allow_all_tools = False
        elif enable_all_tools:
            allowed_tool_names = None
            allow_all_tools = True
        else:
            allowed_tool_names = selected_tool_names
            allow_all_tools = False

        allowed_tool_sources = cls.normalize_tool_sources(resolved_tool_sources)
        if allowed_tool_sources is not None:
            allowed = set(allowed_tool_names or [])
            allowed_tool_sources = {name: ref for name, ref in allowed_tool_sources.items() if name in allowed}

        if resolved_kb_uuids is not None:
            allowed_kb_uuids = cls.normalize_names(resolved_kb_uuids)
        elif 'knowledge-bases' in config:
            allowed_kb_uuids = cls.normalize_names(config.get('knowledge-bases'))
        else:
            allowed_kb_uuids = None

        return ResourcePolicy(
            allowed_model_uuids=cls.normalize_optional_names(resolved_model_uuids),
            allowed_tool_names=allowed_tool_names,
            allowed_tool_sources=allowed_tool_sources,
            allow_all_tools=allow_all_tools,
            allowed_kb_uuids=allowed_kb_uuids,
            allowed_skill_names=cls.normalize_optional_names(resolved_skill_names),
        )

    @staticmethod
    def normalize_names(values: typing.Any) -> list[str]:
        """Return unique, non-empty string identifiers in source order."""
        if not isinstance(values, collections.abc.Iterable) or isinstance(values, (str, bytes, dict)):
            return []

        names: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value or value in seen:
                continue
            seen.add(value)
            names.append(value)
        return names

    @classmethod
    def normalize_optional_names(
        cls,
        values: collections.abc.Iterable[typing.Any] | None,
    ) -> list[str] | None:
        if values is None:
            return None
        return cls.normalize_names(values)

    @classmethod
    def extract_tool_names(cls, tools: collections.abc.Iterable[typing.Any] | None) -> list[str]:
        """Extract tool identifiers from dictionary and SDK object shapes."""
        if tools is None:
            return []

        names: list[str] = []
        for tool in tools:
            name = tool.get('name') if isinstance(tool, dict) else getattr(tool, 'name', None)
            if isinstance(name, str):
                names.append(name)
        return cls.normalize_names(names)

    @staticmethod
    def normalize_tool_sources(
        values: typing.Mapping[str, typing.Any] | None,
    ) -> dict[str, dict[str, str | None]] | None:
        if values is None:
            return None

        normalized: dict[str, dict[str, str | None]] = {}
        for name, value in values.items():
            if not isinstance(name, str) or not name or not isinstance(value, collections.abc.Mapping):
                continue
            source = value.get('source')
            if not isinstance(source, str) or not source:
                continue
            source_id = value.get('source_id')
            normalized[name] = {
                'source': source,
                'source_id': source_id if isinstance(source_id, str) and source_id else None,
            }
        return normalized

    @classmethod
    def filter_tools(
        cls,
        tools: collections.abc.Iterable[typing.Any],
        policy: ResourcePolicy,
    ) -> list[typing.Any]:
        """Apply a projected policy to an already scoped tool collection."""
        tool_list = list(tools)
        if policy.allow_all_tools:
            return tool_list

        allowed_names = set(policy.allowed_tool_names or [])
        return [
            tool
            for tool in tool_list
            if (tool.get('name') if isinstance(tool, dict) else getattr(tool, 'name', None)) in allowed_names
        ]
