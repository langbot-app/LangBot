from __future__ import annotations

import asyncio
import base64
import quart
import os

from ...authz import Permission
from ...context import ExecutionContext, RequestContext
from .....operation_trace import service as settings_service
from .. import group
from .....workspace.errors import WorkspaceNotFoundError
from langbot_plugin.entities.io.errors import ActionCallError


from .....plugin.management import (
    normalize_plugin_asset_path as _normalize_plugin_asset_path,
)


# Resolve the built-in page SDK JS from the langbot_plugin package
_PAGE_SDK_PATH = None
try:
    import langbot_plugin.assets as _assets_pkg

    _candidate = os.path.join(os.path.dirname(_assets_pkg.__file__), 'langbot-page-sdk.js')
    if os.path.exists(_candidate):
        _PAGE_SDK_PATH = _candidate
except Exception:
    pass


def _get_request_origin() -> str:
    """Return the public request origin, respecting reverse-proxy headers."""
    forwarded_proto = quart.request.headers.get('X-Forwarded-Proto', '').split(',')[0].strip()
    forwarded_host = quart.request.headers.get('X-Forwarded-Host', '').split(',')[0].strip()

    scheme = forwarded_proto or quart.request.scheme
    host = forwarded_host or quart.request.host
    return f'{scheme}://{host}'


