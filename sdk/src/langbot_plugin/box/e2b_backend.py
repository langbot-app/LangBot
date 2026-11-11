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
_MAX_E2B_SYNC_ENTRIES = 2048
_MAX_E2B_SYNC_FILE_BYTES = 10 * 1024 * 1024
_MAX_E2B_SYNC_TOTAL_BYTES = 256 * 1024 * 1024
_E2B_UPLOAD_BATCH_FILES = 32
_E2B_UPLOAD_BATCH_BYTES = 8 * 1024 * 1024
_E2B_DOWNLOAD_CONCURRENCY = 8
_ARTIFACT_ROOT = "/opt/langbot-artifact-cache"


def _read_e2b_host_file_limited(path: str) -> bytes:
    if os.path.getsize(path) > _MAX_E2B_SYNC_FILE_BYTES:
        raise ValueError("E2B host sync file exceeds the size limit")
    with open(path, "rb") as file:
        body = file.read(_MAX_E2B_SYNC_FILE_BYTES + 1)
    if len(body) > _MAX_E2B_SYNC_FILE_BYTES:
        raise ValueError("E2B host sync file exceeds the size limit")
    return body


def _write_e2b_host_file(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as file:
        file.write(data)


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
        - metadata: CubeSandbox host-mount configuration
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

        # Build metadata for CubeSandbox host-mount
        metadata = {}
        if spec.host_path and spec.host_path_mode != BoxHostMountMode.NONE:
            metadata["host-mount"] = json.dumps(
                [
                    {
                        "hostPath": spec.host_path,
                        "mountPath": mount_path,
                        "readOnly": spec.host_path_mode == BoxHostMountMode.READ_ONLY,
                    }
                ]
            )
        if metadata:
            create_kwargs["metadata"] = metadata

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

        await self._sync_mounts_to_e2b(sandbox, spec)

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

        await self._sync_mounts_from_e2b(sandbox, spec)

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

    async def _sync_mounts_to_e2b(self, sandbox, spec: BoxSpec) -> None:
        """Upload Workspace data and atomically materialize immutable mounts."""
        shadowed_paths = self._main_mount_shadow_paths(spec)
        if spec.host_path is not None and spec.host_path_mode != BoxHostMountMode.NONE:
            if spec.host_path_mode == BoxHostMountMode.READ_ONLY:
                await self._materialize_immutable_mount(
                    sandbox,
                    host_root=spec.host_path,
                    remote_root=_adapt_path_for_e2b(spec.mount_path),
                )
            else:
                await self._sync_host_tree_to_e2b(
                    sandbox,
                    host_root=spec.host_path,
                    remote_root=_adapt_path_for_e2b(spec.mount_path),
                    excluded_relative_paths=shadowed_paths,
                )

        for mount in spec.extra_mounts:
            if mount.mode == BoxHostMountMode.NONE:
                continue
            if mount.mode == BoxHostMountMode.READ_ONLY:
                await self._materialize_immutable_mount(
                    sandbox,
                    host_root=mount.host_path,
                    remote_root=_adapt_path_for_e2b(mount.mount_path),
                    expected_digest=mount.content_digest,
                    manifest_path=mount.manifest_path,
                )
            else:
                await self._sync_host_tree_to_e2b(
                    sandbox,
                    host_root=mount.host_path,
                    remote_root=_adapt_path_for_e2b(mount.mount_path),
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

    async def _sync_mounts_from_e2b(self, sandbox, spec: BoxSpec) -> None:
        """Best-effort download of writable E2B mounts into host paths."""
        if (
            spec.host_path is not None
            and spec.host_path_mode == BoxHostMountMode.READ_WRITE
        ):
            await self._sync_e2b_tree_to_host(
                sandbox,
                remote_root=_adapt_path_for_e2b(spec.mount_path),
                host_root=spec.host_path,
                excluded_relative_paths=self._main_mount_shadow_paths(spec),
            )

        for mount in spec.extra_mounts:
            if mount.mode != BoxHostMountMode.READ_WRITE:
                continue
            await self._sync_e2b_tree_to_host(
                sandbox,
                remote_root=_adapt_path_for_e2b(mount.mount_path),
                host_root=mount.host_path,
            )

    async def _sync_host_tree_to_e2b(
        self,
        sandbox,
        *,
        host_root: str,
        remote_root: str,
        excluded_relative_paths: set[str] | None = None,
    ) -> None:
        """Best-effort sync for public E2B, which has no local bind mounts."""
        if not os.path.isdir(host_root):
            return

        synced_files = 0
        synced_bytes = 0
        pending = []
        pending_bytes = 0

        async def flush():
            nonlocal synced_files, synced_bytes, pending_bytes
            if not pending:
                return
            try:
                if len(pending) == 1:
                    await sandbox.files.write(pending[0]["path"], pending[0]["data"])
                else:
                    await sandbox.files.write_files(list(pending))
                synced_files += len(pending)
                synced_bytes += pending_bytes
            except Exception as exc:
                self.logger.debug(f"Failed to upload E2B sync batch: {exc}")
                if len(pending) > 1:
                    # A failed batch must not prevent independent files from syncing.
                    for entry in pending:
                        try:
                            await sandbox.files.write(entry["path"], entry["data"])
                            synced_files += 1
                            synced_bytes += len(entry["data"])
                        except Exception as file_exc:
                            self.logger.debug(
                                f"Failed to sync host file to E2B {entry['path']}: {file_exc}"
                            )
            pending.clear()
            pending_bytes = 0

        excluded = excluded_relative_paths or set()
        for root, dirs, files in os.walk(host_root):
            rel_dir = os.path.relpath(root, host_root)
            portable_rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
            dirs[:] = [
                directory
                for directory in dirs
                if directory not in {".git", "__pycache__", ".venv", "node_modules"}
                and not self._path_is_shadowed(
                    posixpath.join(portable_rel_dir, directory).lstrip("/"),
                    excluded,
                )
            ]
            remote_dir = (
                remote_root
                if rel_dir == "."
                else posixpath.join(remote_root, rel_dir.replace(os.sep, "/"))
            )
            try:
                await sandbox.commands.run(
                    f"mkdir -p {shlex.quote(remote_dir)}", timeout=10
                )
            except Exception as exc:
                self.logger.debug(f"Failed to create E2B sync dir {remote_dir}: {exc}")
                continue

            for filename in files:
                relative_file = posixpath.join(portable_rel_dir, filename).lstrip("/")
                if self._path_is_shadowed(relative_file, excluded):
                    continue
                if synced_files + len(pending) >= _MAX_E2B_SYNC_FILES:
                    await flush()
                    return
                host_file = os.path.join(root, filename)
                try:
                    data = await asyncio.to_thread(
                        _read_e2b_host_file_limited,
                        host_file,
                    )
                    if (
                        synced_bytes + pending_bytes + len(data)
                        > _MAX_E2B_SYNC_TOTAL_BYTES
                    ):
                        await flush()
                        return
                    remote_file = posixpath.join(remote_dir, filename)
                    if pending and pending_bytes + len(data) > _E2B_UPLOAD_BATCH_BYTES:
                        await flush()
                    pending.append({"path": remote_file, "data": data})
                    pending_bytes += len(data)
                    if len(pending) >= _E2B_UPLOAD_BATCH_FILES:
                        await flush()
                except Exception as exc:
                    self.logger.debug(
                        f"Failed to sync host file to E2B {host_file}: {exc}"
                    )
        await flush()

    async def _sync_e2b_tree_to_host(
        self,
        sandbox,
        *,
        remote_root: str,
        host_root: str,
        excluded_relative_paths: set[str] | None = None,
    ) -> None:
        """Best-effort download of an E2B mount into the matching host path."""
        await asyncio.to_thread(os.makedirs, host_root, exist_ok=True)
        try:
            entries = await sandbox.files.list(remote_root, depth=16)
        except Exception as exc:
            self.logger.debug(f"Failed to list E2B mount for sync {remote_root}: {exc}")
            return

        synced_files = 0
        synced_bytes = 0
        pending = []

        async def download(remote_path):
            try:
                stream = await sandbox.files.read(
                    remote_path, format="stream", request_timeout=30
                )
                data = bytearray()
                async for chunk in stream:
                    if len(data) + len(chunk) > _MAX_E2B_SYNC_FILE_BYTES:
                        raise ValueError("E2B remote sync file exceeds the size limit")
                    if (
                        synced_bytes + len(data) + len(chunk)
                        > _MAX_E2B_SYNC_TOTAL_BYTES
                    ):
                        raise ValueError("E2B remote sync exceeds the total size limit")
                    data.extend(chunk)
                return bytes(data)
            except Exception as exc:
                self.logger.debug(
                    f"Failed to sync E2B file to host {remote_path}: {exc}"
                )

        async def flush_downloads():
            nonlocal synced_files, synced_bytes
            if len(pending) == 1:
                bodies = [await download(pending[0][0])]
            else:
                bodies = await asyncio.gather(*(download(path) for path, _ in pending))
            # Commit in listing order; failed reads/writes must not consume quota.
            for (remote_path, host_path), data in zip(pending, bodies):
                if data is None:
                    continue
                try:
                    if synced_bytes + len(data) > _MAX_E2B_SYNC_TOTAL_BYTES:
                        raise ValueError("E2B remote sync exceeds the total size limit")
                    await asyncio.to_thread(_write_e2b_host_file, host_path, data)
                    synced_files += 1
                    synced_bytes += len(data)
                except Exception as exc:
                    self.logger.debug(
                        f"Failed to sync E2B file to host {remote_path}: {exc}"
                    )
            pending.clear()

        excluded = excluded_relative_paths or set()
        for entry in entries[:_MAX_E2B_SYNC_ENTRIES]:
            remote_path = str(getattr(entry, "path", "") or "")
            if (
                not remote_path
                or remote_path == remote_root
                or not remote_path.startswith(remote_root + "/")
            ):
                continue
            rel_path = remote_path[len(remote_root) :].lstrip("/")
            if self._path_is_shadowed(rel_path, excluded):
                continue
            real_host_root = os.path.realpath(host_root)
            host_path = os.path.realpath(
                os.path.join(real_host_root, *rel_path.split("/"))
            )
            if not (
                host_path == real_host_root
                or host_path.startswith(real_host_root + os.sep)
            ):
                continue

            entry_type = getattr(getattr(entry, "type", None), "value", "")
            try:
                if entry_type == "dir":
                    await asyncio.to_thread(os.makedirs, host_path, exist_ok=True)
                elif entry_type == "file":
                    if synced_files >= _MAX_E2B_SYNC_FILES:
                        break
                    declared_size = int(getattr(entry, "size", 0) or 0)
                    if declared_size > _MAX_E2B_SYNC_FILE_BYTES:
                        continue
                    pending.append((remote_path, host_path))
                    if len(pending) >= min(
                        _E2B_DOWNLOAD_CONCURRENCY, _MAX_E2B_SYNC_FILES - synced_files
                    ):
                        await flush_downloads()
            except Exception as exc:
                self.logger.debug(
                    f"Failed to sync E2B file to host {remote_path}: {exc}"
                )
        if pending:
            await flush_downloads()

    @staticmethod
    def _main_mount_shadow_paths(spec: BoxSpec) -> set[str]:
        main_root = _adapt_path_for_e2b(spec.mount_path).rstrip("/")
        shadowed: set[str] = set()
        for mount in spec.extra_mounts:
            if mount.mode == BoxHostMountMode.NONE:
                continue
            target = _adapt_path_for_e2b(mount.mount_path)
            if target.startswith(main_root + "/"):
                shadowed.add(target[len(main_root) :].lstrip("/"))
        return shadowed

    @staticmethod
    def _path_is_shadowed(relative_path: str, shadowed_paths: set[str]) -> bool:
        normalized = posixpath.normpath(relative_path).lstrip("/")
        return any(
            normalized == shadowed or normalized.startswith(shadowed + "/")
            for shadowed in shadowed_paths
        )

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
