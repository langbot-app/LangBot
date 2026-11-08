from __future__ import annotations

import asyncio
import base64
import hashlib
import mimetypes
import os
import weakref

from langbot_plugin.skill_store import (
    SkillRevisionConflictError,
    SkillRevisionMismatchError,
    SkillRevisionNotFoundError,
    SkillStore,
    skill_namespace,
)

from ..api.http.context import ExecutionContext
from ..api.http.service.tenant import TenantContext, require_workspace_uuid
from ..utils.bounded_executor import blocking_work_scope, run_blocking_atomic


# Per-file ceiling for a binary resource handed back as base64. Kept well under
# the SDK's 1 MiB UTF-8 ceiling so an image/PDF never degrades into a huge
# inline string.
_MAX_SKILL_RESOURCE_BYTES = 256 * 1024

# MIME types a model can consume as tool text. Everything else (images, PDFs,
# archives, office documents) goes back as base64 instead of a mojibake string.
_TEXT_SKILL_MIME_TYPES = frozenset(
    {
        'application/javascript',
        'application/json',
        'application/sql',
        'application/toml',
        'application/x-httpd-php',
        'application/x-sh',
        'application/x-yaml',
        'application/xml',
    }
)


def is_text_skill_resource(path: str) -> bool:
    """Whether a Skill resource should be delivered as UTF-8 tool text."""

    mime_type = mimetypes.guess_type(str(path or ''))[0] or ''
    return mime_type.startswith('text/') or mime_type in _TEXT_SKILL_MIME_TYPES


def _resolve_resource_under(package_root: str, path: str) -> tuple[str, str]:
    """Resolve a Skill-relative path, refusing escapes and symlinked files.

    Mirrors the SDK guard so the binary path enforces exactly the protections
    the UTF-8 path already had: relative, non-escaping, regular file, and a
    realpath that stays inside the pinned package root.
    """

    relative = str(path or '').strip() or '.'
    if os.path.isabs(relative):
        raise ValueError('path must be relative to the skill package root')
    normalized = os.path.normpath(relative)
    if normalized == '..' or normalized.startswith('..' + os.sep):
        raise ValueError('path must stay within the skill package root')
    root = os.path.realpath(package_root)
    absolute = os.path.realpath(os.path.join(root, normalized))
    if absolute != root and not absolute.startswith(root + os.sep):
        raise ValueError('path must stay within the skill package root')
    return normalized.replace(os.sep, '/'), absolute


