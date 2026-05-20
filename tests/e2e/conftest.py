"""E2E test fixtures.

Provides fixtures for starting real LangBot process with minimal configuration.
"""

from __future__ import annotations

import pytest
import tempfile
import shutil
import logging
from pathlib import Path

from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
from tests.e2e.utils.process_manager import LangBotProcess, find_project_root

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope='session')
def e2e_port():
    """Port for E2E testing (non-default to avoid conflicts)."""
    return 15300


@pytest.fixture(scope='session')
def e2e_tmpdir():
    """Create temporary directory for E2E testing."""
    tmpdir = Path(tempfile.mkdtemp(prefix='langbot_e2e_'))
    logger.info(f'E2E tmpdir: {tmpdir}')

    yield tmpdir

    # Cleanup
    logger.info(f'Cleaning up E2E tmpdir: {tmpdir}')
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope='session')
def e2e_config_path(e2e_tmpdir, e2e_port):
    """Create minimal config.yaml for E2E testing."""
    config_path = create_minimal_config(e2e_tmpdir, port=e2e_port)
    create_test_directories(e2e_tmpdir)
    logger.info(f'E2E config: {config_path}')
    return config_path


@pytest.fixture(scope='session')
def langbot_process(e2e_config_path, e2e_port, e2e_tmpdir):
    """Start real LangBot process for E2E testing.

    This fixture starts LangBot once per session and reuses it for all tests.
    Coverage data is collected from the subprocess.
    """
    project_root = find_project_root()
    collect_coverage = True

    proc = LangBotProcess(
        project_root=project_root,
        work_dir=e2e_tmpdir,  # Run in tmpdir where data/config.yaml exists
        port=e2e_port,
        timeout=60,  # Longer timeout for first startup
        collect_coverage=collect_coverage,
    )

    success = proc.start()
    if not success:
        stdout, stderr = proc.get_logs()
        pytest.fail(f'LangBot failed to start:\nstdout: {stdout}\nstderr: {stderr}')

    yield proc

    # Cleanup
    proc.stop()

    # Combine coverage data if collected
    if collect_coverage and proc.get_coverage_file():
        coverage_file = proc.get_coverage_file()
        if coverage_file.exists():
            # Copy coverage data to project root for combining
            target = project_root / '.coverage.e2e'
            shutil.copy(coverage_file, target)
            logger.info(f'Coverage data saved to: {target}')


@pytest.fixture
def e2e_client(e2e_port, langbot_process):
    """HTTP client for E2E testing."""
    import httpx

    base_url = f'http://127.0.0.1:{e2e_port}'

    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        yield client


@pytest.fixture(scope='session')
def e2e_db_path(e2e_tmpdir):
    """Path to SQLite database file."""
    return e2e_tmpdir / 'data' / 'langbot.db'