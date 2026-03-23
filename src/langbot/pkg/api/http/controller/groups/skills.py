from __future__ import annotations

import quart

from .. import group


@group.group_class('skills', '/api/v1/skills')
class SkillsRouterGroup(group.RouterGroup):
    """Skills management API endpoints"""

    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def list_or_create_skills() -> quart.Response:
            """List all skills or create a new skill"""
            if quart.request.method == 'GET':
                is_enabled = quart.request.args.get('is_enabled')

                skills = await self.ap.skill_service.list_skills(
                    is_enabled=is_enabled.lower() == 'true' if is_enabled else None,
                )

                return self.success(data={'skills': skills})

            elif quart.request.method == 'POST':
                data = await quart.request.json

                # name is the only required DB field
                if 'name' not in data or not data['name']:
                    return self.http_status(400, -1, 'Missing required field: name')

                # Validate name format
                if not data['name'].replace('-', '').replace('_', '').isalnum():
                    return self.http_status(
                        400, -1, 'Skill name can only contain letters, numbers, hyphens and underscores'
                    )

                if len(data['name']) > 64:
                    return self.http_status(400, -1, 'Skill name cannot exceed 64 characters')

                try:
                    skill = await self.ap.skill_service.create_skill(data)
                    return self.success(data={'skill': skill})
                except ValueError as e:
                    return self.http_status(400, -1, str(e))

        @self.route('/<skill_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def get_update_delete_skill(skill_uuid: str) -> quart.Response:
            """Get, update or delete a skill"""
            if quart.request.method == 'GET':
                skill = await self.ap.skill_service.get_skill(skill_uuid)
                if not skill:
                    return self.http_status(404, -1, 'Skill not found')
                return self.success(data={'skill': skill})

            elif quart.request.method == 'PUT':
                data = await quart.request.json

                if 'name' in data:
                    if not data['name'].replace('-', '').replace('_', '').isalnum():
                        return self.http_status(
                            400, -1, 'Skill name can only contain letters, numbers, hyphens and underscores'
                        )
                    if len(data['name']) > 64:
                        return self.http_status(400, -1, 'Skill name cannot exceed 64 characters')

                try:
                    skill = await self.ap.skill_service.update_skill(skill_uuid, data)
                    return self.success(data={'skill': skill})
                except ValueError as e:
                    return self.http_status(400, -1, str(e))

            elif quart.request.method == 'DELETE':
                try:
                    await self.ap.skill_service.delete_skill(skill_uuid)
                    return self.success()
                except ValueError as e:
                    return self.http_status(400, -1, str(e))

        @self.route('/<skill_uuid>/toggle', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def toggle_skill(skill_uuid: str) -> quart.Response:
            """Enable or disable a skill"""
            data = await quart.request.json
            is_enabled = data.get('is_enabled', True)

            try:
                skill = await self.ap.skill_service.toggle_skill(skill_uuid, is_enabled)
                return self.success(data={'skill': skill})
            except ValueError as e:
                return self.http_status(400, -1, str(e))

        @self.route('/<skill_uuid>/preview', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def preview_skill(skill_uuid: str) -> quart.Response:
            """Preview skill instructions"""
            skill = await self.ap.skill_service.get_skill(skill_uuid)
            if not skill:
                return self.http_status(404, -1, 'Skill not found')

            runtime_data = self.ap.skill_mgr.get_skill_runtime_data(skill['name'])
            if not runtime_data:
                return self.http_status(404, -1, 'Skill not found in manager')

            return self.success(
                data={
                    'instructions': runtime_data['instructions'],
                }
            )

        # ========== Skill Index Endpoint ==========

        @self.route('/index', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def get_skill_index() -> quart.Response:
            """Get the skill index that would be injected into system prompt"""
            pipeline_uuid = quart.request.args.get('pipeline_uuid')
            bound_skills = quart.request.args.getlist('bound_skills')

            skill_index = self.ap.skill_mgr.get_skill_index(
                pipeline_uuid=pipeline_uuid, bound_skills=bound_skills if bound_skills else None
            )

            return self.success(data={'index': skill_index})

        # ========== Install Endpoints ==========

        @self.route('/install/github', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def install_skill_from_github() -> quart.Response:
            """Install a skill from a GitHub release asset (zip)"""
            data = await quart.request.json

            required_fields = ['asset_url', 'owner', 'repo', 'release_tag']
            for field in required_fields:
                if field not in data or not data[field]:
                    return self.http_status(400, -1, f'Missing required field: {field}')

            try:
                skill = await self.ap.skill_service.install_from_github(data)
                return self.success(data={'skill': skill})
            except ValueError as e:
                return self.http_status(400, -1, str(e))
            except Exception as e:
                return self.http_status(500, -1, f'Failed to install skill: {e}')

        # ========== Scan / Import Endpoint ==========

        @self.route('/scan', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def scan_skill_directory() -> quart.Response:
            """Scan a local directory for skill metadata (YAML frontmatter in SKILL.md)"""
            path = quart.request.args.get('path', '').strip()
            if not path:
                return self.http_status(400, -1, 'Missing required parameter: path')

            try:
                result = self.ap.skill_service.scan_directory(path)
                return self.success(data=result)
            except ValueError as e:
                return self.http_status(400, -1, str(e))
