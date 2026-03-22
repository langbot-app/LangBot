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
from .models import DEFAULT_BOX_MOUNT_PATH, BoxExecutionResult, BoxExecutionStatus, BoxHostMountMode, BoxNetworkMode, BoxSessionInfo, BoxSpec
from .security import validate_sandbox_security

# Hard cap on raw subprocess output to prevent unbounded memory usage.
# Container timeout already bounds duration, but fast commands can still
# produce large output within the time limit.  After this many bytes the
# remaining output is discarded before decoding.
_MAX_RAW_OUTPUT_BYTES = 1_048_576  # 1 MB per stream


@dataclasses.dataclass(slots=True)
class _CommandResult:
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class BaseSandboxBackend(abc.ABC):
    name: str
    instance_id: str = ''

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

    async def start_managed_process(self, session: BoxSessionInfo, spec):
        raise BoxError(f'{self.name} backend does not support managed processes')

    async def cleanup_orphaned_containers(self, current_instance_id: str = ''):
        """Remove lingering containers from previous runs. No-op by default."""
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
        validate_sandbox_security(spec)

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
            '--label',
            f'langbot.box.instance_id={self.instance_id}',
        ]

        if spec.network == BoxNetworkMode.OFF:
            args.extend(['--network', 'none'])

        # Resource limits
        args.extend(['--cpus', str(spec.cpus)])
        args.extend(['--memory', f'{spec.memory_mb}m'])
        args.extend(['--pids-limit', str(spec.pids_limit)])

        if spec.read_only_rootfs:
            args.append('--read-only')
            args.extend(['--tmpfs', '/tmp:size=64m'])

        if spec.host_path is not None and spec.host_path_mode != BoxHostMountMode.NONE:
            mount_spec = f'{spec.host_path}:{DEFAULT_BOX_MOUNT_PATH}:{spec.host_path_mode.value}'
            args.extend(['-v', mount_spec])

        args.extend([spec.image, 'sh', '-lc', 'while true; do sleep 3600; done'])

        self.logger.info(
            f'LangBot Box backend start_session: backend={self.name} '
            f'session_id={spec.session_id} container_name={container_name} '
            f'image={spec.image} network={spec.network.value} '
            f'host_path={spec.host_path} host_path_mode={spec.host_path_mode.value} '
            f'cpus={spec.cpus} memory_mb={spec.memory_mb} pids_limit={spec.pids_limit} '
            f'read_only_rootfs={spec.read_only_rootfs}'
        )

        await self._run_command(args, timeout_sec=30, check=True)

        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=container_name,
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            host_path_mode=spec.host_path_mode,
            cpus=spec.cpus,
            memory_mb=spec.memory_mb,
            pids_limit=spec.pids_limit,
            read_only_rootfs=spec.read_only_rootfs,
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

        cmd_preview = spec.cmd.strip()
        if len(cmd_preview) > 400:
            cmd_preview = f'{cmd_preview[:397]}...'
        self.logger.info(
            f'LangBot Box backend exec: backend={self.name} '
            f'session_id={session.session_id} container_name={session.backend_session_id} '
            f'workdir={spec.workdir} timeout_sec={spec.timeout_sec} '
            f'env_keys={sorted(spec.env.keys())} cmd={cmd_preview}'
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
        self.logger.info(
            f'LangBot Box backend stop_session: backend={self.name} '
            f'session_id={session.session_id} container_name={session.backend_session_id}'
        )
        await self._run_command(
            [self.command, 'rm', '-f', session.backend_session_id],
            timeout_sec=20,
            check=False,
        )

    async def cleanup_orphaned_containers(self, current_instance_id: str = ''):
        """Remove langbot.box containers from previous instances.

        Only removes containers whose ``langbot.box.instance_id`` label does
        NOT match *current_instance_id*.  Containers without the label (from
        older versions) are also removed.
        """
        result = await self._run_command(
            [self.command, 'ps', '-a', '--filter', 'label=langbot.box=true',
             '--format', '{{.ID}}\t{{.Label "langbot.box.instance_id"}}'],
            timeout_sec=10,
            check=False,
        )
        if result.return_code != 0 or not result.stdout.strip():
            return
        orphan_ids = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            cid = parts[0].strip()
            label_instance = parts[1].strip() if len(parts) > 1 else ''
            if label_instance != current_instance_id:
                orphan_ids.append(cid)
        if not orphan_ids:
            return
        for cid in orphan_ids:
            self.logger.info(f'Cleaning up orphaned Box container: {cid}')
        await self._run_command(
            [self.command, 'rm', '-f', *orphan_ids],
            timeout_sec=30,
            check=False,
        )

    async def start_managed_process(self, session: BoxSessionInfo, spec) -> asyncio.subprocess.Process:
        args = [self.command, 'exec', '-i']

        for key, value in spec.env.items():
            args.extend(['-e', f'{key}={value}'])

        args.extend(
            [
                session.backend_session_id,
                'sh',
                '-lc',
                self._build_spawn_command(spec.cwd, spec.command, spec.args),
            ]
        )

        self.logger.info(
            f'LangBot Box backend start_managed_process: backend={self.name} '
            f'session_id={session.session_id} container_name={session.backend_session_id} '
            f'cwd={spec.cwd} env_keys={sorted(spec.env.keys())} command={spec.command} args={spec.args}'
        )

        return await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    def _build_container_name(self, session_id: str) -> str:
        normalized = re.sub(r'[^a-zA-Z0-9_.-]+', '-', session_id).strip('-').lower() or 'session'
        suffix = uuid.uuid4().hex[:8]
        return f'langbot-box-{normalized[:32]}-{suffix}'

    def _build_exec_command(self, workdir: str, cmd: str) -> str:
        quoted_workdir = shlex.quote(workdir)
        return f'mkdir -p {quoted_workdir} && cd {quoted_workdir} && {cmd}'

    def _build_spawn_command(self, cwd: str, command: str, args: list[str]) -> str:
        quoted_cwd = shlex.quote(cwd)
        command_parts = [shlex.quote(command), *[shlex.quote(arg) for arg in args]]
        return f'mkdir -p {quoted_cwd} && cd {quoted_cwd} && exec {" ".join(command_parts)}'

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
        stdout_task = asyncio.create_task(self._read_stream(process.stdout))
        stderr_task = asyncio.create_task(self._read_stream(process.stderr))

        timed_out = False
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            process.kill()
            timed_out = True
            await process.wait()

        stdout_bytes, stdout_total = await stdout_task
        stderr_bytes, stderr_total = await stderr_task

        if timed_out:
            return _CommandResult(
                return_code=-1,
                stdout=self._clip_captured_bytes(stdout_bytes, stdout_total),
                stderr=self._clip_captured_bytes(stderr_bytes, stderr_total),
                timed_out=True,
            )

        stdout = self._clip_captured_bytes(stdout_bytes, stdout_total)
        stderr = self._clip_captured_bytes(stderr_bytes, stderr_total)

        if check and process.returncode != 0:
            raise BoxError(self._format_cli_error(stderr or stdout or 'unknown backend error'))

        return _CommandResult(
            return_code=process.returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
        )

    @staticmethod
    def _clip_captured_bytes(data: bytes, total_size: int, limit: int = _MAX_RAW_OUTPUT_BYTES) -> str:
        text = data.decode('utf-8', errors='replace').strip()
        if total_size > limit:
            text += f'\n... [raw output clipped at {limit} bytes, {total_size - limit} bytes discarded]'
        return text

    @staticmethod
    async def _read_stream(
        stream: asyncio.StreamReader | None,
        limit: int = _MAX_RAW_OUTPUT_BYTES,
    ) -> tuple[bytes, int]:
        if stream is None:
            return b'', 0

        chunks = bytearray()
        total_size = 0
        while True:
            chunk = await stream.read(65536)
            if not chunk:
                break
            total_size += len(chunk)
            remaining = limit - len(chunks)
            if remaining > 0:
                chunks.extend(chunk[:remaining])

        return bytes(chunks), total_size

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
