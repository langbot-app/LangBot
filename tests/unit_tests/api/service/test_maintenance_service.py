"""
Unit tests for MaintenanceService.

Tests storage maintenance and diagnostics including:
- Cleanup expired files
- Storage analysis
- File counting and sizing
- Monitoring counts
- Binary storage stats

Source: src/langbot/pkg/api/http/service/maintenance.py
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from types import SimpleNamespace
import datetime
from pathlib import Path

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.service.maintenance import MaintenanceService
from langbot.pkg.api.http.context import ExecutionContext, PrincipalContext, PrincipalType
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.bstorage import BinaryStorage
from langbot.pkg.entity.persistence.monitoring import MonitoringMessage
from langbot.pkg.entity.persistence.workspace import Workspace


pytestmark = pytest.mark.asyncio
TEST_CONTEXT = ExecutionContext(
    instance_uuid='test-instance',
    workspace_uuid='test-workspace',
    placement_generation=1,
)


@pytest.fixture(autouse=True)
def assume_oss_singleton(monkeypatch):
    async def is_oss_singleton(_self, _context):
        return True

    monkeypatch.setattr(MaintenanceService, '_is_oss_singleton', is_oss_singleton)


def _create_mock_result(scalar_value=None):
    """Create mock result object for persistence queries."""
    result = Mock()
    result.scalar = Mock(return_value=scalar_value)
    return result


def _scoped_storage_manager():
    prefix = 'instances/i/workspaces/w/generations/1/owners/upload/o/'
    return SimpleNamespace(
        scoped_prefix=Mock(return_value=prefix),
        is_scoped_object_key=Mock(side_effect=lambda key, **_: key == f'{prefix}uploaded_file.txt'),
    )


class TestMaintenanceServiceCleanupExpiredFiles:
    """Tests for cleanup_expired_files method."""

    async def test_cleanup_expired_files_default_retention(self):
        """Uses default retention days when config not set."""
        # Setup
        ap = SimpleNamespace()
        ap.storage_mgr = _scoped_storage_manager()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.storage_mgr = SimpleNamespace()

        # Create a proper mock object with __class__.__name__
        storage_provider = MagicMock()
        storage_provider.__class__.__name__ = 'LocalStorageProvider'
        ap.storage_mgr.storage_provider = storage_provider

        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        service = MaintenanceService(ap)

        # Mock the internal cleanup methods - one is async, one is not
        service._cleanup_expired_uploaded_files = AsyncMock(return_value=0)
        service._cleanup_expired_log_files = Mock(return_value=0)  # NOT async!

        # Execute
        result = await service.cleanup_expired_files(TEST_CONTEXT)

        # Verify - returns counts
        assert 'uploaded_files' in result
        assert 'log_files' in result
        assert result['uploaded_files'] == 0
        assert result['log_files'] == 0

    async def test_cleanup_expired_files_custom_retention(self):
        """Uses custom retention days from config."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'storage': {
                'cleanup': {
                    'uploaded_file_retention_days': 14,
                    'log_retention_days': 7,
                }
            }
        }
        ap.storage_mgr = SimpleNamespace()

        storage_provider = MagicMock()
        storage_provider.__class__.__name__ = 'LocalStorageProvider'
        ap.storage_mgr.storage_provider = storage_provider

        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        service = MaintenanceService(ap)

        # Mock the internal cleanup methods
        service._cleanup_expired_uploaded_files = AsyncMock(return_value=2)
        service._cleanup_expired_log_files = Mock(return_value=3)  # NOT async

        # Execute
        result = await service.cleanup_expired_files(TEST_CONTEXT)

        # Verify
        assert result['uploaded_files'] == 2
        assert result['log_files'] == 3

    async def test_cleanup_expired_files_s3_provider(self):
        """Handles S3StorageProvider correctly."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.storage_mgr = SimpleNamespace()

        # Mock S3 provider
        s3_provider = MagicMock()
        s3_provider.__class__.__name__ = 'S3StorageProvider'
        s3_provider.delete = AsyncMock()
        ap.storage_mgr.storage_provider = s3_provider
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        service = MaintenanceService(ap)

        # Mock the internal cleanup methods
        service._cleanup_expired_uploaded_files = AsyncMock(return_value=1)
        service._cleanup_expired_log_files = Mock(return_value=0)  # NOT async

        # Execute
        result = await service.cleanup_expired_files(TEST_CONTEXT)

        # Verify
        assert result['uploaded_files'] == 1
        assert result['log_files'] == 0

    async def test_cleanup_expired_files_invalid_retention(self):
        """Uses default for invalid retention config."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'storage': {
                'cleanup': {
                    'uploaded_file_retention_days': 'invalid',  # Invalid
                    'log_retention_days': 0,  # Invalid (less than 1)
                }
            }
        }
        ap.storage_mgr = SimpleNamespace()

        storage_provider = MagicMock()
        storage_provider.__class__.__name__ = 'LocalStorageProvider'
        ap.storage_mgr.storage_provider = storage_provider

        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        service = MaintenanceService(ap)

        # Mock the internal cleanup methods
        service._cleanup_expired_uploaded_files = AsyncMock(return_value=0)
        service._cleanup_expired_log_files = Mock(return_value=0)  # NOT async

        # Execute
        result = await service.cleanup_expired_files(TEST_CONTEXT)

        # Verify - warning logged, defaults used
        assert ap.logger.warning.called
        assert 'uploaded_files' in result


