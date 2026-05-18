from __future__ import annotations

import datetime
import os
import re
from pathlib import Path
from typing import Any

import sqlalchemy

from ....core import app
from ....entity.persistence import bstorage as persistence_bstorage
from ....entity.persistence import monitoring as persistence_monitoring


LOG_FILE_PATTERN = re.compile(r'^langbot-(\d{4}-\d{2}-\d{2})\.log(?:\.\d+)?$')
DEFAULT_UPLOAD_FILE_RETENTION_DAYS = 7
DEFAULT_LOG_RETENTION_DAYS = 3


class MaintenanceService:
    """Storage maintenance and diagnostics."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def cleanup_expired_files(self) -> dict[str, int]:
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
            'uploaded_files': await self._cleanup_expired_uploaded_files(upload_retention_days),
            'log_files': self._cleanup_expired_log_files(log_retention_days),
        }

    async def get_storage_analysis(self) -> dict[str, Any]:
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
        roots: list[tuple[str, Path | None]] = [
            ('database', database_path),
            ('logs', Path('data/logs')),
            ('storage', Path('data/storage')),
            ('vector_store', Path('data/chroma')),
            ('plugins', Path('data/plugins')),
            ('mcp', Path('data/mcp')),
            ('temp', Path('data/temp')),
        ]

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

        monitoring_counts = await self._monitoring_counts()
        binary_storage = await self._binary_storage_stats()
        upload_candidates = await self._expired_uploaded_candidates(upload_retention_days)
        log_candidates = self._expired_log_candidates(log_retention_days)

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
            'tasks': self.ap.task_mgr.get_stats() if self.ap.task_mgr else {},
        }

    async def _cleanup_expired_uploaded_files(self, retention_days: int) -> int:
        provider = self.ap.storage_mgr.storage_provider
        provider_name = provider.__class__.__name__
        if provider_name == 'LocalStorageProvider':
            candidates = self._expired_local_upload_candidates(retention_days, include_paths=True)
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
            return await self._cleanup_expired_s3_uploaded_files(retention_days)

        return 0

    async def _expired_uploaded_candidates(self, retention_days: int) -> list[dict[str, Any]]:
        provider_name = self.ap.storage_mgr.storage_provider.__class__.__name__
        if provider_name == 'LocalStorageProvider':
            return self._expired_local_upload_candidates(retention_days)
        if provider_name == 'S3StorageProvider':
            return await self._expired_s3_upload_candidates(retention_days)
        return []

    async def _cleanup_expired_s3_uploaded_files(self, retention_days: int) -> int:
        provider = self.ap.storage_mgr.storage_provider
        candidates = await self._expired_s3_upload_candidates(retention_days)
        deleted = 0
        for item in candidates:
            await provider.delete(item['key'])
            deleted += 1
        return deleted

    async def _expired_s3_upload_candidates(self, retention_days: int) -> list[dict[str, Any]]:
        provider = self.ap.storage_mgr.storage_provider
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)
        candidates = []
        paginator = provider.s3_client.get_paginator('list_objects_v2')

        for page in paginator.paginate(Bucket=provider.bucket_name):
            for obj in page.get('Contents', []):
                key = obj.get('Key', '')
                last_modified = obj.get('LastModified')
                if not self._is_uploaded_file_key(key):
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
        self, retention_days: int, include_paths: bool = False
    ) -> list[dict[str, Any]]:
        storage_root = Path('data/storage')
        if not storage_root.exists():
            return []

        cutoff = datetime.datetime.now().timestamp() - retention_days * 86400
        candidates = []
        for entry in storage_root.iterdir():
            if not entry.is_file() or not self._is_uploaded_file_key(entry.name):
                continue
            stat = entry.stat()
            if stat.st_mtime >= cutoff:
                continue
            item = {
                'key': entry.name,
                'size_bytes': stat.st_size,
                'modified_at': datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc).isoformat(),
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

    def _is_uploaded_file_key(self, key: str) -> bool:
        return '/' not in key and not key.startswith('plugin_config_')

    async def _monitoring_counts(self) -> dict[str, int]:
        tables = {
            'messages': persistence_monitoring.MonitoringMessage.id,
            'llm_calls': persistence_monitoring.MonitoringLLMCall.id,
            'embedding_calls': persistence_monitoring.MonitoringEmbeddingCall.id,
            'errors': persistence_monitoring.MonitoringError.id,
            'sessions': persistence_monitoring.MonitoringSession.session_id,
            'feedback': persistence_monitoring.MonitoringFeedback.id,
        }
        counts: dict[str, int] = {}
        for key, column in tables.items():
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(sqlalchemy.func.count(column)))
            counts[key] = result.scalar() or 0
        return counts

    async def _binary_storage_stats(self) -> dict[str, Any]:
        count_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(sqlalchemy.func.count(persistence_bstorage.BinaryStorage.unique_key))
        )
        size_bytes = None
        try:
            size_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(sqlalchemy.func.sum(sqlalchemy.func.length(persistence_bstorage.BinaryStorage.value)))
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
