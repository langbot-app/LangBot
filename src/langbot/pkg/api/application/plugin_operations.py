"""Workspace plugin management operations independent of HTTP adapters."""

from __future__ import annotations

import asyncio
import base64
import os
import re
import uuid
import zipfile
from typing import Any
from typing_extensions import TypedDict
from urllib.parse import urlparse

import httpx
import sqlalchemy
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource
from pydantic import Field

from ...core import taskmgr
from ...entity.persistence import plugin as persistence_plugin
from ...i18n import t
from ...plugin.archive import inspect_plugin_archive_metadata
from ...plugin.github import validate_github_plugin_install_info
from ...plugin.management import (
    count_plugin_components,
    normalize_plugin_asset_path,
    parse_github_repo_url,
    redact_plugin_secrets,
    restore_plugin_secret_placeholders,
)
from ...utils import httpclient
from ...workspace.errors import WorkspaceNotFoundError
from ..authz import Permission
from ..http.service.workspace_limits import workspace_limits
from .contracts import Input, Operation


class PluginsResult(TypedDict):
    plugins: list[dict[str, Any]]


class PluginResult(TypedDict):
    plugin: dict[str, Any]


class ConfigResult(TypedDict):
    config: dict[str, Any]


class DebugResult(TypedDict):
    debug_url: str
    plugin_debug_key: str
    expires_at: str


class TaskResult(TypedDict):
    task_id: int


class BinaryResult(TypedDict):
    content: bytes
    mime_type: str


class ReadmeResult(TypedDict):
    readme: str


class FileResult(TypedDict):
    file_key: str


class DeletedResult(TypedDict):
    deleted: bool


class PluginInput(Input):
    author: str = Field(min_length=1)
    plugin_name: str = Field(min_length=1)


class DeleteInput(PluginInput):
    delete_data: bool = False


class ConfigInput(PluginInput):
    config: dict[str, Any]


class ReadmeInput(PluginInput):
    language: str = 'en'


class LogsInput(PluginInput):
    limit: int = Field(default=200, ge=1)
    level: str | None = None


class AssetInput(PluginInput):
    filepath: str


class PageInput(PluginInput):
    page_id: str
    endpoint: str
    method: str = 'POST'
    body: Any = None


class GithubRepoInput(Input):
    repo_url: str


class GithubAssetsInput(Input):
    owner: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9-]{0,38}$')
    repo: str = Field(pattern=r'^[A-Za-z0-9._-]{1,100}$')
    release_id: int = Field(gt=0)


class GithubInstallInput(Input):
    owner: str
    repo: str
    release_tag: str
    asset_url: str | None = None
    asset_id: int | None = None
    release_id: int | None = None


class MarketplaceInput(Input):
    plugin_author: str = Field(min_length=1)
    plugin_name: str = Field(min_length=1)
    plugin_version: str | None = None


class FileInput(Input):
    content: bytes
    filename: str = 'config.bin'


class LocalInstallInput(FileInput):
    filename: str = 'local plugin'
    administrator_force: bool = False


class FileKeyInput(Input):
    file_key: str


async def _fence(ap, context):
    return await ap.plugin_connector.require_workspace_context(context)


async def _get(ap, context, payload):
    await _fence(ap, context)
    plugin = await ap.plugin_connector.get_plugin_info(payload.author, payload.plugin_name)
    if plugin is None:
        raise WorkspaceNotFoundError('Plugin not found')
    return plugin


async def _stored_config(ap, context, payload, plugin):
    result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_plugin.PluginSetting.config)
        .where(persistence_plugin.PluginSetting.workspace_uuid == context.workspace_uuid)
        .where(persistence_plugin.PluginSetting.plugin_author == payload.author)
        .where(persistence_plugin.PluginSetting.plugin_name == payload.plugin_name)
    )
    config = result.scalar_one_or_none()
    return config if config is not None else plugin['plugin_config']


async def list_plugins(ap, context, payload):
    await _fence(ap, context)
    return {'plugins': redact_plugin_secrets(await ap.plugin_connector.list_plugins())}