class TestMaintenanceServiceGetStorageAnalysis:
    """Tests for get_storage_analysis method."""

    async def test_get_storage_analysis_basic(self):
        """Returns basic storage analysis."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'database': {'use': 'sqlite', 'sqlite': {'path': 'data/langbot.db'}}}
        ap.persistence_mgr = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()
        ap.task_mgr = SimpleNamespace()
        ap.task_mgr.get_stats = Mock(return_value={'running': 0})

        # Mock monitoring counts
        count_result = _create_mock_result(scalar_value=10)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=count_result)

        service = MaintenanceService(ap)

        # Mock file operations
        service._path_size = Mock(return_value=1000)
        service._file_count = Mock(return_value=5)
        service._monitoring_counts = AsyncMock(return_value={'messages': 10, 'errors': 0})
        service._binary_storage_stats = AsyncMock(return_value={'count': 5, 'size_bytes': 500})
        service._expired_uploaded_candidates = AsyncMock(return_value=[])
        service._expired_log_candidates = Mock(return_value=[])

        # Execute
        result = await service.get_storage_analysis(TEST_CONTEXT)

        # Verify
        assert 'generated_at' in result
        assert 'cleanup_policy' in result
        assert 'sections' in result
        assert 'database' in result
        assert 'cleanup_candidates' in result

    async def test_get_storage_analysis_sections(self):
        """Returns all storage sections."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'database': {'use': 'postgresql'}}
        ap.persistence_mgr = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()
        ap.task_mgr = None

        count_result = _create_mock_result(scalar_value=0)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=count_result)

        service = MaintenanceService(ap)

        service._path_size = Mock(return_value=0)
        service._file_count = Mock(return_value=0)
        service._monitoring_counts = AsyncMock(return_value={})
        service._binary_storage_stats = AsyncMock(return_value={'count': 0, 'size_bytes': 0})
        service._expired_uploaded_candidates = AsyncMock(return_value=[])
        service._expired_log_candidates = Mock(return_value=[])

        # Execute
        result = await service.get_storage_analysis(TEST_CONTEXT)

        # Verify - all sections present
        sections = {s['key'] for s in result['sections']}
        assert 'database' in sections
        assert 'logs' in sections
        assert 'storage' in sections
        assert 'vector_store' in sections
        assert 'plugins' in sections
        assert 'mcp' in sections
        assert 'temp' in sections

    async def test_get_storage_analysis_postgresql(self):
        """Handles PostgreSQL database type."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'database': {'use': 'postgresql'}}
        ap.persistence_mgr = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()
        ap.task_mgr = None

        count_result = _create_mock_result(scalar_value=0)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=count_result)

        service = MaintenanceService(ap)

        service._path_size = Mock(return_value=0)
        service._file_count = Mock(return_value=0)
        service._monitoring_counts = AsyncMock(return_value={})
        service._binary_storage_stats = AsyncMock(return_value={'count': 0, 'size_bytes': None})
        service._expired_uploaded_candidates = AsyncMock(return_value=[])
        service._expired_log_candidates = Mock(return_value=[])

        # Execute
        result = await service.get_storage_analysis(TEST_CONTEXT)

        # Verify
        assert result['database']['type'] == 'postgresql'

    async def test_get_storage_analysis_with_cleanup_candidates(self):
        """Returns cleanup candidates in analysis."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.persistence_mgr = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()
        ap.task_mgr = None

        count_result = _create_mock_result(scalar_value=0)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=count_result)

        service = MaintenanceService(ap)

        service._path_size = Mock(return_value=0)
        service._file_count = Mock(return_value=0)
        service._monitoring_counts = AsyncMock(return_value={})
        service._binary_storage_stats = AsyncMock(return_value={'count': 0, 'size_bytes': 0})
        service._expired_uploaded_candidates = AsyncMock(return_value=[{'key': 'old_file', 'size_bytes': 100}])
        service._expired_log_candidates = Mock(return_value=[{'name': 'old_log', 'size_bytes': 50}])

        # Execute
        result = await service.get_storage_analysis(TEST_CONTEXT)

        # Verify
        assert len(result['cleanup_candidates']['uploaded_files']) == 1
        assert len(result['cleanup_candidates']['log_files']) == 1


