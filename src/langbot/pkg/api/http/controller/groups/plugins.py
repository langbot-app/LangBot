from __future__ import annotations

import base64
import io
import quart
import re
import httpx
import uuid
import os
import zipfile
import yaml
from urllib.parse import urlparse
import posixpath
import sqlalchemy

from .....core import taskmgr
from .....entity.persistence import plugin as persistence_plugin
from .. import group
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource

# Resolve the built-in page SDK JS from the langbot_plugin package
_PAGE_SDK_PATH = None
try:
    import langbot_plugin.assets as _assets_pkg

    _candidate = os.path.join(os.path.dirname(_assets_pkg.__file__), 'langbot-page-sdk.js')
    if os.path.exists(_candidate):
        _PAGE_SDK_PATH = _candidate
except Exception:
    pass


def _normalize_plugin_asset_path(filepath: str) -> str | None:
    filepath = filepath.replace('\\', '/')
    if filepath.startswith('/'):
        return None

    normalized = posixpath.normpath(filepath)
    if normalized == '.' or normalized.startswith('../') or normalized == '..':
        return None

    if normalized.startswith('components/pages/'):
        return normalized

    return f'assets/{normalized}'


def _get_request_origin() -> str:
    """Return the public request origin, respecting reverse-proxy headers."""
    forwarded_proto = quart.request.headers.get('X-Forwarded-Proto', '').split(',')[0].strip()
    forwarded_host = quart.request.headers.get('X-Forwarded-Host', '').split(',')[0].strip()

    scheme = forwarded_proto or quart.request.scheme
    host = forwarded_host or quart.request.host
    return f'{scheme}://{host}'