@group.group_class('plugins', '/api/v1/plugins')
class PluginsRouterGroup(group.RouterGroup):
    async def _require_authenticated_plugin_runtime_context(
        self,
        request_context: RequestContext,
    ) -> ExecutionContext:
        """Fence an authenticated resource request to its injected Workspace."""
        return await self.ap.plugin_connector.require_workspace_context(request_context)

    async def _require_public_plugin_runtime_context(self) -> ExecutionContext:
        """Resolve public assets only for the OSS singleton Workspace.

        Public image and iframe requests cannot carry the WebUI bearer token.
        They therefore remain available for the one-Workspace Core deployment,
        but fail closed instead of guessing a Workspace when multi-Workspace
        policy is active.
        """

        workspace_service = getattr(self.ap, 'workspace_service', None)
        policy = getattr(workspace_service, 'policy', None)
        if workspace_service is None or policy is None or getattr(policy, 'multi_workspace_enabled', False):
            raise WorkspaceNotFoundError('Plugin resource not found')
        binding = await workspace_service.get_local_execution_binding()
        execution_context = ExecutionContext(
            instance_uuid=binding.instance_uuid,
            workspace_uuid=binding.workspace_uuid,
            placement_generation=binding.placement_generation,
        )
        return await self.ap.plugin_connector.require_workspace_context(execution_context)

    async def initialize(self) -> None:
        @self.route('/_sdk/page-sdk.js', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> quart.Response:
            """Serve the built-in LangBot page SDK JavaScript."""
            if _PAGE_SDK_PATH and os.path.exists(_PAGE_SDK_PATH):
                with open(_PAGE_SDK_PATH, 'r') as f:
                    content = f.read()
                return quart.Response(content, mimetype='application/javascript')
            return quart.Response('// SDK not found', status=404, mimetype='application/javascript')

        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=await self.call_application('plugin.list', request_context, {}))

        @self.route(
            '/debug-info',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=await self.call_application('plugin.debug_info', request_context, {}))

        async def _space_access_token_for_workspace(
            request_context: RequestContext,
        ) -> str | None:
            """Resolve the Workspace owner's or requesting account's LangBot Space token, if bound.

            Every step is best-effort: a Space account is optional for the
            underlying LangBot install, so an unavailable identity service must
            not turn the upload page's metadata read into a 500.
            """
            try:
                user_service = getattr(self.ap, 'user_service', None)
                space_service = getattr(self.ap, 'space_service', None)
                if user_service is None or space_service is None:
                    return None
                if request_context.account_uuid:
                    account = await user_service.get_user_by_uuid(request_context.account_uuid)
                    if account and account.account_type == 'space':
                        token = await space_service.get_valid_access_token(account.user)
                        if token:
                            return token
                owner = await user_service.get_workspace_owner(request_context.workspace_uuid)
                if owner is None:
                    return None
                return await space_service.get_valid_access_token(owner.user)
            except Exception:
                return None

        async def _resolve_upload_target(author: str, plugin_name: str) -> dict | None:
            """Resolve a plugin for the upload page, preferring debug connections.

            A plugin shown as "debugging" is not persisted as an installation, so
            it is looked up through the OSS debug bridge first; installed plugins
            remain a fallback so the page also works for local/marketplace ones.
            """
            connector = self.ap.plugin_connector
            for resolver in (
                getattr(connector, 'get_debug_plugin_info', None),
                getattr(connector, 'get_plugin_info', None),
            ):
                if resolver is None:
                    continue
                try:
                    info = await resolver(author, plugin_name)
                except Exception:
                    self.ap.logger.exception('Failed to resolve plugin %s/%s for upload', author, plugin_name)
                    continue
                if info:
                    return info
            return None

        @self.route(
            '/<author>/<plugin_name>/space-upload/config',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> str:
            """Metadata and connection state for the "upload to Space" page."""
            await self._require_authenticated_plugin_runtime_context(request_context)
            plugin = await _resolve_upload_target(author, plugin_name)
            if plugin is None:
                return self.http_status(404, -1, 'plugin not found')

            metadata = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {}) or {}
            access_token = await _space_access_token_for_workspace(request_context)
            space_connected = False
            has_creator_profile = False
            creator_slug = None
            author_matches = False

            if access_token:
                try:
                    space_service = getattr(self.ap, 'space_service', None)
                    if space_service is not None:
                        token_valid, creator_profile = await space_service.get_creator_profile(access_token)
                        if token_valid:
                            space_connected = True
                            if creator_profile and creator_profile.get('slug'):
                                has_creator_profile = True
                                creator_slug = creator_profile['slug']
                                plugin_author = metadata.get('author', author)
                                if plugin_author and creator_slug and plugin_author.lower() == creator_slug.lower():
                                    author_matches = True
                except Exception:
                    self.ap.logger.exception('Failed to retrieve creator profile for space-upload/config')

            return self.success(
                data={
                    'debug': bool(plugin.get('debug')),
                    'metadata': {
                        'author': metadata.get('author', author),
                        'name': metadata.get('name', plugin_name),
                        'label': metadata.get('label'),
                        'description': metadata.get('description'),
                        'version': metadata.get('version'),
                        'repository': metadata.get('repository'),
                        'license': metadata.get('license'),
                    },
                    'space_connected': space_connected,
                    'has_creator_profile': has_creator_profile,
                    'creator_slug': creator_slug,
                    'author_matches': author_matches,
                    'cloud_service_url': self.ap.instance_config.data.get('space', {}).get(
                        'web_url',
                        self.ap.instance_config.data.get('space', {}).get('url', 'https://space.langbot.app'),
                    ),
                }
            )

        @self.route(
            '/<author>/<plugin_name>/space-upload',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> str:
            """Build the debug plugin and publish it to LangBot Space.

            Optionally synchronises the working directory to GitHub first, so the
            published plugin and the repository stay aligned.
            """
            await self._require_authenticated_plugin_runtime_context(request_context)
            try:
                data = await quart.request.get_json(silent=True) or {}
            except Exception:
                data = {}
            if not isinstance(data, dict):
                return self.http_status(400, -1, 'invalid request body')

            overrides = data.get('manifest_overrides') or {}
            if not isinstance(overrides, dict):
                return self.http_status(400, -1, 'manifest_overrides must be an object')

            sync_github = data.get('sync_github') is True
            git_result: dict | None = None

            try:
                package_result = await self.ap.plugin_connector.get_plugin_package(
                    author,
                    plugin_name,
                    manifest_overrides=overrides,
                )
            except Exception as exc:
                self.ap.logger.warning('Building package for %s/%s failed: %s', author, plugin_name, exc)
                message = str(exc)
                if 'build_plugin_package' in message and 'not found' in message.lower():
                    message = (
                        'The debugging plugin process does not support packaging yet. '
                        'Update the LangBot plugin SDK used by `lbp run` and restart it.'
                    )
                return self.http_status(400, -1, message)

            package_bytes = package_result.get('package') or b''
            if not package_bytes:
                return self.http_status(400, -1, 'Failed to build the plugin package')

            if sync_github:
                try:
                    git_result = await self.ap.plugin_connector.git_sync_plugin(
                        author,
                        plugin_name,
                        repo_url=str(data.get('repo_url') or ''),
                        token=str(data.get('token') or ''),
                        branch=str(data.get('branch') or ''),
                        commit_message=str(data.get('commit_message') or ''),
                        manifest_overrides=overrides,
                    )
                except Exception as exc:
                    self.ap.logger.warning('Git sync failed for %s/%s: %s', author, plugin_name, exc)
                    return self.http_status(400, -1, f'Git sync failed: {exc}')

            access_token = await _space_access_token_for_workspace(request_context)
            if not access_token:
                return self.http_status(
                    400,
                    -1,
                    'Please connect a LangBot Space account before uploading plugins',
                )

            space_service = getattr(self.ap, 'space_service', None)
            if space_service is not None:
                token_valid, creator_profile = await space_service.get_creator_profile(access_token)
                if not token_valid:
                    return self.http_status(401, -1, 'Space login session has expired. Please re-authenticate.')
                if not creator_profile or not creator_profile.get('slug'):
                    return self.http_status(
                        400, -1, 'Please set up a creator profile on Space before uploading plugins.'
                    )
                creator_slug = creator_profile.get('slug')
                if author and creator_slug and author.lower() != creator_slug.lower():
                    return self.http_status(
                        400,
                        -1,
                        f"Plugin author '{author}' does not match your Space creator slug '@{creator_slug}'.",
                    )

            try:
                submission = await self.ap.space_service.publish_plugin(
                    access_token,
                    package_bytes,
                    filename=package_result.get('filename') or 'plugin.lbpkg',
                    changelog=str(data.get('changelog') or ''),
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

            quart.g.operation_log_resource_id = f'{author}/{plugin_name}'
            return self.success(
                data={
                    'submission': submission,
                    'git': git_result,
                    'filename': package_result.get('filename', ''),
                }
            )

        @self.route(
            '/<author>/<plugin_name>/space-upload/git-sync',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> str:
            """Synchronise only the debug plugin's working directory to GitHub."""
            await self._require_authenticated_plugin_runtime_context(request_context)
            try:
                data = await quart.request.get_json(silent=True) or {}
            except Exception:
                data = {}
            if not isinstance(data, dict):
                return self.http_status(400, -1, 'invalid request body')

            overrides = data.get('manifest_overrides') or {}
            if not isinstance(overrides, dict):
                return self.http_status(400, -1, 'manifest_overrides must be an object')

            try:
                git_result = await self.ap.plugin_connector.git_sync_plugin(
                    author,
                    plugin_name,
                    repo_url=str(data.get('repo_url') or ''),
                    token=str(data.get('token') or ''),
                    branch=str(data.get('branch') or ''),
                    commit_message=str(data.get('commit_message') or ''),
                    manifest_overrides=overrides,
                )
            except Exception as exc:
                self.ap.logger.warning('Git sync failed for %s/%s: %s', author, plugin_name, exc)
                return self.http_status(400, -1, str(exc))

            return self.success(data={'git': git_result})

        @self.route(
            '/<author>/<plugin_name>/upgrade',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> str:
            return self.success(
                data=await self.call_application(
                    'plugin.upgrade', request_context, {'author': author, 'plugin_name': plugin_name}
                )
            )

        @self.route(
            '/<author>/<plugin_name>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> str:
            try:
                result = await self.call_application(
                    'plugin.get', request_context, {'author': author, 'plugin_name': plugin_name}
                )
            except WorkspaceNotFoundError:
                return self.http_status(404, -1, 'plugin not found')
            return self.success(data=result)

        @self.route(
            '/<author>/<plugin_name>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> str:
            delete_data = quart.request.args.get('delete_data', 'false').lower() == 'true'
            return self.success(
                data=await self.call_application(
                    'plugin.delete',
                    request_context,
                    {
                        'author': author,
                        'plugin_name': plugin_name,
                        'delete_data': delete_data,
                    },
                )
            )

        @self.route(
            '/<author>/<plugin_name>/config',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> quart.Response:
            try:
                result = await self.call_application(
                    'plugin.config.get', request_context, {'author': author, 'plugin_name': plugin_name}
                )
            except WorkspaceNotFoundError:
                return self.http_status(404, -1, 'plugin not found')
            return self.success(data=result)

        @self.route(
            '/<author>/<plugin_name>/config',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> quart.Response:
            try:
                incoming_config = await quart.request.get_json(silent=True)
                result = await self.call_application(
                    'plugin.config.update',
                    request_context,
                    {
                        'author': author,
                        'plugin_name': plugin_name,
                        'config': incoming_config,
                    },
                )
            except WorkspaceNotFoundError:
                return self.http_status(404, -1, 'plugin not found')
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            config_changes = result['changes']
            rule = settings_service.ACTION_RULES_BY_ACTION.get('plugin_config')
            quart.g.operation_log_resource_id = f'{author}/{plugin_name}'
            quart.g.operation_log_changes = config_changes
            if rule is not None and config_changes:
                quart.g.operation_log_summary = settings_service.build_summary(rule, config_changes)
            return self.success(data={})

        @self.route(
            '/<author>/<plugin_name>/readme',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> quart.Response:
            language = quart.request.args.get('language', 'en')
            return self.success(
                data=await self.call_application(
                    'plugin.readme',
                    request_context,
                    {
                        'author': author,
                        'plugin_name': plugin_name,
                        'language': language,
                    },
                )
            )

        @self.route(
            '/<author>/<plugin_name>/logs',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> quart.Response:
            try:
                limit = int(quart.request.args.get('limit', 200))
            except (TypeError, ValueError):
                limit = 200
            level = quart.request.args.get('level') or None
            return self.success(
                data=await self.call_application(
                    'plugin.logs',
                    request_context,
                    {
                        'author': author,
                        'plugin_name': plugin_name,
                        'limit': limit,
                        'level': level,
                    },
                )
            )

        @self.route(
            '/<author>/<plugin_name>/authenticated-icon',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(
            author: str,
            plugin_name: str,
            request_context: RequestContext,
        ) -> quart.Response:
            try:
                result = await self.call_application(
                    'plugin.icon', request_context, {'author': author, 'plugin_name': plugin_name}
                )
            except WorkspaceNotFoundError:
                return quart.Response('Icon not found', status=404)
            return quart.Response(result['content'], mimetype=result['mime_type'])

        @self.route(
            '/<author>/<plugin_name>/authenticated-assets/<path:filepath>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(
            author: str,
            plugin_name: str,
            filepath: str,
            request_context: RequestContext,
        ) -> quart.Response:
            try:
                result = await self.call_application(
                    'plugin.asset',
                    request_context,
                    {
                        'author': author,
                        'plugin_name': plugin_name,
                        'filepath': filepath,
                    },
                )
            except WorkspaceNotFoundError:
                return quart.Response('Asset not found', status=404)
            return quart.Response(result['content'], mimetype=result['mime_type'])

        @self.route(
            '/<author>/<plugin_name>/icon',
            methods=['GET'],
            auth_type=group.AuthType.NONE,
        )
        async def _(author: str, plugin_name: str) -> quart.Response:
            try:
                await self._require_public_plugin_runtime_context()
                icon_data = await self.ap.plugin_connector.get_plugin_icon(author, plugin_name)
                if not icon_data or not icon_data.get('plugin_icon_base64'):
                    return quart.Response('Icon not found', status=404)
                icon_bytes = await asyncio.to_thread(base64.b64decode, icon_data['plugin_icon_base64'])
                return quart.Response(icon_bytes, mimetype=icon_data.get('mime_type', 'image/svg+xml'))
            except (ValueError, ActionCallError, WorkspaceNotFoundError):
                return quart.Response('Icon not found', status=404)

        @self.route(
            '/<author>/<plugin_name>/assets/<path:filepath>',
            methods=['GET'],
            auth_type=group.AuthType.NONE,
        )
        async def _(author: str, plugin_name: str, filepath: str) -> quart.Response:
            try:
                await self._require_public_plugin_runtime_context()
                asset_path = _normalize_plugin_asset_path(filepath)
                if asset_path is None:
                    return quart.Response('Asset not found', status=404)

                asset_data = await self.ap.plugin_connector.get_plugin_assets(author, plugin_name, asset_path)
                if not asset_data.get('asset_base64'):
                    return quart.Response('Asset not found', status=404)
                asset_bytes = await asyncio.to_thread(
                    base64.b64decode,
                    asset_data['asset_base64'],
                )
                mime_type = asset_data['mime_type']
                resp = quart.Response(asset_bytes, mimetype=mime_type)
            except (ValueError, ActionCallError, WorkspaceNotFoundError):
                return quart.Response('Asset not found', status=404)
            # CSP for HTML pages served to sandboxed iframes (opaque origin).
            # 'self' doesn't work in sandboxed iframes — use actual server origin.
            if mime_type and mime_type.startswith('text/html'):
                origin = _get_request_origin()
                resp.headers['Content-Security-Policy'] = (
                    f'default-src {origin}; '
                    f"script-src {origin} 'unsafe-inline'; "
                    f"style-src {origin} 'unsafe-inline'; "
                    f'img-src {origin} data:; '
                    f'connect-src {origin}; '
                    "frame-src 'none'; "
                    "object-src 'none'"
                )
            return resp

        @self.route(
            '/<author>/<plugin_name>/page-api',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(author: str, plugin_name: str, request_context: RequestContext) -> str:
            data = await quart.request.json
            if not isinstance(data, dict):
                return self.http_status(400, -1, 'invalid request body')
            page_id = data.get('page_id', '')
            endpoint = data.get('endpoint', '')
            method = data.get('method', 'POST')
            if not isinstance(page_id, str) or not isinstance(endpoint, str) or not isinstance(method, str):
                return self.http_status(400, -1, 'invalid page api request')
            if not endpoint.startswith('/') or '..' in endpoint:
                return self.http_status(400, -1, 'invalid endpoint')
            try:
                result = await self.call_application(
                    'plugin.page_action',
                    request_context,
                    {
                        'author': author,
                        'plugin_name': plugin_name,
                        'page_id': page_id,
                        'endpoint': endpoint,
                        'method': method,
                        'body': data.get('body'),
                    },
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data=result)

        @self.route(
            '/github/releases',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            data = await quart.request.json
            try:
                result = await self.call_application(
                    'plugin.github.releases', request_context, {'repo_url': data.get('repo_url', '')}
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data=result)

        @self.route(
            '/github/release-assets',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            data = await quart.request.json
            payload = {key: data.get(key, '') for key in ('owner', 'repo', 'release_id')}
            if not all(payload.values()):
                return self.http_status(400, -1, 'Missing required parameters')
            try:
                result = await self.call_application('plugin.github.assets', request_context, payload)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data=result)

        @self.route(
            '/install/github',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            data = await quart.request.json or {}
            try:
                result = await self.call_application(
                    'plugin.install.github',
                    request_context,
                    {
                        key: data.get(key)
                        for key in ('owner', 'repo', 'release_tag', 'asset_url', 'asset_id', 'release_id')
                    },
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            quart.g.operation_log_resource_id = f'{data["owner"]}/{data["repo"]}'
            return self.success(data=result)

        @self.route(
            '/install/marketplace',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            data = await quart.request.json
            try:
                result = await self.call_application('plugin.install.marketplace', request_context, data)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            quart.g.operation_log_resource_id = f'{data["plugin_author"]}/{data["plugin_name"]}'
            return self.success(data=result)

        @self.route(
            '/install/local',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')
            form = await quart.request.form
            filename = file.filename or 'local plugin'
            try:
                result = await self.call_application(
                    'plugin.install.local',
                    request_context,
                    {
                        'content': file.read(),
                        'filename': filename,
                        'administrator_force': form.get('administrator_force', '').strip().lower() == 'true',
                    },
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            quart.g.operation_log_resource_id = filename
            return self.success(data=result)

        @self.route(
            '/install/local/preview',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')
            try:
                result = await self.call_application(
                    'plugin.install.local.preview',
                    request_context,
                    {
                        'content': file.read(),
                        'filename': file.filename or 'local plugin',
                    },
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc) or 'invalid .lbpkg file')
            return self.success(data=result)

        @self.route(
            '/config-files',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')
            file_bytes = file.read()
            if len(file_bytes) > 10 * 1024 * 1024:
                return self.http_status(400, -1, 'file size exceeds 10MB limit')
            return self.success(
                data=await self.call_application(
                    'plugin.config_file.upload',
                    request_context,
                    {
                        'content': file_bytes,
                        'filename': file.filename or 'config.bin',
                    },
                )
            )

        @self.route(
            '/config-files/<path:file_key>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(file_key: str, request_context: RequestContext) -> str:
            try:
                result = await self.call_application(
                    'plugin.config_file.delete', request_context, {'file_key': file_key}
                )
            except ValueError:
                return self.http_status(400, -1, 'invalid file key')
            return self.success(data=result)