class TestMaintenanceServiceMonitoringCounts:
    """Tests for _monitoring_counts method."""

    async def test_monitoring_counts_returns_counts(self):
        """Returns counts for all monitoring tables."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        count_result = _create_mock_result(scalar_value=42)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=count_result)

        service = MaintenanceService(ap)

        # Execute
        result = await service._monitoring_counts(TEST_CONTEXT)

        # Verify - all table keys present
        assert 'messages' in result
        assert 'llm_calls' in result
        assert 'embedding_calls' in result
        assert 'errors' in result
        assert 'sessions' in result
        assert 'feedback' in result

    async def test_monitoring_counts_zero_results(self):
        """Returns zero counts when tables empty."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        count_result = _create_mock_result(scalar_value=0)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=count_result)

        service = MaintenanceService(ap)

        # Execute
        result = await service._monitoring_counts(TEST_CONTEXT)

        # Verify - all zero
        assert all(v == 0 for v in result.values())


class TestMaintenanceServiceBinaryStorageStats:
    """Tests for _binary_storage_stats method."""

    async def test_binary_storage_stats_returns_stats(self):
        """Returns count and size for binary storage."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        # Mock count result
        count_result = _create_mock_result(scalar_value=10)
        # Mock size result
        size_result = _create_mock_result(scalar_value=5000)

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return count_result
            return size_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = MaintenanceService(ap)

        # Execute
        result = await service._binary_storage_stats(TEST_CONTEXT)

        # Verify
        assert result['count'] == 10
        assert result['size_bytes'] == 5000

    async def test_binary_storage_stats_size_error(self):
        """Handles error when calculating size."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        count_result = _create_mock_result(scalar_value=5)

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return count_result
            raise Exception('Size calculation error')

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)

        service = MaintenanceService(ap)

        # Execute
        result = await service._binary_storage_stats(TEST_CONTEXT)

        # Verify - warning logged, size_bytes None or 0
        assert ap.logger.warning.called
        assert result['count'] == 5


class TestMaintenanceServicePathSize:
    """Tests for _path_size method."""

    def test_path_size_nonexistent_path(self):
        """Returns 0 for nonexistent path."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()

        service = MaintenanceService(ap)

        # Execute
        result = service._path_size(Path('/nonexistent/path'))

        # Verify
        assert result == 0

    def test_path_size_single_file(self):
        """Returns size for single file."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()

        service = MaintenanceService(ap)

        # Mock file
        mock_stat = Mock()
        mock_stat.st_size = 100

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=True):
                with patch.object(Path, 'stat', return_value=mock_stat):
                    result = service._path_size(Path('test.txt'))

        # Verify
        assert result == 100

    def test_path_size_directory(self):
        """Returns total size for directory."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()

        service = MaintenanceService(ap)

        # Mock os.walk
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=False):
                with patch('os.walk') as mock_walk:
                    mock_walk.return_value = [
                        ('/test_dir', [], ['file1.txt', 'file2.txt']),
                    ]

                    # Mock file stat
                    mock_stat = Mock()
                    mock_stat.st_size = 50

                    with patch.object(Path, 'stat', return_value=mock_stat):
                        result = service._path_size(Path('/test_dir'))

        # Verify - 2 files * 50 bytes
        assert result == 100


class TestMaintenanceServiceFileCount:
    """Tests for _file_count method."""

    def test_file_count_nonexistent_path(self):
        """Returns 0 for nonexistent path."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()

        service = MaintenanceService(ap)

        # Execute
        result = service._file_count(Path('/nonexistent/path'))

        # Verify
        assert result == 0

    def test_file_count_single_file(self):
        """Returns 1 for single file."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()

        service = MaintenanceService(ap)

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=True):
                result = service._file_count(Path('test.txt'))

        # Verify
        assert result == 1

    def test_file_count_directory(self):
        """Returns file count for directory."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()

        service = MaintenanceService(ap)

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_file', return_value=False):
                with patch('os.walk') as mock_walk:
                    mock_walk.return_value = [
                        ('/test_dir', [], ['file1.txt', 'file2.txt', 'file3.txt']),
                    ]
                    result = service._file_count(Path('/test_dir'))

        # Verify
        assert result == 3


