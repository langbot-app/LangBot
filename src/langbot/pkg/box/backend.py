from __future__ import annotations

import abc
import asyncio
import dataclasses
import datetime as dt
import logging
import re
import shlex
import shutil
import uuid

from .errors import BoxError
from .models import BoxExecutionResult, BoxExecutionStatus, BoxSessionInfo, BoxSpec


@dataclasses.dataclass(slots=True)
class _CommandResult:
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class BaseSandboxBackend(abc.ABC):
    name: str

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def initialize(self):
        return None

    @abc.abstractmethod
    async def is_available(self) -> bool:
        pass

    @abc.abstractmethod
    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        pass

    @abc.abstractmethod
    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        pass

    @abc.abstractmethod
    async def stop_session(self, session: BoxSessionInfo):
        pass


class CLISandboxBackend(BaseSandboxBackend):
    command: str

    def __init__(self, logger: logging.Logger, command: str, backend_name: str):
        super().__init__(logger)
        self.command = command
        self.name = backend_name

    async def is_available(self) -> bool:
        if shutil.which(self.command) is None:
            return False

        result = await self._run_command([self.command, 'info'], timeout_sec=5, check=False)
        return result.return_code == 0 and not result.timed_out

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        now = dt.datetime.now(dt.UTC)
        container_name = self._build_container_name(spec.session_id)

        args = [
            self.command,
            'run',
            '-d',
            '--rm',
            '--name',
            container_name,
            '--label',
            'langbot.box=true',
            '--label',
            f'langbot.session_id={spec.session_id}',
        ]

        if spec.network.value == 'off':
            args.extend(['--network', 'none'])

        args.extend([spec.image, 'sh', '-lc', 'while true; do sleep 3600; done'])

        await self._run_command(args, timeout_sec=30, check=True)

        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=container_name,
            image=spec.image,
            network=spec.network,
            created_at=now,
            last_used_at=now,
        )

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        start = dt.datetime.now(dt.UTC)
        args = [self.command, 'exec']

        for key, value in spec.env.items():
            args.extend(['-e', f'{key}={value}'])

        args.extend(
            [
                session.backend_session_id,
                'sh',
                '-lc',
                self._build_exec_command(spec.workdir, spec.cmd),
            ]
        )

        result = await self._run_command(args, timeout_sec=spec.timeout_sec, check=False)
        duration_ms = int((dt.datetime.now(dt.UTC) - start).total_seconds() * 1000)

        if result.timed_out:
            return BoxExecutionResult(
                session_id=session.session_id,
                backend_name=self.name,
                status=BoxExecutionStatus.TIMED_OUT,
                exit_code=None,
                stdout=result.stdout,
                stderr=result.stderr or f'Command timed out after {spec.timeout_sec} seconds.',
                duration_ms=duration_ms,
            )

        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=duration_ms,
        )

    async def stop_session(self, session: BoxSessionInfo):
        await self._run_command(
            [self.command, 'rm', '-f', session.backend_session_id],
            timeout_sec=20,
            check=False,
        )

    def _build_container_name(self, session_id: str) -> str:
        normalized = re.sub(r'[^a-zA-Z0-9_.-]+', '-', session_id).strip('-').lower() or 'session'
        suffix = uuid.uuid4().hex[:8]
        return f'langbot-box-{normalized[:32]}-{suffix}'

    def _build_exec_command(self, workdir: str, cmd: str) -> str:
        quoted_workdir = shlex.quote(workdir)
        return f'mkdir -p {quoted_workdir} && cd {quoted_workdir} && {cmd}'

    async def _run_command(
        self,
        args: list[str],
        timeout_sec: int,
        check: bool,
    ) -> _CommandResult:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()
            return _CommandResult(
                return_code=-1,
                stdout=stdout_bytes.decode('utf-8', errors='replace').strip(),
                stderr=stderr_bytes.decode('utf-8', errors='replace').strip(),
                timed_out=True,
            )

        stdout = stdout_bytes.decode('utf-8', errors='replace').strip()
        stderr = stderr_bytes.decode('utf-8', errors='replace').strip()

        if check and process.returncode != 0:
            raise BoxError(self._format_cli_error(stderr or stdout or 'unknown backend error'))

        return _CommandResult(
            return_code=process.returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
        )

    def _format_cli_error(self, message: str) -> str:
        message = ' '.join(message.split())
        if len(message) > 300:
            message = f'{message[:297]}...'
        return f'{self.name} backend error: {message}'


class PodmanBackend(CLISandboxBackend):
    def __init__(self, logger: logging.Logger):
        super().__init__(logger=logger, command='podman', backend_name='podman')


class DockerBackend(CLISandboxBackend):
    def __init__(self, logger: logging.Logger):
        super().__init__(logger=logger, command='docker', backend_name='docker')
