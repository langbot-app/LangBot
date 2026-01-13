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
                skill_type = quart.request.args.get('type')
                is_enabled = quart.request.args.get('is_enabled')
                tags = quart.request.args.getlist('tags')

                skills = await self.ap.skill_service.list_skills(
                    skill_type=skill_type,
                    is_enabled=is_enabled.lower() == 'true' if is_enabled else None,
                    tags=tags if tags else None,
                )

                return self.success(data={'skills': skills})

            elif quart.request.method == 'POST':
                data = await quart.request.json

                # Validate required fields
                required_fields = ['name', 'description', 'instructions']
                for field in required_fields:
                    if field not in data or not data[field]:
                        return self.http_status(400, -1, f'Missing required field: {field}')

                # Validate name format
                if not data['name'].replace('-', '').replace('_', '').isalnum():
                    return self.http_status(
                        400, -1, 'Skill name can only contain letters, numbers, hyphens and underscores'
                    )

                if len(data['name']) > 64:
                    return self.http_status(400, -1, 'Skill name cannot exceed 64 characters')

                if len(data['description']) > 1024:
                    return self.http_status(400, -1, 'Skill description cannot exceed 1024 characters')

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

                # Validate name if provided
                if 'name' in data:
                    if not data['name'].replace('-', '').replace('_', '').isalnum():
                        return self.http_status(
                            400, -1, 'Skill name can only contain letters, numbers, hyphens and underscores'
                        )
                    if len(data['name']) > 64:
                        return self.http_status(400, -1, 'Skill name cannot exceed 64 characters')

                if 'description' in data and len(data['description']) > 1024:
                    return self.http_status(400, -1, 'Skill description cannot exceed 1024 characters')

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
            """Preview resolved skill instructions with sub-skills expanded"""
            skill = await self.ap.skill_service.get_skill(skill_uuid)
            if not skill:
                return self.http_status(404, -1, 'Skill not found')

            resolved = self.ap.skill_mgr.get_skill_with_dependencies(skill['name'])
            if not resolved:
                return self.http_status(404, -1, 'Skill not found in manager')

            return self.success(
                data={
                    'skill': skill,
                    'resolved_instructions': resolved['resolved_instructions'],
                    'all_tools': resolved['all_tools'],
                    'all_kbs': resolved['all_kbs'],
                }
            )

        # ========== Pipeline Binding Endpoints ==========

        @self.route(
            '/pipelines/<pipeline_uuid>', methods=['GET', 'PUT'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def get_or_update_pipeline_skills(pipeline_uuid: str) -> quart.Response:
            """Get or update skills bound to a pipeline"""
            if quart.request.method == 'GET':
                skills = await self.ap.skill_service.get_pipeline_skills(pipeline_uuid)
                return self.success(data={'skills': skills})

            elif quart.request.method == 'PUT':
                data = await quart.request.json
                skill_bindings = data.get('skills', [])

                # Validate bindings format
                for binding in skill_bindings:
                    if 'skill_uuid' not in binding:
                        return self.http_status(400, -1, 'Each binding must have skill_uuid')

                skills = await self.ap.skill_service.update_pipeline_skill_bindings(pipeline_uuid, skill_bindings)
                return self.success(data={'skills': skills})

        @self.route(
            '/pipelines/<pipeline_uuid>/bind/<skill_uuid>', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY
        )
        async def bind_skill_to_pipeline(pipeline_uuid: str, skill_uuid: str) -> quart.Response:
            """Bind a skill to a pipeline"""
            data = await quart.request.json if quart.request.content_length else {}
            priority = data.get('priority', 0)

            binding = await self.ap.skill_service.bind_skill_to_pipeline(skill_uuid, pipeline_uuid, priority)
            return self.success(data={'binding': binding})

        @self.route(
            '/pipelines/<pipeline_uuid>/unbind/<skill_uuid>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def unbind_skill_from_pipeline(pipeline_uuid: str, skill_uuid: str) -> quart.Response:
            """Unbind a skill from a pipeline"""
            await self.ap.skill_service.unbind_skill_from_pipeline(skill_uuid, pipeline_uuid)
            return self.success()

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