class TestMaintenanceServicePositiveInt:
    """Tests for _positive_int helper method."""

    def test_positive_int_valid_value(self):
        """Returns valid positive integer."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        service = MaintenanceService(ap)

        # Execute
        result = service._positive_int(7, 5, 'test_param')

        # Verify
        assert result == 7
        assert not ap.logger.warning.called

    def test_positive_int_invalid_string(self):
        """Returns default for invalid string."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        service = MaintenanceService(ap)

        # Execute
        result = service._positive_int('invalid', 5, 'test_param')

        # Verify
        assert result == 5
        assert ap.logger.warning.called

    def test_positive_int_invalid_none(self):
        """Returns default for None."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        service = MaintenanceService(ap)

        # Execute
        result = service._positive_int(None, 5, 'test_param')

        # Verify
        assert result == 5
        assert ap.logger.warning.called

    def test_positive_int_negative_value(self):
        """Returns default for negative value."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        service = MaintenanceService(ap)

        # Execute
        result = service._positive_int(-1, 5, 'test_param')

        # Verify
        assert result == 5
        assert ap.logger.warning.called

    def test_positive_int_zero_value(self):
        """Returns default for zero value."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.logger.warning = Mock()

        service = MaintenanceService(ap)

        # Execute
        result = service._positive_int(0, 5, 'test_param')

        # Verify
        assert result == 5
        assert ap.logger.warning.called


class TestMaintenanceServiceIsUploadedFileKey:
    """Tests for _is_uploaded_file_key helper method."""

    def test_is_uploaded_file_key_valid(self):
        """Returns True for valid upload file key."""
        # Setup
        ap = SimpleNamespace()
        ap.storage_mgr = _scoped_storage_manager()

        service = MaintenanceService(ap)

        # Execute - simple filename without path
        key = f'{ap.storage_mgr.scoped_prefix(TEST_CONTEXT, owner_type="upload")}uploaded_file.txt'
        result = service._is_uploaded_file_key(TEST_CONTEXT, key)

        # Verify
        assert result is True

    def test_is_uploaded_file_key_with_path(self):
        """Returns False for key with path separator."""
        # Setup
        ap = SimpleNamespace()
        ap.storage_mgr = _scoped_storage_manager()

        service = MaintenanceService(ap)

        # Execute - key with path
        result = service._is_uploaded_file_key(TEST_CONTEXT, 'path/to/file.txt')

        # Verify
        assert result is False

    def test_is_uploaded_file_key_plugin_config(self):
        """Returns False for plugin config prefix."""
        # Setup
        ap = SimpleNamespace()
        ap.storage_mgr = _scoped_storage_manager()

        service = MaintenanceService(ap)

        # Execute - plugin config file
        result = service._is_uploaded_file_key(TEST_CONTEXT, 'plugin_config_some_plugin.json')

        # Verify
        assert result is False


class TestMaintenanceServiceExpiredLogCandidates:
    """Tests for _expired_log_candidates method."""

    def test_expired_log_candidates_nonexistent_dir(self):
        """Returns empty list when logs dir not exists."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.storage_mgr = _scoped_storage_manager()

        service = MaintenanceService(ap)

        with patch.object(Path, 'exists', return_value=False):
            result = service._expired_log_candidates(3)

        # Verify
        assert result == []

    def test_expired_log_candidates_matches_pattern(self):
        """Matches log file pattern correctly."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()

        service = MaintenanceService(ap)

        # Mock directory with log files
        old_date = datetime.date.today() - datetime.timedelta(days=10)
        old_log_name = f'langbot-{old_date.isoformat()}.log'
        recent_log_name = f'langbot-{datetime.date.today().isoformat()}.log'

        mock_entry_old = Mock(spec=Path)
        mock_entry_old.is_file = Mock(return_value=True)
        mock_entry_old.name = old_log_name
        mock_stat = Mock()
        mock_stat.st_size = 1000
        mock_entry_old.stat = Mock(return_value=mock_stat)

        mock_entry_recent = Mock(spec=Path)
        mock_entry_recent.is_file = Mock(return_value=True)
        mock_entry_recent.name = recent_log_name
        mock_stat2 = Mock()
        mock_stat2.st_size = 500
        mock_entry_recent.stat = Mock(return_value=mock_stat2)

        # Non-log file
        mock_entry_other = Mock(spec=Path)
        mock_entry_other.is_file = Mock(return_value=True)
        mock_entry_other.name = 'other_file.txt'

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'iterdir') as mock_iterdir:
                mock_iterdir.return_value = [mock_entry_old, mock_entry_recent, mock_entry_other]
                result = service._expired_log_candidates(3)

        # Verify - only old log included
        assert len(result) == 1
        assert result[0]['name'] == old_log_name

    def test_expired_log_candidates_includes_path(self):
        """Includes path when include_paths=True."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()

        service = MaintenanceService(ap)

        old_date = datetime.date.today() - datetime.timedelta(days=10)
        old_log_name = f'langbot-{old_date.isoformat()}.log'

        mock_entry = Mock(spec=Path)
        mock_entry.is_file = Mock(return_value=True)
        mock_entry.name = old_log_name
        mock_entry.__str__ = Mock(return_value='/data/logs/' + old_log_name)
        mock_stat = Mock()
        mock_stat.st_size = 1000
        mock_entry.stat = Mock(return_value=mock_stat)

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'iterdir') as mock_iterdir:
                mock_iterdir.return_value = [mock_entry]
                result = service._expired_log_candidates(3, include_paths=True)

        # Verify - path included
        assert 'path' in result[0]


