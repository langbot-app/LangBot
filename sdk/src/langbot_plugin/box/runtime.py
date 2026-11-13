from __future__ import annotations

import asyncio
import collections
import contextlib
import dataclasses
import datetime as dt
import hashlib
import heapq
import json
import logging
import os
from pathlib import Path
import stat
import time
import weakref
from typing import TYPE_CHECKING

import pydantic

from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.event_loop_monitor import EventLoopLagMonitor

from .backend import BaseSandboxBackend, CLISandboxBackend, DockerBackend
from .host_backend import HostProcessBackend
from .identity import BoxIdentity
from .nsjail_backend import NsjailBackend
from .errors import (
    BoxAdmissionError,
    BoxBackendUnavailableError,
    BoxCapacityExceededError,
    BoxError,
    BoxManagedProcessNotFoundError,
    BoxReadinessError,
    BoxSessionConflictError,
    BoxSessionNotFoundError,
    BoxRuntimeUnavailableError,
    BoxValidationError,
)
from .models import (
    DEFAULT_BOX_IMAGE,
    DEFAULT_BOX_MOUNT_PATH,
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxManagedProcessInfo,
    BoxManagedProcessSpec,
    BoxManagedProcessStatus,
    BoxMountSpec,
    BoxSessionInfo,
    BoxSpec,
    E2BConnectionConfig,
    BoxHostMountMode,
    BoxNetworkMode,
    SandboxAdmissionGrant,
    SandboxAdmissionPolicy,
    SandboxAdmissionRevocation,
)
from .security import validate_shared_workspace_probe_name
from .tenancy import (
    box_namespace,
    namespace_session_id,
)
from langbot_plugin.storage import collect_storage_directories, storage_total_bytes

if TYPE_CHECKING:
    from .e2b_backend import E2BSandboxBackend

_UTC = dt.timezone.utc
_MANAGED_PROCESS_STDERR_PREVIEW_LIMIT = 4000
_MANAGED_PROCESS_STDERR_READ_BYTES = 64 * 1024
_MANAGED_PROCESS_STDERR_LOG_CHUNKS_PER_WINDOW = 4
_MANAGED_PROCESS_STDERR_LOG_WINDOW_SEC = 1.0
_MANAGED_PROCESS_STDERR_LOG_EXCERPT_CHARS = 512
_REAPER_INTERVAL_SEC = 30
_UNSAFE_SOFT_STORAGE_LIMITS_ENV = "LANGBOT_BOX_ALLOW_UNSAFE_SOFT_STORAGE_LIMITS"
MAX_RUNTIME_SESSIONS = 5_000
MAX_RUNTIME_MANAGED_PROCESSES = 1_024
MAX_RUNTIME_COMPLETED_PROCESSES = 10_000
MAX_RUNTIME_ADMISSION_RECORDS = 250_000
MAX_RUNTIME_RPC_FILE_BYTES = 100 * 1024 * 1024
MAX_RUNTIME_COMPLETED_RETENTION_SEC = 86_400
MAX_ADMITTED_READ_ONLY_MOUNTS = 256


