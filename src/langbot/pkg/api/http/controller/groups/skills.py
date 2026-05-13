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

        @self.route('/<skill_name>/files', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def list_skill_files(skill_name: str) -> quart.Response:
            """List files in skill package directory."""
            path = quart.request.args.get('path', '.').strip()
            include_hidden = quart.request.args.get('include_hidden', 'false').lower() == 'true'

            try:
                result = await self.ap.skill_service.list_skill_files(
                    skill_name,
                    path=path,
                    include_hidden=include_hidden,
                )
                return self.success(data=result)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route('/<skill_name>/files/<path:path>', methods=['GET', 'PUT'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def read_or_write_skill_file(skill_name: str, path: str) -> quart.Response:
            """Read or write a file in skill package."""
            if quart.request.method == 'GET':
                try:
                    result = await self.ap.skill_service.read_skill_file(skill_name, path)
                    return self.success(data=result)
                except ValueError as exc:
                    return self.http_status(400, -1, str(exc))

            # PUT - write file
            data = await quart.request.json
            content = data.get('content', '')
            if content is None:
                return self.http_status(400, -1, 'Missing required field: content')

            try:
                result = await self.ap.skill_service.write_skill_file(skill_name, path, content)
                return self.success(data=result)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route('/<skill_name>/preview', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def preview_skill(skill_name: str) -> quart.Response:
            skill = self.ap.skill_mgr.get_skill_by_name(skill_name)
            if not skill:
                return self.http_status(404, -1, 'Skill not found')
            return self.success(data={'instructions': skill.get('instructions', '')})

        @self.route('/install/github', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def install_skill_from_github() -> quart.Response:
            data = await quart.request.json
            required_fields = ['asset_url', 'owner', 'repo', 'release_tag']
            for field in required_fields:
                if field not in data or not data[field]:
                    return self.http_status(400, -1, f'Missing required field: {field}')

            try:
                skill = await self.ap.skill_service.install_from_github(data)
                return self.success(data={'skills': skill})
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            except Exception as exc:
                return self.http_status(500, -1, f'Failed to install skill: {exc}')

        @self.route('/install/github/preview', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def preview_skill_from_github() -> quart.Response:
            data = await quart.request.json
            required_fields = ['asset_url', 'owner', 'repo', 'release_tag']
            for field in required_fields:
                if field not in data or not data[field]:
                    return self.http_status(400, -1, f'Missing required field: {field}')

            try:
                preview = await self.ap.skill_service.preview_install_from_github(data)
                return self.success(data={'skills': preview})
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            except Exception as exc:
                return self.http_status(500, -1, f'Failed to preview skill: {exc}')

        @self.route('/install/upload', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def install_skill_from_upload() -> quart.Response:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')
            form = await quart.request.form

            try:
                skill = await self.ap.skill_service.install_from_zip_upload(
                    file_bytes=file.read(),
                    filename=file.filename or '',
                    source_paths=form.getlist('source_paths'),
                )
                return self.success(data={'skills': skill})
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            except Exception as exc:
                return self.http_status(500, -1, f'Failed to install skill: {exc}')

        @self.route('/install/upload/preview', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def preview_skill_from_upload() -> quart.Response:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')

            try:
                preview = await self.ap.skill_service.preview_install_from_zip_upload(
                    file_bytes=file.read(),
                    filename=file.filename or '',
                )
                return self.success(data={'skills': preview})
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            except Exception as exc:
                return self.http_status(500, -1, f'Failed to preview skill: {exc}')

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