class TestMaintenanceServiceExpiredLocalUploadCandidates:
    """Tests for _expired_local_upload_candidates method."""

    def test_expired_local_upload_candidates_nonexistent_dir(self):
        """Returns empty list when storage dir not exists."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.storage_mgr = _scoped_storage_manager()

        service = MaintenanceService(ap)

        with patch.object(Path, 'exists', return_value=False):
            result = service._expired_local_upload_candidates(TEST_CONTEXT, 7)

        # Verify
        assert result == []

    def test_expired_local_upload_candidates_filters_uploaded(self):
        """Only returns uploaded files matching pattern."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.storage_mgr = _scoped_storage_manager()

        service = MaintenanceService(ap)
        # Create one file and one non-file entry under the scoped upload root.
        mock_entry_valid = Mock(spec=Path)
        mock_entry_valid.is_file = Mock(return_value=True)
        mock_entry_valid.name = 'valid_upload.txt'
        mock_stat = Mock()
        mock_stat.st_size = 100
        mock_stat.st_mtime = 0  # Very old
        mock_entry_valid.stat = Mock(return_value=mock_stat)
        mock_entry_valid.relative_to = Mock(return_value=Path('scoped/valid_upload.txt'))

        mock_entry_plugin = Mock(spec=Path)
        mock_entry_plugin.is_file = Mock(return_value=False)
        mock_entry_plugin.name = 'plugin_config_test.json'
        mock_stat2 = Mock()
        mock_stat2.st_size = 200
        mock_stat2.st_mtime = 0
        mock_entry_plugin.stat = Mock(return_value=mock_stat2)

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'rglob') as mock_rglob:
                mock_rglob.return_value = [mock_entry_valid, mock_entry_plugin]
                result = service._expired_local_upload_candidates(TEST_CONTEXT, 7)

        # Verify - only valid upload included
        assert len(result) == 1
        assert result[0]['key'] == 'scoped/valid_upload.txt'

    def test_expired_local_upload_candidates_includes_path(self):
        """Includes path when include_paths=True."""
        # Setup
        ap = SimpleNamespace()
        ap.logger = SimpleNamespace()
        ap.storage_mgr = _scoped_storage_manager()

        service = MaintenanceService(ap)
        mock_entry = Mock(spec=Path)
        mock_entry.is_file = Mock(return_value=True)
        mock_entry.name = 'old_file.txt'
        mock_entry.__str__ = Mock(return_value='/data/storage/old_file.txt')
        mock_stat = Mock()
        mock_stat.st_size = 100
        mock_stat.st_mtime = 0
        mock_entry.stat = Mock(return_value=mock_stat)
        mock_entry.relative_to = Mock(return_value=Path('scoped/old_file.txt'))

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'rglob') as mock_rglob:
                mock_rglob.return_value = [mock_entry]
                result = service._expired_local_upload_candidates(
                    TEST_CONTEXT,
                    7,
                    include_paths=True,
                )

        # Verify - path included
        assert 'path' in result[0]