def _unsafe_soft_storage_limits_enabled() -> bool:
    return os.getenv(_UNSAFE_SOFT_STORAGE_LIMITS_ENV, "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _bounded_runtime_limit(
    limits: dict,
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = limits.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"box.limits.{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"box.limits.{name} must be between {minimum} and {maximum}")
    return value


def _resolve_local_path(path_value: str, *, base: str | None = None) -> str:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = (Path(base).expanduser() / path) if base else (Path.cwd() / path)
    return str(path.resolve())


@dataclasses.dataclass(slots=True)
class _ManagedProcess:
    spec: BoxManagedProcessSpec
    process: asyncio.subprocess.Process
    started_at: dt.datetime
    attach_lock: asyncio.Lock
    stderr_chunks: collections.deque[str]
    stderr_total_len: int = 0
    exit_code: int | None = None
    exited_at: dt.datetime | None = None

    @property
    def is_running(self) -> bool:
        return self.exit_code is None and self.process.returncode is None


@dataclasses.dataclass(slots=True)
class _RuntimeSession:
    info: BoxSessionInfo
    lock: asyncio.Lock
    backend: BaseSandboxBackend | None = None
    workspace_key: tuple[str, str] | None = None
    managed_processes: dict[str, _ManagedProcess] = dataclasses.field(
        default_factory=dict
    )
    # Signature of the extra bind mounts the container was created with. Used
    # to detect when a reused session would be missing newly-requested mounts.
    extra_mounts_key: frozenset[tuple[str, str, str, str, str]] = frozenset()
    closing: bool = False
    idle_ttl_sec: int | None = None


def _compute_extra_mounts_key(
    spec: BoxSpec,
) -> frozenset[tuple[str, str, str, str, str]]:
    """Signature of a spec's effective extra bind mounts.

    Mirrors the backend's mount filtering (``mode == "none"`` mounts are not
    bind-mounted; see ``DockerBackend.start_session``) so two specs that produce
    the same set of ``-v`` flags compare equal. A bind mount cannot be added to
    an already-running container, so this is used to detect when a reused
    session would be missing newly-requested mounts and must reject reuse.
    """
    key: set[tuple[str, str, str, str, str]] = set()
    for mount in spec.extra_mounts:
        mode_val = mount.mode.value if hasattr(mount.mode, "value") else str(mount.mode)
        if mode_val == "none":
            continue
        key.add(
            (
                mount.host_path,
                mount.mount_path,
                mode_val,
                str(mount.content_digest or ""),
                str(mount.manifest_path or ""),
            )
        )
    return frozenset(key)


class BoxRuntime:
    def __init__(
        self,
        logger: logging.Logger,
        backends: list[BaseSandboxBackend] | None = None,
        session_ttl_sec: int = 300,
        max_sessions: int = 64,
        max_managed_processes: int = 64,
        max_completed_processes: int = 256,
        completed_process_retention_sec: int = 300,
        instance_id: str | None = None,
        data_dir: str | Path | None = None,
    ):
        self.logger = logger
        self._unsafe_soft_storage_limits = _unsafe_soft_storage_limits_enabled()
        if self._unsafe_soft_storage_limits:
            logger.warning(
                "%s is enabled: managed sandboxes do not have hard byte/inode "
                "storage quotas; use only in disposable non-production environments",
                _UNSAFE_SOFT_STORAGE_LIMITS_ENV,
            )

        # Load configuration from environment variable (passed by LangBot)
        self._box_config: dict = {}
        config_json = os.getenv("LANGBOT_BOX_CONFIG", "")
        if config_json:
            try:
                self._box_config = json.loads(config_json)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse LANGBOT_BOX_CONFIG: {config_json[:100]}"
                )

        # Build backend list
        if backends is None:
            backends = [
                DockerBackend(logger),
                NsjailBackend(logger),
                self._create_e2b_backend(logger),
                HostProcessBackend(logger),
            ]

        self.backends = backends
        self.session_ttl_sec = session_ttl_sec
        limits = self._box_config.get("limits") or {}
        if not isinstance(limits, dict):
            raise ValueError("box.limits must be an object")
        self.max_sessions = _bounded_runtime_limit(
            limits,
            "max_sessions",
            max_sessions,
            minimum=0,
            maximum=MAX_RUNTIME_SESSIONS,
        )
        self.max_managed_processes = _bounded_runtime_limit(
            limits,
            "max_managed_processes",
            max_managed_processes,
            minimum=0,
            maximum=MAX_RUNTIME_MANAGED_PROCESSES,
        )
        self.max_completed_processes = _bounded_runtime_limit(
            limits,
            "max_completed_processes",
            max_completed_processes,
            minimum=0,
            maximum=MAX_RUNTIME_COMPLETED_PROCESSES,
        )
        self.max_admission_records = _bounded_runtime_limit(
            limits,
            "max_admission_records",
            100_000,
            minimum=1,
            maximum=MAX_RUNTIME_ADMISSION_RECORDS,
        )
        self.max_rpc_file_bytes = _bounded_runtime_limit(
            limits,
            "max_rpc_file_bytes",
            20 * 1024 * 1024,
            minimum=1,
            maximum=MAX_RUNTIME_RPC_FILE_BYTES,
        )
        self.completed_process_retention_sec = _bounded_runtime_limit(
            limits,
            "completed_process_retention_sec",
            completed_process_retention_sec,
            minimum=0,
            maximum=MAX_RUNTIME_COMPLETED_RETENTION_SEC,
        )
        self._backend: BaseSandboxBackend | None = None
        self._backend_lock = asyncio.Lock()
        self._backends_cache: tuple[float, list[dict]] | None = None
        self._backends_probe_lock = asyncio.Lock()
        self._initialized_backends: set[str] = set()
        self._can_cleanup_orphans = False
        self._sessions: dict[str, _RuntimeSession] = {}
        self._expirable_session_ids: set[str] = set()
        self._managed_process_session_ids: set[str] = set()
        self._session_ids_by_workspace: dict[tuple[str, str], set[str]] = {}
        self._workspace_reserved_sessions: dict[tuple[str, str], set[str]] = {}
        self._lock = asyncio.Lock()
        self._session_operation_locks: weakref.WeakValueDictionary[
            str, asyncio.Lock
        ] = weakref.WeakValueDictionary()
        self._session_leases: collections.Counter[str] = collections.Counter()
        self._creating_session_tasks: dict[str, asyncio.Task] = {}
        self._managed_starting_count = 0
        self._shutdown_in_progress = False
        self._reaper_task: asyncio.Task | None = None
        self._reaper_wakeup = asyncio.Event()
        self._active_exec_counts: collections.Counter[str] = collections.Counter()
        self._closing_session_tasks: dict[str, asyncio.Task[None]] = {}
        self._background_tasks: set[asyncio.Task] = set()
        self._identity = BoxIdentity(
            logger,
            instance_id
            if instance_id is not None
            else (
                os.environ.get("LANGBOT_BOX_INSTANCE_ID")
                or self._box_config.get("instance_id")
            ),
            data_dir,
        )
        self.instance_id = self._identity.instance_id
        for backend in self.backends:
            if backend is not None:
                backend.instance_id = self.instance_id
        self._admission_policy = SandboxAdmissionPolicy()
        self._admission_config_error: str | None = None
        self._admission_grants: dict[tuple[str, str], SandboxAdmissionGrant] = {}
        self._admission_expiry_heap: list[tuple[float, tuple[str, str], int, int]] = []
        self._admission_revisions: dict[tuple[str, str], int] = {}
        self._admission_generations: dict[tuple[str, str], int] = {}
        self._admission_limit_fingerprints: dict[tuple[str, str], tuple[int, int]] = {}
        self._revoked_admission_revisions: dict[tuple[str, str], int] = {}
        self._readiness_cache: tuple[float, dict] | None = None
        self.event_loop_monitor = EventLoopLagMonitor()
        self._refresh_admission_policy()

    def _create_e2b_backend(self, logger: logging.Logger) -> "E2BSandboxBackend | None":
        """Create E2B backend if package is installed."""
        try:
            from .e2b_backend import E2BSandboxBackend

            return E2BSandboxBackend(logger)
        except ImportError:
            logger.debug("e2b package not installed, E2B backend unavailable")
            return None

    async def initialize(self):
        # Apply configuration from env var to all backends
        if self._box_config:
            self._apply_config_to_backends(self._box_config)
            self._ensure_default_workspace()

        self._backend = await self._select_backend()
        self._can_cleanup_orphans = self._identity.acquire()
        if self._backend is not None:
            self._initialized_backends.add(self._backend.name)
            if self._can_cleanup_orphans:
                try:
                    await self._backend.cleanup_orphaned_containers(self.instance_id)
                except Exception as exc:
                    self.logger.warning(
                        f"LangBot Box orphan container cleanup failed: {exc}"
                    )
                except BaseException:
                    self._identity.release()
                    raise

        self.start_background_reaper()
        self.event_loop_monitor.start()

    def init(self, config: dict) -> None:
        """Initialize with full box configuration from LangBot.

        Called via RPC (INIT action) when connecting over WebSocket.
        """
        if "instance_id" in config and config["instance_id"] != self.instance_id:
            raise ValueError(
                "Box instance_id is fixed at startup; configure it before launching the runtime"
            )
        previous_admission_policy = self._admission_policy
        candidate_config = dict(self._box_config)
        candidate_config.update(config)
        limits = candidate_config.get("limits") or {}
        if not isinstance(limits, dict):
            raise ValueError("box.limits must be an object")
        max_sessions = _bounded_runtime_limit(
            limits,
            "max_sessions",
            self.max_sessions,
            minimum=0,
            maximum=MAX_RUNTIME_SESSIONS,
        )
        max_managed_processes = _bounded_runtime_limit(
            limits,
            "max_managed_processes",
            self.max_managed_processes,
            minimum=0,
            maximum=MAX_RUNTIME_MANAGED_PROCESSES,
        )
        max_completed_processes = _bounded_runtime_limit(
            limits,
            "max_completed_processes",
            self.max_completed_processes,
            minimum=0,
            maximum=MAX_RUNTIME_COMPLETED_PROCESSES,
        )
        max_admission_records = _bounded_runtime_limit(
            limits,
            "max_admission_records",
            self.max_admission_records,
            minimum=1,
            maximum=MAX_RUNTIME_ADMISSION_RECORDS,
        )
        max_rpc_file_bytes = _bounded_runtime_limit(
            limits,
            "max_rpc_file_bytes",
            self.max_rpc_file_bytes,
            minimum=1,
            maximum=MAX_RUNTIME_RPC_FILE_BYTES,
        )
        completed_process_retention_sec = _bounded_runtime_limit(
            limits,
            "completed_process_retention_sec",
            self.completed_process_retention_sec,
            minimum=0,
            maximum=MAX_RUNTIME_COMPLETED_RETENTION_SEC,
        )
        self._box_config = candidate_config
        self.max_sessions = max_sessions
        self.max_managed_processes = max_managed_processes
        self.max_completed_processes = max_completed_processes
        self.max_admission_records = max_admission_records
        self.max_rpc_file_bytes = max_rpc_file_bytes
        self.completed_process_retention_sec = completed_process_retention_sec
        self._apply_config_to_backends(config)
        self._refresh_admission_policy()
        if previous_admission_policy.required and not self._admission_policy.required:
            self._admission_policy = previous_admission_policy
            self._admission_config_error = (
                "Sandbox admission enforcement cannot be disabled without "
                "restarting the Box Runtime"
            )
        self._readiness_cache = None
        self._backends_cache = None
        self._ensure_default_workspace()
        if not self._sessions:
            self._backend = None

    @property
    def admission_required(self) -> bool:
        return bool(self._admission_policy.required)

    @property
    def admission_policy(self) -> SandboxAdmissionPolicy:
        return self._admission_policy

    def _refresh_admission_policy(self) -> None:
        raw_policy = self._box_config.get("admission")
        if raw_policy is None:
            self._admission_policy = SandboxAdmissionPolicy()
            self._admission_config_error = None
            return
        try:
            self._admission_policy = SandboxAdmissionPolicy.model_validate(raw_policy)
            self._admission_config_error = None
        except (pydantic.ValidationError, TypeError, ValueError) as exc:
            # Merely having a malformed admission section must never downgrade
            # the runtime to unrestricted OSS behavior.
            self._admission_policy = SandboxAdmissionPolicy(required=True)
            self._admission_config_error = str(exc)

    def _local_config(self) -> dict:
        return self._box_config.get("local") or {}

    def _host_root(self) -> str | None:
        host_root = str(self._local_config().get("host_root", "") or "").strip()
        if not host_root:
            return None
        return _resolve_local_path(host_root)

    def _default_workspace(self) -> str | None:
        host_root = self._host_root()
        default_workspace = str(
            self._local_config().get("default_workspace", "") or ""
        ).strip()
        if not default_workspace:
            if host_root is None:
                return None
            default_workspace = "default"
        return _resolve_local_path(default_workspace, base=host_root)

    def _allowed_mount_roots(self) -> list[str]:
        configured_roots = self._local_config().get("allowed_mount_roots", [])
        if isinstance(configured_roots, str):
            configured_roots = [
                item.strip() for item in configured_roots.split(",") if item.strip()
            ]

        host_root = self._host_root()
        roots: list[str] = []
        for root in configured_roots or []:
            root_value = str(root or "").strip()
            if root_value:
                # Mount allow-list entries are host paths. Relative values in
                # the shipped config (for example ``./data/box``) are relative
                # to the runtime working directory, not nested under host_root.
                roots.append(_resolve_local_path(root_value))

        if not roots and host_root is not None:
            roots.append(host_root)
        return roots

    def _ensure_default_workspace(self) -> None:
        default_workspace = self._default_workspace()
        if default_workspace is None:
            return

        if os.path.isdir(default_workspace):
            return

        if os.path.exists(default_workspace):
            raise BoxValidationError(
                "box.local.default_workspace must point to a directory on the Box runtime host"
            )

        allowed_roots = self._allowed_mount_roots()
        if not allowed_roots:
            raise BoxValidationError(
                "box.local.default_workspace cannot be created because no allowed_mount_roots are configured"
            )

        for allowed_root in allowed_roots:
            if default_workspace == allowed_root or default_workspace.startswith(
                f"{allowed_root}{os.sep}"
            ):
                os.makedirs(default_workspace, exist_ok=True)
                return

        raise BoxValidationError(
            "box.local.default_workspace is outside allowed_mount_roots: "
            + ", ".join(allowed_roots)
        )

    @staticmethod
    def _grant_context(grant: SandboxAdmissionGrant) -> ActionContext:
        return ActionContext(
            instance_uuid=grant.instance_uuid,
            workspace_uuid=grant.workspace_uuid,
            placement_generation=grant.execution_generation,
        )

    @staticmethod
    def _path_is_under(path: str, root: str) -> bool:
        try:
            return os.path.commonpath((path, root)) == root
        except ValueError:
            return False

    def _managed_workspace_root(self) -> str:
        default_workspace = self._default_workspace()
        if default_workspace is None:
            raise BoxReadinessError(
                "Managed sandbox admission requires box.local.default_workspace"
            )
        resolved_default = _resolve_local_path(default_workspace)
        allowed_roots = self._allowed_mount_roots()
        if not allowed_roots or not any(
            self._path_is_under(resolved_default, allowed_root)
            for allowed_root in allowed_roots
        ):
            raise BoxReadinessError(
                "Managed sandbox workspace is outside box.local.allowed_mount_roots"
            )
        if not os.path.isdir(resolved_default):
            raise BoxReadinessError("Managed sandbox workspace path is not a directory")
        if not os.access(resolved_default, os.R_OK | os.W_OK | os.X_OK):
            raise BoxReadinessError("Managed sandbox workspace path is not writable")
        return resolved_default

    async def get_storage_analysis(self, action_context: ActionContext) -> dict:
        """Measure host-persistent and backend-internal Workspace storage."""

        context = ActionContext.model_validate(action_context).without_installation()
        namespace = box_namespace(context)
        host_roots: list[tuple[str, Path, str, str | None]] = []
        try:
            managed_root = self._managed_workspace_root()
        except BoxReadinessError:
            managed_root = None
        if managed_root is not None:
            tenants_root = _resolve_local_path(os.path.join(managed_root, "tenants"))
            if not self._path_is_under(tenants_root, managed_root):
                raise BoxAdmissionError(
                    "Managed sandbox tenant directory escapes the configured workspace"
                )
            workspace_path = Path(tenants_root) / namespace
            host_roots.extend(
                (
                    ("workspace", workspace_path, "root", None),
                    ("mcp", workspace_path / ".mcp", "detail", "workspace"),
                    ("inbox", workspace_path / "inbox", "detail", "workspace"),
                    ("outbox", workspace_path / "outbox", "detail", "workspace"),
                )
            )

        directories = await asyncio.to_thread(collect_storage_directories, host_roots)
        for directory in directories:
            directory["scope"] = "runtime_host"

        async with self._lock:
            sessions = [
                self._sessions[session_id]
                for session_id in self._workspace_session_ids_locked(context)
                if session_id in self._sessions
            ]
            managed_processes = sum(
                len(runtime_session.managed_processes) for runtime_session in sessions
            )

        sandbox_reports = await asyncio.gather(
            *(
                self._sandbox_session_storage(runtime_session)
                for runtime_session in sessions
            ),
            return_exceptions=True,
        )
        directories.extend(self._aggregate_sandbox_storage(sessions, sandbox_reports))
        return {
            "size_bytes": storage_total_bytes(directories),
            "directories": directories,
            "active_sessions": len(sessions),
            "managed_processes": managed_processes,
        }

    async def _sandbox_session_storage(
        self,
        runtime_session: _RuntimeSession,
    ) -> dict[str, dict[str, int | bool]]:
        command = """
for item in 'session_workspaces|/workspace' 'session_caches|/root/.cache' 'session_temp|/tmp'; do
  key=${item%%|*}
  path=${item#*|}
  if [ -e "$path" ]; then
    set -- $(du -sk "$path" 2>/dev/null)
    kb=${1:-0}
    files=$(find "$path" -type f 2>/dev/null | wc -l)
    printf '%s\t1\t%s\t%s\n' "$key" "$kb" "$files"
  else
    printf '%s\t0\t0\t0\n' "$key"
  fi
done
""".strip()
        spec = BoxSpec(
            session_id=runtime_session.info.session_id,
            cmd=command,
            workdir="/",
            timeout_sec=15,
        )
        async with runtime_session.lock:
            if runtime_session.closing:
                raise BoxSessionNotFoundError(
                    f"session {runtime_session.info.session_id} is being deleted"
                )
            result = await runtime_session.backend.exec(runtime_session.info, spec)
        if not result.ok:
            raise BoxError(result.stderr or "Sandbox storage probe failed")

        report: dict[str, dict[str, int | bool]] = {}
        for line in result.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) != 4 or fields[0] not in {
                "session_workspaces",
                "session_caches",
                "session_temp",
            }:
                continue
            try:
                report[fields[0]] = {
                    "exists": fields[1] == "1",
                    "size_bytes": max(int(fields[2]), 0) * 1024,
                    "file_count": max(int(fields[3]), 0),
                }
            except ValueError:
                continue
        return report

    @staticmethod
    def _aggregate_sandbox_storage(
        sessions: list[_RuntimeSession],
        reports: list[dict[str, dict[str, int | bool]] | BaseException],
    ) -> list[dict]:
        keys = ("session_workspaces", "session_caches", "session_temp")
        totals = {
            key: {"exists": False, "size_bytes": 0, "file_count": 0} for key in keys
        }
        managed_workspaces = {"exists": False, "size_bytes": 0, "file_count": 0}
        error_count = 0
        included_sessions = 0
        managed_sessions = 0
        for runtime_session, report in zip(sessions, reports, strict=True):
            if isinstance(report, BaseException):
                error_count += 1
                continue
            included_sessions += 1
            workspace_is_host_mounted = runtime_session.info.host_path is not None
            has_managed_process = bool(runtime_session.managed_processes)
            for key in keys:
                if key == "session_workspaces" and workspace_is_host_mounted:
                    continue
                value = report.get(key) or {}
                totals[key]["exists"] = totals[key]["exists"] or bool(
                    value.get("exists")
                )
                totals[key]["size_bytes"] += int(value.get("size_bytes") or 0)
                totals[key]["file_count"] += int(value.get("file_count") or 0)
            if has_managed_process and not workspace_is_host_mounted:
                managed_sessions += 1
                value = report.get("session_workspaces") or {}
                managed_workspaces["exists"] = managed_workspaces["exists"] or bool(
                    value.get("exists")
                )
                managed_workspaces["size_bytes"] += int(value.get("size_bytes") or 0)
                managed_workspaces["file_count"] += int(value.get("file_count") or 0)

        if not sessions:
            return []
        directories = []
        paths = {
            "session_workspaces": "/workspace",
            "session_caches": "/root/.cache",
            "session_temp": "/tmp",
        }
        for key in keys:
            value = totals[key]
            directories.append(
                {
                    "key": key,
                    "path": f"{paths[key]} ({included_sessions} sandbox sessions)",
                    "kind": "root",
                    "exists": value["exists"],
                    "size_bytes": value["size_bytes"],
                    "file_count": value["file_count"],
                    "error_count": error_count,
                    "scope": "sandbox_sessions",
                }
            )
        if managed_sessions:
            directories.append(
                {
                    "key": "managed_process_workspaces",
                    "path": f"/workspace ({managed_sessions} managed-process sessions)",
                    "kind": "detail",
                    "parent_key": "session_workspaces",
                    "exists": managed_workspaces["exists"],
                    "size_bytes": managed_workspaces["size_bytes"],
                    "file_count": managed_workspaces["file_count"],
                    "error_count": error_count,
                    "scope": "sandbox_sessions",
                }
            )
        return directories

    def verify_shared_workspace(self, marker_name: str) -> dict:
        """Digest one Core-created marker from the canonical shared root.

        This host-control operation intentionally accepts only an opaque
        basename. It never accepts a caller-supplied directory and never follows
        the marker if an attacker replaces it with a symlink.
        """

        marker_name = validate_shared_workspace_probe_name(marker_name)
        workspace_root = self._managed_workspace_root()
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        root_fd: int | None = None
        marker_fd: int | None = None
        try:
            if os.name == "nt":
                # Windows does not allow opening a directory with os.open().
                # Validate the marker itself before and after opening it so a
                # reparse point or path swap cannot redirect the readiness probe.
                marker_path = os.path.join(workspace_root, marker_name)
                marker_lstat = os.lstat(marker_path)
                file_attributes = getattr(marker_lstat, "st_file_attributes", 0)
                reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                if stat.S_ISLNK(marker_lstat.st_mode) or (
                    reparse_point and file_attributes & reparse_point
                ):
                    raise BoxReadinessError(
                        "Box Runtime cannot read the Core shared Workspace probe"
                    )
                marker_fd = os.open(
                    marker_path,
                    os.O_RDONLY | getattr(os, "O_BINARY", 0),
                )
                marker_stat = os.fstat(marker_fd)
                if (marker_lstat.st_dev, marker_lstat.st_ino) != (
                    marker_stat.st_dev,
                    marker_stat.st_ino,
                ):
                    raise BoxReadinessError(
                        "Box shared Workspace probe changed while being verified"
                    )
            else:
                directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                root_fd = os.open(workspace_root, directory_flags | nofollow)
                marker_fd = os.open(
                    marker_name,
                    os.O_RDONLY | nofollow,
                    dir_fd=root_fd,
                )
                marker_stat = os.fstat(marker_fd)

            if not stat.S_ISREG(marker_stat.st_mode):
                raise BoxReadinessError(
                    "Box shared Workspace probe is not a regular file"
                )
            if marker_stat.st_size <= 0 or marker_stat.st_size > 1024:
                raise BoxReadinessError(
                    "Box shared Workspace probe has an invalid size"
                )
            digest = hashlib.sha256()
            total = 0
            while True:
                chunk = os.read(marker_fd, min(1024 - total + 1, 1024))
                if not chunk:
                    break
                total += len(chunk)
                if total > 1024:
                    raise BoxReadinessError(
                        "Box shared Workspace probe exceeds the size limit"
                    )
                digest.update(chunk)
            if total != marker_stat.st_size:
                raise BoxReadinessError(
                    "Box shared Workspace probe changed while being verified"
                )
            return {
                "marker_name": marker_name,
                "sha256": digest.hexdigest(),
                "size": total,
            }
        except (FileNotFoundError, NotADirectoryError, OSError) as exc:
            if isinstance(exc, BoxReadinessError):
                raise
            raise BoxReadinessError(
                "Box Runtime cannot read the Core shared Workspace probe"
            ) from exc
        finally:
            if marker_fd is not None:
                os.close(marker_fd)
            if root_fd is not None:
                os.close(root_fd)

    def _canonical_workspace_path(self, context: ActionContext) -> str:
        context = ActionContext.model_validate(context).without_installation()
        default_workspace = self._managed_workspace_root()
        raw_tenants_root = os.path.join(default_workspace, "tenants")
        os.makedirs(raw_tenants_root, exist_ok=True)
        tenants_root = _resolve_local_path(raw_tenants_root)
        if not self._path_is_under(tenants_root, default_workspace):
            raise BoxAdmissionError(
                "Managed sandbox tenant directory escapes the configured workspace"
            )

        raw_workspace_path = os.path.join(tenants_root, box_namespace(context))
        workspace_path = _resolve_local_path(raw_workspace_path)
        if not self._path_is_under(workspace_path, tenants_root):
            raise BoxAdmissionError(
                "Managed sandbox Workspace path escapes its tenant directory"
            )
        os.makedirs(workspace_path, exist_ok=True)
        return workspace_path

    def _normalize_admitted_extra_mounts(
        self,
        mounts: list[BoxMountSpec],
    ) -> list[BoxMountSpec]:
        """Validate trusted Core-provided artifacts without domain semantics."""

        if len(mounts) > MAX_ADMITTED_READ_ONLY_MOUNTS:
            raise BoxAdmissionError(
                f"Managed sandbox accepts at most {MAX_ADMITTED_READ_ONLY_MOUNTS} read-only mounts"
            )
        allowed_roots = self._allowed_mount_roots()
        if mounts and not allowed_roots:
            raise BoxAdmissionError(
                "Managed sandbox read-only mounts require allowed_mount_roots"
            )

        normalized: list[BoxMountSpec] = []
        destinations: set[str] = set()
        for mount in mounts:
            if mount.mode != BoxHostMountMode.READ_ONLY:
                raise BoxAdmissionError(
                    "Managed sandbox additional mounts must be read-only"
                )
            host_path = _resolve_local_path(mount.host_path)
            if not os.path.isdir(host_path):
                raise BoxAdmissionError(
                    "Managed sandbox read-only mount source is unavailable"
                )
            if not any(
                self._path_is_under(host_path, allowed_root)
                for allowed_root in allowed_roots
            ):
                raise BoxAdmissionError(
                    "Managed sandbox read-only mount source is outside allowed_mount_roots"
                )
            manifest_path = None
            if mount.manifest_path is not None:
                if mount.content_digest is None:
                    raise BoxAdmissionError(
                        "Managed sandbox mount manifests require content_digest"
                    )
                manifest_path = _resolve_local_path(mount.manifest_path)
                if not os.path.isfile(manifest_path):
                    raise BoxAdmissionError(
                        "Managed sandbox read-only mount manifest is unavailable"
                    )
                if not any(
                    self._path_is_under(manifest_path, allowed_root)
                    for allowed_root in allowed_roots
                ):
                    raise BoxAdmissionError(
                        "Managed sandbox read-only mount manifest is outside allowed_mount_roots"
                    )
            mount_path = mount.mount_path
            if not mount.is_content_addressed and not mount_path.startswith(
                f"{DEFAULT_BOX_MOUNT_PATH}/"
            ):
                raise BoxAdmissionError(
                    "Managed sandbox additional mount targets must stay under /workspace"
                )
            if mount_path in destinations:
                raise BoxAdmissionError(
                    "Managed sandbox additional mount targets must be unique"
                )
            destinations.add(mount_path)
            normalized.append(
                mount.model_copy(
                    update={
                        "host_path": host_path,
                        "manifest_path": manifest_path,
                    }
                )
            )
        return normalized

    def _normalize_admitted_spec(
        self,
        spec: BoxSpec,
        action_context: ActionContext,
    ) -> BoxSpec:
        if (
            spec.backend is not None
            and spec.backend != self.admission_policy.required_backend
        ):
            raise BoxAdmissionError("Backend is restricted by managed sandbox policy")
        context = ActionContext.model_validate(action_context).without_installation()
        policy = self._admission_policy
        if spec.network != BoxNetworkMode.OFF:
            raise BoxAdmissionError("Managed sandbox network access is disabled")
        if spec.mount_path != DEFAULT_BOX_MOUNT_PATH:
            raise BoxAdmissionError("Managed sandbox mount_path is runtime-owned")
        if spec.workdir != DEFAULT_BOX_MOUNT_PATH and not spec.workdir.startswith(
            f"{DEFAULT_BOX_MOUNT_PATH}/"
        ):
            raise BoxAdmissionError(
                "Managed sandbox workdir must stay under /workspace"
            )

        workspace_path = self._canonical_workspace_path(context)
        if spec.host_path is not None:
            submitted_host_path = _resolve_local_path(spec.host_path)
            if submitted_host_path != workspace_path:
                raise BoxAdmissionError("Managed sandbox host_path is runtime-owned")

        extra_mounts = self._normalize_admitted_extra_mounts(spec.extra_mounts)

        return spec.model_copy(
            update={
                "session_id": namespace_session_id(context, policy.logical_session_id),
                "network": BoxNetworkMode.OFF,
                "image": DEFAULT_BOX_IMAGE,
                "host_path": workspace_path,
                "host_path_mode": BoxHostMountMode.READ_WRITE,
                "mount_path": DEFAULT_BOX_MOUNT_PATH,
                "extra_mounts": extra_mounts,
                "persistent": True,
                "timeout_sec": min(spec.timeout_sec, policy.max_timeout_sec),
                "cpus": policy.cpus,
                "memory_mb": policy.memory_mb,
                "pids_limit": policy.pids_limit,
                "read_only_rootfs": policy.read_only_rootfs,
                "workspace_quota_mb": policy.workspace_quota_mb,
            }
        )

    def _workspace_session_ids_locked(self, context: ActionContext) -> list[str]:
        context = ActionContext.model_validate(context).without_installation()
        return list(
            self._session_ids_by_workspace.get(
                (context.instance_uuid, context.workspace_uuid),
                (),
            )
        )

    def _drop_workspace_sessions_locked(
        self, context: ActionContext
    ) -> list[asyncio.Task[None]]:
        cleanup_tasks: list[asyncio.Task[None]] = []
        for session_id in self._workspace_session_ids_locked(context):
            cleanup_task = self._drop_session_locked(session_id)
            if cleanup_task is not None:
                cleanup_tasks.append(cleanup_task)
        return cleanup_tasks

    def _reap_expired_admissions_locked(
        self, now: dt.datetime | None = None
    ) -> list[asyncio.Task[None]]:
        current_time = now or dt.datetime.now(_UTC)
        cleanup_tasks: list[asyncio.Task[None]] = []
        deadline = current_time.timestamp()
        while (
            self._admission_expiry_heap
            and self._admission_expiry_heap[0][0] <= deadline
        ):
            expires_at, key, revision, generation = heapq.heappop(
                self._admission_expiry_heap
            )
            grant = self._admission_grants.get(key)
            if grant is None:
                continue
            if (
                grant.expires_at.timestamp() != expires_at
                or grant.entitlement_revision != revision
                or grant.execution_generation != generation
                or not grant.is_expired(current_time)
            ):
                # A renewed/replaced grant owns a newer heap entry.
                continue
            self._admission_grants.pop(key, None)
            cleanup_tasks.extend(
                self._drop_workspace_sessions_locked(self._grant_context(grant))
            )
        return cleanup_tasks

    def _index_admission_expiry_locked(
        self,
        grant: SandboxAdmissionGrant,
    ) -> None:
        heapq.heappush(
            self._admission_expiry_heap,
            (
                grant.expires_at.timestamp(),
                grant.workspace_key,
                grant.entitlement_revision,
                grant.execution_generation,
            ),
        )
        compact_limit = len(self._admission_grants) * 2 + 1_024
        if len(self._admission_expiry_heap) <= compact_limit:
            return
        self._admission_expiry_heap = [
            (
                current.expires_at.timestamp(),
                current.workspace_key,
                current.entitlement_revision,
                current.execution_generation,
            )
            for current in self._admission_grants.values()
        ]
        heapq.heapify(self._admission_expiry_heap)

    def _require_admission_locked(
        self, action_context: ActionContext
    ) -> SandboxAdmissionGrant:
        if not self.admission_required:
            raise BoxAdmissionError("Sandbox admission enforcement is not enabled")
        if self._admission_config_error:
            raise BoxReadinessError(
                f"Invalid sandbox admission configuration: {self._admission_config_error}"
            )
        context = ActionContext.model_validate(action_context).without_installation()
        grant = self._admission_grants.get(
            (context.instance_uuid, context.workspace_uuid)
        )
        if grant is None:
            raise BoxAdmissionError("Sandbox admission grant is missing")
        if grant.is_expired():
            raise BoxAdmissionError("Sandbox admission grant has expired")
        if grant.execution_generation != context.placement_generation:
            raise BoxAdmissionError(
                "Sandbox admission grant belongs to another execution generation"
            )
        if grant.max_sessions <= 0:
            raise BoxAdmissionError("Sandbox admission grant does not permit sessions")
        if (
            grant.max_sessions > self._admission_policy.max_sessions
            or grant.max_managed_processes
            > self._admission_policy.max_managed_processes
        ):
            raise BoxAdmissionError(
                "Sandbox admission grant exceeds the active runtime policy"
            )
        return grant

    async def require_sandbox_admission(
        self, action_context: ActionContext
    ) -> SandboxAdmissionGrant:
        await self._ensure_managed_readiness()
        async with self._lock:
            self._reap_expired_admissions_locked()
            return self._require_admission_locked(action_context)

    async def upsert_sandbox_admission_grant(
        self, grant: SandboxAdmissionGrant
    ) -> dict:
        grant = SandboxAdmissionGrant.model_validate(grant)
        if not self.admission_required:
            raise BoxAdmissionError("Sandbox admission enforcement is not enabled")
        if self._admission_config_error:
            raise BoxReadinessError(
                f"Invalid sandbox admission configuration: {self._admission_config_error}"
            )

        policy = self._admission_policy
        now = dt.datetime.now(_UTC)
        if grant.is_expired(now):
            raise BoxAdmissionError("Cannot install an expired sandbox admission grant")
        if grant.expires_at > now + dt.timedelta(seconds=policy.max_grant_ttl_sec):
            raise BoxAdmissionError(
                "Sandbox admission grant lifetime exceeds the configured maximum"
            )
        if grant.max_sessions > policy.max_sessions:
            raise BoxAdmissionError("Sandbox admission grant exceeds the session cap")
        if grant.max_managed_processes > policy.max_managed_processes:
            raise BoxAdmissionError(
                "Sandbox admission grant exceeds the managed-process cap"
            )

        key = grant.workspace_key
        context = self._grant_context(grant)
        cleanup_tasks: list[asyncio.Task[None]] = []
        installed_grant = grant
        async with self._lock:
            cleanup_tasks.extend(self._reap_expired_admissions_locked(now))
            if (
                key not in self._admission_revisions
                and len(self._admission_revisions) >= self.max_admission_records
            ):
                raise BoxAdmissionError(
                    "Sandbox admission record capacity reached; "
                    "refusing an unbounded Workspace fence allocation"
                )
            revoked_revision = self._revoked_admission_revisions.get(key, 0)
            if grant.entitlement_revision <= revoked_revision:
                raise BoxAdmissionError("Sandbox admission grant revision was revoked")

            highest_revision = self._admission_revisions.get(key, 0)
            if grant.entitlement_revision < highest_revision:
                raise BoxAdmissionError("Sandbox admission grant revision is stale")
            highest_generation = self._admission_generations.get(key, 0)
            if grant.execution_generation < highest_generation:
                raise BoxAdmissionError(
                    "Sandbox admission execution generation is stale"
                )

            limit_fingerprint = (grant.max_sessions, grant.max_managed_processes)
            previous_fingerprint = self._admission_limit_fingerprints.get(key)
            if (
                grant.entitlement_revision == highest_revision
                and previous_fingerprint is not None
                and previous_fingerprint != limit_fingerprint
            ):
                raise BoxAdmissionError(
                    "Sandbox admission limits changed without a new entitlement revision"
                )

            current = self._admission_grants.get(key)
            if (
                current is not None
                and grant.entitlement_revision == current.entitlement_revision
                and grant.execution_generation == current.execution_generation
                and grant.expires_at < current.expires_at
            ):
                # Two Core replicas can renew the same immutable entitlement
                # with slightly different wall clocks. A shorter duplicate is
                # idempotent; rejecting it would invite the losing replica to
                # revoke a grant that remains valid for the whole Workspace.
                installed_grant = current
            else:
                self._admission_grants[key] = grant
                self._index_admission_expiry_locked(grant)
                self._admission_revisions[key] = grant.entitlement_revision
                self._admission_generations[key] = grant.execution_generation
                self._admission_limit_fingerprints[key] = limit_fingerprint

                if (
                    current is None
                    or current.execution_generation != grant.execution_generation
                    or grant.max_sessions == 0
                ):
                    cleanup_tasks.extend(self._drop_workspace_sessions_locked(context))
                else:
                    canonical_session_id = namespace_session_id(
                        context, policy.logical_session_id
                    )
                    for session_id in self._workspace_session_ids_locked(context):
                        if session_id == canonical_session_id:
                            continue
                        cleanup_task = self._drop_session_locked(session_id)
                        if cleanup_task is not None:
                            cleanup_tasks.append(cleanup_task)

        await self._wait_for_session_cleanups(cleanup_tasks)
        return {
            "installed": True,
            "workspace_uuid": installed_grant.workspace_uuid,
            "execution_generation": installed_grant.execution_generation,
            "entitlement_revision": installed_grant.entitlement_revision,
            "max_sessions": installed_grant.max_sessions,
            "max_managed_processes": installed_grant.max_managed_processes,
            "expires_at": installed_grant.expires_at.isoformat(),
        }

    async def revoke_sandbox_admission_grant(
        self, revocation: SandboxAdmissionRevocation
    ) -> dict:
        revocation = SandboxAdmissionRevocation.model_validate(revocation)
        if not self.admission_required:
            raise BoxAdmissionError("Sandbox admission enforcement is not enabled")
        key = revocation.workspace_key
        cleanup_tasks: list[asyncio.Task[None]] = []
        async with self._lock:
            if (
                key not in self._admission_revisions
                and len(self._admission_revisions) >= self.max_admission_records
            ):
                raise BoxAdmissionError(
                    "Sandbox admission record capacity reached; "
                    "refusing an unbounded Workspace fence allocation"
                )
            highest_revision = self._admission_revisions.get(key, 0)
            revoked_revision = self._revoked_admission_revisions.get(key, 0)
            if revocation.entitlement_revision < max(
                highest_revision, revoked_revision
            ):
                raise BoxAdmissionError("Sandbox admission revocation is stale")

            active = self._admission_grants.pop(key, None)
            self._admission_revisions[key] = max(
                highest_revision, revocation.entitlement_revision
            )
            self._revoked_admission_revisions[key] = max(
                revoked_revision, revocation.entitlement_revision
            )
            context = (
                self._grant_context(active)
                if active is not None
                else ActionContext(
                    instance_uuid=revocation.instance_uuid,
                    workspace_uuid=revocation.workspace_uuid,
                    placement_generation=max(
                        self._admission_generations.get(key, 1), 1
                    ),
                )
            )
            cleanup_tasks.extend(self._drop_workspace_sessions_locked(context))

        await self._wait_for_session_cleanups(cleanup_tasks)
        return {
            "revoked": True,
            "workspace_uuid": revocation.workspace_uuid,
            "entitlement_revision": revocation.entitlement_revision,
        }

    def _apply_config_to_backends(self, config: dict) -> None:
        """Apply configuration sections to corresponding backends."""
        for backend in self.backends:
            if backend is None:
                continue
            if isinstance(backend, CLISandboxBackend):
                backend.artifact_cache_parent = self._host_root()
            backend_config = config.get(backend.name, {})
            if backend_config and hasattr(backend, "configure"):
                backend.configure(backend_config)

    async def execute(
        self,
        spec: BoxSpec,
        action_context: ActionContext | None = None,
    ) -> BoxExecutionResult:
        if not spec.cmd:
            raise BoxValidationError("cmd must not be empty")
        if self.admission_required:
            if action_context is None:
                raise BoxAdmissionError(
                    "Managed sandbox execution requires a trusted Workspace context"
                )
            await self.require_sandbox_admission(action_context)
            spec = self._normalize_admitted_spec(spec, action_context)
        session = await self._get_or_create_session(
            spec,
            track_active_exec=True,
            action_context=action_context,
        )

        result: BoxExecutionResult | None = None
        cleanup_task: asyncio.Task[None] | None = None
        execution_cancelled = False
        try:
            async with session.lock:
                if session.closing:
                    raise BoxSessionNotFoundError(
                        f"session {spec.session_id} is being deleted"
                    )
                self.logger.info(
                    "LangBot Box execute: "
                    f"session_id={spec.session_id} "
                    f"backend_session_id={session.info.backend_session_id} "
                    f"backend={session.info.backend_name} "
                    f"workdir={spec.workdir} "
                    f"timeout_sec={spec.timeout_sec}"
                )
                try:
                    result = await session.backend.exec(session.info, spec)
                except asyncio.CancelledError:
                    execution_cancelled = True
                    session.closing = True
                    raise
                if result.status == BoxExecutionStatus.TIMED_OUT:
                    # Fence queued callers before releasing the execution lock.
                    session.closing = True
            return result
        finally:
            async with self._lock:
                if self._sessions.get(spec.session_id) is session:
                    session.info.last_used_at = dt.datetime.now(_UTC)
                    remaining = self._active_exec_counts.get(spec.session_id, 0) - 1
                    if remaining > 0:
                        self._active_exec_counts[spec.session_id] = remaining
                    else:
                        self._active_exec_counts.pop(spec.session_id, None)

                    if execution_cancelled or (
                        result is not None
                        and result.status == BoxExecutionStatus.TIMED_OUT
                    ):
                        cleanup_task = self._drop_session_locked(spec.session_id)
            if cleanup_task is not None:
                try:
                    await self._wait_for_session_cleanup(spec.session_id, cleanup_task)
                except Exception:
                    if not execution_cancelled:
                        raise

    async def upload_file(
        self,
        session_id: str,
        path: str,
        content: bytes,
        action_context: ActionContext,
    ) -> None:
        if len(content) > self.max_rpc_file_bytes:
            raise BoxValidationError("File exceeds the configured transfer size limit")
        await self._transfer_file(session_id, path, action_context, content=content)

    async def download_file(
        self,
        session_id: str,
        path: str,
        action_context: ActionContext,
    ) -> bytes:
        return await self._transfer_file(session_id, path, action_context)

    async def _transfer_file(
        self,
        session_id: str,
        path: str,
        action_context: ActionContext,
        *,
        content: bytes | None = None,
    ):
        from .file_io import workspace_relative_path
        from .tenancy import session_belongs_to_placement

        if not session_belongs_to_placement(action_context, session_id):
            raise BoxValidationError(
                "File transfer session does not belong to this Workspace placement"
            )
        if self.admission_required:
            await self.require_sandbox_admission(action_context)
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.closing:
                raise BoxSessionNotFoundError(f"session {session_id} not found")
            self._session_leases[session_id] += 1
        try:
            async with session.lock:
                if session.closing or self._sessions.get(session_id) is not session:
                    raise BoxSessionNotFoundError(
                        f"session {session_id} is being deleted"
                    )
                if self.admission_required:
                    await self.require_sandbox_admission(action_context)
                workspace_relative_path(session.info.mount_path, path)
                for _, mount_path, _, _, _ in session.extra_mounts_key:
                    if path == mount_path or path.startswith(
                        mount_path.rstrip("/") + "/"
                    ):
                        raise BoxValidationError(
                            "File transfer cannot access additional mounts"
                        )
                backend = session.backend
                if content is not None:
                    await backend.upload_file(
                        session.info, path, content, self.max_rpc_file_bytes
                    )
                    return None
                return await backend.download_file(
                    session.info, path, self.max_rpc_file_bytes
                )
        except (ValueError, OSError) as exc:
            raise BoxValidationError(str(exc)) from exc
        finally:
            async with self._lock:
                if self._sessions.get(session_id) is session:
                    session.info.last_used_at = dt.datetime.now(_UTC)
                self._session_leases[session_id] -= 1
                if self._session_leases[session_id] <= 0:
                    self._session_leases.pop(session_id, None)

    def start_background_reaper(self) -> None:
        if (
            self.session_ttl_sec <= 0
            and not self.admission_required
            and not any(
                session.idle_ttl_sec is not None for session in self._sessions.values()
            )
        ):
            return
        if self._reaper_task is not None and not self._reaper_task.done():
            self._reaper_wakeup.set()
            return
        self._reaper_task = asyncio.create_task(self._reaper_loop())

    async def stop_background_reaper(self) -> None:
        task = self._reaper_task
        self._reaper_task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.event_loop_monitor.stop()

    async def _reaper_loop(self) -> None:
        while (
            self.session_ttl_sec > 0
            or self.admission_required
            or any(
                session.idle_ttl_sec is not None for session in self._sessions.values()
            )
        ):
            self._reaper_wakeup.clear()
            intervals = [_REAPER_INTERVAL_SEC]
            if self.session_ttl_sec > 0:
                intervals.append(self.session_ttl_sec)
            intervals.extend(
                session.idle_ttl_sec
                for session in self._sessions.values()
                if session.idle_ttl_sec is not None
            )
            interval = min(intervals)
            try:
                await asyncio.wait_for(self._reaper_wakeup.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
            try:
                cleanup_tasks: list[asyncio.Task[None]]
                async with self._lock:
                    cleanup_tasks = self._reap_expired_admissions_locked()
                    cleanup_tasks.extend(await self._reap_expired_sessions_locked())
                await self._wait_for_session_cleanups(cleanup_tasks)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.warning(
                    f"LangBot Box background reaper failed: {exc}", exc_info=True
                )

    async def shutdown(self, *, release_identity: bool = True):
        self._shutdown_in_progress = True
        try:
            while True:
                async with self._lock:
                    creating = [
                        task
                        for task in self._creating_session_tasks.values()
                        if task is not asyncio.current_task()
                    ]
                if not creating:
                    break
                await asyncio.gather(*creating, return_exceptions=True)

            async with self._lock:
                cleanup_tasks = list(self._closing_session_tasks.values())
                for session_id in list(self._sessions):
                    cleanup_task = self._drop_session_locked(session_id)
                    if cleanup_task is not None:
                        cleanup_tasks.append(cleanup_task)
            await self._wait_for_session_cleanups(cleanup_tasks)

            tasks = list(self._background_tasks)
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._background_tasks.clear()
        finally:
            if release_identity:
                self._identity.release()
            self._shutdown_in_progress = False

    async def create_session(
        self,
        spec: BoxSpec,
        action_context: ActionContext | None = None,
    ) -> dict:
        if self.admission_required:
            if action_context is None:
                raise BoxAdmissionError(
                    "Managed sandbox session creation requires a trusted Workspace context"
                )
            await self.require_sandbox_admission(action_context)
            spec = self._normalize_admitted_spec(spec, action_context)
        session = await self._get_or_create_session(spec, action_context=action_context)
        return self._session_to_dict(session.info)

    async def delete_session(self, session_id: str) -> None:
        # Serialize against a session that is still being created. Otherwise a
        # delete can return "not found" while start_session is in flight and
        # leave the just-created backend resource alive.
        operation_lock = await self._get_session_operation_lock(session_id)
        async with operation_lock:
            cleanup_task: asyncio.Task[None] | None
            async with self._lock:
                cleanup_task = self._closing_session_tasks.get(session_id)
                if cleanup_task is None and session_id not in self._sessions:
                    raise BoxSessionNotFoundError(f"session {session_id} not found")
                if cleanup_task is None:
                    cleanup_task = self._drop_session_locked(session_id)
            if cleanup_task is not None:
                await self._wait_for_session_cleanup(session_id, cleanup_task)

    async def start_managed_process(
        self,
        session_id: str,
        spec: BoxManagedProcessSpec,
        action_context: ActionContext | None = None,
    ) -> dict:
        if self.admission_required:
            if action_context is None:
                raise BoxAdmissionError(
                    "Managed process creation requires a trusted Workspace context"
                )
            grant = await self.require_sandbox_admission(action_context)
            if grant.max_managed_processes <= 0:
                raise BoxAdmissionError(
                    "Sandbox admission grant does not permit managed processes"
                )
            expected_session_id = namespace_session_id(
                action_context, self._admission_policy.logical_session_id
            )
            if session_id != expected_session_id:
                raise BoxAdmissionError("Managed sandbox session_id is runtime-owned")
        async with self._lock:
            if self.admission_required:
                assert action_context is not None
                grant = self._require_admission_locked(action_context)
            runtime_session = self._sessions.get(session_id)
            if runtime_session is None:
                raise BoxSessionNotFoundError(f"session {session_id} not found")

        async with runtime_session.lock:
            if self.admission_required:
                active_processes = sum(
                    1
                    for managed_process in runtime_session.managed_processes.values()
                    if managed_process.is_running
                )
                if active_processes >= grant.max_managed_processes:
                    raise BoxAdmissionError(
                        "Sandbox admission managed-process limit reached"
                    )
            process_id = spec.process_id
            async with self._lock:
                self._reap_completed_processes()
                if (
                    runtime_session.closing
                    or self._sessions.get(session_id) is not runtime_session
                ):
                    raise BoxSessionNotFoundError(
                        f"session {session_id} is being deleted"
                    )
                running = sum(
                    1
                    for session_id in self._managed_process_session_ids
                    if (session := self._sessions.get(session_id)) is not None
                    for managed_id, managed in session.managed_processes.items()
                    if managed.is_running
                    and not (session is runtime_session and managed_id == process_id)
                )
                if running + self._managed_starting_count >= self.max_managed_processes:
                    raise BoxCapacityExceededError(
                        "Box managed process capacity reached "
                        f"({self.max_managed_processes})"
                    )
                self._managed_starting_count += 1
            try:
                existing = runtime_session.managed_processes.get(process_id)
                if existing is not None and existing.is_running:
                    # A reconnect may legitimately replace the old generation.
                    self.logger.info(
                        "LangBot Box terminating stale managed process before restart: "
                        f"session_id={session_id} process_id={process_id}"
                    )
                    await self._terminate_managed_process(existing)
                    del runtime_session.managed_processes[process_id]
                    self._sync_managed_process_session_index(
                        session_id,
                        runtime_session,
                    )

                backend = runtime_session.backend
                process = await backend.start_managed_process(
                    runtime_session.info, spec
                )
            finally:
                async with self._lock:
                    self._managed_starting_count -= 1
            managed_process = _ManagedProcess(
                spec=spec,
                process=process,
                started_at=dt.datetime.now(_UTC),
                attach_lock=asyncio.Lock(),
                stderr_chunks=collections.deque(),
            )
            runtime_session.managed_processes[process_id] = managed_process
            self._managed_process_session_ids.add(session_id)
            runtime_session.info.last_used_at = dt.datetime.now(_UTC)
            self._track_background_task(
                asyncio.create_task(
                    self._drain_managed_process_stderr(
                        runtime_session.info.session_id, process_id, managed_process
                    )
                )
            )
            self._track_background_task(
                asyncio.create_task(
                    self._watch_managed_process(
                        runtime_session.info.session_id, process_id, managed_process
                    )
                )
            )
            return self._managed_process_to_dict(
                runtime_session.info.session_id, process_id, managed_process
            )

    def get_managed_process(self, session_id: str, process_id: str = "default") -> dict:
        runtime_session = self._sessions.get(session_id)
        if runtime_session is None:
            raise BoxSessionNotFoundError(f"session {session_id} not found")
        managed_process = runtime_session.managed_processes.get(process_id)
        if managed_process is None:
            raise BoxManagedProcessNotFoundError(
                f"session {session_id} has no managed process with process_id={process_id}"
            )
        return self._managed_process_to_dict(session_id, process_id, managed_process)

    async def stop_managed_process(
        self, session_id: str, process_id: str = "default"
    ) -> None:
        runtime_session = self._sessions.get(session_id)
        if runtime_session is None:
            raise BoxSessionNotFoundError(f"session {session_id} not found")

        async with runtime_session.lock:
            managed_process = runtime_session.managed_processes.pop(process_id, None)
            if managed_process is None:
                raise BoxManagedProcessNotFoundError(
                    f"session {session_id} has no managed process with process_id={process_id}"
                )
            await self._terminate_managed_process(managed_process)
            self._sync_managed_process_session_index(
                session_id,
                runtime_session,
            )
            runtime_session.info.last_used_at = dt.datetime.now(_UTC)
            self.logger.info(
                f"LangBot Box managed process stopped: session_id={session_id} process_id={process_id}"
            )

    # ── Observability ─────────────────────────────────────────────────

    async def get_readiness(self, *, force: bool = False) -> dict:
        """Return process readiness, including strict managed-mode guarantees."""

        cache_ttl = self._admission_policy.readiness_cache_sec
        now_monotonic = time.monotonic()
        if (
            not force
            and self._readiness_cache is not None
            and now_monotonic - self._readiness_cache[0] <= cache_ttl
        ):
            return dict(self._readiness_cache[1])

        if self._backend is None:
            self._backend = await self._select_backend()
        backend = self._backend

        if not self.admission_required:
            available = False
            if backend is not None:
                try:
                    available = await backend.is_available()
                except Exception:
                    available = False
            backend_info = {
                "name": backend.name if backend is not None else None,
                "available": available,
            }
            if backend is not None and getattr(
                backend, "unsafe_direct_execution", False
            ):
                backend_info["unsafe_direct_execution"] = True
            result = {
                "ready": available,
                "mode": "standard",
                "backend": backend_info,
                "checks": {"backend_available": available},
            }
            self._readiness_cache = (now_monotonic, result)
            return dict(result)

        checks: dict[str, bool] = {
            "configuration": self._admission_config_error is None,
            "required_backend": bool(
                backend is not None
                and backend.name == self._admission_policy.required_backend
            ),
            "workspace_mount": False,
            "backend_available": False,
            "cgroup_v2": False,
            "namespace_isolation": False,
            "mount_isolation": False,
            "network_isolation": False,
            "hard_workspace_quota": False,
            "hard_read_only_mount_quota": False,
            "bounded_ephemeral_storage": False,
            "inode_quota": False,
            "session_cap": self._admission_policy.max_sessions <= 1,
            "managed_process_cap": self._admission_policy.max_managed_processes == 0,
        }
        workspace_path: str | None = None
        readiness_error = self._admission_config_error
        try:
            workspace_path = self._managed_workspace_root()
            checks["workspace_mount"] = True
        except BoxReadinessError as exc:
            readiness_error = str(exc)

        backend_readiness: dict = {}
        if backend is not None and checks["required_backend"]:
            try:
                backend_readiness = await backend.get_readiness(
                    workspace_path=workspace_path,
                    strict=True,
                )
            except Exception as exc:
                readiness_error = str(exc)
            checks["backend_available"] = bool(
                backend_readiness.get("available", False)
            )
            for name in (
                "cgroup_v2",
                "namespace_isolation",
                "mount_isolation",
                "network_isolation",
                "hard_workspace_quota",
                "hard_read_only_mount_quota",
                "bounded_ephemeral_storage",
                "inode_quota",
            ):
                checks[name] = backend_readiness.get(name) is True
            if self._unsafe_soft_storage_limits:
                # Operator-only escape hatch for disposable integration hosts
                # whose filesystem cannot provide project/subvolume quotas.
                # Namespace, mount, network and cgroup checks still fail closed.
                for name in (
                    "hard_workspace_quota",
                    "hard_read_only_mount_quota",
                    "bounded_ephemeral_storage",
                    "inode_quota",
                ):
                    checks[name] = True
            readiness_error = backend_readiness.get("error") or readiness_error

        result = {
            "ready": all(checks.values()),
            "mode": "grant_enforced",
            "backend": {
                "name": backend.name if backend is not None else None,
                "available": checks["backend_available"],
                "details": backend_readiness,
            },
            "checks": checks,
            "unsafe_soft_storage_limits": self._unsafe_soft_storage_limits,
        }
        if readiness_error:
            result["error"] = readiness_error
        self._readiness_cache = (now_monotonic, result)
        return dict(result)

    async def _ensure_managed_readiness(self) -> None:
        if not self.admission_required:
            return
        readiness = await self.get_readiness()
        if readiness.get("ready"):
            return
        failed_checks = [
            name
            for name, passed in (readiness.get("checks") or {}).items()
            if not passed
        ]
        detail = ", ".join(failed_checks) or "unknown"
        raise BoxReadinessError(
            f"Managed sandbox isolation is not ready (failed checks: {detail})"
        )

    @staticmethod
    def _limit_capabilities(
        name: str, backend: BaseSandboxBackend | None = None
    ) -> dict:
        local = name in ("docker", "nsjail")
        hard_resources = local
        if name == "nsjail" and backend is not None:
            hard_resources = bool(
                getattr(backend, "_cgroup_v2_available", False)
                or getattr(backend, "_cgroup_v1_available", False)
            )
        return {
            "timeout_sec": True,
            "idle_ttl_sec": True,
            "max_sessions": True,
            "cpus": hard_resources
            and bool(getattr(backend, "cpu_limit_enabled", True)),
            "memory_mb": hard_resources,
            "pids_limit": hard_resources,
            "workspace_quota_mb": local,
        }

    async def _probe_backend(
        self, name: str, e2b_config: E2BConnectionConfig | None = None
    ) -> dict:
        if self.admission_required and name != self.admission_policy.required_backend:
            return {
                "name": name,
                "available": False,
                "reason": "policy_restricted",
                "limit_capabilities": self._limit_capabilities(name),
            }
        backend = next(
            (b for b in self.backends if b is not None and b.name == name), None
        )
        try:

            async def check():
                nonlocal backend
                backend = await self._get_backend(name, e2b_config)
                if (
                    name == "e2b"
                    and not self.admission_required
                    and hasattr(backend, "inspect_template")
                ):
                    return await backend.inspect_template(validate=False)
                available = (
                    bool((await self.get_readiness()).get("ready"))
                    if self.admission_required
                    else await backend.probe_available()
                )
                return available

            available = await asyncio.wait_for(check(), timeout=8)
            if isinstance(available, dict):
                return {
                    **available,
                    "limit_capabilities": self._limit_capabilities(name, backend),
                }
            return {
                "name": name,
                "available": available,
                "reason": None if available else backend.unavailable_reason(),
                "limit_capabilities": self._limit_capabilities(name, backend),
                "managed_processes": type(backend).start_managed_process
                is not BaseSandboxBackend.start_managed_process,
            }
        except asyncio.TimeoutError:
            reason = "probe_timeout"
        except Exception as exc:
            if (
                getattr(exc, "status_code", None) in (401, 403)
                or type(exc).__name__ == "AuthenticationException"
            ):
                reason = "authentication_failed"
            elif backend is not None:
                reason = backend.unavailable_reason()
            else:
                reason = "sdk_missing" if name == "e2b" else "environment_unavailable"
        return {
            "name": name,
            "available": False,
            "reason": reason,
            "limit_capabilities": self._limit_capabilities(name, backend),
        }

    async def get_backends(
        self,
        *,
        refresh: bool = False,
        e2b_config: E2BConnectionConfig | None = None,
        validate_e2b_template: bool = False,
    ) -> list[dict]:
        """Probe on the execution host; draft E2B config never changes live backends."""
        if validate_e2b_template:
            items = await self.get_backends(refresh=refresh)
            if self.admission_required:
                return items
            try:
                backend = await self._get_backend("e2b", e2b_config)
                e2b = await backend.inspect_template(validate=True)
                e2b["limit_capabilities"] = self._limit_capabilities("e2b", backend)
            except Exception:
                e2b = {
                    "name": "e2b",
                    "available": False,
                    "reason": "environment_unavailable",
                }
            return [e2b if item["name"] == "e2b" else item for item in items]
        if e2b_config is not None:
            items = await self.get_backends(refresh=refresh)
            e2b = await self._probe_backend("e2b", e2b_config)
            return [e2b if item["name"] == "e2b" else item for item in items]
        async with self._backends_probe_lock:
            if (
                not refresh
                and self._backends_cache is not None
                and time.monotonic() - self._backends_cache[0] < 15
            ):
                return [dict(item) for item in self._backends_cache[1]]
            results = await asyncio.gather(
                *(self._probe_backend(name) for name in ("docker", "e2b", "nsjail"))
            )
            self._backends_cache = (time.monotonic(), results)
            return [dict(item) for item in results]

    async def get_backend_info(self) -> dict:
        if self.admission_required:
            readiness = await self.get_readiness()
            return {
                "name": readiness.get("backend", {}).get("name"),
                "available": bool(readiness.get("ready", False)),
                "readiness": readiness,
            }
        if self._backend is None:
            async with self._backend_lock:
                if self._backend is None:
                    self._backend = await self._select_backend()
        backend = self._backend
        if backend is None:
            return {"name": None, "available": False}
        try:
            available = await backend.is_available()
        except Exception:
            available = False
        result = {"name": backend.name, "available": available}
        if getattr(backend, "unsafe_direct_execution", False):
            result["unsafe_direct_execution"] = True
        return result

    def get_sessions(self) -> list[dict]:
        return [self._session_to_dict(s.info) for s in self._sessions.values()]

    def get_sessions_for_workspace(
        self,
        action_context: ActionContext,
    ) -> list[dict]:
        """Return sessions using the Workspace index instead of a global scan."""

        return [
            self._session_to_dict(self._sessions[session_id].info)
            for session_id in self._workspace_session_ids_locked(action_context)
            if session_id in self._sessions
        ]

    def get_session(self, session_id: str) -> dict:
        runtime_session = self._sessions.get(session_id)
        if runtime_session is None:
            raise BoxSessionNotFoundError(f"session {session_id} not found")
        result = self._session_to_dict(runtime_session.info)
        if runtime_session.managed_processes:
            managed_processes = {
                pid: self._managed_process_to_dict(session_id, pid, mp)
                for pid, mp in runtime_session.managed_processes.items()
            }
            result["managed_processes"] = managed_processes
            if "default" in managed_processes:
                result["managed_process"] = managed_processes["default"]
        return result

    async def get_capacity(self, action_context: ActionContext) -> dict:
        """Return effective capacity; admission still runs atomically during create."""
        if self.admission_required:
            await self.require_sandbox_admission(action_context)
        async with self._lock:
            used = len(self._workspace_session_ids_locked(action_context))
            limit = self.max_sessions
            if self.admission_required:
                limit = min(
                    limit, self._require_admission_locked(action_context).max_sessions
                )
            remaining = max(
                0, min(limit - used, self.max_sessions - len(self._sessions))
            )
            return {"limit": limit, "used": used, "remaining": remaining}

    async def get_status(self) -> dict:
        backend_info = await self.get_backend_info()
        return {
            "backend": backend_info,
            "active_sessions": len(self._sessions),
            "managed_processes": sum(
                1
                for session_id in self._managed_process_session_ids
                if (runtime_session := self._sessions.get(session_id)) is not None
                for mp in runtime_session.managed_processes.values()
                if mp.is_running
            ),
            "session_ttl_sec": self.session_ttl_sec,
            "limits": {
                "max_sessions": self.max_sessions,
                "max_managed_processes": self.max_managed_processes,
                "max_completed_processes": self.max_completed_processes,
                "max_admission_records": self.max_admission_records,
                "max_rpc_file_bytes": self.max_rpc_file_bytes,
            },
        }

    async def _get_or_create_session(
        self,
        spec: BoxSpec,
        *,
        track_active_exec: bool = False,
        action_context: ActionContext | None = None,
    ) -> _RuntimeSession:
        workspace_key = None
        if action_context is not None:
            context = ActionContext.model_validate(
                action_context
            ).without_installation()
            workspace_key = (context.instance_uuid, context.workspace_uuid)
        elif spec.workspace_max_sessions is not None:
            raise BoxValidationError(
                "Workspace session limits require a trusted Workspace context"
            )
        existing_session = self._sessions.get(spec.session_id)
        if existing_session is not None:
            backend = existing_session.backend
            if (
                spec.e2b_config is not None
                and getattr(backend, "connection_config", None) != spec.e2b_config
            ):
                raise BoxSessionConflictError(
                    "E2B configuration cannot change after Box creation"
                )
            if spec.backend is not None and spec.backend != backend.name:
                raise BoxSessionConflictError(
                    "Box backend cannot change after creation"
                )
        else:
            backend = await self._get_backend(spec.backend, spec.e2b_config)
        signature_spec = spec
        if backend.content_addressed_mounts:
            signature_spec = spec.model_copy(
                update={
                    "extra_mounts": [
                        mount
                        for mount in spec.extra_mounts
                        if not mount.is_content_addressed
                    ]
                }
            )
        new_extra_mounts_key = _compute_extra_mounts_key(signature_spec)
        operation_lock = await self._get_session_operation_lock(spec.session_id)

        async with operation_lock:
            while True:
                cleanup_task: asyncio.Task[None] | None = None
                existing: _RuntimeSession | None = None
                async with self._lock:
                    if self._shutdown_in_progress:
                        raise BoxRuntimeUnavailableError("Box runtime is shutting down")
                    self._reap_expired_admissions_locked()
                    await self._reap_expired_sessions_locked()
                    if self.admission_required:
                        if action_context is None:
                            raise BoxAdmissionError(
                                "Managed sandbox session requires a trusted Workspace context"
                            )
                        grant = self._require_admission_locked(action_context)
                        workspace_session_ids = self._workspace_session_ids_locked(
                            action_context
                        )
                        if len(workspace_session_ids) > grant.max_sessions:
                            raise BoxAdmissionError(
                                "Sandbox admission session limit exceeded"
                            )
                        if (
                            spec.session_id not in self._sessions
                            and len(workspace_session_ids) >= grant.max_sessions
                        ):
                            raise BoxAdmissionError(
                                "Sandbox admission session limit reached"
                            )

                    cleanup_task = self._closing_session_tasks.get(spec.session_id)
                    if cleanup_task is None:
                        existing = self._sessions.get(spec.session_id)
                        if existing is not None and existing.closing:
                            cleanup_task = self._drop_session_locked(spec.session_id)
                        elif existing is not None:
                            if (
                                spec.backend is not None
                                and existing.info.backend_name != spec.backend
                            ):
                                raise BoxSessionConflictError(
                                    "Box backend cannot change after creation"
                                )
                            if (
                                spec.e2b_config is not None
                                and getattr(existing.backend, "connection_config", None)
                                != spec.e2b_config
                            ):
                                raise BoxSessionConflictError(
                                    "E2B configuration cannot change after Box creation"
                                )
                            backend = existing.backend
                            self._assert_session_compatible(existing.info, spec)
                            if (
                                not backend.execution_scoped_mounts
                                and existing.extra_mounts_key != new_extra_mounts_key
                            ):
                                raise BoxSessionConflictError(
                                    "Box mounts differ from this session's immutable mount set; "
                                    "acquire a Box with a distinct reuse key for different host mounts. "
                                    "The existing session was preserved."
                                )
                            self._session_leases[spec.session_id] += 1

                if cleanup_task is not None:
                    await self._wait_for_session_cleanup(spec.session_id, cleanup_task)
                    continue

                if existing is not None:
                    try:
                        try:
                            alive = await backend.is_session_alive(existing.info)
                        except Exception as exc:
                            alive = False
                            self.logger.warning(
                                "LangBot Box session liveness probe failed: "
                                f"session_id={spec.session_id} error={exc}"
                            )
                    finally:
                        async with self._lock:
                            self._session_leases[spec.session_id] -= 1
                            if self._session_leases[spec.session_id] <= 0:
                                self._session_leases.pop(spec.session_id, None)

                    async with self._lock:
                        current = self._sessions.get(spec.session_id)
                        if current is existing and not existing.closing and alive:
                            existing.info.last_used_at = dt.datetime.now(_UTC)
                            if track_active_exec:
                                self._active_exec_counts[spec.session_id] += 1
                            self.logger.info(
                                "LangBot Box session reused: "
                                f"session_id={spec.session_id} "
                                f"backend_session_id={existing.info.backend_session_id} "
                                f"backend={existing.info.backend_name}"
                            )
                            return existing
                        if current is existing:
                            self.logger.warning(
                                "LangBot Box session backend disappeared, "
                                f"recreating: session_id={spec.session_id}"
                            )
                            cleanup_task = self._drop_session_locked(spec.session_id)
                        else:
                            cleanup_task = self._closing_session_tasks.get(
                                spec.session_id
                            )
                    if cleanup_task is not None:
                        await self._wait_for_session_cleanup(
                            spec.session_id, cleanup_task
                        )
                    continue

                async with self._lock:
                    if (
                        workspace_key is not None
                        and spec.workspace_max_sessions is not None
                    ):
                        used = len(
                            self._workspace_reserved_sessions.get(workspace_key, ())
                        )
                        if used >= min(spec.workspace_max_sessions, self.max_sessions):
                            raise BoxCapacityExceededError(
                                "Workspace Box session capacity reached"
                            )
                    if (
                        len(self._sessions)
                        + len(self._creating_session_tasks)
                        + len(self._closing_session_tasks)
                        >= self.max_sessions
                    ):
                        raise BoxCapacityExceededError(
                            f"Box session capacity reached ({self.max_sessions})"
                        )
                    if workspace_key is not None:
                        self._workspace_reserved_sessions.setdefault(
                            workspace_key, set()
                        ).add(spec.session_id)
                    current_task = asyncio.current_task()
                    if current_task is not None:
                        self._creating_session_tasks[spec.session_id] = current_task

                info: BoxSessionInfo | None = None
                try:
                    info = await backend.start_session(spec)
                    runtime_session = _RuntimeSession(
                        info=info,
                        backend=backend,
                        lock=asyncio.Lock(),
                        workspace_key=workspace_key,
                        extra_mounts_key=new_extra_mounts_key,
                        idle_ttl_sec=spec.idle_ttl_sec,
                    )
                    async with self._lock:
                        if self._shutdown_in_progress:
                            runtime_session.closing = True
                        else:
                            self._sessions[spec.session_id] = runtime_session
                            if (
                                not runtime_session.info.persistent
                                or spec.idle_ttl_sec is not None
                            ):
                                self._expirable_session_ids.add(spec.session_id)
                            if workspace_key is not None:
                                self._session_ids_by_workspace.setdefault(
                                    workspace_key,
                                    set(),
                                ).add(spec.session_id)
                            if track_active_exec:
                                self._active_exec_counts[spec.session_id] += 1
                    if runtime_session.closing:
                        await backend.stop_session(info)
                        raise BoxRuntimeUnavailableError("Box runtime is shutting down")
                finally:
                    async with self._lock:
                        if (
                            self._creating_session_tasks.get(spec.session_id)
                            is asyncio.current_task()
                        ):
                            self._creating_session_tasks.pop(spec.session_id, None)
                        if (
                            spec.session_id not in self._sessions
                            and spec.session_id not in self._closing_session_tasks
                        ):
                            self._release_workspace_slot_locked(
                                workspace_key, spec.session_id
                            )

                if spec.idle_ttl_sec is not None:
                    self.start_background_reaper()
                self.logger.info(
                    "LangBot Box session created: "
                    f"session_id={spec.session_id} "
                    f"backend_session_id={info.backend_session_id} "
                    f"backend={info.backend_name} image={info.image} "
                    f"network={info.network.value} host_path={info.host_path} "
                    f"host_path_mode={info.host_path_mode.value} "
                    f"mount_path={info.mount_path} "
                    f"workspace_quota_mb={info.workspace_quota_mb}"
                )
                return runtime_session

    def _release_workspace_slot_locked(
        self, workspace_key: tuple[str, str] | None, session_id: str
    ) -> None:
        slots = self._workspace_reserved_sessions.get(workspace_key)
        if slots is not None:
            slots.discard(session_id)
            if not slots:
                self._workspace_reserved_sessions.pop(workspace_key, None)

    async def _get_session_operation_lock(self, session_id: str) -> asyncio.Lock:
        async with self._lock:
            lock = self._session_operation_locks.get(session_id)
            if lock is None:
                lock = asyncio.Lock()
                self._session_operation_locks[session_id] = lock
            return lock

    async def _get_backend(
        self, name: str | None = None, e2b_config: E2BConnectionConfig | None = None
    ) -> BaseSandboxBackend:
        if name is not None:
            if (
                self.admission_required
                and name != self.admission_policy.required_backend
            ):
                raise BoxAdmissionError(
                    "Backend is restricted by managed sandbox policy"
                )
            if name == "e2b" and e2b_config is not None:
                from .e2b_backend import E2BSandboxBackend

                backend = E2BSandboxBackend(self.logger, connection_config=e2b_config)
                backend.instance_id = self.instance_id
                await backend.initialize()
                return backend
            async with self._backend_lock:
                backend = next(
                    (b for b in self.backends if b is not None and b.name == name), None
                )
                if backend is None:
                    raise BoxBackendUnavailableError(
                        f"Backend {name} is not registered"
                    )
                if name not in self._initialized_backends:
                    await backend.initialize()
                    backend.instance_id = self.instance_id
                    if self._can_cleanup_orphans:
                        try:
                            await backend.cleanup_orphaned_containers(self.instance_id)
                        except Exception as exc:
                            self.logger.warning(
                                "Box orphan cleanup failed for %s: %s", name, exc
                            )
                    self._initialized_backends.add(name)
            return backend
        if self._backend is None:
            async with self._backend_lock:
                if self._backend is None:
                    self._backend = await self._select_backend()
        if self._backend is None:
            raise BoxBackendUnavailableError(
                "LangBot Box backend unavailable. Install and start Docker or "
                "nsjail, configure E2B, or explicitly select the unsafe host backend."
            )
        return self._backend

    # Backends grouped under each top-level box.backend choice.
    # 'local' picks the first available local container backend (docker → nsjail).
    _LOCAL_BACKEND_NAMES = ("docker", "nsjail")

    async def _select_backend(self) -> BaseSandboxBackend | None:
        # Backend selection comes from box.backend only.
        # Accepted values: 'local', 'docker', 'nsjail', 'e2b', 'host'. 'local'
        # fans out to local sandbox backends. The unsafe host backend is never
        # auto-selected and must be requested explicitly.
        forced = (self._box_config.get("backend") or "").strip()
        source_label = "box.backend"

        candidates: list[BaseSandboxBackend]
        if forced == "local":
            candidates = [
                b
                for b in self.backends
                if b is not None and b.name in self._LOCAL_BACKEND_NAMES
            ]
            if not candidates:
                self.logger.error(
                    f"LangBot Box: no local backend registered "
                    f"({source_label}={forced})"
                )
                return None
        elif forced:
            candidates = [
                b for b in self.backends if b is not None and b.name == forced
            ]
            if not candidates:
                available_names = [b.name for b in self.backends if b is not None]
                self.logger.error(
                    f'LangBot Box backend "{forced}" not found '
                    f"({source_label}={forced}, available: {available_names})"
                )
                return None
        else:
            candidates = [
                b
                for b in self.backends
                if b is not None and not getattr(b, "unsafe_direct_execution", False)
            ]

        for backend in candidates:
            try:
                await backend.initialize()
                if await backend.is_available():
                    label = (
                        f"{backend.name} (forced via {source_label}={forced})"
                        if forced
                        else backend.name
                    )
                    self.logger.info(f"LangBot Box using backend: {label}")
                    return backend
            except Exception as exc:
                self.logger.warning(
                    f"LangBot Box backend {backend.name} probe failed: {exc}"
                )

        if forced:
            self.logger.error(
                f'LangBot Box backend "{forced}" probed but not available '
                f"({source_label}={forced})"
            )

        self.logger.warning(
            "LangBot Box backend unavailable: no supported sandbox backend "
            "(Docker, nsjail, E2B) is ready; the unsafe host backend is "
            "available only through explicit box.backend=host configuration"
        )
        return None

    async def _reap_expired_sessions_locked(self) -> list[asyncio.Task[None]]:
        self._reap_completed_processes()
        now = dt.datetime.now(_UTC)
        expired_session_ids: list[str] = []
        for session_id in tuple(self._expirable_session_ids):
            session = self._sessions.get(session_id)
            if session is None:
                self._expirable_session_ids.discard(session_id)
                continue
            ttl = (
                session.idle_ttl_sec
                if session.idle_ttl_sec is not None
                else self.session_ttl_sec
            )
            if (
                ttl > 0
                and session.info.last_used_at < now - dt.timedelta(seconds=ttl)
                and self._active_exec_counts.get(session_id, 0) <= 0
                and self._session_leases.get(session_id, 0) <= 0
                and not any(mp.is_running for mp in session.managed_processes.values())
            ):
                expired_session_ids.append(session_id)

        cleanup_tasks: list[asyncio.Task[None]] = []
        for session_id in expired_session_ids:
            cleanup_task = self._drop_session_locked(session_id)
            if cleanup_task is not None:
                cleanup_tasks.append(cleanup_task)
        return cleanup_tasks

    def _reap_completed_processes(self) -> None:
        """Bound retained diagnostics without one sleeping task per process."""
        now = dt.datetime.now(_UTC)
        deadline = now - dt.timedelta(seconds=self.completed_process_retention_sec)
        completed: list[
            tuple[dt.datetime, str, _RuntimeSession, str, _ManagedProcess]
        ] = []
        for session_id in tuple(self._managed_process_session_ids):
            session = self._sessions.get(session_id)
            if session is None:
                self._managed_process_session_ids.discard(session_id)
                continue
            for process_id, managed_process in list(session.managed_processes.items()):
                if managed_process.is_running or managed_process.exited_at is None:
                    continue
                if (
                    self.completed_process_retention_sec <= 0
                    or managed_process.exited_at <= deadline
                ):
                    if session.managed_processes.get(process_id) is managed_process:
                        session.managed_processes.pop(process_id, None)
                    continue
                completed.append(
                    (
                        managed_process.exited_at,
                        session_id,
                        session,
                        process_id,
                        managed_process,
                    )
                )
            self._sync_managed_process_session_index(session_id, session)

        overflow = len(completed) - max(self.max_completed_processes, 0)
        if overflow <= 0:
            return
        for _, session_id, session, process_id, managed_process in sorted(
            completed, key=lambda item: item[0]
        )[:overflow]:
            if session.managed_processes.get(process_id) is managed_process:
                session.managed_processes.pop(process_id, None)
                self._sync_managed_process_session_index(
                    session_id,
                    session,
                )

    def _sync_managed_process_session_index(
        self,
        session_id: str,
        runtime_session: _RuntimeSession,
    ) -> None:
        if runtime_session.managed_processes:
            self._managed_process_session_ids.add(session_id)
        else:
            self._managed_process_session_ids.discard(session_id)

    def _drop_session_locked(self, session_id: str) -> asyncio.Task[None] | None:
        closing_task = self._closing_session_tasks.get(session_id)
        if closing_task is not None:
            return closing_task

        runtime_session = self._sessions.pop(session_id, None)
        self._expirable_session_ids.discard(session_id)
        self._managed_process_session_ids.discard(session_id)
        if runtime_session is not None:
            runtime_session.closing = True
            if runtime_session.workspace_key is not None:
                workspace_session_ids = self._session_ids_by_workspace.get(
                    runtime_session.workspace_key
                )
                if workspace_session_ids is not None:
                    workspace_session_ids.discard(session_id)
                    if not workspace_session_ids:
                        self._session_ids_by_workspace.pop(
                            runtime_session.workspace_key,
                            None,
                        )
        self._active_exec_counts.pop(session_id, None)
        backend = runtime_session.backend if runtime_session is not None else None
        if runtime_session is None or backend is None:
            return None

        cleanup_task = asyncio.create_task(
            self._cleanup_session_resources(session_id, runtime_session, backend)
        )
        # Reaper-triggered tasks can have no waiter; cleanup logs their failures.
        cleanup_task.add_done_callback(
            lambda task: task.exception() if not task.cancelled() else None
        )
        self._closing_session_tasks[session_id] = cleanup_task
        return cleanup_task

    async def _cleanup_session_resources(
        self,
        session_id: str,
        runtime_session: _RuntimeSession,
        backend: BaseSandboxBackend,
    ) -> None:
        cleaned_up = False
        try:
            async with runtime_session.lock:
                process_error: Exception | None = None
                for mp in list(runtime_session.managed_processes.values()):
                    try:
                        await self._terminate_managed_process(mp)
                    except Exception as exc:
                        process_error = exc
                        self.logger.warning(
                            f"Failed to terminate managed process in {session_id}: {exc}",
                            exc_info=True,
                        )

                self.logger.info(
                    "LangBot Box session cleanup: "
                    f"session_id={session_id} "
                    f"backend_session_id={runtime_session.info.backend_session_id} "
                    f"backend={runtime_session.info.backend_name}"
                )
                await backend.stop_session(runtime_session.info)
                if process_error is not None:
                    raise BoxError(
                        f"Failed to terminate managed processes in session {session_id}"
                    ) from process_error
                runtime_session.managed_processes.clear()
                self._managed_process_session_ids.discard(session_id)
                cleaned_up = True
        except Exception as exc:
            self.logger.warning(
                f"Failed to finalize box session cleanup {session_id}: {exc}",
                exc_info=True,
            )
            raise
        finally:
            current_task = asyncio.current_task()
            async with self._lock:
                if self._closing_session_tasks.get(session_id) is current_task:
                    if not cleaned_up:
                        # Retain the fence and resources for the next acquire/delete.
                        self._sessions[session_id] = runtime_session
                        if runtime_session.workspace_key is not None:
                            self._session_ids_by_workspace.setdefault(
                                runtime_session.workspace_key, set()
                            ).add(session_id)
                        self._sync_managed_process_session_index(
                            session_id, runtime_session
                        )
                    self._closing_session_tasks.pop(session_id, None)
                    self._release_workspace_slot_locked(
                        runtime_session.workspace_key, session_id
                    )

    async def _wait_for_session_cleanups(
        self, cleanup_tasks: list[asyncio.Task[None]]
    ) -> None:
        for cleanup_task in cleanup_tasks:
            await self._wait_for_session_cleanup(None, cleanup_task)

    async def _wait_for_session_cleanup(
        self, session_id: str | None, cleanup_task: asyncio.Task[None]
    ) -> None:
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            label = f" {session_id}" if session_id is not None else ""
            self.logger.warning(
                f"LangBot Box session cleanup task failed{label}: {exc}",
                exc_info=True,
            )
            raise BoxError(f"Failed to clean up box session{label}: {exc}") from exc

    def _assert_session_compatible(self, session: BoxSessionInfo, spec: BoxSpec):
        _COMPAT_FIELDS = (
            "network",
            "image",
            "host_path",
            "host_path_mode",
            "mount_path",
            "persistent",
            "cpus",
            "memory_mb",
            "pids_limit",
            "read_only_rootfs",
            "workspace_quota_mb",
        )
        for field in _COMPAT_FIELDS:
            session_val = getattr(session, field)
            spec_val = getattr(spec, field)
            if session_val != spec_val:
                display = (
                    session_val.value if hasattr(session_val, "value") else session_val
                )
                raise BoxSessionConflictError(
                    f"Box session {spec.session_id} already exists with {field}={display}"
                )

    async def _drain_managed_process_stderr(
        self, session_id: str, process_id: str, managed_process: _ManagedProcess
    ) -> None:
        stream = managed_process.process.stderr
        if stream is None:
            return

        log_window_started = time.monotonic()
        logged_chunks = 0
        suppressed_chunks = 0

        def flush_suppressed() -> None:
            nonlocal suppressed_chunks
            if suppressed_chunks:
                self.logger.warning(
                    "LangBot Box suppressed managed-process stderr chunks: "
                    f"session_id={session_id} process_id={process_id} "
                    f"suppressed={suppressed_chunks}"
                )
                suppressed_chunks = 0

        try:
            while True:
                chunk = await stream.read(_MANAGED_PROCESS_STDERR_READ_BYTES)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace").rstrip()
                if not text:
                    continue
                managed_process.stderr_chunks.append(text)
                managed_process.stderr_total_len += (
                    len(text) + 1
                )  # +1 for '\n' separator
                while (
                    managed_process.stderr_total_len
                    > _MANAGED_PROCESS_STDERR_PREVIEW_LIMIT
                    and managed_process.stderr_chunks
                ):
                    removed = managed_process.stderr_chunks.popleft()
                    managed_process.stderr_total_len -= len(removed) + 1

                now = time.monotonic()
                if now - log_window_started >= _MANAGED_PROCESS_STDERR_LOG_WINDOW_SEC:
                    flush_suppressed()
                    log_window_started = now
                    logged_chunks = 0
                if logged_chunks < _MANAGED_PROCESS_STDERR_LOG_CHUNKS_PER_WINDOW:
                    excerpt = text[:_MANAGED_PROCESS_STDERR_LOG_EXCERPT_CHARS]
                    self.logger.info(
                        "LangBot Box managed process stderr: "
                        f"session_id={session_id} process_id={process_id} {excerpt}"
                    )
                    logged_chunks += 1
                else:
                    suppressed_chunks += 1
        except Exception as exc:
            self.logger.warning(
                f"Failed to drain managed process stderr for {session_id}/{process_id}: {exc}"
            )
        finally:
            flush_suppressed()

    async def _watch_managed_process(
        self, session_id: str, process_id: str, managed_process: _ManagedProcess
    ) -> None:
        return_code = await managed_process.process.wait()
        managed_process.exit_code = return_code
        managed_process.exited_at = dt.datetime.now(_UTC)
        runtime_session = self._sessions.get(session_id)
        if runtime_session is not None:
            runtime_session.info.last_used_at = managed_process.exited_at
        self.logger.info(
            f"LangBot Box managed process exited: session_id={session_id} process_id={process_id} return_code={return_code}"
        )
        # Retention is reaped synchronously from the in-memory registry. This
        # avoids accumulating one five-minute sleeping task for every short-
        # lived process while still preserving bounded exit diagnostics.
        self._reap_completed_processes()

    def _track_background_task(self, task: asyncio.Task) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _terminate_managed_process(
        self, managed_process: _ManagedProcess
    ) -> None:
        if not managed_process.is_running:
            return

        process = managed_process.process
        try:
            if process.stdin is not None:
                process.stdin.close()
        except Exception as exc:
            self.logger.debug(
                "Failed to close managed process stdin: %s", exc, exc_info=True
            )

        try:
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError as exc:
                    self.logger.debug(
                        "Managed process exited before terminate: %s", exc
                    )
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=5)
        except asyncio.TimeoutError:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError as exc:
                    self.logger.debug("Managed process exited before kill: %s", exc)
            await process.wait()
        finally:
            managed_process.exit_code = process.returncode
            managed_process.exited_at = dt.datetime.now(_UTC)

    def _managed_process_to_dict(
        self, session_id: str, process_id: str, managed_process: _ManagedProcess
    ) -> dict:
        stderr_preview = "\n".join(managed_process.stderr_chunks)
        status = (
            BoxManagedProcessStatus.RUNNING
            if managed_process.is_running
            else BoxManagedProcessStatus.EXITED
        )
        return BoxManagedProcessInfo(
            session_id=session_id,
            process_id=process_id,
            status=status,
            command=managed_process.spec.command,
            args=managed_process.spec.args,
            cwd=managed_process.spec.cwd,
            env_keys=sorted(managed_process.spec.env.keys()),
            attached=managed_process.attach_lock.locked(),
            started_at=managed_process.started_at,
            exited_at=managed_process.exited_at,
            exit_code=managed_process.exit_code,
            stderr_preview=stderr_preview,
        ).model_dump(mode="json")

    def _session_to_dict(self, info: BoxSessionInfo) -> dict:
        result = info.model_dump(mode="json")
        session = self._sessions.get(info.session_id)
        result["status"] = (
            "closing"
            if session and session.closing
            else "running"
            if self._active_exec_counts.get(info.session_id, 0)
            else "idle"
        )
        return result
