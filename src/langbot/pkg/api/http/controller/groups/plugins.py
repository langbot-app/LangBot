from __future__ import annotations

import base64
import quart
import re
import httpx
import uuid
import os

from .....core import taskmgr
from .. import group
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource


@group.group_class('plugins', '/api/v1/plugins')
class PluginsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            plugins = await self.ap.plugin_connector.list_plugins()

            return self.success(data={'plugins': plugins})

        @self.route(
            '/<author>/<plugin_name>/upgrade',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN,
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
            auth_type=group.AuthType.USER_TOKEN,
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
            auth_type=group.AuthType.USER_TOKEN,
        )
        async def _(author: str, plugin_name: str) -> quart.Response:
            plugin = await self.ap.plugin_connector.get_plugin_info(author, plugin_name)
            if plugin is None:
                return self.http_status(404, -1, 'plugin not found')

            if quart.request.method == 'GET':
                return self.success(data={'config': plugin['plugin_config']})
            elif quart.request.method == 'PUT':
                data = await quart.request.json

                await self.ap.plugin_connector.set_plugin_config(author, plugin_name, data)

                return self.success(data={})

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

        @self.route('/github/releases', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """Get releases from a GitHub repository URL"""
            data = await quart.request.json
            repo_url = data.get('repo_url', '')

            # Parse GitHub repository URL to extract owner and repo
            # Supports: https://github.com/owner/repo or github.com/owner/repo
            pattern = r'github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$'
            match = re.search(pattern, repo_url)

            if not match:
                return self.http_status(400, -1, 'Invalid GitHub repository URL')

            owner, repo = match.groups()

            try:
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

                return self.success(data={'releases': formatted_releases, 'owner': owner, 'repo': repo})
            except httpx.RequestError as e:
                return self.http_status(500, -1, f'Failed to fetch releases: {str(e)}')

        @self.route(
            '/github/release-assets',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN,
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

        @self.route('/install/github', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """Install plugin from GitHub release asset"""
            data = await quart.request.json
            asset_url = data.get('asset_url', '')
            owner = data.get('owner', '')
            repo = data.get('repo', '')
            release_tag = data.get('release_tag', '')

            if not asset_url:
                return self.http_status(400, -1, 'Missing asset_url parameter')

            ctx = taskmgr.TaskContext.new()
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
            auth_type=group.AuthType.USER_TOKEN,
        )
        async def _() -> str:
            data = await quart.request.json

            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_connector.install_plugin(PluginInstallSource.MARKETPLACE, data, task_context=ctx),
                kind='plugin-operation',
                name='plugin-install-marketplace',
                label=f'Installing plugin from marketplace ...{data}',
                context=ctx,
            )

            return self.success(data={'task_id': wrapper.id})

        @self.route('/install/local', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            file = (await quart.request.files).get('file')
            if file is None:
                return self.http_status(400, -1, 'file is required')

            file_bytes = file.read()

            data = {
                'plugin_file': file_bytes,
            }

            ctx = taskmgr.TaskContext.new()
            wrapper = self.ap.task_mgr.create_user_task(
                self.ap.plugin_connector.install_plugin(PluginInstallSource.LOCAL, data, task_context=ctx),
                kind='plugin-operation',
                name='plugin-install-local',
                label=f'Installing plugin from local ...{file.filename}',
                context=ctx,
            )

            return self.success(data={'task_id': wrapper.id})

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