class SkillRepository:
    """Async, Workspace-scoped adapter around the SDK SkillStore."""

    def __init__(self, ap) -> None:
        self.ap = ap
        config = getattr(getattr(ap, 'instance_config', None), 'data', {}) or {}
        self._local_config = (config.get('box') or {}).get('local') or {}
        self._skills_config = config.get('skills') or {}
        self._store = SkillStore(self._skills_root())
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

    def _workspace_lock(self, namespace: str) -> asyncio.Lock:
        lock = self._locks.get(namespace)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[namespace] = lock
        return lock

    def _host_root(self) -> str:
        configured = str(self._local_config.get('host_root') or './data/box').strip()
        return os.path.realpath(os.path.abspath(os.path.expanduser(configured)))

    def _skills_root(self) -> str:
        configured = str(self._skills_config.get('root') or '').strip()
        if not configured:
            # Online-upgrade bridge for installations whose persisted config
            # predates the standalone Skill domain.
            # TODO(next-major): remove box.local.skills_root fallback.
            legacy = str(self._local_config.get('skills_root') or '').strip()
            configured = legacy or 'skills'
            if not os.path.isabs(configured):
                configured = os.path.join(self._host_root(), configured)
        return os.path.realpath(os.path.abspath(os.path.expanduser(configured)))

    def _default_workspace(self) -> str:
        configured = str(self._local_config.get('default_workspace') or '').strip()
        if not configured:
            configured = os.path.join(self._host_root(), 'default')
        elif not os.path.isabs(configured):
            configured = os.path.join(self._host_root(), configured)
        return os.path.realpath(os.path.abspath(os.path.expanduser(configured)))

    @staticmethod
    def _execution_context(context: TenantContext) -> ExecutionContext:
        workspace_uuid = require_workspace_uuid(context)
        instance_uuid = str(getattr(context, 'instance_uuid', '') or '').strip()
        generation = getattr(context, 'placement_generation', None)
        if not instance_uuid:
            raise ValueError('Skill operations require an explicit instance UUID')
        if isinstance(generation, bool) or not isinstance(generation, int) or generation <= 0:
            raise ValueError('Skill operations require a positive placement generation')
        return ExecutionContext(
            instance_uuid=instance_uuid,
            workspace_uuid=workspace_uuid,
            placement_generation=generation,
            bot_uuid=getattr(context, 'bot_uuid', None),
            pipeline_uuid=getattr(context, 'pipeline_uuid', None),
            query_uuid=getattr(context, 'query_uuid', None),
            entitlement_revision=getattr(context, 'entitlement_revision', 0),
        )

    @classmethod
    def _namespace(cls, context: TenantContext) -> str:
        execution_context = cls._execution_context(context)
        return skill_namespace(
            execution_context.instance_uuid,
            execution_context.workspace_uuid,
        )

    async def _validated_execution_context(self, context: TenantContext) -> ExecutionContext:
        execution_context = self._execution_context(context)
        binding = await self.ap.workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )
        if (
            binding.instance_uuid != execution_context.instance_uuid
            or str(getattr(binding, 'workspace_uuid', '') or '') != execution_context.workspace_uuid
            or getattr(binding, 'placement_generation', None) != execution_context.placement_generation
        ):
            raise ValueError('Skill execution context belongs to a stale Workspace placement')
        return execution_context

    def _workspace_root(self, namespace: str) -> str:
        return os.path.join(self._default_workspace(), 'tenants', namespace)

    def storage_root(self, context: TenantContext) -> str:
        return self._store.scoped(self._namespace(context)).root

    async def _call(self, context: TenantContext, method_name: str, *args, **kwargs):
        execution_context = await self._validated_execution_context(context)
        namespace = self._namespace(execution_context)

        def invoke():
            method = getattr(self._store.scoped(namespace), method_name)
            return method(*args, **kwargs)

        async with self._workspace_lock(namespace):
            with blocking_work_scope(f'skill:{namespace}'):
                return await run_blocking_atomic(invoke)

    async def list_skills(self, context: TenantContext) -> list[dict]:
        return await self._call(context, 'list_skills')

    async def get_skill(
        self,
        context: TenantContext,
        name: str,
        *,
        snapshot: bool = False,
        revision: str | None = None,
    ) -> dict | None:
        if revision is not None:
            return await self._call(context, 'get_skill_snapshot', name, revision)
        return await self._call(context, 'get_skill_snapshot' if snapshot else 'get_skill', name)

    async def create_skill(self, context: TenantContext, skill: dict) -> dict:
        return await self._call(context, 'create_skill', skill)

    async def import_skill_directory(
        self,
        context: TenantContext,
        path: str,
        skill: dict,
        *,
        base_revision: str | None = None,
    ) -> dict:
        namespace = self._namespace(context)
        return await self._call(
            context,
            'import_skill_directory',
            path,
            skill,
            source_root=self._workspace_root(namespace),
            base_revision=base_revision,
        )

    async def update_skill(
        self,
        context: TenantContext,
        name: str,
        skill: dict,
        *,
        base_revision: str | None,
    ) -> dict:
        return await self._call(
            context,
            'update_skill',
            name,
            skill,
            base_revision=base_revision,
        )

    async def delete_skill(self, context: TenantContext, name: str) -> None:
        await self._call(context, 'delete_skill', name)

    async def scan_skill_directory(self, context: TenantContext, path: str) -> dict:
        namespace = self._namespace(context)
        return await self._call(
            context,
            'scan_import_directory',
            path,
            source_root=self._workspace_root(namespace),
        )

    async def list_skill_files(
        self,
        context: TenantContext,
        name: str,
        path: str = '.',
        include_hidden: bool = False,
        max_entries: int = 200,
    ) -> dict:
        return await self._call(context, 'list_skill_files', name, path, include_hidden, max_entries)

    async def read_skill_file(self, context: TenantContext, name: str, path: str) -> dict:
        return await self._call(context, 'read_skill_file', name, path)

    async def list_skill_resources(
        self,
        context: TenantContext,
        name: str,
        path: str = '.',
        *,
        expected_revision: str | None = None,
    ) -> dict:
        return await self._call(
            context,
            'list_skill_resources',
            name,
            path,
            False,
            200,
            expected_revision=expected_revision,
        )

    async def read_skill_resource(
        self,
        context: TenantContext,
        name: str,
        path: str,
        *,
        expected_revision: str | None = None,
        max_bytes: int | None = None,
    ) -> dict:
        """Read one activated Skill resource, text or binary.

        Text resources keep the SDK's UTF-8 contract and `content` stays a
        string. Image/PDF and other binary resources are returned with
        `encoding='base64'` plus mime type, size and pinned revision, so a
        caller can hand them to an attachment consumer without a sandbox.
        """

        if is_text_skill_resource(path):
            try:
                return await self._call(
                    context,
                    'read_skill_resource',
                    name,
                    path,
                    expected_revision=expected_revision,
                )
            except ValueError as exc:
                if 'not valid UTF-8' not in str(exc):
                    raise
        return await self.read_skill_resource_bytes(
            context,
            name,
            path,
            expected_revision=expected_revision,
            max_bytes=max_bytes,
        )

    async def read_skill_resource_bytes(
        self,
        context: TenantContext,
        name: str,
        path: str,
        *,
        expected_revision: str | None = None,
        max_bytes: int | None = None,
    ) -> dict:
        """Read the exact pinned bytes of one Skill resource as base64."""

        limit = _MAX_SKILL_RESOURCE_BYTES if max_bytes is None else int(max_bytes)
        if limit <= 0:
            raise ValueError('Skill resource read limit must be positive')

        def invoke():
            execution_context = self._execution_context(context)
            store = self._store.scoped(self._namespace(execution_context))
            package_root = store.resolve_skill_package_root(name, expected_revision)
            skill = store.get_skill_snapshot(name, expected_revision)
            revision = str((skill or {}).get('revision') or '')
            relative, absolute = _resolve_resource_under(package_root, path)
            if not os.path.isfile(absolute):
                raise ValueError(f'Skill file not found: {relative}')
            size = os.path.getsize(absolute)
            if size > limit:
                raise ValueError(
                    f'Skill file {relative} is {size} bytes and exceeds the {limit}-byte read limit'
                )
            with open(absolute, 'rb') as file:
                data = file.read(limit + 1)
            if len(data) > limit:
                raise ValueError(
                    f'Skill file {relative} exceeds the {limit}-byte read limit'
                )
            return {
                'skill': {'name': name},
                'path': relative,
                'content': base64.b64encode(data).decode('ascii'),
                'encoding': 'base64',
                'size': len(data),
                'sha256': hashlib.sha256(data).hexdigest(),
                'mime_type': mimetypes.guess_type(relative)[0] or 'application/octet-stream',
                'revision': revision,
            }

        namespace = self._namespace(context)
        async with self._workspace_lock(namespace):
            with blocking_work_scope(f'skill:{namespace}'):
                return await run_blocking_atomic(invoke)

    async def write_skill_file(
        self,
        context: TenantContext,
        name: str,
        path: str,
        content: str,
        *,
        base_revision: str | None,
    ) -> dict:
        return await self._call(
            context,
            'write_skill_file',
            name,
            path,
            content,
            base_revision=base_revision,
        )

    async def preview_skill_zip(self, context: TenantContext, file_bytes: bytes, filename: str, **kwargs) -> list[dict]:
        return await self._call(context, 'preview_zip_upload', file_bytes=file_bytes, filename=filename, **kwargs)

    async def install_skill_zip(self, context: TenantContext, file_bytes: bytes, filename: str, **kwargs) -> list[dict]:
        return await self._call(context, 'install_zip_upload', file_bytes=file_bytes, filename=filename, **kwargs)


__all__ = [
    'SkillRepository',
    'SkillRevisionConflictError',
    'SkillRevisionMismatchError',
    'SkillRevisionNotFoundError',
]
