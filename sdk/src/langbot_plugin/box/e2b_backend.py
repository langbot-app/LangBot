from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import os
import posixpath
import re
import shlex
import uuid

from ..artifact import build_tree_manifest, load_tree_manifest
from .backend import BaseSandboxBackend, _MAX_RAW_OUTPUT_BYTES
from .errors import BoxError
from .models import (
    ARTIFACT_MOUNT_ROOT,
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxHostMountMode,
    BoxSessionInfo,
    BoxSpec,
)
from .security import validate_sandbox_security

_MAX_E2B_SYNC_FILES = 2048
_MAX_E2B_SYNC_FILE_BYTES = 10 * 1024 * 1024
_MAX_E2B_SYNC_TOTAL_BYTES = 256 * 1024 * 1024
_ARTIFACT_ROOT = "/opt/langbot-artifact-cache"


def _read_e2b_host_file_limited(path: str) -> bytes:
    if os.path.getsize(path) > _MAX_E2B_SYNC_FILE_BYTES:
        raise ValueError("E2B host sync file exceeds the size limit")
    with open(path, "rb") as file:
        body = file.read(_MAX_E2B_SYNC_FILE_BYTES + 1)
    if len(body) > _MAX_E2B_SYNC_FILE_BYTES:
        raise ValueError("E2B host sync file exceeds the size limit")
    return body


def _build_e2b_host_manifest(host_root: str) -> tuple[str, dict]:
    """Build the same canonical tree digest used by published Skill revisions."""

    return build_tree_manifest(
        host_root,
        max_files=_MAX_E2B_SYNC_FILES,
        max_total_bytes=_MAX_E2B_SYNC_TOTAL_BYTES,
        skip_directories={".git", ".venv", "__pycache__", "node_modules"},
        subject="E2B immutable mount",
    )


# E2B sandbox uses /home/user as the default writable directory
# We map /workspace to /home/user/workspace for compatibility
E2B_DEFAULT_WORKDIR = "/home/user"
E2B_WORKSPACE_DIR = "/home/user/workspace"

# Lazy imports for e2b - only imported when actually needed
_e2b_available: bool | None = None
_AsyncSandbox = None
_CommandResult = None


def _check_e2b_available(force: bool = False) -> bool:
    """Check if e2b package is available (cached result).

    Args:
        force: If True, re-check even if cached result exists.
    """
    global _e2b_available, _AsyncSandbox, _CommandResult
    if _e2b_available is not None and not force:
        return _e2b_available

    try:
        from e2b import AsyncSandbox, CommandResult

        _AsyncSandbox = AsyncSandbox
        _CommandResult = CommandResult
        _e2b_available = True
    except ImportError:
        _e2b_available = False

    return _e2b_available


def _reset_e2b_cache() -> None:
    """Reset the e2b availability cache, forcing re-check on next call."""
    global _e2b_available, _AsyncSandbox, _CommandResult
    _e2b_available = None
    _AsyncSandbox = None
    _CommandResult = None


def _adapt_path_for_e2b(path: str) -> str:
    """Adapt paths for E2B sandbox environment.

    E2B sandbox doesn't have /workspace by default, so we map it to
    /home/user/workspace which is writable.
    """
    if path == "/workspace" or path.startswith("/workspace/"):
        return path.replace("/workspace", E2B_WORKSPACE_DIR, 1)
    return path


def _rewrite_command_paths_for_e2b(command: str) -> str:
    """Rewrite LangBot's logical /workspace paths for E2B's real writable path."""
    return re.sub(r"(?<![\w.-])/workspace(?=$|/|[^\w.-])", E2B_WORKSPACE_DIR, command)