async def get_plugin(ap, context, payload):
    return {'plugin': redact_plugin_secrets(await _get(ap, context, payload))}


async def debug_info(ap, context, payload):
    execution = await _fence(ap, context)
    info = await ap.plugin_connector.get_debug_info(execution)
    url = ap.instance_config.data.get('plugin', {}).get(
        'display_plugin_debug_url', 'ws://localhost:5401/plugin/debug/ws'
    )
    parsed = urlparse(url)
    if parsed.scheme in {'http', 'https'}:
        url = parsed._replace(
            scheme='wss' if parsed.scheme == 'https' else 'ws', path=parsed.path or '/plugin/debug/ws'
        ).geturl()
    return {
        'debug_url': url,
        'plugin_debug_key': info.get('plugin_debug_key', ''),
        'expires_at': info.get('expires_at', ''),
    }


async def get_config(ap, context, payload):
    plugin = await _get(ap, context, payload)
    return {'config': redact_plugin_secrets(await _stored_config(ap, context, payload, plugin))}


async def update_config(ap, context, payload):
    plugin = await _get(ap, context, payload)
    config = restore_plugin_secret_placeholders(payload.config, await _stored_config(ap, context, payload, plugin))
    await _fence(ap, context)
    await ap.plugin_connector.set_plugin_config(payload.author, payload.plugin_name, config)
    return {}


async def readme(ap, context, payload):
    await _fence(ap, context)
    return {
        'readme': await ap.plugin_connector.get_plugin_readme(
            payload.author, payload.plugin_name, language=payload.language
        )
    }


async def logs(ap, context, payload):
    await _fence(ap, context)
    return {
        'logs': await ap.plugin_connector.get_plugin_logs(
            payload.author, payload.plugin_name, limit=payload.limit, level=payload.level
        )
    }


async def icon(ap, context, payload):
    await _fence(ap, context)
    try:
        result = await ap.plugin_connector.get_plugin_icon(payload.author, payload.plugin_name)
    except ValueError as exc:
        if 'is not installed in this workspace' in str(exc).lower():
            raise WorkspaceNotFoundError('Icon not found') from exc
        raise
    return {
        'content': await asyncio.to_thread(base64.b64decode, result['plugin_icon_base64']),
        'mime_type': result['mime_type'],
    }


async def asset(ap, context, payload):
    await _fence(ap, context)
    path = normalize_plugin_asset_path(payload.filepath)
    if path is None:
        raise WorkspaceNotFoundError('Asset not found')
    result = await ap.plugin_connector.get_plugin_assets(payload.author, payload.plugin_name, path)
    if not result.get('asset_base64'):
        raise WorkspaceNotFoundError('Asset not found')
    return {
        'content': await asyncio.to_thread(base64.b64decode, result['asset_base64']),
        'mime_type': result['mime_type'],
    }


async def page_action(ap, context, payload):
    await _fence(ap, context)
    if not payload.endpoint.startswith('/') or '..' in payload.endpoint:
        raise ValueError('Invalid endpoint')
    result = await ap.plugin_connector.handle_page_api(
        payload.author, payload.plugin_name, payload.page_id, payload.endpoint, payload.method.upper(), payload.body
    )
    if result.get('error'):
        raise ValueError(result['error'])
    return result.get('data')