@group.group_class('plugins', '/api/v1/plugins')
class PluginsRouterGroup(group.RouterGroup):
    @staticmethod
    def _normalize_archive_path(path: str) -> str:
        normalized = str(path or '').replace('\\', '/').strip('/')
        return posixpath.normpath(normalized) if normalized else ''

    @classmethod
    def _component_source_path(cls, entry) -> str:
        if isinstance(entry, dict):
            return cls._normalize_archive_path(entry.get('path') or '')
        return cls._normalize_archive_path(str(entry or ''))

    @classmethod
    def _count_component_configs(cls, component_config, archive_names: list[str]) -> int:
        normalized_names = [cls._normalize_archive_path(name) for name in archive_names]
        component_files: set[str] = set()

        if isinstance(component_config, list):
            return len(component_config)
        if not isinstance(component_config, dict):
            return 1 if component_config else 0

        for entry in component_config.get('fromFiles') or []:
            source_path = cls._component_source_path(entry)
            if source_path and source_path in normalized_names:
                component_files.add(source_path)

        for entry in component_config.get('fromDirs') or []:
            source_dir = cls._component_source_path(entry).rstrip('/')
            if not source_dir:
                continue
            prefix = f'{source_dir}/'
            for archive_name in normalized_names:
                if not archive_name.startswith(prefix):
                    continue
                if archive_name.lower().endswith(('.yaml', '.yml')):
                    component_files.add(archive_name)

        if component_files:
            return len(component_files)

        return 1 if any(key in component_config for key in ('path', 'name', 'kind')) else 0

    @classmethod
    def _count_plugin_components(cls, components, archive_names: list[str]) -> dict[str, int]:
        if not isinstance(components, dict):
            return {}

        component_counts: dict[str, int] = {}
        for kind, component_config in components.items():
            count = cls._count_component_configs(component_config, archive_names)
            if count > 0:
                component_counts[str(kind)] = count
        return component_counts

    @staticmethod
    def _parse_github_repo_url(repo_url: str) -> dict | None:
        raw_url = str(repo_url or '').strip()
        if not raw_url:
            return None

        if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', raw_url):
            raw_url = f'https://{raw_url}'

        parsed = urlparse(raw_url)
        if parsed.netloc.lower() not in ('github.com', 'www.github.com'):
            return None

        parts = [part for part in parsed.path.strip('/').split('/') if part]
        if len(parts) < 2:
            return None

        owner = parts[0]
        repo = parts[1]
        if repo.endswith('.git'):
            repo = repo[:-4]
        if not owner or not repo:
            return None

        ref = ''
        subdir = ''
        if len(parts) >= 4 and parts[2] in ('tree', 'blob'):
            ref = parts[3]
            subdir = '/'.join(parts[4:]).strip('/')

        return {
            'owner': owner,
            'repo': repo,
            'ref': ref,
            'subdir': subdir,
        }

    async def _check_extensions_limit(self) -> str | None:
        """Check if extensions limit is reached. Returns error response if limit exceeded, None otherwise."""
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_extensions = limitation.get('max_extensions', -1)
        if max_extensions >= 0:
            plugins = await self.ap.plugin_connector.list_plugins()
            mcp_servers = await self.ap.mcp_service.get_mcp_servers()
            total_extensions = len(plugins) + len(mcp_servers)
            if total_extensions >= max_extensions:
                return self.http_status(400, -1, f'Maximum number of extensions ({max_extensions}) reached')
        return None

    async def initialize(self) -> None:
        @self.route('/_sdk/page-sdk.js', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> quart.Response:
            """Serve the built-in LangBot page SDK JavaScript."""
            if _PAGE_SDK_PATH and os.path.exists(_PAGE_SDK_PATH):
                with open(_PAGE_SDK_PATH, 'r') as f:
                    content = f.read()
                return quart.Response(content, mimetype='application/javascript')
            return quart.Response('// SDK not found', status=404, mimetype='application/javascript')

        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            plugins = await self.ap.plugin_connector.list_plugins()

            return self.success(data={'plugins': plugins})

        @self.route('/debug-info', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            """Get plugin debug information including debug URL and key"""
            debug_info = await self.ap.plugin_connector.get_debug_info()

            # Get debug URL from config
            plugin_config = self.ap.instance_config.data.get('plugin', {})
            debug_url = plugin_config.get('display_plugin_debug_url', 'http://localhost:5401')

            return self.success(
                data={
                    'debug_url': debug_url,
                    'plugin_debug_key': debug_info.get('plugin_debug_key', ''),
                }
            )

        @self.route(
            '/<author>/<plugin_name>/upgrade',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def _(author: str, plugin_name: str) -> str:
            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_connector.upgrade_plugin(author, plugin_name, task_context=ctx),
                kind='plugin-operation',
                name=f'plugin-upgrade-{plugin_name}',
                label=f'Upgrading plugin {plugin_name}',
                context=ctx,
            )
            return self.success(data={'task_id': wrapper.id})

        @self.route(
            '/<author>/<plugin_name>',
            methods=['GET', 'DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def _(author: str, plugin_name: str) -> str:
            if quart.request.method == 'GET':
                plugin = await self.ap.plugin_connector.get_plugin_info(author, plugin_name)
                if plugin is None:
                    return self.http_status(404, -1, 'plugin not found')
                return self.success(data={'plugin': plugin})
            elif quart.request.method == 'DELETE':
                delete_data = quart.request.args.get('delete_data', 'false').lower() == 'true'
                ctx = taskmgr.TaskContext.new()
                wrapper = self.ap.task_mgr.create_user_task(
                    self.ap.plugin_connector.delete_plugin(
                        author, plugin_name, delete_data=delete_data, task_context=ctx
                    ),
                    kind='plugin-operation',
                    name=f'plugin-remove-{plugin_name}',
                    label=f'Removing plugin {plugin_name}',
                    context=ctx,
                )

                return self.success(data={'task_id': wrapper.id})

        @self.route(
            '/<author>/<plugin_name>/config',
            methods=['GET', 'PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def _(author: str, plugin_name: str) -> quart.Response:
            plugin = await self.ap.plugin_connector.get_plugin_info(author, plugin_name)
            if plugin is None:
                return self.http_status(404, -1, 'plugin not found')

            if quart.request.method == 'GET':
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_plugin.PluginSetting.config)
                    .where(persistence_plugin.PluginSetting.plugin_author == author)
                    .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
                )
                persisted_config = result.scalar_one_or_none()

                config = persisted_config if persisted_config is not None else plugin['plugin_config']
                return self.success(data={'config': config})
            elif quart.request.method == 'PUT':
                data = await quart.request.json

                result = await self.ap.plugin_connector.set_plugin_config(author, plugin_name, data)

                return self.success(data={'config': result.get('config', data)})

        @self.route(
            '/<author>/<plugin_name>/readme',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def _(author: str, plugin_name: str) -> quart.Response:
            language = quart.request.args.get('language', 'en')
            readme = await self.ap.plugin_connector.get_plugin_readme(author, plugin_name, language=language)
            return self.success(data={'readme': readme})

        @self.route(
            '/<author>/<plugin_name>/logs',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def _(author: str, plugin_name: str) -> quart.Response:
            try:
                limit = int(quart.request.args.get('limit', 200))
            except (TypeError, ValueError):
                limit = 200
            level = quart.request.args.get('level') or None
            logs = await self.ap.plugin_connector.get_plugin_logs(author, plugin_name, limit=limit, level=level)
            return self.success(data={'logs': logs})

        @self.route(
            '/<author>/<plugin_name>/icon',
            methods=['GET'],
            auth_type=group.AuthType.NONE,
        )
        async def _(author: str, plugin_name: str) -> quart.Response:
            icon_data = await self.ap.plugin_connector.get_plugin_icon(author, plugin_name)
            icon_base64 = icon_data['plugin_icon_base64']
            mime_type = icon_data['mime_type']

            icon_data = base64.b64decode(icon_base64)

            return quart.Response(icon_data, mimetype=mime_type)

        @self.route(
            '/<author>/<plugin_name>/assets/<path:filepath>',
            methods=['GET'],
            auth_type=group.AuthType.NONE,
        )
        async def _(author: str, plugin_name: str, filepath: str) -> quart.Response:
            asset_path = _normalize_plugin_asset_path(filepath)
            if asset_path is None:
                return quart.Response('Asset not found', status=404)

            asset_data = await self.ap.plugin_connector.get_plugin_assets(author, plugin_name, asset_path)
            if not asset_data.get('asset_base64'):
                return quart.Response('Asset not found', status=404)
            asset_bytes = base64.b64decode(asset_data['asset_base64'])
            mime_type = asset_data['mime_type']
            resp = quart.Response(asset_bytes, mimetype=mime_type)
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
        )
        async def _(author: str, plugin_name: str) -> str:
            """Forward a page API request to the plugin."""
            data = await quart.request.json
            if not isinstance(data, dict):
                return self.http_status(400, -1, 'invalid request body')

            page_id = data.get('page_id', '')
            endpoint = data.get('endpoint', '')
            method = data.get('method', 'POST')
            body = data.get('body')
            if not isinstance(page_id, str) or not isinstance(endpoint, str) or not isinstance(method, str):
                return self.http_status(400, -1, 'invalid page api request')
            if not endpoint.startswith('/') or '..' in endpoint:
                return self.http_status(400, -1, 'invalid endpoint')

            result = await self.ap.plugin_connector.handle_page_api(
                author, plugin_name, page_id, endpoint, method.upper(), body
            )
            if result.get('error'):
                return self.http_status(400, -1, result['error'])
            return self.success(data=result.get('data'))

        @self.route('/github/releases', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            """Get releases from a GitHub repository URL"""
            data = await quart.request.json
            repo_url = data.get('repo_url', '')

            parsed_repo = self._parse_github_repo_url(repo_url)
            if not parsed_repo:
                return self.http_status(400, -1, 'Invalid GitHub repository URL')

            owner = parsed_repo['owner']
            repo = parsed_repo['repo']
            requested_ref = parsed_repo['ref']
            requested_subdir = parsed_repo['subdir']

            try:
                if requested_ref:
                    return self.success(
                        data={
                            'releases': [
                                {
                                    'id': 0,
                                    'tag_name': requested_ref,
                                    'name': requested_ref,
                                    'published_at': '',
                                    'prerelease': False,
                                    'draft': False,
                                    'source_type': 'branch',
                                    'archive_url': f'https://api.github.com/repos/{owner}/{repo}/zipball/{requested_ref}',
                                }
                            ],
                            'owner': owner,
                            'repo': repo,
                            'source_subdir': requested_subdir,
                        }
                    )

                # Fetch releases from GitHub API
                url = f'https://api.github.com/repos/{owner}/{repo}/releases'
                async with httpx.AsyncClient(
                    trust_env=True,
                    follow_redirects=True,
                    timeout=10,
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    releases = response.json()

                # Format releases data for frontend
                formatted_releases = []
                for release in releases:
                    formatted_releases.append(
                        {
                            'id': release['id'],
                            'tag_name': release['tag_name'],
                            'name': release['name'],
                            'published_at': release['published_at'],
                            'prerelease': release['prerelease'],
                            'draft': release['draft'],
                        }
                    )

                return self.success(
                    data={
                        'releases': formatted_releases,
                        'owner': owner,
                        'repo': repo,
                        'source_subdir': requested_subdir,
                    }
                )
            except httpx.RequestError as e:
                return self.http_status(500, -1, f'Failed to fetch releases: {str(e)}')

        @self.route(
            '/github/release-assets',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def _() -> str:
            """Get assets from a specific GitHub release"""
            data = await quart.request.json
            owner = data.get('owner', '')
            repo = data.get('repo', '')
            release_id = data.get('release_id', '')

            if not all([owner, repo, release_id]):
                return self.http_status(400, -1, 'Missing required parameters')

            try:
                # Fetch release assets from GitHub API
                url = f'https://api.github.com/repos/{owner}/{repo}/releases/{release_id}'
                async with httpx.AsyncClient(
                    trust_env=True,
                    follow_redirects=True,
                    timeout=10,
                ) as client:
                    response = await client.get(
                        url,
                    )
                    response.raise_for_status()
                    release = response.json()

                # Format assets data for frontend
                formatted_assets = []
                for asset in release.get('assets', []):
                    formatted_assets.append(
                        {
                            'id': asset['id'],
                            'name': asset['name'],
                            'size': asset['size'],
                            'download_url': asset['browser_download_url'],
                            'content_type': asset['content_type'],
                        }
                    )

                # add zipball as a downloadable asset
                # formatted_assets.append(
                #     {
                #         "id": 0,
                #         "name": "Source code (zip)",
                #         "size": -1,
                #         "download_url": release["zipball_url"],
                #         "content_type": "application/zip",
                #     }
                # )

                return self.success(data={'assets': formatted_assets})
            except httpx.RequestError as e:
                return self.http_status(500, -1, f'Failed to fetch release assets: {str(e)}')

        @self.route('/install/github', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            """Install plugin from GitHub release asset"""
            limit_error = await self._check_extensions_limit()
            if limit_error is not None:
                return limit_error

            data = await quart.request.json
            asset_url = data.get('asset_url', '')
            owner = data.get('owner', '')
            repo = data.get('repo', '')
            release_tag = data.get('release_tag', '')

            if not asset_url:
                return self.http_status(400, -1, 'Missing asset_url parameter')

            ctx = taskmgr.TaskContext.new()
            ctx.metadata['plugin_name'] = f'{owner}/{repo}'
            ctx.metadata['install_source'] = 'github'
            install_info = {
                'asset_url': asset_url,
                'owner': owner,
                'repo': repo,
                'release_tag': release_tag,
                'github_url': f'https://github.com/{owner}/{repo}',
            }

            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_connector.install_plugin(PluginInstallSource.GITHUB, install_info, task_context=ctx),
                kind='plugin-operation',
                name='plugin-install-github',
                label=f'Installing plugin from GitHub {owner}/{repo}@{release_tag}',
                context=ctx,
            )

            return self.success(data={'task_id': wrapper.id})

        @self.route(
            '/install/marketplace',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def _() -> str:
            limit_error = await self._check_extensions_limit()
            if limit_error is not None:
                return limit_error

            data = await quart.request.json

            plugin_author = data.get('plugin_author', '')
            plugin_name = data.get('plugin_name', '')

            ctx = taskmgr.TaskContext.new()
            ctx.metadata['plugin_name'] = f'{plugin_author}/{plugin_name}'
            ctx.metadata['install_source'] = 'marketplace'
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_connector.install_plugin(PluginInstallSource.MARKETPLACE, data, task_context=ctx),
                kind='plugin-operation',
                name='plugin-install-marketplace',
                label=f'Installing plugin from marketplace {plugin_author}/{plugin_name}',
                context=ctx,
            )

            return self.success(data={'task_id': wrapper.id})

        @self.route('/install/local', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            limit_error = await self._check_extensions_limit()
            if limit_error is not None:
                return limit_error

            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')

            file_bytes = file.read()

            data = {
                'plugin_file': file_bytes,
            }

            ctx = taskmgr.TaskContext.new()
            ctx.metadata['plugin_name'] = file.filename or 'local plugin'
            ctx.metadata['install_source'] = 'local'
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_connector.install_plugin(PluginInstallSource.LOCAL, data, task_context=ctx),
                kind='plugin-operation',
                name='plugin-install-local',
                label=f'Installing plugin from local {file.filename}',
                context=ctx,
            )

            return self.success(data={'task_id': wrapper.id})

        @self.route('/install/local/preview', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')

            file_bytes = file.read()
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                    names = [name for name in zf.namelist() if not name.endswith('/')]
                    manifest_name = next(
                        (
                            name
                            for name in names
                            if name.replace('\\', '/').strip('/').lower() in ('manifest.yaml', 'manifest.yml')
                        ),
                        None,
                    )
                    if manifest_name is None:
                        return self.http_status(400, -1, 'manifest.yaml is required')

                    manifest = yaml.safe_load(zf.read(manifest_name).decode('utf-8')) or {}
                    requirements: list[str] = []
                    requirements_name = next(
                        (name for name in names if name.replace('\\', '/').strip('/').lower() == 'requirements.txt'),
                        None,
                    )
                    if requirements_name is not None:
                        requirements = [
                            line.strip()
                            for line in zf.read(requirements_name).decode('utf-8', errors='ignore').splitlines()
                            if line.strip() and not line.strip().startswith('#')
                        ]

                    spec = manifest.get('spec') or {}
                    components = spec.get('components') or {}
                    component_counts = self._count_plugin_components(components, names)
                    component_types = list(component_counts.keys())

                    return self.success(
                        data={
                            'filename': file.filename or 'local plugin',
                            'size': len(file_bytes),
                            'manifest': manifest,
                            'metadata': manifest.get('metadata') or {},
                            'component_types': component_types,
                            'component_counts': component_counts,
                            'requirements': requirements,
                            'file_count': len(names),
                        }
                    )
            except zipfile.BadZipFile:
                return self.http_status(400, -1, 'invalid .lbpkg file')
            except Exception as exc:
                return self.http_status(500, -1, f'Failed to preview plugin package: {exc}')

        @self.route('/config-files', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """Upload a file for plugin configuration"""
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')

            # Check file size (10MB limit)
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
            file_bytes = file.read()
            if len(file_bytes) > MAX_FILE_SIZE:
                return self.http_status(400, -1, 'file size exceeds 10MB limit')

            # Generate unique file key with original extension
            original_filename = file.filename
            _, ext = os.path.splitext(original_filename)
            file_key = f'plugin_config_{uuid.uuid4().hex}{ext}'

            # Save file using storage manager
            await self.ap.storage_mgr.storage_provider.save(file_key, file_bytes)

            return self.success(data={'file_key': file_key})

        @self.route('/config-files/<file_key>', methods=['DELETE'], auth_type=group.AuthType.USER_TOKEN)
        async def _(file_key: str) -> str:
            """Delete a plugin configuration file"""
            # Only allow deletion of files with plugin_config_ prefix for security
            if not file_key.startswith('plugin_config_'):
                return self.http_status(400, -1, 'invalid file key')

            try:
                await self.ap.storage_mgr.storage_provider.delete(file_key)
                return self.success(data={'deleted': True})
            except Exception as e:
                return self.http_status(500, -1, f'failed to delete file: {str(e)}')
