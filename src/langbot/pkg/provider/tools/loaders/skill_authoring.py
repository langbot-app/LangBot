from __future__ import annotations

import os
import typing

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from .. import loader
from .availability import is_box_backend_available

# Align with Claude Code's Skill tool design:
# - activate: Activate a skill via Tool Call, returns SKILL.md content
# - register_skill: Register a skill from sandbox directory to data/skills/
# - This protects KV Cache and follows industry standard

ACTIVATE_SKILL_TOOL_NAME = 'activate'
REGISTER_SKILL_TOOL_NAME = 'register_skill'

SKILL_TOOL_NAMES = {
    ACTIVATE_SKILL_TOOL_NAME,
    REGISTER_SKILL_TOOL_NAME,
}


class SkillToolLoader(loader.ToolLoader):
    """Skill tools aligned with Claude Code's design."""

    def __init__(self, ap):
        super().__init__(ap)
        self._tools: list[resource_tool.LLMTool] = []
        self._sandbox_available: bool = False

    async def initialize(self):
        # Check if sandbox backend is available (same check as native tools)
        self._sandbox_available = await self._check_sandbox_available()
        if self._sandbox_available:
            self._tools = [
                self._build_activate_skill_tool(),
                self._build_register_skill_tool(),
            ]
        else:
            self.ap.logger.info(
                'Skill tools (activate/register_skill) are NOT available. '
                'No sandbox backend (Docker/nsjail/E2B) is ready.'
            )

    async def _check_sandbox_available(self) -> bool:
        """Check if the box backend is truly available (not just the runtime)."""
        return await is_box_backend_available(self.ap)

    async def get_tools(self, bound_plugins: list[str] | None = None) -> list[resource_tool.LLMTool]:
        if not self._is_available():
            return []
        return list(self._tools)

    async def has_tool(self, name: str) -> bool:
        return self._is_available() and name in SKILL_TOOL_NAMES

    def _is_available(self) -> bool:
        """Check if skill tools should be available.

        Skill tools require both a skill manager and a sandbox backend.
        """
        return self._has_skill_manager() and self._sandbox_available

    async def invoke_tool(self, name: str, parameters: dict, query) -> typing.Any:
        if name == ACTIVATE_SKILL_TOOL_NAME:
            return await self._invoke_activate_skill(parameters, query)
        if name == REGISTER_SKILL_TOOL_NAME:
            return await self._invoke_register_skill(parameters)
        raise ValueError(f'Unknown skill tool: {name}')

    async def shutdown(self):
        pass

    def _has_skill_manager(self) -> bool:
        return getattr(self.ap, 'skill_mgr', None) is not None

    async def _invoke_activate_skill(self, parameters: dict, query) -> typing.Any:
        """Activate a skill and return SKILL.md content via Tool Result."""
        skill_name = str(parameters.get('skill_name', '') or '').strip()
        if not skill_name:
            raise ValueError('skill_name is required')

        from . import skill as skill_loader

        skill_data = skill_loader.get_visible_skill(self.ap, query, skill_name)
        if skill_data is None:
            visible_skills = skill_loader.get_visible_skills(self.ap, query)
            available_names = ', '.join(sorted(visible_skills.keys())) or 'none'
            raise ValueError(f'Skill "{skill_name}" not found. Available skills: {available_names}')

        # Register activated skill for sandbox mount path resolution
        skill_loader.register_activated_skill(query, skill_data)
        await skill_loader.persist_activated_skill(self.ap, query, skill_name)

        # Return SKILL.md content as Tool Result (injects into context)
        instructions = skill_data.get('instructions', '')
        package_root = skill_data.get('package_root', '')
        mount_path = skill_loader.get_virtual_skill_mount_path(skill_name)

        # Build Tool Result content
        result_content = f'<command-message>The "{skill_name}" skill is activated</command-message>\n'
        result_content += '<skill-activation>\n'
        result_content += f'<skill-name>{skill_name}</skill-name>\n'
        result_content += f'<mount-path>{mount_path}</mount-path>\n'
        result_content += f'<package-root>{package_root}</package-root>\n'
        result_content += f'\n## Instructions\n{instructions}\n'
        result_content += '\n## Runtime Context\n'
        result_content += f'The skill package is mounted at {mount_path}. Use the standard tools to interact with it:\n'
        result_content += f'- Use `read` to inspect files under {mount_path}\n'
        result_content += f'- Use `exec` with workdir set to {mount_path} to run commands in that package\n'
        result_content += '- Use `write` and `edit` on that path when the instructions require updating files\n'
        result_content += '</skill-activation>\n'

        return {
            'activated': True,
            'skill_name': skill_name,
            'mount_path': mount_path,
            'content': result_content,
        }

    async def _invoke_register_skill(self, parameters: dict) -> typing.Any:
        """Register a skill from sandbox directory to data/skills/."""
        sandbox_path = str(parameters.get('path', '') or '').strip()
        if not sandbox_path:
            raise ValueError('path is required')

        # Resolve sandbox path to host path
        host_path = self._resolve_workspace_directory(sandbox_path)

        # Get or create skill service
        skill_service = getattr(self.ap, 'skill_service', None)
        if skill_service is None:
            raise ValueError('Skill service not available')

        # Scan and register the skill
        scanned = await skill_service.scan_directory_async(host_path)

        # Override name if provided
        skill_name = str(parameters.get('name') or scanned['name']).strip()
        if not skill_name:
            raise ValueError('skill name is required')

        # Create the skill
        created = await skill_service.create_skill(
            {
                'name': skill_name,
                'display_name': str(parameters.get('display_name') or scanned.get('display_name', '')).strip(),
                'description': str(parameters.get('description') or scanned.get('description', '')).strip(),
                'instructions': str(parameters.get('instructions') or scanned.get('instructions', '')),
                'package_root': host_path,
            }
        )

        return {
            'registered': True,
            'skill_name': skill_name,
            'source_path': sandbox_path,
            'skill': created,
        }

    def _resolve_workspace_directory(self, sandbox_path: str) -> str:
        """Resolve sandbox path to host filesystem path."""
        box_service = getattr(self.ap, 'box_service', None)
        workspace_root = getattr(box_service, 'default_workspace', None)
        if not workspace_root:
            raise ValueError('No default workspace configured')

        normalized_path = str(sandbox_path).strip() or '/workspace'
        if not normalized_path.startswith('/workspace'):
            raise ValueError('path must be under /workspace')

        relative = normalized_path[len('/workspace') :].lstrip('/')
        host_root = os.path.realpath(workspace_root)
        host_path = os.path.realpath(os.path.join(host_root, relative))

        # Security check: ensure path doesn't escape workspace
        if not (host_path == host_root or host_path.startswith(host_root + os.sep)):
            raise ValueError('path escapes the workspace boundary')

        if getattr(box_service, 'available', False):
            return host_path

        if not os.path.isdir(host_path):
            raise ValueError(f'Directory does not exist: {sandbox_path}')

        return host_path

    def _build_activate_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=ACTIVATE_SKILL_TOOL_NAME,
            human_desc='Activate a skill',
            description='Activate a pipeline-visible skill by name and return its instructions as a tool result.',
            parameters={
                'type': 'object',
                'properties': {
                    'skill_name': {
                        'type': 'string',
                        'description': 'The skill name to activate.',
                    },
                },
                'required': ['skill_name'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )

    def _build_register_skill_tool(self) -> resource_tool.LLMTool:
        return resource_tool.LLMTool(
            name=REGISTER_SKILL_TOOL_NAME,
            human_desc='Register a skill from sandbox',
            description=(
                "Register a skill package from a directory under /workspace into LangBot's skill store. "
                'Use this after creating or preparing a skill in the sandbox with exec/read/write/edit. '
                'The directory must contain a SKILL.md file. '
                'After registration, the skill can be activated with the activate tool.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'path': {
                        'type': 'string',
                        'description': 'Directory path under /workspace containing the skill package (must have SKILL.md)',
                    },
                    'name': {
                        'type': 'string',
                        'description': 'Optional skill name override. Defaults to the name in SKILL.md or directory name.',
                    },
                    'display_name': {
                        'type': 'string',
                        'description': 'Optional display name override.',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Optional description override.',
                    },
                    'instructions': {
                        'type': 'string',
                        'description': 'Optional instructions override.',
                    },
                },
                'required': ['path'],
                'additionalProperties': False,
            },
            func=lambda parameters: parameters,
        )
