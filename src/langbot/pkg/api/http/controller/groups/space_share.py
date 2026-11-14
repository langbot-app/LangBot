from __future__ import annotations

import quart

from ...authz import Permission
from ...context import RequestContext
from ...service import space_share
from ...service.space import SpaceAPIError
from .. import group


@group.group_class('space_share', '/api/v1/space-share')
class SpaceShareRouterGroup(group.RouterGroup):
    """Share Skills, remote MCP servers and prompts to LangBot Space, and use
    the Space prompt library from Pipeline / Agent configuration (LANG-439).

    Prompt library reads are public on Space; favorites belong to the LangBot
    Account bound to this instance (requesting member first, then the
    Workspace owner) and are only available when one is bound.
    """

    def _fail(self, exc: Exception):
        if isinstance(exc, space_share.ShareError):
            body = {'code': -1, 'msg': str(exc), 'data': {'findings': exc.findings} if exc.findings else None}
            return quart.jsonify(body), exc.status
        if isinstance(exc, SpaceAPIError):
            status = exc.status if 400 <= exc.status < 500 else 502
            return self.http_status(status, -1, str(exc))
        raise exc

    async def _body(self) -> dict:
        data = await quart.request.get_json(silent=True)
        if not isinstance(data, dict):
            raise space_share.ShareError('invalid request body')
        return data

    async def initialize(self) -> None:
        @self.route(
            '/context',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=await space_share.share_context(self.ap, request_context))

        # ---------------- prompt library ----------------
        @self.route(
            '/prompts/library',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            args = quart.request.args
            params = {k: args.get(k) for k in ('kind', 'q', 'language', 'sort', 'page', 'page_size', 'tags')}
            try:
                data = await self.ap.space_service.space_api('GET', '/api/v1/marketplace/prompts', params=params)
            except Exception as exc:
                return self._fail(exc)
            return self.success(data=data)

        @self.route(
            '/prompts/library/<author>/<name>/use',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(author: str, name: str, request_context: RequestContext) -> str:
            try:
                await self.ap.space_service.space_api('POST', f'/api/v1/marketplace/prompts/{author}/{name}/use')
            except Exception as exc:
                return self._fail(exc)
            return self.success(data={'ok': True})

        @self.route(
            '/prompts/favorites',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            token = await space_share.resolve_space_access_token(self.ap, request_context)
            if not token:
                return self.success(data={'available': False, 'prompts': [], 'prompt_ids': []})
            try:
                data = await self.ap.space_service.space_api(
                    'GET',
                    '/api/v1/marketplace/prompts/favorites',
                    access_token=token,
                    params={'kind': quart.request.args.get('kind')},
                )
            except Exception as exc:
                return self._fail(exc)
            return self.success(data={'available': True, **(data or {})})

        @self.route(
            '/prompts/favorites/<author>/<name>',
            methods=['PUT', 'DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(author: str, name: str, request_context: RequestContext) -> str:
            token = await space_share.resolve_space_access_token(self.ap, request_context)
            if not token:
                return self.http_status(400, -1, 'Bind a LangBot Account to favorite prompts')
            try:
                data = await self.ap.space_service.space_api(
                    quart.request.method,
                    f'/api/v1/marketplace/prompts/{author}/{name}/favorite',
                    access_token=token,
                )
            except Exception as exc:
                return self._fail(exc)
            return self.success(data=data)

        # ---------------- sharing ----------------
        @self.route(
            '/prompts/preview',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            try:
                payload, findings = space_share.build_prompt_payload(await self._body())
            except Exception as exc:
                return self._fail(exc)
            return self.success(data={'payload': payload, 'findings': findings})

        @self.route(
            '/prompts',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            try:
                data = await self._body()
                payload, findings = space_share.build_prompt_payload(data)
                blocking = [f for f in findings if f['severity'] == 'block']
                if blocking:
                    raise space_share.ShareError('Remove credentials from the prompt before sharing', findings=blocking)
                if any(f['severity'] == 'warn' for f in findings) and data.get('acknowledge_warnings') is not True:
                    raise space_share.ShareError(
                        'The prompt contains personal or internal data; confirm before sharing',
                        status=409,
                        findings=findings,
                    )
                meta = space_share.validate_share_metadata(data)
                token, _slug = await space_share.require_creator_token(self.ap, request_context)
                result = await self.ap.space_service.submit_content(
                    token,
                    'prompt',
                    {**meta, 'payload': payload, 'source_client': f'LangBot {self.ap.ver_mgr.get_current_version()}'},
                )
            except Exception as exc:
                return self._fail(exc)
            quart.g.operation_log_resource_id = f'prompt:{meta["name"]}'
            return self.success(data=result)

        @self.route(
            '/skills/<skill_name>/preview',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(skill_name: str, request_context: RequestContext) -> str:
            try:
                package = await self.ap.skill_service.get_skill_package(request_context, skill_name)
                info = space_share.inspect_skill_zip(package['content'])
            except space_share.ShareError as exc:
                return self._fail(exc)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={**info, 'size': len(package['content']), 'revision': package.get('revision')})

        @self.route(
            '/skills/<skill_name>',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(skill_name: str, request_context: RequestContext) -> str:
            try:
                data = await self._body()
                meta = space_share.validate_share_metadata(data)
                package = await self.ap.skill_service.get_skill_package(request_context, skill_name)
                info = space_share.inspect_skill_zip(package['content'])
                blocking = [f for f in info['findings'] if f['severity'] == 'block']
                if blocking:
                    raise space_share.ShareError(
                        'Remove credentials from the skill files before sharing', findings=blocking
                    )
                token, _slug = await space_share.require_creator_token(self.ap, request_context)
                result = await self.ap.space_service.submit_content(
                    token,
                    'skill',
                    {**meta, 'source_client': f'LangBot {self.ap.ver_mgr.get_current_version()}'},
                    file_bytes=package['content'],
                    filename=f'{skill_name}.zip',
                )
            except space_share.ShareError as exc:
                return self._fail(exc)
            except SpaceAPIError as exc:
                return self._fail(exc)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            quart.g.operation_log_resource_id = f'skill:{skill_name}'
            return self.success(data=result)

        async def _mcp_payload(server_name: str, request_context: RequestContext, overrides: dict | None) -> dict:
            execution_context = await self.ap.mcp_service._execution_context(request_context)
            raw = await self.ap.mcp_service._get_mcp_server_by_name_raw(execution_context, server_name)
            if raw is None:
                raise space_share.ShareError('MCP server not found', status=404)
            runtime_info = await self.ap.mcp_service.get_runtime_info(request_context, server_name)
            if not runtime_info or runtime_info.get('status') != 'connected':
                raise space_share.ShareError(
                    'Connect the MCP server successfully before sharing it, so its tool list can be published'
                )
            return space_share.sanitize_mcp_server(raw, runtime_info, overrides)

        @self.route(
            '/mcp/<path:server_name>/preview',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(server_name: str, request_context: RequestContext) -> str:
            try:
                data = await quart.request.get_json(silent=True) or {}
                result = await _mcp_payload(server_name, request_context, data.get('overrides'))
            except Exception as exc:
                return self._fail(exc)
            return self.success(data=result)

        @self.route(
            '/mcp/<path:server_name>',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(server_name: str, request_context: RequestContext) -> str:
            try:
                data = await self._body()
                meta = space_share.validate_share_metadata(data)
                sanitized = await _mcp_payload(server_name, request_context, data.get('overrides'))
                token, _slug = await space_share.require_creator_token(self.ap, request_context)
                result = await self.ap.space_service.submit_content(
                    token,
                    'mcp',
                    {
                        **meta,
                        'payload': sanitized['payload'],
                        'source_client': f'LangBot {self.ap.ver_mgr.get_current_version()}',
                    },
                )
            except Exception as exc:
                return self._fail(exc)
            quart.g.operation_log_resource_id = f'mcp:{server_name}'
            return self.success(data=result)

        @self.route(
            '/items',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            """Items the bound LangBot Account already published, so the share
            dialog can publish a new version of one of them."""
            token = await space_share.resolve_space_access_token(self.ap, request_context)
            if not token:
                return self.success(data={'available': False, 'items': []})
            item_type = quart.request.args.get('type')
            if item_type not in (None, '', 'prompt', 'skill', 'mcp'):
                return self.http_status(400, -1, 'type must be prompt, skill or mcp')
            try:
                data = await self.ap.space_service.space_api(
                    'GET',
                    '/api/v1/marketplace/content-items/mine',
                    access_token=token,
                    params={'type': item_type or None},
                )
            except Exception as exc:
                return self._fail(exc)
            return self.success(data={'available': True, 'items': (data or {}).get('items') or []})

        @self.route(
            '/submissions',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            token = await space_share.resolve_space_access_token(self.ap, request_context)
            if not token:
                return self.success(data={'available': False, 'submissions': []})
            try:
                data = await self.ap.space_service.space_api(
                    'GET', '/api/v1/marketplace/content-submissions/mine', access_token=token
                )
            except Exception as exc:
                return self._fail(exc)
            return self.success(data={'available': True, **(data or {})})
