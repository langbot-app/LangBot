from __future__ import annotations

import asyncio
import datetime
import os
import time
from pathlib import Path

import sqlalchemy

from ....core import app
from ....entity.persistence import monitoring as persistence_monitoring
from ....utils import constants


class SystemService:
    """System settings and background maintenance service."""

    _loop_poll_seconds = 60

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self._last_cleanup_started_at = 0.0

    @staticmethod
    def _default_auto_cleanup_settings() -> dict:
        return {
            'enabled': False,
            'interval_hours': 24,
            'log_retention_days': 7,
            'monitoring_retention_days': 30,
            'runtime_session_idle_hours': 24,
        }

    @staticmethod
    def _coerce_non_negative_int(value, field_name: str) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{field_name} must be an integer') from exc

        if result < 0:
            raise ValueError(f'{field_name} must be greater than or equal to 0')

        return result

    def get_auto_cleanup_settings(self) -> dict:
        settings = self._default_auto_cleanup_settings()
        settings.update(self.ap.instance_config.data.get('system', {}).get('auto_cleanup', {}))
        return settings

    def normalize_auto_cleanup_settings(self, settings: dict | None) -> dict:
        settings = settings or {}

        interval_hours = self._coerce_non_negative_int(settings.get('interval_hours', 24), 'interval_hours')
        if interval_hours <= 0:
            raise ValueError('interval_hours must be greater than 0')

        return {
            'enabled': bool(settings.get('enabled', False)),
            'interval_hours': interval_hours,
            'log_retention_days': self._coerce_non_negative_int(
                settings.get('log_retention_days', 7), 'log_retention_days'
            ),
            'monitoring_retention_days': self._coerce_non_negative_int(
                settings.get('monitoring_retention_days', 30), 'monitoring_retention_days'
            ),
            'runtime_session_idle_hours': self._coerce_non_negative_int(
                settings.get('runtime_session_idle_hours', 24), 'runtime_session_idle_hours'
            ),
        }

    async def update_auto_cleanup_settings(self, settings: dict | None) -> dict:
        normalized = self.normalize_auto_cleanup_settings(settings)

        system_config = self.ap.instance_config.data.setdefault('system', {})
        system_config['auto_cleanup'] = normalized
        await self.ap.instance_config.dump_config()

        return normalized

    def get_system_info(self) -> dict:
        return {
            'version': constants.semantic_version,
            'debug': constants.debug_mode,
            'edition': constants.edition,
            'enable_marketplace': self.ap.instance_config.data.get('plugin', {}).get('enable_marketplace', True),
            'cloud_service_url': self.ap.instance_config.data.get('space', {}).get('url', 'https://space.langbot.app'),
            'allow_modify_login_info': self.ap.instance_config.data.get('system', {}).get(
                'allow_modify_login_info', True
            ),
            'disable_models_service': self.ap.instance_config.data.get('space', {}).get(
                'disable_models_service', False
            ),
            'limitation': self.ap.instance_config.data.get('system', {}).get('limitation', {}),
            'auto_cleanup': self.get_auto_cleanup_settings(),
        }

    async def run_auto_cleanup_loop(self) -> None:
        while True:
            try:
                settings = self.get_auto_cleanup_settings()
                interval_hours = max(settings.get('interval_hours', 24), 1)
                interval_seconds = interval_hours * 3600
                should_run = settings.get('enabled', False) and (
                    self._last_cleanup_started_at <= 0
                    or (time.time() - self._last_cleanup_started_at) >= interval_seconds
                )

                if should_run:
                    self._last_cleanup_started_at = time.time()
                    result = await self.run_auto_cleanup_once(settings)
                    self.ap.logger.info(
                        'Auto cleanup finished: logs=%s monitoring=%s sessions=%s'
                        % (
                            result['deleted_log_files'],
                            result['deleted_monitoring_rows'],
                            result['deleted_runtime_sessions'],
                        )
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.ap.logger.error(f'Auto cleanup failed: {exc}')

            await asyncio.sleep(self._loop_poll_seconds)

    async def run_auto_cleanup_once(self, settings: dict | None = None) -> dict:
        settings = self.normalize_auto_cleanup_settings(settings or self.get_auto_cleanup_settings())

        deleted_log_files = await self._cleanup_log_files(settings['log_retention_days'])
        deleted_monitoring_rows = await self._cleanup_monitoring_records(settings['monitoring_retention_days'])
        deleted_runtime_sessions = await self._cleanup_runtime_sessions(settings['runtime_session_idle_hours'])

        return {
            'deleted_log_files': deleted_log_files,
            'deleted_monitoring_rows': deleted_monitoring_rows,
            'deleted_runtime_sessions': deleted_runtime_sessions,
            'finished_at': datetime.datetime.utcnow().isoformat(),
        }

    async def _cleanup_log_files(self, retention_days: int) -> int:
        if retention_days <= 0:
            return 0

        log_dir = Path('data/logs')
        if not log_dir.exists():
            return 0

        cutoff_ts = time.time() - retention_days * 24 * 3600
        deleted = 0

        for file_path in log_dir.glob('langbot-*.log*'):
            try:
                if not file_path.is_file():
                    continue

                if file_path.stat().st_mtime >= cutoff_ts:
                    continue

                os.remove(file_path)
                deleted += 1
            except FileNotFoundError:
                continue

        return deleted

    async def _cleanup_monitoring_records(self, retention_days: int) -> int:
        if retention_days <= 0:
            return 0

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)

        statements = [
            sqlalchemy.delete(persistence_monitoring.MonitoringMessage).where(
                persistence_monitoring.MonitoringMessage.timestamp < cutoff
            ),
            sqlalchemy.delete(persistence_monitoring.MonitoringLLMCall).where(
                persistence_monitoring.MonitoringLLMCall.timestamp < cutoff
            ),
            sqlalchemy.delete(persistence_monitoring.MonitoringEmbeddingCall).where(
                persistence_monitoring.MonitoringEmbeddingCall.timestamp < cutoff
            ),
            sqlalchemy.delete(persistence_monitoring.MonitoringError).where(
                persistence_monitoring.MonitoringError.timestamp < cutoff
            ),
            sqlalchemy.delete(persistence_monitoring.MonitoringSession).where(
                persistence_monitoring.MonitoringSession.last_activity < cutoff
            ),
        ]

        deleted = 0
        for statement in statements:
            result = await self.ap.persistence_mgr.execute_async(statement)
            deleted += max(result.rowcount or 0, 0)

        return deleted

    async def _cleanup_runtime_sessions(self, idle_hours: int) -> int:
        if idle_hours <= 0:
            return 0

        return self.ap.sess_mgr.cleanup_inactive_sessions(idle_hours * 3600)
