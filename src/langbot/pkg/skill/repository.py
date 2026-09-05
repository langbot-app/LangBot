from __future__ import annotations

import asyncio
import os

from langbot_plugin.skill_store import (
    SkillRevisionMismatchError,
    SkillStore,
    skill_namespace,
)

from ..api.http.context import ExecutionContext
from ..api.http.service.tenant import TenantContext, require_workspace_uuid
from ..utils.bounded_executor import blocking_work_scope, run_blocking_atomic


class SkillRepository:
    """Async, Workspace-scoped adapter around the SDK SkillStore."""

    def __init__(self, ap) -> None:
        self.ap = ap
        config = getattr(getattr(ap, 'instance_config', None), 'data', {}) or {}
        self._local_config = (config.get('box') or {}).get('local') or {}
        self._skills_config = config.get('skills') or {}
        self._store = SkillStore(self._skills_root())
        self._lock = asyncio.Lock()

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

    async def _call(self, context: TenantContext, method_name: str, *args, **kwargs):
        execution_context = await self._validated_execution_context(context)
        namespace = self._namespace(execution_context)

        def invoke():
            method = getattr(self._store.scoped(namespace), method_name)
            return method(*args, **kwargs)

        async with self._lock:
            with blocking_work_scope(f'skill:{namespace}'):
                return await run_blocking_atomic(invoke)

    async def list_skills(self, context: TenantContext) -> list[dict]:
        return await self._call(context, 'list_skills')

    async def get_skill(self, context: TenantContext, name: str, *, snapshot: bool = False) -> dict | None:
        return await self._call(context, 'get_skill_snapshot' if snapshot else 'get_skill', name)

    async def create_skill(self, context: TenantContext, skill: dict) -> dict:
        return await self._call(context, 'create_skill', skill)

    async def import_skill_directory(self, context: TenantContext, path: str, skill: dict) -> dict:
        namespace = self._namespace(context)
        return await self._call(
            context,
            'import_skill_directory',
            path,
            skill,
            source_root=self._workspace_root(namespace),
        )

    async def update_skill(self, context: TenantContext, name: str, skill: dict) -> dict:
        return await self._call(context, 'update_skill', name, skill)

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
    ) -> dict:
        return await self._call(
            context,
            'read_skill_resource',
            name,
            path,
            expected_revision=expected_revision,
        )

    async def write_skill_file(self, context: TenantContext, name: str, path: str, content: str) -> dict:
        return await self._call(context, 'write_skill_file', name, path, content)

    async def preview_skill_zip(self, context: TenantContext, file_bytes: bytes, filename: str, **kwargs) -> list[dict]:
        return await self._call(context, 'preview_zip_upload', file_bytes=file_bytes, filename=filename, **kwargs)

    async def install_skill_zip(self, context: TenantContext, file_bytes: bytes, filename: str, **kwargs) -> list[dict]:
        return await self._call(context, 'install_zip_upload', file_bytes=file_bytes, filename=filename, **kwargs)


__all__ = ['SkillRepository', 'SkillRevisionMismatchError']