class E2BSandboxBackend(BaseSandboxBackend):
    """E2B/CubeSandbox sandbox backend.

    Supports both E2B cloud service and self-hosted CubeSandbox.
    Configuration sources (priority from high to low):
    1. Environment variables: E2B_API_KEY, E2B_API_URL
    2. Configuration passed via configure() method (from LangBot config.yaml)
    """

    content_addressed_mounts = True
    name = "e2b"

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)
        self._api_key: str | None = None
        self._api_url: str | None = None
        self._template: str | None = None
        self._config_from_langbot: dict = {}

    def configure(self, config: dict) -> None:
        """Apply configuration from LangBot config.yaml.

        Environment variables take precedence over config.yaml values.
        """
        self._config_from_langbot = config
        # Reset cache to force re-check if e2b package was installed later
        _reset_e2b_cache()

    async def initialize(self):
        """Load configuration from environment variables (priority) or config.yaml."""
        # Environment variables take precedence
        self._api_key = os.getenv("E2B_API_KEY") or self._config_from_langbot.get(
            "api_key"
        )
        self._api_url = os.getenv("E2B_API_URL") or self._config_from_langbot.get(
            "api_url"
        )
        self._template = self._config_from_langbot.get("template")

    async def is_available(self) -> bool:
        """Check if E2B backend is available.

        Returns True if:
        1. e2b package is installed
        2. E2B_API_KEY environment variable is set
        """
        if not _check_e2b_available():
            self.logger.info("e2b package not installed")
            return False

        if not self._api_key:
            self.logger.info("E2B_API_KEY not set")
            return False

        return True

    async def start_session(self, spec: BoxSpec) -> BoxSessionInfo:
        """Create a new E2B sandbox session.

        Maps BoxSpec fields to AsyncSandbox.create() parameters:
        - template: spec.image (E2B template ID)
        - envs: spec.env
        - timeout: sandbox lifetime timeout (not command timeout)
        """
        validate_sandbox_security(spec)

        if not _check_e2b_available():
            raise BoxError("e2b package not installed")

        now = dt.datetime.now(dt.timezone.utc)

        # Adapt paths for E2B environment
        mount_path = _adapt_path_for_e2b(spec.mount_path)

        # Build create parameters
        create_kwargs = {}

        # Template - use spec.image if provided, otherwise configured template, otherwise E2B default
        if spec.image and spec.image != "rockchin/langbot-sandbox:latest":
            create_kwargs["template"] = spec.image
        elif self._template:
            create_kwargs["template"] = self._template

        # Environment variables
        if spec.env:
            create_kwargs["envs"] = spec.env

        # API key and domain (for CubeSandbox self-deployment)
        if self._api_key:
            create_kwargs["api_key"] = self._api_key
        if self._api_url:
            # E2B SDK uses 'domain' for self-hosted API URL
            create_kwargs["domain"] = self._api_url

        # Network mode - E2B uses allow_internet_access parameter
        # Note: E2B SDK doesn't have this directly in create(), but CubeSandbox may support it
        # For now, we rely on template configuration for network access

        self.logger.info(
            f"LangBot Box backend start_session: backend=e2b "
            f"session_id={spec.session_id} "
            f"template={create_kwargs.get('template', 'default')} "
            f"network={spec.network.value} "
            f"host_path={spec.host_path} host_path_mode={spec.host_path_mode.value} mount_path={mount_path} "
            f"env_keys={sorted(spec.env.keys())}"
        )

        try:
            sandbox = await _AsyncSandbox.create(**create_kwargs)
        except Exception as exc:
            raise BoxError(f"Failed to create E2B sandbox: {exc}")

        return BoxSessionInfo(
            session_id=spec.session_id,
            backend_name=self.name,
            backend_session_id=sandbox.sandbox_id,
            image=spec.image,
            network=spec.network,
            host_path=spec.host_path,
            host_path_mode=spec.host_path_mode,
            # Keep the logical mount path in session metadata. The runtime
            # compares future BoxSpec objects against this value when reusing
            # sessions; storing the E2B-internal path here makes every later
            # /workspace request look incompatible.
            mount_path=spec.mount_path,
            persistent=spec.persistent,
            cpus=spec.cpus,
            memory_mb=spec.memory_mb,
            pids_limit=spec.pids_limit,
            read_only_rootfs=spec.read_only_rootfs,
            workspace_quota_mb=spec.workspace_quota_mb,
            created_at=now,
            last_used_at=now,
        )

    async def exec(self, session: BoxSessionInfo, spec: BoxSpec) -> BoxExecutionResult:
        """Execute a command in the E2B sandbox.

        Reconnects to existing sandbox via AsyncSandbox.connect() and runs command.
        """
        if not _check_e2b_available():
            raise BoxError("e2b package not installed")

        start = dt.datetime.now(dt.timezone.utc)

        # Connect kwargs
        connect_kwargs = {}
        if self._api_key:
            connect_kwargs["api_key"] = self._api_key
        if self._api_url:
            connect_kwargs["domain"] = self._api_url

        # Adapt workdir and logical /workspace command paths for E2B.
        workdir = _adapt_path_for_e2b(spec.workdir)
        command = _rewrite_command_paths_for_e2b(spec.cmd)

        cmd_preview = spec.cmd.strip()
        if len(cmd_preview) > 400:
            cmd_preview = f"{cmd_preview[:397]}..."
        self.logger.info(
            f"LangBot Box backend exec: backend=e2b "
            f"session_id={session.session_id} sandbox_id={session.backend_session_id} "
            f"workdir={workdir} timeout_sec={spec.timeout_sec} "
            f"env_keys={sorted(spec.env.keys())} cmd={cmd_preview}"
        )

        try:
            sandbox = await _AsyncSandbox.connect(
                sandbox_id=session.backend_session_id, **connect_kwargs
            )
        except Exception as exc:
            raise BoxError(f"Failed to connect to E2B sandbox: {exc}")

        await self._prepare_read_only_mounts(sandbox, spec)
        await self._check_workspace_quota(sandbox, spec)

        # Run the command
        # Note: E2B requires cwd to exist before running command. We create it
        # as part of the command and then run from that directory.
        run_kwargs = {
            "cmd": f"mkdir -p {shlex.quote(workdir)} && cd {shlex.quote(workdir)} && {command}",
            "timeout": spec.timeout_sec,
        }
        if spec.env:
            run_kwargs["envs"] = spec.env

        try:
            result = await sandbox.commands.run(**run_kwargs)
        except Exception as exc:
            # Check if it's a timeout
            duration_ms = int(
                (dt.datetime.now(dt.timezone.utc) - start).total_seconds() * 1000
            )
            error_msg = str(exc)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                return BoxExecutionResult(
                    session_id=session.session_id,
                    backend_name=self.name,
                    status=BoxExecutionStatus.TIMED_OUT,
                    exit_code=None,
                    stdout="",
                    stderr=f"Command timed out after {spec.timeout_sec} seconds.",
                    duration_ms=duration_ms,
                )
            raise BoxError(f"E2B command execution failed: {exc}")

        await self._check_workspace_quota(sandbox, spec)

        duration_ms = int(
            (dt.datetime.now(dt.timezone.utc) - start).total_seconds() * 1000
        )

        # Process output - apply truncation if needed
        stdout = self._truncate_output(result.stdout or "")
        stderr = self._truncate_output(result.stderr or "")

        return BoxExecutionResult(
            session_id=session.session_id,
            backend_name=self.name,
            status=BoxExecutionStatus.COMPLETED,
            exit_code=result.exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
        )

    async def _check_workspace_quota(self, sandbox, spec: BoxSpec) -> None:
        if spec.workspace_quota_mb <= 0:
            return
        limit = spec.workspace_quota_mb * 1024 * 1024
        script = """import os, sys
root, limit = sys.argv[1], int(sys.argv[2])
size = entries = 0
def failed(error):
    raise error
for directory, dirs, files in os.walk(root, followlinks=False, onerror=failed):
    entries += len(dirs) + len(files)
    if entries > 100000:
        raise ValueError('workspace entry limit exceeded')
    for name in files:
        size += os.lstat(os.path.join(directory, name)).st_size
        if size > limit:
            raise ValueError('workspace quota exceeded')
"""
        result = await sandbox.commands.run(
            "python3 -c "
            + shlex.quote(script)
            + " "
            + shlex.quote(_adapt_path_for_e2b(spec.mount_path))
            + " "
            + str(limit),
            timeout=30,
        )
        if result.exit_code != 0:
            raise BoxError("E2B workspace quota check failed: " + (result.stderr or ""))

    async def _prepare_read_only_mounts(self, sandbox, spec: BoxSpec) -> None:
        """Import immutable resources without mirroring the writable workspace."""
        if spec.host_path and spec.host_path_mode == BoxHostMountMode.READ_ONLY:
            await self._materialize_immutable_mount(
                sandbox,
                host_root=spec.host_path,
                remote_root=_adapt_path_for_e2b(spec.mount_path),
            )
        for mount in spec.extra_mounts:
            if mount.mode == BoxHostMountMode.NONE:
                continue
            if mount.mode != BoxHostMountMode.READ_ONLY:
                raise BoxError(
                    "E2B writable host mounts are unsupported; explicitly import files into the Box"
                )
            await self._materialize_immutable_mount(
                sandbox,
                host_root=mount.host_path,
                remote_root=_adapt_path_for_e2b(mount.mount_path),
                expected_digest=mount.content_digest,
                manifest_path=mount.manifest_path,
            )

    async def _materialize_immutable_mount(
        self,
        sandbox,
        *,
        host_root: str,
        remote_root: str,
        expected_digest: str | None = None,
        manifest_path: str | None = None,
    ) -> None:
        """Prepare a verified revision directory, then switch its projection.

        No live mount path is incrementally overwritten. Any interrupted upload
        remains isolated in a staging directory and execution is blocked.
        """

        if manifest_path is not None:
            digest, manifest = await asyncio.to_thread(
                load_tree_manifest,
                manifest_path,
                max_files=_MAX_E2B_SYNC_FILES,
                max_total_bytes=_MAX_E2B_SYNC_TOTAL_BYTES,
                subject="E2B immutable mount",
            )
        else:
            digest, manifest = await asyncio.to_thread(
                _build_e2b_host_manifest,
                host_root,
            )
        if expected_digest is not None and digest != expected_digest:
            raise BoxError(
                "Immutable mount source does not match its declared content_digest "
                f"(expected {expected_digest}, actual {digest})"
            )
        digest_hex = digest[len("sha256:") :]
        ready_root = posixpath.join(_ARTIFACT_ROOT, digest_hex)
        marker_path = posixpath.join(ready_root, "ready")
        if await self._remote_revision_ready(sandbox, marker_path, digest):
            await self._project_remote_revision(
                sandbox,
                ready_root=ready_root,
                remote_root=remote_root,
            )
            return

        staging_root = posixpath.join(
            _ARTIFACT_ROOT,
            f".{digest_hex}.staging-{uuid.uuid4().hex}",
        )
        sealed_root = staging_root + ".sealed"
        staging_package = posixpath.join(staging_root, "package")
        try:
            await self._run_e2b_checked(
                sandbox,
                f"mkdir -p {shlex.quote(_ARTIFACT_ROOT)} && "
                f"chown root:root {shlex.quote(_ARTIFACT_ROOT)} && "
                f"chmod 0755 {shlex.quote(_ARTIFACT_ROOT)} && "
                f"mkdir -p {shlex.quote(staging_package)} && "
                f"chown -R user:user {shlex.quote(staging_root)}",
                subject="create immutable mount staging directory",
                user="root",
            )
            created_directories = {staging_package}
            for entry in manifest["files"]:
                relative = str(entry["path"])
                remote_file = posixpath.join(staging_package, relative)
                remote_directory = posixpath.dirname(remote_file)
                if remote_directory not in created_directories:
                    await self._run_e2b_checked(
                        sandbox,
                        f"mkdir -p {shlex.quote(remote_directory)}",
                        subject="create immutable mount directory",
                    )
                    created_directories.add(remote_directory)
                host_file = os.path.join(host_root, *relative.split("/"))
                data = await asyncio.to_thread(_read_e2b_host_file_limited, host_file)
                if (
                    len(data) != entry["size"]
                    or hashlib.sha256(data).hexdigest() != entry["sha256"]
                ):
                    raise BoxError(
                        f"Immutable mount source changed during upload: {relative}"
                    )
                await sandbox.files.write(remote_file, data)
                if entry["executable"]:
                    await self._run_e2b_checked(
                        sandbox,
                        f"chmod 0555 {shlex.quote(remote_file)}",
                        subject="preserve immutable executable mode",
                    )

            manifest_path = posixpath.join(staging_root, "manifest.json")
            manifest_body = json.dumps(
                manifest,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            await sandbox.files.write(manifest_path, manifest_body)
            # Copy into root-only storage so open upload-file handles cannot alter the verified tree.
            await self._run_e2b_checked(
                sandbox,
                f"mkdir -m 0700 {shlex.quote(sealed_root)} && "
                f"cp -R -P {shlex.quote(staging_package)} {shlex.quote(manifest_path)} {shlex.quote(sealed_root)}/ && "
                f"chown -R root:root {shlex.quote(sealed_root)} && "
                f"chmod -R a-w {shlex.quote(sealed_root)}",
                subject="seal immutable mount staging",
                user="root",
            )
            await self._verify_remote_manifest(
                sandbox,
                package_root=posixpath.join(sealed_root, "package"),
                manifest_path=posixpath.join(sealed_root, "manifest.json"),
                expected_digest=digest,
                user="root",
            )
            await self._run_e2b_checked(
                sandbox,
                f"chmod u+w {shlex.quote(sealed_root)} && "
                f"printf %s {shlex.quote(digest)} > {shlex.quote(posixpath.join(sealed_root, 'ready'))} && "
                f"chmod 0555 {shlex.quote(sealed_root)} && "
                f"chmod -R a+rX {shlex.quote(sealed_root)} && "
                f"test ! -e {shlex.quote(ready_root)} && "
                f"mv {shlex.quote(sealed_root)} {shlex.quote(ready_root)}",
                subject="publish immutable mount revision",
                user="root",
            )
        except BaseException as exc:
            if not isinstance(exc, Exception) or isinstance(exc, BoxError):
                raise
            raise BoxError(f"Failed to materialize immutable E2B mount: {exc}") from exc
        finally:
            try:
                await sandbox.commands.run(
                    f"chmod -R u+w {shlex.quote(staging_root)} {shlex.quote(sealed_root)} 2>/dev/null || true; "
                    f"rm -rf {shlex.quote(staging_root)} {shlex.quote(sealed_root)}",
                    timeout=10,
                    user="root",
                )
            except Exception:
                pass

        await self._project_remote_revision(
            sandbox,
            ready_root=ready_root,
            remote_root=remote_root,
        )

    async def _remote_revision_ready(
        self,
        sandbox,
        marker_path: str,
        expected_digest: str,
    ) -> bool:
        try:
            result = await sandbox.commands.run(
                f"cat {shlex.quote(marker_path)}",
                timeout=10,
            )
        except Exception:
            return False
        marker_matches = (
            getattr(result, "exit_code", 1) == 0
            and str(getattr(result, "stdout", "") or "").strip() == expected_digest
        )
        if not marker_matches:
            return False
        ready_root = posixpath.dirname(marker_path)
        try:
            await self._verify_remote_manifest(
                sandbox,
                package_root=posixpath.join(ready_root, "package"),
                manifest_path=posixpath.join(ready_root, "manifest.json"),
                expected_digest=expected_digest,
            )
        except BoxError:
            return False
        return True

    async def _project_remote_revision(
        self,
        sandbox,
        *,
        ready_root: str,
        remote_root: str,
    ) -> None:
        if remote_root.startswith(ARTIFACT_MOUNT_ROOT + "/"):
            target = posixpath.join(ready_root, "package")
            await self._run_e2b_checked(
                sandbox,
                f"mkdir -p {shlex.quote(ARTIFACT_MOUNT_ROOT)} && "
                f"chown root:root {shlex.quote(ARTIFACT_MOUNT_ROOT)} && "
                f"chmod 0755 {shlex.quote(ARTIFACT_MOUNT_ROOT)} && "
                f"(ln -sT {shlex.quote(target)} {shlex.quote(remote_root)} 2>/dev/null || "
                f'test "$(readlink {shlex.quote(remote_root)})" = {shlex.quote(target)})',
                subject="publish immutable artifact projection",
                user="root",
            )
            return
        await self._run_e2b_checked(
            sandbox,
            f"mkdir -p {shlex.quote(posixpath.dirname(remote_root))} && "
            f"rm -rf {shlex.quote(remote_root)} && "
            f"ln -s {shlex.quote(posixpath.join(ready_root, 'package'))} {shlex.quote(remote_root)}",
            subject="project immutable mount revision",
        )

    async def _verify_remote_manifest(
        self,
        sandbox,
        *,
        package_root: str,
        manifest_path: str,
        expected_digest: str,
        user: str | None = None,
    ) -> None:
        verifier = """
import hashlib,json,os,stat,sys
root,manifest_path,expected=sys.argv[1:]
if not stat.S_ISDIR(os.lstat(root).st_mode) or not stat.S_ISREG(os.lstat(manifest_path).st_mode):
    raise SystemExit(42)
with open(manifest_path,encoding='utf-8') as f:
    manifest=json.load(f)
actual=[]
for current,dirs,names in os.walk(root,followlinks=False):
    dirs.sort(); names.sort()
    if any(os.path.islink(os.path.join(current,name)) for name in dirs):
        raise SystemExit(42)
    for name in names:
        path=os.path.join(current,name)
        info=os.stat(path,follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode): raise SystemExit(42)
        digest=hashlib.sha256()
        with open(path,'rb') as f:
            while True:
                chunk=f.read(262144)
                if not chunk: break
                digest.update(chunk)
        actual.append({'path':os.path.relpath(path,root).replace(os.sep,'/'),'size':info.st_size,'sha256':digest.hexdigest(),'executable':bool(stat.S_IMODE(info.st_mode)&0o111)})
candidate={'algorithm':'sha256-tree-v1','files':actual,'total_bytes':sum(item['size'] for item in actual)}
body=json.dumps(candidate,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode('utf-8')
if candidate != manifest or 'sha256:'+hashlib.sha256(body).hexdigest() != expected:
    raise SystemExit(42)
""".strip()
        await self._run_e2b_checked(
            sandbox,
            "python3 -c "
            f"{shlex.quote(verifier)} {shlex.quote(package_root)} "
            f"{shlex.quote(manifest_path)} {shlex.quote(expected_digest)}",
            subject="verify immutable mount manifest",
            user=user,
        )

    @staticmethod
    async def _run_e2b_checked(
        sandbox,
        command: str,
        *,
        subject: str,
        user: str | None = None,
    ) -> None:
        try:
            kwargs = {"timeout": 30}
            if user is not None:
                kwargs["user"] = user
            result = await sandbox.commands.run(command, **kwargs)
        except Exception as exc:
            raise BoxError(f"Failed to {subject}: {exc}") from exc
        if getattr(result, "exit_code", 1) != 0:
            stderr = str(getattr(result, "stderr", "") or "").strip()
            raise BoxError(f"Failed to {subject}: {stderr or 'remote command failed'}")

    async def stop_session(self, session: BoxSessionInfo):
        """Kill the E2B sandbox."""
        self.logger.info(
            f"LangBot Box backend stop_session: backend=e2b "
            f"session_id={session.session_id} sandbox_id={session.backend_session_id}"
        )

        if not _check_e2b_available():
            return  # Nothing to do if package not available

        try:
            await _AsyncSandbox.kill(
                sandbox_id=session.backend_session_id,
                api_key=self._api_key,
                domain=self._api_url,
            )
        except Exception as exc:
            self.logger.warning(f"Failed to kill E2B sandbox: {exc}")

    async def is_session_alive(self, session: BoxSessionInfo) -> bool:
        """Probe the remote sandbox rather than trusting stale local metadata."""
        if not _check_e2b_available():
            return False
        kwargs = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._api_url:
            kwargs["domain"] = self._api_url
        try:
            await _AsyncSandbox.connect(sandbox_id=session.backend_session_id, **kwargs)
            return True
        except Exception as exc:
            self.logger.info(
                "E2B sandbox liveness probe failed for %s: %s",
                session.backend_session_id,
                exc,
            )
            return False

    def _truncate_output(self, output: str, limit: int = _MAX_RAW_OUTPUT_BYTES) -> str:
        """Truncate output if exceeds the limit."""
        if len(output.encode("utf-8", errors="replace")) > limit:
            # Truncate to approximately the limit
            truncated = output[:limit]
            truncated += f"\n... [output clipped at {limit} bytes]"
            return truncated
        return output