async def _github_json(url):
    async with httpx.AsyncClient(
        trust_env=True, follow_redirects=True, timeout=10, event_hooks=httpclient.httpx_response_limit_hooks()
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return await httpclient.parse_json_response(response)


async def github_releases(ap, context, payload):
    await _fence(ap, context)
    repo = parse_github_repo_url(payload.repo_url)
    if not repo:
        raise ValueError('Invalid GitHub repository URL')
    owner, name, ref = repo['owner'], repo['repo'], repo['ref']
    # Repository parts become URL path segments, never a caller-selected host/path.
    if (
        re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', owner) is None
        or re.fullmatch(r'[A-Za-z0-9._-]{1,100}', name) is None
    ):
        raise ValueError('Invalid GitHub repository URL')
    if ref:
        releases = [
            {
                'id': 0,
                'tag_name': ref,
                'name': ref,
                'published_at': '',
                'prerelease': False,
                'draft': False,
                'source_type': 'branch',
                'archive_url': f'https://api.github.com/repos/{owner}/{name}/zipball/{ref}',
            }
        ]
    else:
        data = await _github_json(f'https://api.github.com/repos/{owner}/{name}/releases')
        releases = [
            {key: release[key] for key in ('id', 'tag_name', 'name', 'published_at', 'prerelease', 'draft')}
            for release in data
        ]
    return {'releases': releases, 'owner': owner, 'repo': name, 'source_subdir': repo['subdir']}


async def github_assets(ap, context, payload):
    await _fence(ap, context)
    release = await _github_json(
        f'https://api.github.com/repos/{payload.owner}/{payload.repo}/releases/{payload.release_id}'
    )
    return {
        'assets': [
            {
                'id': item['id'],
                'name': item['name'],
                'size': item['size'],
                'download_url': item['browser_download_url'],
                'content_type': item['content_type'],
            }
            for item in release.get('assets', [])
        ]
    }


async def _check_limit(ap, context):
    await _fence(ap, context)
    limits = await workspace_limits(ap, context.workspace_uuid)
    limit = limits.get('max_extensions', -1)
    if limit >= 0:
        plugins = await ap.plugin_connector.list_plugins()
        servers = await ap.mcp_service.get_mcp_servers(context)
        if len(plugins) + len(servers) >= limit:
            raise ValueError(t('Maximum number of {resource} ({limit}) reached', resource=t('extensions'), limit=limit))


async def _run_fenced(ap, execution, operation):
    async with ap.persistence_mgr.tenant_scope(execution.workspace_uuid):
        await _fence(ap, execution)
        return await operation()


async def _queue(ap, context, name, label, task, operation):
    execution = await _fence(ap, context)
    wrapper = ap.task_mgr.create_user_task(
        _run_fenced(ap, execution, operation),
        kind='plugin-operation',
        name=name,
        label=label,
        context=task,
        instance_uuid=context.instance_uuid,
        workspace_uuid=context.workspace_uuid,
        placement_generation=context.placement_generation,
    )
    return {'task_id': wrapper.id}


async def upgrade(ap, context, payload):
    task = taskmgr.TaskContext.new()
    task.metadata.update(
        {
            'plugin_name': f'{payload.author}/{payload.plugin_name}',
            'install_source': 'marketplace',
            'operation': 'upgrade',
            'progress_percent': 3,
        }
    )
    task.set_current_action('checking for latest version')
    return await _queue(
        ap,
        context,
        f'plugin-upgrade-{payload.plugin_name}',
        f'Upgrading plugin {payload.plugin_name}',
        task,
        lambda: ap.plugin_connector.upgrade_plugin(payload.author, payload.plugin_name, task_context=task),
    )


async def delete(ap, context, payload):
    task = taskmgr.TaskContext.new()
    return await _queue(
        ap,
        context,
        f'plugin-remove-{payload.plugin_name}',
        f'Removing plugin {payload.plugin_name}',
        task,
        lambda: ap.plugin_connector.delete_plugin(
            payload.author, payload.plugin_name, delete_data=payload.delete_data, task_context=task
        ),
    )


async def _install(ap, context, source, data, identity, label):
    task = taskmgr.TaskContext.new()
    task.metadata.update({'plugin_name': identity, 'install_source': source.value})
    return await _queue(
        ap,
        context,
        f'plugin-install-{source.value}',
        label,
        task,
        lambda: ap.plugin_connector.install_plugin(source, data, task_context=task),
    )


async def install_github(ap, context, payload):
    await _check_limit(ap, context)
    data = validate_github_plugin_install_info(payload.model_dump())
    identity = f'{data["owner"]}/{data["repo"]}'
    return await _install(
        ap,
        context,
        PluginInstallSource.GITHUB,
        data,
        identity,
        f'Installing plugin from GitHub {identity}@{data["release_tag"]}',
    )


async def install_marketplace(ap, context, payload):
    await _check_limit(ap, context)
    identity = f'{payload.plugin_author}/{payload.plugin_name}'
    return await _install(
        ap,
        context,
        PluginInstallSource.MARKETPLACE,
        payload.model_dump(exclude_none=True),
        identity,
        f'Installing plugin from marketplace {identity}',
    )


async def install_local(ap, context, payload):
    await _check_limit(ap, context)
    return await _install(
        ap,
        context,
        PluginInstallSource.LOCAL,
        {'plugin_file': payload.content, 'administrator_force': payload.administrator_force},
        payload.filename,
        f'Installing plugin from local {payload.filename}',
    )


async def preview_local(ap, context, payload):
    await _fence(ap, context)
    try:
        manifest, requirements, names = await asyncio.to_thread(inspect_plugin_archive_metadata, payload.content)
    except zipfile.BadZipFile as exc:
        raise ValueError('Invalid .lbpkg file') from exc
    counts = count_plugin_components((manifest.get('spec') or {}).get('components') or {}, names)
    return {
        'filename': payload.filename,
        'size': len(payload.content),
        'manifest': manifest,
        'metadata': manifest.get('metadata') or {},
        'component_types': list(counts),
        'component_counts': counts,
        'requirements': requirements,
        'file_count': len(names),
    }


async def upload_config_file(ap, context, payload):
    await _fence(ap, context)
    if len(payload.content) > 10 * 1024 * 1024:
        raise ValueError('File size exceeds 10MB limit')
    _, ext = os.path.splitext(payload.filename)
    key = await ap.storage_mgr.save_scoped(
        context,
        owner_type='plugin_config',
        owner=context.workspace_uuid,
        key=f'plugin_config_{uuid.uuid4().hex}{ext}',
        value=payload.content,
    )
    return {'file_key': key}


async def delete_config_file(ap, context, payload):
    await _fence(ap, context)
    if not ap.storage_mgr.is_scoped_object_key(payload.file_key, expected_owner_type='plugin_config'):
        raise ValueError('Invalid file key')
    await ap.storage_mgr.delete_scoped_object_key(context, payload.file_key, expected_owner_type='plugin_config')
    return {'deleted': True}


def operations() -> list[Operation]:
    view, manage = Permission.RESOURCE_VIEW, Permission.RESOURCE_MANAGE
    return [
        Operation('plugin.list', view, list_plugins, Input, PluginsResult),
        Operation('plugin.get', view, get_plugin, PluginInput, PluginResult),
        Operation('plugin.debug_info', manage, debug_info, Input, DebugResult),
        Operation('plugin.config.get', view, get_config, PluginInput, ConfigResult),
        Operation('plugin.config.update', manage, update_config, ConfigInput, dict, side_effect=True),
        Operation('plugin.readme', view, readme, ReadmeInput, ReadmeResult),
        Operation('plugin.logs', Permission.AUDIT_VIEW, logs, LogsInput, dict),
        Operation('plugin.icon', view, icon, PluginInput, BinaryResult),
        Operation('plugin.asset', view, asset, AssetInput, BinaryResult),
        Operation('plugin.page_action', manage, page_action, PageInput, Any, side_effect=True),
        Operation('plugin.github.releases', view, github_releases, GithubRepoInput, dict),
        Operation('plugin.github.assets', view, github_assets, GithubAssetsInput, dict),
        Operation('plugin.upgrade', manage, upgrade, PluginInput, TaskResult, side_effect=True),
        Operation('plugin.delete', manage, delete, DeleteInput, TaskResult, side_effect=True),
        Operation('plugin.install.github', manage, install_github, GithubInstallInput, TaskResult, side_effect=True),
        Operation(
            'plugin.install.marketplace', manage, install_marketplace, MarketplaceInput, TaskResult, side_effect=True
        ),
        Operation('plugin.install.local', manage, install_local, LocalInstallInput, TaskResult, side_effect=True),
        Operation('plugin.install.local.preview', manage, preview_local, FileInput, dict),
        Operation('plugin.config_file.upload', manage, upload_config_file, FileInput, FileResult, side_effect=True),
        Operation(
            'plugin.config_file.delete', manage, delete_config_file, FileKeyInput, DeletedResult, side_effect=True
        ),
    ]
