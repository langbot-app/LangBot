from __future__ import annotations

import datetime
import functools
import os
import re
from pathlib import Path
from typing import Any

import sqlalchemy

from ....core import app
from ....entity.persistence import bstorage as persistence_bstorage
from ....entity.persistence import monitoring as persistence_monitoring
from ..authz import WorkspaceRequiredError
from ..context import ExecutionContext
from .tenant import TenantContext, require_workspace_uuid


LOG_FILE_PATTERN = re.compile(r'^langbot-(\d{4}-\d{2}-\d{2})\.log(?:\.\d+)?$')
DEFAULT_UPLOAD_FILE_RETENTION_DAYS = 7
DEFAULT_LOG_RETENTION_DAYS = 3
UPLOAD_OWNER_TYPES = ('upload_image', 'upload_document', 'upload')


def _workspace_scope(method):
    """Bind maintenance work to a Workspace without spanning external I/O."""

    @functools.wraps(method)
    async def wrapped(self, context, *args, **kwargs):
        workspace_uuid = require_workspace_uuid(context)
        persistence_mgr = getattr(self.ap, 'persistence_mgr', None)
        tenant_scope = getattr(persistence_mgr, 'tenant_scope', None)
        cloud_runtime = getattr(getattr(persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime'
        if cloud_runtime:
            if not callable(tenant_scope):
                raise RuntimeError('Cloud maintenance requires an explicit tenant scope')
            async with tenant_scope(workspace_uuid):
                return await method(self, context, *args, **kwargs)
        return await method(self, context, *args, **kwargs)

    return wrapped


class MaintenanceService:
    """Storage maintenance and diagnostics."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    @_workspace_scope
    async def cleanup_expired_files(self, context: ExecutionContext) -> dict[str, int]:
        if not isinstance(context, ExecutionContext):
            raise WorkspaceRequiredError('Storage cleanup requires an ExecutionContext')
        require_workspace_uuid(context)
        cleanup_cfg = self.ap.instance_config.data.get('storage', {}).get('cleanup', {})
        upload_retention_days = self._positive_int(
            cleanup_cfg.get('uploaded_file_retention_days'),
            DEFAULT_UPLOAD_FILE_RETENTION_DAYS,
            'storage.cleanup.uploaded_file_retention_days',
        )
        log_retention_days = self._positive_int(
            cleanup_cfg.get('log_retention_days'),
            DEFAULT_LOG_RETENTION_DAYS,
            'storage.cleanup.log_retention_days',
        )

        return {
            'uploaded_files': await self._cleanup_expired_uploaded_files(context, upload_retention_days),
            'log_files': self._cleanup_expired_log_files(log_retention_days)
            if await self._is_oss_singleton(context)
            else 0,
        }

    async def get_storage_analysis(self, context: TenantContext) -> dict[str, Any]:
        require_workspace_uuid(context)
        cleanup_cfg = self.ap.instance_config.data.get('storage', {}).get('cleanup', {})
        upload_retention_days = self._positive_int(
            cleanup_cfg.get('uploaded_file_retention_days'),
            DEFAULT_UPLOAD_FILE_RETENTION_DAYS,
            'storage.cleanup.uploaded_file_retention_days',
        )
        log_retention_days = self._positive_int(
            cleanup_cfg.get('log_retention_days'),
            DEFAULT_LOG_RETENTION_DAYS,
            'storage.cleanup.log_retention_days',
        )

        database_cfg = self.ap.instance_config.data.get('database', {})
        database_type = database_cfg.get('use', 'sqlite')
        database_path = (
            Path(database_cfg.get('sqlite', {}).get('path', 'data/langbot.db')) if database_type == 'sqlite' else None
        )
        is_oss_singleton = await self._is_oss_singleton(context)
        if is_oss_singleton:
            roots: list[tuple[str, Path | None]] = [
                ('database', database_path),
                ('logs', Path('data/logs')),
                ('storage', Path('data/storage')),
                ('vector_store', Path('data/chroma')),
                ('plugins', Path('data/plugins')),
                ('mcp', Path('data/mcp')),
                ('temp', Path('data/temp')),
            ]
        else:
            scoped_storage_path = Path('data/storage') / self.ap.storage_mgr.scoped_prefix(context)
            roots = [('storage', scoped_storage_path)]

        sections = []
        for key, path in roots:
            sections.append(
                {
                    'key': key,
                    'path': str(path) if path else '',
                    'exists': path.exists() if path else False,
                    'size_bytes': self._path_size(path) if path else 0,
                    'file_count': self._file_count(path) if path else 0,
                }
            )

        monitoring_counts = await self._monitoring_counts(context)
        binary_storage = await self._binary_storage_stats(context)
        upload_candidates = await self._expired_uploaded_candidates(context, upload_retention_days)
        log_candidates = self._expired_log_candidates(log_retention_days) if is_oss_singleton else []

        return {
            'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'cleanup_policy': {
                'uploaded_file_retention_days': upload_retention_days,
                'log_retention_days': log_retention_days,
            },
            'sections': sections,
            'database': {
                'type': database_type,
                'monitoring_counts': monitoring_counts,
                'binary_storage': binary_storage,
            },
            'cleanup_candidates': {
                'uploaded_files': upload_candidates,
                'log_files': log_candidates,
            },
            'tasks': self.ap.task_mgr.get_stats() if is_oss_singleton and self.ap.task_mgr else {},
        }

    async def _is_oss_singleton(self, context: TenantContext) -> bool:
        try:
            await self.ap.workspace_service.get_local_execution_binding(
                require_workspace_uuid(context),
                expected_generation=getattr(context, 'placement_generation', None),
            )
        except Exception:
            return False
        return True

    async def _cleanup_expired_uploaded_files(
        self,
        context: ExecutionContext,
        retention_days: int,
    ) -> int:
        provider = self.ap.storage_mgr.storage_provider
        provider_name = provider.__class__.__name__
        if provider_name == 'LocalStorageProvider':
            candidates = self._expired_local_upload_candidates(
                context,
                retention_days,
                include_paths=True,
            )
            deleted = 0
            for item in candidates:
                try:
                    os.remove(item['path'])
                    deleted += 1
                except FileNotFoundError:
                    pass
                except Exception as e:
                    self.ap.logger.warning(f'Failed to delete expired uploaded file {item["key"]}: {e}')
            return deleted

        if provider_name == 'S3StorageProvider':
            return await self._cleanup_expired_s3_uploaded_files(context, retention_days)

        return 0

    async def _expired_uploaded_candidates(
        self,
        context: TenantContext,
        retention_days: int,
    ) -> list[dict[str, Any]]:
        provider_name = self.ap.storage_mgr.storage_provider.__class__.__name__
        if provider_name == 'LocalStorageProvider':
            return self._expired_local_upload_candidates(context, retention_days)
        if provider_name == 'S3StorageProvider':
            return await self._expired_s3_upload_candidates(context, retention_days)
        return []

    async def _cleanup_expired_s3_uploaded_files(
        self,
        context: ExecutionContext,
        retention_days: int,
    ) -> int:
        provider = self.ap.storage_mgr.storage_provider
        candidates = await self._expired_s3_upload_candidates(context, retention_days)
        deleted = 0
        for item in candidates:
            await provider.delete(item['key'])
            deleted += 1
        return deleted

    async def _expired_s3_upload_candidates(
        self,
        context: TenantContext,
        retention_days: int,
    ) -> list[dict[str, Any]]:
        provider = self.ap.storage_mgr.storage_provider
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)
        candidates = []
        paginator = provider.s3_client.get_paginator('list_objects_v2')

        seen_prefixes: set[str] = set()
        for owner_type in UPLOAD_OWNER_TYPES:
            prefix = self.ap.storage_mgr.scoped_prefix(context, owner_type=owner_type)
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            for page in paginator.paginate(Bucket=provider.bucket_name, Prefix=prefix):
                for obj in page.get('Contents', []):
                    key = obj.get('Key', '')
                    last_modified = obj.get('LastModified')
                    if not self._is_uploaded_file_key(context, key):
                        continue
                    if last_modified and last_modified < cutoff:
                        candidates.append(
                            {
                                'key': key,
                                'size_bytes': obj.get('Size', 0),
                                'modified_at': last_modified.isoformat(),
                            }
                        )

        return candidates

    def _cleanup_expired_log_files(self, retention_days: int) -> int:
        deleted = 0
        for item in self._expired_log_candidates(retention_days, include_paths=True):
            try:
                os.remove(item['path'])
                deleted += 1
            except FileNotFoundError:
                pass
            except Exception as e:
                self.ap.logger.warning(f'Failed to delete expired log file {item["name"]}: {e}')
        return deleted

    def _expired_local_upload_candidates(
        self,
        context: TenantContext,
        retention_days: int,
        include_paths: bool = False,
    ) -> list[dict[str, Any]]:
        storage_root = Path('data/storage')
        cutoff = datetime.datetime.now().timestamp() - retention_days * 86400
        candidates = []
        seen_roots: set[Path] = set()
        for owner_type in UPLOAD_OWNER_TYPES:
            scoped_root = storage_root / self.ap.storage_mgr.scoped_prefix(context, owner_type=owner_type)
            if scoped_root in seen_roots:
                continue
            seen_roots.add(scoped_root)
            if not scoped_root.exists():
                continue
            for entry in scoped_root.rglob('*'):
                if not entry.is_file():
                    continue
                stat = entry.stat()
                if stat.st_mtime >= cutoff:
                    continue
                item = {
                    'key': entry.relative_to(storage_root).as_posix(),
                    'size_bytes': stat.st_size,
                    'modified_at': datetime.datetime.fromtimestamp(
                        stat.st_mtime,
                        datetime.timezone.utc,
                    ).isoformat(),
                }
                if include_paths:
                    item['path'] = str(entry)
                candidates.append(item)
        return candidates

    def _expired_log_candidates(self, retention_days: int, include_paths: bool = False) -> list[dict[str, Any]]:
        log_root = Path('data/logs')
        if not log_root.exists():
            return []

        cutoff_date = datetime.date.today() - datetime.timedelta(days=retention_days - 1)
        candidates = []
        for entry in log_root.iterdir():
            if not entry.is_file():
                continue
            match = LOG_FILE_PATTERN.match(entry.name)
            if not match:
                continue
            try:
                file_date = datetime.date.fromisoformat(match.group(1))
            except ValueError:
                continue
            if file_date >= cutoff_date:
                continue
            stat = entry.stat()
            item = {
                'name': entry.name,
                'date': file_date.isoformat(),
                'size_bytes': stat.st_size,
            }
            if include_paths:
                item['path'] = str(entry)
            candidates.append(item)
        return candidates

    def _is_uploaded_file_key(self, context: TenantContext, key: str) -> bool:
        return any(
            key.startswith(self.ap.storage_mgr.scoped_prefix(context, owner_type=owner_type))
            and self.ap.storage_mgr.is_scoped_object_key(key, expected_owner_type=owner_type)
            for owner_type in UPLOAD_OWNER_TYPES
        )

    async def _monitoring_counts(self, context: TenantContext) -> dict[str, int]:
        workspace_uuid = require_workspace_uuid(context)
        tables = {
            'messages': (persistence_monitoring.MonitoringMessage, persistence_monitoring.MonitoringMessage.id),
            'llm_calls': (persistence_monitoring.MonitoringLLMCall, persistence_monitoring.MonitoringLLMCall.id),
            'tool_calls': (persistence_monitoring.MonitoringToolCall, persistence_monitoring.MonitoringToolCall.id),
            'embedding_calls': (
                persistence_monitoring.MonitoringEmbeddingCall,
                persistence_monitoring.MonitoringEmbeddingCall.id,
            ),
            'errors': (persistence_monitoring.MonitoringError, persistence_monitoring.MonitoringError.id),
            'sessions': (
                persistence_monitoring.MonitoringSession,
                persistence_monitoring.MonitoringSession.session_id,
            ),
            'feedback': (persistence_monitoring.MonitoringFeedback, persistence_monitoring.MonitoringFeedback.id),
        }
        counts: dict[str, int] = {}
        for key, (model, column) in tables.items():
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(sqlalchemy.func.count(column)).where(model.workspace_uuid == workspace_uuid)
            )
            counts[key] = result.scalar() or 0
        return counts

    async def _binary_storage_stats(self, context: TenantContext) -> dict[str, Any]:
        workspace_uuid = require_workspace_uuid(context)
        count_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(sqlalchemy.func.count(persistence_bstorage.BinaryStorage.unique_key)).where(
                persistence_bstorage.BinaryStorage.workspace_uuid == workspace_uuid
            )
        )
        size_bytes = None
        try:
            size_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(
                    sqlalchemy.func.sum(sqlalchemy.func.length(persistence_bstorage.BinaryStorage.value))
                ).where(persistence_bstorage.BinaryStorage.workspace_uuid == workspace_uuid)
            )
            size_bytes = size_result.scalar() or 0
        except Exception as e:
            self.ap.logger.warning(f'Failed to estimate binary storage size: {e}')

        return {
            'count': count_result.scalar() or 0,
            'size_bytes': size_bytes,
        }

    def _path_size(self, path: Path) -> int:
        if not path.exists():
            return 0
        if path.is_file():
            return path.stat().st_size
        total = 0
        for root, _, files in os.walk(path):
            for file_name in files:
                file_path = Path(root) / file_name
                try:
                    total += file_path.stat().st_size
                except FileNotFoundError:
                    pass
        return total

    def _file_count(self, path: Path) -> int:
        if not path.exists():
            return 0
        if path.is_file():
            return 1
        count = 0
        for _, _, files in os.walk(path):
            count += len(files)
        return count

    def _positive_int(self, value: Any, default: int, name: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            self.ap.logger.warning(f'Invalid {name}: {value!r}, using {default}')
            return default
        if parsed < 1:
            self.ap.logger.warning(f'Invalid {name}: {value!r}, using {default}')
            return default
        return parsed
