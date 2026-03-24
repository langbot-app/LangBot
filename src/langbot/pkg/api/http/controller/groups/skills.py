from __future__ import annotations

import quart

from .. import group


@group.group_class('skills', '/api/v1/skills')
class SkillsRouterGroup(group.RouterGroup):
    """Skills management API endpoints."""

    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def list_or_create_skills() -> quart.Response:
            if quart.request.method == 'GET':
                skills = await self.ap.skill_service.list_skills()
                return self.success(data={'skills': skills})

            data = await quart.request.json
            if 'name' not in data or not data['name']:
                return self.http_status(400, -1, 'Missing required field: name')

            try:
                skill = await self.ap.skill_service.create_skill(data)
                return self.success(data={'skill': skill})
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route('/<skill_name>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def get_update_delete_skill(skill_name: str) -> quart.Response:
            if quart.request.method == 'GET':
                skill = await self.ap.skill_service.get_skill(skill_name)
                if not skill:
                    return self.http_status(404, -1, 'Skill not found')
                return self.success(data={'skill': skill})

            if quart.request.method == 'PUT':
                data = await quart.request.json
                try:
                    skill = await self.ap.skill_service.update_skill(skill_name, data)
                    return self.success(data={'skill': skill})
                except ValueError as exc:
                    return self.http_status(400, -1, str(exc))

            try:
                await self.ap.skill_service.delete_skill(skill_name)
                return self.success()
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route('/<skill_name>/preview', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def preview_skill(skill_name: str) -> quart.Response:
            runtime_data = self.ap.skill_mgr.get_skill_runtime_data(skill_name)
            if not runtime_data:
                return self.http_status(404, -1, 'Skill not found')
            return self.success(data={'instructions': runtime_data['instructions']})

        @self.route('/index', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def get_skill_index() -> quart.Response:
            pipeline_uuid = quart.request.args.get('pipeline_uuid')
            bound_skills = quart.request.args.getlist('bound_skills')
            skill_index = self.ap.skill_mgr.get_skill_index(
                pipeline_uuid=pipeline_uuid,
                bound_skills=bound_skills if bound_skills else None,
            )
            return self.success(data={'index': skill_index})

        @self.route('/install/github', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def install_skill_from_github() -> quart.Response:
            data = await quart.request.json
            required_fields = ['asset_url', 'owner', 'repo', 'release_tag']
            for field in required_fields:
                if field not in data or not data[field]:
                    return self.http_status(400, -1, f'Missing required field: {field}')

            try:
                skill = await self.ap.skill_service.install_from_github(data)
                return self.success(data={'skill': skill})
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            except Exception as exc:
                return self.http_status(500, -1, f'Failed to install skill: {exc}')

        @self.route('/scan', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def scan_skill_directory() -> quart.Response:
            path = quart.request.args.get('path', '').strip()
            if not path:
                return self.http_status(400, -1, 'Missing required parameter: path')

            try:
                result = self.ap.skill_service.scan_directory(path)
                return self.success(data=result)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
