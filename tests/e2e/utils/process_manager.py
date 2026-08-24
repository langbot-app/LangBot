"""E2E test process manager.

Manages LangBot subprocess lifecycle for E2E testing.
"""

from __future__ import annotations

import subprocess
import time
import signal
import os
import sys
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class LangBotProcess:
    """Manages a LangBot subprocess for E2E testing."""

    def __init__(
        self,
        project_root: Path,
        work_dir: Path,
        port: int = 15300,
        timeout: int = 30,
        collect_coverage: bool = True,
        debug: bool = False,
        cli_args: list[str] | None = None,
    ):
        self.project_root = project_root
        self.work_dir = work_dir  # Directory containing data/config.yaml
        self.port = port
        self.timeout = timeout
        self.collect_coverage = collect_coverage
        self.debug = debug
        self.cli_args = cli_args or []
        self.process: Optional[subprocess.Popen] = None
        self._stdout_file = None
        self._stderr_file = None
        self._stdout_path = self.work_dir / 'langbot.stdout.log'
        self._stderr_path = self.work_dir / 'langbot.stderr.log'
        self._stdout_data: bytes = b''
        self._stderr_data: bytes = b''
        self._coverage_file: Optional[Path] = None

    def start(self) -> bool:
        """Start LangBot process and wait for it to be ready."""
        import httpx

        # Prepare environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(self.project_root / 'src')
        for proxy_key in (
            'HTTP_PROXY',
            'HTTPS_PROXY',
            'ALL_PROXY',
            'http_proxy',
            'https_proxy',
            'all_proxy',
        ):
            env.pop(proxy_key, None)
        env['NO_PROXY'] = '127.0.0.1,localhost'
        env['no_proxy'] = '127.0.0.1,localhost'

        # Set API port via environment variable
        env['API__PORT'] = str(self.port)
        env['API__WEBHOOK_PREFIX'] = f'http://127.0.0.1:{self.port}'

        # Disable telemetry
        env['SPACE__DISABLE_TELEMETRY'] = 'true'
        env['SPACE__DISABLE_MODELS_SERVICE'] = 'true'
        if self.debug:
            env['DEBUG'] = 'true'

        # Build command
        if self.collect_coverage:
            # Use coverage.py to collect coverage data
            # Set COVERAGE_PROCESS_START to enable coverage in subprocess
            self._coverage_file = self.work_dir / '.coverage.e2e'
            env['COVERAGE_FILE'] = str(self._coverage_file)

            # Create .coveragerc for subprocess
            coveragerc_content = """
[run]
source = langbot.pkg
parallel = True
data_file = {}
omit =
    */tests/*
    */test_*.py

[report]
precision = 2
""".format(str(self._coverage_file))
            coveragerc_path = self.work_dir / '.coveragerc'
            with open(coveragerc_path, 'w') as f:
                f.write(coveragerc_content)
            env['COVERAGE_PROCESS_START'] = str(coveragerc_path)

            cmd = [
                sys.executable,
                '-m',
                'coverage',
                'run',
                '--rcfile=' + str(coveragerc_path),
                '-m',
                'langbot',
                *self.cli_args,
            ]
        else:
            cmd = [sys.executable, '-m', 'langbot', *self.cli_args]

        logger.info(f'Starting LangBot in: {self.work_dir}')
        logger.info(f'Command: {cmd}')

        # Start process (run in work_dir so it finds data/config.yaml)
        self._stdout_file = open(self._stdout_path, 'wb')
        self._stderr_file = open(self._stderr_path, 'wb')
        self.process = subprocess.Popen(
            cmd,
            cwd=self.work_dir,
            env=env,
            stdout=self._stdout_file,
            stderr=self._stderr_file,
            preexec_fn=os.setsid if os.name != 'nt' else None,
        )

        # Wait for startup
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            # Check if process died
            if self.process.poll() is not None:
                if self._stdout_file:
                    self._stdout_file.close()
                    self._stdout_file = None
                if self._stderr_file:
                    self._stderr_file.close()
                    self._stderr_file = None
                self._stdout_data = self._stdout_path.read_bytes() if self._stdout_path.exists() else b''
                self._stderr_data = self._stderr_path.read_bytes() if self._stderr_path.exists() else b''
                logger.error(f'LangBot process died: {self._stderr_data.decode()}')
                return False

            # Try to connect
            try:
                r = httpx.get(
                    f'http://127.0.0.1:{self.port}/api/v1/system/info',
                    timeout=2.0,
                    follow_redirects=False,
                    trust_env=False,
                )
                if r.status_code == 200:
                    logger.info(f'LangBot started successfully on port {self.port}')
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass

            time.sleep(1)

        # Timeout
        logger.error(f'LangBot startup timeout after {self.timeout}s')
        self.stop()
        return False

    def stop(self) -> None:
        """Stop LangBot process gracefully."""
        if self.process is None:
            return

        logger.info('Stopping LangBot process...')

        # Try graceful shutdown first
        if os.name != 'nt':
            # Send SIGTERM to process group
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        else:
            self.process.terminate()

        # Wait for graceful shutdown
        try:
            self.process.wait(timeout=5)
            logger.info('LangBot stopped gracefully')
        except subprocess.TimeoutExpired:
            # Force kill
            logger.warning('Force killing LangBot process')
            if os.name != 'nt':
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            else:
                self.process.kill()
            self.process.wait()

        # Collect output for debugging
        if self._stdout_file:
            self._stdout_file.close()
            self._stdout_file = None
        if self._stderr_file:
            self._stderr_file.close()
            self._stderr_file = None
        self._stdout_data = self._stdout_path.read_bytes() if self._stdout_path.exists() else b''
        self._stderr_data = self._stderr_path.read_bytes() if self._stderr_path.exists() else b''

        self.process = None

    def is_running(self) -> bool:
        """Check if process is still running."""
        return self.process is not None and self.process.poll() is None

    def get_logs(self) -> tuple[str, str]:
        """Get stdout and stderr logs."""
        stdout = self._stdout_data.decode('utf-8', errors='replace')
        stderr = self._stderr_data.decode('utf-8', errors='replace')
        if not stdout and self._stdout_path.exists():
            stdout = self._stdout_path.read_text(encoding='utf-8', errors='replace')
        if not stderr and self._stderr_path.exists():
            stderr = self._stderr_path.read_text(encoding='utf-8', errors='replace')
        return stdout, stderr

    def get_coverage_file(self) -> Optional[Path]:
        """Get coverage data file path."""
        return self._coverage_file

    def health_check(self) -> bool:
        """Check if LangBot API is responding."""
        import httpx

        if not self.is_running():
            return False

        try:
            r = httpx.get(
                f'http://127.0.0.1:{self.port}/api/v1/system/info',
                timeout=5.0,
                follow_redirects=False,
                trust_env=False,
            )
            return r.status_code == 200
        except Exception:
            return False


def find_project_root() -> Path:
    """Find LangBot project root directory."""
    current = Path(__file__).resolve()

    # Walk up until we find src/langbot
    for parent in current.parents:
        if (parent / 'src' / 'langbot').exists():
            return parent

    # Fallback to LangBot-test-build directory
    return Path('/home/glwuy/langbot-app/LangBot-test-build')
