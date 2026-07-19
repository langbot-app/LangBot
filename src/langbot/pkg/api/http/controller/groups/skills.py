from __future__ import annotations

import quart

from langbot_plugin.box.errors import BoxError

from ...authz import Permission
from ...context import RequestContext
from .. import group


@group.group_class('skills', '/api/v1/skills')
class SkillsRouterGroup(group.RouterGroup):
    """Skills management API endpoints."""

    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def list_skills(request_context: RequestContext) -> quart.Response:
            try:
                skills = await self.ap.skill_service.list_skills(request_context)
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'skills': skills})

        @self.route(
            '',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def create_skill(request_context: RequestContext) -> quart.Response:
            data = await quart.request.json
            if 'name' not in data or not data['name']:
                return self.http_status(400, -1, 'Missing required field: name')

            try:
                skill = await self.ap.skill_service.create_skill(request_context, data)
                return self.success(data={'skill': skill})
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<skill_name>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_skill(skill_name: str, request_context: RequestContext) -> quart.Response:
            try:
                skill = await self.ap.skill_service.get_skill(request_context, skill_name)
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))
            if not skill:
                return self.http_status(404, -1, 'Skill not found')
            return self.success(data={'skill': skill})

        @self.route(
            '/<skill_name>',
            methods=['PUT', 'DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def update_delete_skill(skill_name: str, request_context: RequestContext) -> quart.Response:
            if quart.request.method == 'PUT':
                data = await quart.request.json
                try:
                    skill = await self.ap.skill_service.update_skill(request_context, skill_name, data)
                    return self.success(data={'skill': skill})
                except (ValueError, BoxError) as exc:
                    return self.http_status(400, -1, str(exc))

            try:
                await self.ap.skill_service.delete_skill(request_context, skill_name)
                return self.success()
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<skill_name>/files',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def list_skill_files(skill_name: str, request_context: RequestContext) -> quart.Response:
            """List files in skill package directory."""
            path = quart.request.args.get('path', '.').strip()
            include_hidden = quart.request.args.get('include_hidden', 'false').lower() == 'true'

            try:
                result = await self.ap.skill_service.list_skill_files(
                    request_context,
                    skill_name,
                    path=path,
                    include_hidden=include_hidden,
                )
                return self.success(data=result)
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<skill_name>/files/<path:path>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def read_skill_file(skill_name: str, path: str, request_context: RequestContext) -> quart.Response:
            try:
                result = await self.ap.skill_service.read_skill_file(request_context, skill_name, path)
                return self.success(data=result)
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<skill_name>/files/<path:path>',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def write_skill_file(skill_name: str, path: str, request_context: RequestContext) -> quart.Response:
            data = await quart.request.json
            content = data.get('content', '')
            if content is None:
                return self.http_status(400, -1, 'Missing required field: content')

            try:
                result = await self.ap.skill_service.write_skill_file(request_context, skill_name, path, content)
                return self.success(data=result)
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<skill_name>/preview',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def preview_skill(skill_name: str, request_context: RequestContext) -> quart.Response:
            skill = await self.ap.skill_service.get_skill(request_context, skill_name)
            if not skill:
                return self.http_status(404, -1, 'Skill not found')
            return self.success(data={'instructions': skill.get('instructions', '')})

        @self.route(
            '/install/github',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def install_skill_from_github(request_context: RequestContext) -> quart.Response:
            data = await quart.request.json
            required_fields = ['asset_url', 'owner', 'repo']
            for field in required_fields:
                if field not in data or not data[field]:
                    return self.http_status(400, -1, f'Missing required field: {field}')
            asset_url = str(data['asset_url']).strip().lower().split('?', 1)[0].split('#', 1)[0]
            if not asset_url.endswith('skill.md') and not data.get('release_tag'):
                return self.http_status(400, -1, 'Missing required field: release_tag')

            try:
                skill = await self.ap.skill_service.install_from_github(request_context, data)
                return self.success(data={'skills': skill})
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))
            except Exception:
                raise

        @self.route(
            '/install/github/preview',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def preview_skill_from_github(request_context: RequestContext) -> quart.Response:
            data = await quart.request.json
            required_fields = ['asset_url', 'owner', 'repo']
            for field in required_fields:
                if field not in data or not data[field]:
                    return self.http_status(400, -1, f'Missing required field: {field}')
            asset_url = str(data['asset_url']).strip().lower().split('?', 1)[0].split('#', 1)[0]
            if not asset_url.endswith('skill.md') and not data.get('release_tag'):
                return self.http_status(400, -1, 'Missing required field: release_tag')

            try:
                preview = await self.ap.skill_service.preview_install_from_github(request_context, data)
                return self.success(data={'skills': preview})
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))
            except Exception:
                raise

        @self.route(
            '/install/upload',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def install_skill_from_upload(request_context: RequestContext) -> quart.Response:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')
            form = await quart.request.form

            try:
                skill = await self.ap.skill_service.install_from_zip_upload(
                    request_context,
                    file_bytes=file.read(),
                    filename=file.filename or '',
                    source_paths=form.getlist('source_paths'),
                )
                return self.success(data={'skills': skill})
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))
            except Exception:
                raise

        @self.route(
            '/install/upload/preview',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def preview_skill_from_upload(request_context: RequestContext) -> quart.Response:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')

            try:
                preview = await self.ap.skill_service.preview_install_from_zip_upload(
                    request_context,
                    file_bytes=file.read(),
                    filename=file.filename or '',
                )
                return self.success(data={'skills': preview})
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))
            except Exception:
                raise

        @self.route(
            '/scan',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def scan_skill_directory(request_context: RequestContext) -> quart.Response:
            path = quart.request.args.get('path', '').strip()
            if not path:
                return self.http_status(400, -1, 'Missing required parameter: path')

            try:
                result = await self.ap.skill_service.scan_directory_async(request_context, path)
                return self.success(data=result)
            except (ValueError, BoxError) as exc:
                return self.http_status(400, -1, str(exc))