ISOLATION_WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
ISOLATION_WORKSPACE_B = '00000000-0000-0000-0000-00000000000b'


def _tenant_context(workspace_uuid: str) -> ExecutionContext:
    return ExecutionContext(
        instance_uuid='instance',
        workspace_uuid=workspace_uuid,
        placement_generation=1,
        trigger_principal=PrincipalContext(PrincipalType.SYSTEM),
    )


class _RealPersistenceManager:
    def __init__(self, engine):
        self.engine = engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result


@pytest.fixture
async def tenant_maintenance_service(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "maintenance.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            sqlalchemy.insert(Workspace),
            [
                {
                    'uuid': ISOLATION_WORKSPACE_A,
                    'instance_uuid': 'instance',
                    'name': 'A',
                    'slug': 'a',
                    'source': 'cloud_projection',
                },
                {
                    'uuid': ISOLATION_WORKSPACE_B,
                    'instance_uuid': 'instance',
                    'name': 'B',
                    'slug': 'b',
                    'source': 'cloud_projection',
                },
            ],
        )
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        await connection.execute(
            sqlalchemy.insert(MonitoringMessage),
            [
                {
                    'id': 'message-a',
                    'workspace_uuid': ISOLATION_WORKSPACE_A,
                    'timestamp': now,
                    'bot_id': 'bot',
                    'bot_name': 'Bot',
                    'pipeline_id': 'pipeline',
                    'pipeline_name': 'Pipeline',
                    'message_content': 'A',
                    'session_id': 'same-session',
                    'status': 'success',
                    'level': 'info',
                },
                {
                    'id': 'message-b',
                    'workspace_uuid': ISOLATION_WORKSPACE_B,
                    'timestamp': now,
                    'bot_id': 'bot',
                    'bot_name': 'Bot',
                    'pipeline_id': 'pipeline',
                    'pipeline_name': 'Pipeline',
                    'message_content': 'B',
                    'session_id': 'same-session',
                    'status': 'success',
                    'level': 'info',
                },
            ],
        )
        await connection.execute(
            sqlalchemy.insert(BinaryStorage),
            [
                {
                    'workspace_uuid': ISOLATION_WORKSPACE_A,
                    'unique_key': 'a',
                    'key': 'same',
                    'owner_type': 'plugin',
                    'owner': 'same',
                    'value': b'aaa',
                },
                {
                    'workspace_uuid': ISOLATION_WORKSPACE_B,
                    'unique_key': 'b',
                    'key': 'same',
                    'owner_type': 'plugin',
                    'owner': 'same',
                    'value': b'bbbbb',
                },
            ],
        )

    application = SimpleNamespace(
        persistence_mgr=_RealPersistenceManager(engine),
        instance_config=SimpleNamespace(data={}),
        logger=SimpleNamespace(warning=lambda *_: None),
    )
    yield MaintenanceService(application)
    await engine.dispose()


async def test_cleanup_requires_execution_context(tenant_maintenance_service):
    with pytest.raises(WorkspaceRequiredError):
        await tenant_maintenance_service.cleanup_expired_files(None)


async def test_monitoring_counts_are_workspace_scoped(tenant_maintenance_service):
    counts_a = await tenant_maintenance_service._monitoring_counts(_tenant_context(ISOLATION_WORKSPACE_A))
    counts_b = await tenant_maintenance_service._monitoring_counts(_tenant_context(ISOLATION_WORKSPACE_B))
    assert counts_a['messages'] == 1
    assert counts_b['messages'] == 1


async def test_binary_storage_stats_are_workspace_scoped(tenant_maintenance_service):
    stats_a = await tenant_maintenance_service._binary_storage_stats(_tenant_context(ISOLATION_WORKSPACE_A))
    stats_b = await tenant_maintenance_service._binary_storage_stats(_tenant_context(ISOLATION_WORKSPACE_B))
    assert stats_a == {'count': 1, 'size_bytes': 3}
    assert stats_b == {'count': 1, 'size_bytes': 5}


async def test_path_helpers_handle_missing_paths(tenant_maintenance_service, tmp_path):
    missing = tmp_path / 'missing'
    assert tenant_maintenance_service._path_size(missing) == 0
    assert tenant_maintenance_service._file_count(missing) == 0
