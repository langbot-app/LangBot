from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import logging
import os
import pathlib
import shutil
import sys
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Literal, Sequence

from langbot_plugin.entities.io.context import InstallationBinding, PluginWorkerPolicy
from langbot_plugin.runtime import bounded_executor
from langbot_plugin.runtime.helper import pkgmgr as pkgmgr_helper
from langbot_plugin.runtime.io.controllers.stdio import (
    client as stdio_client_controller,
)
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.runtime.io.controller import Controller
from langbot_plugin.runtime.plugin.artifact import (
    PluginArtifact,
    PluginInstallationPaths,
)
from langbot_plugin.runtime.plugin.dependency_environment import (
    DependencyEnvironmentPreparationError,
    DependencyEnvironmentStaging,
    PluginDependencyEnvironment,
    PluginDependencyEnvironmentStore,
)
from langbot_plugin.runtime.security import (
    PLUGIN_FILE_STORAGE_DIR_ENV,
    PLUGIN_REGISTRATION_CAPABILITY_ENV,
    PLUGIN_RUNTIME_PROFILE_ENV,
)
from langbot_plugin.utils.platform import get_platform

logger = logging.getLogger(__name__)

_READONLY_SYSTEM_MOUNTS = (
    "/bin",
    "/lib",
    "/lib64",
    "/sbin",
    "/usr",
)
_READONLY_ETC_FILES = (
    "/etc/hosts",
    "/etc/nsswitch.conf",
    "/etc/resolv.conf",
    "/etc/ssl",
)
_DEV_NODES = ("/dev/null", "/dev/random", "/dev/urandom")
_CGROUP_V2_ROOT = pathlib.Path("/sys/fs/cgroup")
_PROC_SELF_CGROUP = pathlib.Path("/proc/self/cgroup")
_CGROUP_V2_CONTROLLERS = ("cpu", "memory", "pids")
_RUNTIME_CGROUP_NAME = "langbot-runtime"
_WORKERS_CGROUP_NAME = "langbot-plugin-workers"
RUNTIME_MEMORY_RESERVE_MB_ENV = "LANGBOT_PLUGIN_RUNTIME_MEMORY_RESERVE_MB"
_DEFAULT_RUNTIME_MEMORY_RESERVE_MB = 2048
_DEPENDENCY_INSTALL_TIMEOUT_SECONDS = 600
_DEPENDENCY_INSTALLER_SCHEMA_VERSION = 2
_WINDOWS_WORKER_ENV_ALLOWLIST = frozenset(
    {
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
    }
)
_DEPENDENCY_INSTALL_ENV_ALLOWLIST = frozenset(
    {
        "ALL_PROXY",
        "COMSPEC",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "LANG",
        "LC_ALL",
        "NO_PROXY",
        "PATH",
        "PATHEXT",
        "PIP_CERT",
        "PIP_CLIENT_CERT",
        "REQUESTS_CA_BUNDLE",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "SYSTEMROOT",
        "WINDIR",
        "all_proxy",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    }
)


@dataclass(frozen=True, slots=True)
class PluginWorkerLaunchSpec:
    binding: InstallationBinding
    artifact: PluginArtifact
    paths: PluginInstallationPaths
    registration_capability: str
    dependency_environment: PluginDependencyEnvironment | None = None
    runtime_ws_url: str | None = None


class PluginWorkerProcessController(Controller):
    """Own a worker that connects back through the Runtime WebSocket server."""

    def __init__(
        self,
        *,
        command: str,
        args: list[str],
        env: dict[str, str],
        working_dir: str,
    ) -> None:
        self.command = command
        self.args = args
        self.env = env
        self.working_dir = working_dir
        self.process: asyncio.subprocess.Process | None = None

    async def run(
        self,
        new_connection_callback: Callable[[Connection], Coroutine[Any, Any, None]],
    ) -> None:
        # The Runtime WebSocket server owns the connection callback. This
        # controller only owns the child process lifetime.
        del new_connection_callback
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            env=self.env,
            cwd=self.working_dir,
            # This worker uses WebSocket; stdout belongs to the host protocol.
            stdout=sys.stderr,
        )
        try:
            await self.process.wait()
        finally:
            if self.process.returncode is None:
                stopped = await stdio_client_controller.stop_process(self.process)
                if not stopped:
                    raise RuntimeError("Plugin worker did not exit after SIGKILL")


class PluginWorkerLauncher:
    """Build isolated worker processes exclusively from trusted Runtime policy."""

    def __init__(
        self,
        *,
        nsjail_path: str | None = None,
        cgroup_v2_available: bool | None = None,
        platform: str | None = None,
        python_executable: str | None = None,
        python_prefix: str | None = None,
        runtime_import_root: str | None = None,
    ):
        self.nsjail_path = (
            nsjail_path if nsjail_path is not None else shutil.which("nsjail")
        )
        self.cgroup_v2_available = cgroup_v2_available
        # Parent cgroup for nsjail-created worker cgroups. It is nested under
        # the Runtime's own cgroup so the container memory limit and
        # accounting also cover every sandbox.
        self.cgroup_v2_mount: pathlib.Path | None = None
        self.platform = platform or get_platform()
        self.python_executable = pathlib.Path(
            python_executable or sys.executable
        ).absolute()
        self.python_prefix = pathlib.Path(python_prefix or sys.prefix).absolute()
        self.runtime_import_root = pathlib.Path(
            runtime_import_root or pathlib.Path(__file__).resolve().parents[3]
        ).absolute()
        self.policy: PluginWorkerPolicy | None = None
        self.runtime_profile: Literal["oss_dev", "shared"] | None = None
        self.effective_profile: Literal["oss_dev", "shared"] | None = None

    def configure(
        self,
        policy: PluginWorkerPolicy,
        runtime_profile: Literal["oss_dev", "shared"],
    ) -> None:
        if self.policy is not None and self.policy != policy:
            raise ValueError("Plugin worker launcher policy cannot be changed")
        if self.runtime_profile is not None and self.runtime_profile != runtime_profile:
            raise ValueError("Plugin worker launcher profile cannot be changed")

        if runtime_profile == "shared":
            if self.platform == "win32":
                # Windows cannot express nsjail or delegated cgroup v2, so a
                # local development host executes per-plugin workers while the
                # shared authorization contract itself is unchanged.  Linux
                # deployments keep the fences below.
                logger.warning(
                    "Shared plugin workers require Linux nsjail; running per-plugin workers on this Windows host."
                )
                self.effective_profile = "oss_dev"
            else:
                if self.platform != "linux":
                    raise RuntimeError("Shared plugin workers require Linux nsjail")
                if not self.nsjail_path:
                    raise RuntimeError("Shared plugin workers require nsjail")
                self._validate_python_runtime()
                if self.cgroup_v2_available is None:
                    self.cgroup_v2_mount = prepare_worker_cgroup_v2_parent()
                    self.cgroup_v2_available = self.cgroup_v2_mount is not None
                self.effective_profile = "shared"
        else:
            if self.cgroup_v2_available is None:
                self.cgroup_v2_available = False
            self.effective_profile = "oss_dev"
        if policy.require_hard_limits and not self.cgroup_v2_available:
            if self.platform == "win32":
                logger.warning(
                    "Plugin worker hard limits require delegated cgroup v2 controllers; "
                    "this Windows host runs without them."
                )
            else:
                raise RuntimeError(
                    "Plugin worker hard limits require delegated cgroup v2 controllers"
                )

        self.policy = policy
        self.runtime_profile = runtime_profile

    def create_controller(
        self,
        launch_spec: PluginWorkerLaunchSpec,
    ) -> Controller:
        policy, profile = self._require_configuration()
        dependency_environment = self._require_dependency_environment(launch_spec)
        if profile == "shared":
            return stdio_client_controller.StdioClientController(
                command=str(self.nsjail_path),
                args=self.build_nsjail_args(launch_spec),
                env={},
                working_dir="/",
                # A dedicated worker serves one installation and nsjail runs
                # with --really_quiet, so stderr is that plugin's own logging.
                capture_stderr=True,
            )

        # OSS development keeps the historical direct-process behavior and
        # artifact .env loading. Only the one-use registration capability and
        # explicit profile cross this process boundary.
        del policy
        worker_environment = self._windows_worker_environment()
        worker_environment.update(
            {
                PLUGIN_FILE_STORAGE_DIR_ENV: str(
                    (launch_spec.paths.root_path / "rpc-transfer").resolve()
                ),
                PLUGIN_REGISTRATION_CAPABILITY_ENV: (
                    launch_spec.registration_capability
                ),
                PLUGIN_RUNTIME_PROFILE_ENV: "oss_dev",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": os.pathsep.join(
                    (
                        str(self.runtime_import_root),
                        str(dependency_environment.site_packages_path.resolve()),
                    )
                ),
                "PYTHONUNBUFFERED": "1",
            }
        )
        worker_args = [
            "-m",
            "langbot_plugin.cli.__init__",
            "run",
        ]
        process_tag = self._worker_process_tag(launch_spec)
        if process_tag:
            worker_args.extend(["--tag", process_tag])
        worker_args.append("--prod")
        if self.platform == "win32":
            runtime_ws_url = str(launch_spec.runtime_ws_url or "").strip()
            if not runtime_ws_url:
                raise RuntimeError(
                    "Windows plugin worker Runtime WebSocket URL is missing"
                )
            worker_environment["RUNTIME_WS_URL"] = runtime_ws_url
            return PluginWorkerProcessController(
                command=str(self.python_executable),
                args=worker_args,
                env=worker_environment,
                working_dir=str(launch_spec.artifact.code_path),
            )

        return stdio_client_controller.StdioClientController(
            command=str(self.python_executable),
            args=[*worker_args[:-1], "-s", worker_args[-1]],
            env=worker_environment,
            working_dir=str(launch_spec.artifact.code_path),
            # Pipe stderr (the plugin's Python `logging` output) so the
            # handler's log buffer can serve the plugin logs page.
            capture_stderr=True,
        )

    async def prepare_dependency_environment(
        self,
        store: PluginDependencyEnvironmentStore,
        artifact: PluginArtifact,
        *,
        execution_mode: str | None = None,
    ) -> PluginDependencyEnvironment:
        """Prepare artifact dependencies before issuing a worker capability."""

        _, profile = self._require_configuration()
        installer = (
            self._install_dependency_environment
            if profile == "shared"
            else self._install_dependency_environment_direct
        )
        return await store.prepare(
            artifact,
            runtime_fingerprint=self.dependency_runtime_fingerprint(),
            installer=installer,
            execution_mode=execution_mode,
        )

    def dependency_runtime_fingerprint(self) -> str:
        """Key environments by the worker ABI and Runtime dependency contract."""

        _, profile = self._require_configuration()
        try:
            sdk_version = importlib.metadata.version("langbot-plugin")
        except importlib.metadata.PackageNotFoundError:  # pragma: no cover - dev tree
            sdk_version = "uninstalled"
        payload = {
            "installer_schema": _DEPENDENCY_INSTALLER_SCHEMA_VERSION,
            "python_cache_tag": sys.implementation.cache_tag,
            "python_implementation": sys.implementation.name,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "runtime_profile": profile,
            "sdk_version": sdk_version,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    async def _install_dependency_environment(
        self,
        staging: DependencyEnvironmentStaging,
        requirements: Sequence[str],
    ) -> None:
        if not requirements:
            return
        args = await bounded_executor.run_blocking_atomic(
            self.build_dependency_prepare_nsjail_args,
            staging,
            requirements,
        )
        process = await asyncio.create_subprocess_exec(
            str(self.nsjail_path),
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env={},
            cwd="/",
        )
        await self._wait_for_dependency_installer(process)

    async def _install_dependency_environment_direct(
        self,
        staging: DependencyEnvironmentStaging,
        requirements: Sequence[str],
    ) -> None:
        """Prepare an OSS dependency tree without mutating the Runtime venv."""

        if not requirements:
            return
        args = await bounded_executor.run_blocking_atomic(
            self.build_dependency_prepare_direct_args,
            staging,
            requirements,
        )
        tmp_path = self._absolute_runtime_path(staging.tmp_path)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=self._direct_dependency_installer_environment(tmp_path),
            cwd=str(tmp_path),
        )
        await self._wait_for_dependency_installer(process)

    @staticmethod
    async def _wait_for_dependency_installer(
        process: asyncio.subprocess.Process,
    ) -> None:
        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=_DEPENDENCY_INSTALL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.wait()
            raise DependencyEnvironmentPreparationError(
                "Plugin dependency installation timed out"
            ) from exc
        except asyncio.CancelledError:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            raise
        if process.returncode != 0:
            # Never reflect pip output: configured indexes and backend errors
            # can contain credentials. The exit code is stable and sufficient
            # for the desired-state failure; detailed logs belong in a
            # separately redacted operator channel.
            raise DependencyEnvironmentPreparationError(
                f"Plugin dependency installer exited with code {process.returncode}"
            )

    def build_dependency_prepare_direct_args(
        self,
        staging: DependencyEnvironmentStaging,
        requirements: Sequence[str],
    ) -> list[str]:
        """Build the direct OSS pip command for one isolated target tree."""

        _, profile = self._require_configuration()
        if profile != "oss_dev":
            raise RuntimeError(
                "Direct dependency preparation requires the OSS Runtime profile"
            )
        site_packages_path = self._absolute_runtime_path(staging.site_packages_path)
        requirements_path = self._write_dependency_requirements(
            staging,
            requirements,
        )
        return [
            str(self.python_executable),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--ignore-installed",
            "--no-cache-dir",
            "--no-compile",
            "--no-input",
            "--no-warn-script-location",
            "--target",
            str(site_packages_path),
            *pkgmgr_helper.get_pip_index_args(),
            "-r",
            str(requirements_path),
        ]

    def build_dependency_prepare_nsjail_args(
        self,
        staging: DependencyEnvironmentStaging,
        requirements: Sequence[str],
    ) -> list[str]:
        policy, profile = self._require_configuration()
        if profile != "shared" or not self.nsjail_path:
            raise RuntimeError(
                "Dependency preparation requires the shared Runtime profile"
            )

        jail_root_path = self._absolute_runtime_path(staging.jail_root_path)
        site_packages_path = self._absolute_runtime_path(staging.site_packages_path)
        tmp_path = self._absolute_runtime_path(staging.tmp_path)
        self._write_dependency_requirements(staging, requirements)

        runtime_prefix_mount = self._python_prefix_mount()
        self._ensure_jail_mount_targets(
            jail_root_path,
            extra_targets=(runtime_prefix_mount,) if runtime_prefix_mount else (),
        )
        (jail_root_path / "dependency-env").mkdir(exist_ok=True)
        args = ["--mode", "o", "--chroot", str(jail_root_path)]
        args.append("--disable_clone_newnet")
        self._append_readonly_runtime_mounts(args, runtime_prefix_mount)
        args.extend(
            [
                "--bindmount",
                f"{site_packages_path}:/dependency-env",
                "--bindmount",
                f"{tmp_path}:/tmp",
                "--mount",
                "none:/proc:proc:rw",
                "--mount",
                "none:/dev:tmpfs:rw",
            ]
        )
        self._append_device_mounts(args)
        args.extend(
            [
                "--cwd",
                "/tmp",
                "--env",
                "HOME=/tmp",
                "--env",
                "TMPDIR=/tmp",
                "--env",
                "PIP_CACHE_DIR=/tmp/pip-cache",
                "--env",
                "PIP_DISABLE_PIP_VERSION_CHECK=1",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                "--env",
                "PYTHONUNBUFFERED=1",
                "--env",
                "PATH=/usr/local/bin:/usr/bin:/bin",
            ]
        )
        self._append_policy_limits(args, policy)
        args.extend(
            [
                "--really_quiet",
                "--",
                str(self.python_executable),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--ignore-installed",
                "--no-cache-dir",
                "--no-compile",
                "--no-input",
                "--no-warn-script-location",
                "--target",
                "/dependency-env",
                *pkgmgr_helper.get_pip_index_args(),
                "-r",
                "/tmp/requirements.txt",
            ]
        )
        return args

    @staticmethod
    def _worker_process_tag(launch_spec: PluginWorkerLaunchSpec) -> str:
        """Return the cosmetic `author/name` label for the worker command line."""

        artifact = launch_spec.artifact
        author = str(getattr(artifact, "plugin_author", "") or "").strip()
        name = str(getattr(artifact, "plugin_name", "") or "").strip()
        if author and name:
            return f"{author}/{name}"
        return name or author

    def build_nsjail_args(
        self, launch_spec: PluginWorkerLaunchSpec, *, execution_mode: str = "dedicated"
    ) -> list[str]:
        policy, profile = self._require_configuration()
        policy = policy.for_execution_mode(execution_mode, profile)
        if profile != "shared" or not self.nsjail_path:
            raise RuntimeError("nsjail arguments require the shared Runtime profile")

        dependency_environment = self._require_dependency_environment(launch_spec)

        jail_root_path = self._absolute_runtime_path(launch_spec.paths.jail_root_path)
        artifact_code_path = self._absolute_runtime_path(launch_spec.artifact.code_path)
        dependency_site_packages_path = self._absolute_runtime_path(
            dependency_environment.site_packages_path
        )
        home_path = self._absolute_runtime_path(launch_spec.paths.home_path)
        tmp_path = self._absolute_runtime_path(launch_spec.paths.tmp_path)
        data_path = self._absolute_runtime_path(launch_spec.paths.data_path)
        runtime_prefix_mount = self._python_prefix_mount()
        runtime_mounts = [runtime_prefix_mount] if runtime_prefix_mount else []
        # Editable SDK installs live outside the venv. Expose only their
        # trusted source root, not the surrounding checkout or user directory.
        source_mount = self.runtime_import_root
        if not self._path_covered_by_system_mount(source_mount) and not (
            source_mount == self.python_prefix
            or self.python_prefix in source_mount.parents
        ):
            runtime_mounts.append(source_mount)
        self._ensure_jail_mount_targets(
            jail_root_path,
            extra_targets=tuple(runtime_mounts),
        )
        # Plugin installations are resident workers. NsJail defaults to a
        # 600-second jail lifetime, so explicitly disable the wall-time limit;
        # lifecycle revocation is owned by desired state and generation fences.
        args = [
            "--mode",
            "o",
            "--time_limit",
            "0",
            "--chroot",
            str(jail_root_path),
        ]
        args.append("--disable_clone_newnet")
        self._append_readonly_runtime_mounts(args, runtime_prefix_mount)
        if source_mount in runtime_mounts:
            args.extend(["--bindmount_ro", f"{source_mount}:{source_mount}"])

        args.extend(
            [
                "--bindmount_ro",
                f"{artifact_code_path}:/plugin",
                "--bindmount_ro",
                f"{dependency_site_packages_path}:/plugin-dependencies",
                "--bindmount",
                f"{home_path}:/home",
                "--bindmount",
                f"{tmp_path}:/tmp",
                "--bindmount",
                f"{data_path}:/data",
                "--mount",
                "none:/proc:proc:rw",
                "--mount",
                "none:/dev:tmpfs:rw",
            ]
        )
        self._append_device_mounts(args)

        args.extend(
            [
                "--cwd",
                "/plugin",
                "--env",
                "HOME=/home",
                "--env",
                "TMPDIR=/tmp",
                "--env",
                "PYTHONUNBUFFERED=1",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                "--env",
                (f"PYTHONPATH={self.runtime_import_root}:/plugin-dependencies"),
                "--env",
                f"{PLUGIN_RUNTIME_PROFILE_ENV}=shared",
                "--env",
                f"{PLUGIN_REGISTRATION_CAPABILITY_ENV}={launch_spec.registration_capability}",
            ]
        )

        self._append_policy_limits(args, policy)
        process_tag = self._worker_process_tag(launch_spec)
        args.extend(
            [
                "--really_quiet",
                "--",
                str(self.python_executable),
                "-m",
                "langbot_plugin.cli.__init__",
                "run",
                "-s",
                *(["--tag", process_tag] if process_tag else []),
                "--prod",
            ]
        )
        return args

    def build_shared_pool_nsjail_args(
        self,
        launch_spec: PluginWorkerLaunchSpec,
    ) -> list[str]:
        """Build a digest worker without mounting installation-owned paths."""

        args = self.build_nsjail_args(launch_spec, execution_mode="shared-runtime-v1")
        private_mounts = {
            str(self._absolute_runtime_path(launch_spec.paths.home_path)),
            str(self._absolute_runtime_path(launch_spec.paths.tmp_path)),
            str(self._absolute_runtime_path(launch_spec.paths.data_path)),
        }
        cleaned: list[str] = []
        index = 0
        while index < len(args):
            if (
                args[index] == "--bindmount"
                and index + 1 < len(args)
                and args[index + 1].split(":", 1)[0] in private_mounts
            ):
                index += 2
                continue
            cleaned.append(args[index])
            index += 1
        if "HOME=/home" in cleaned:
            cleaned[cleaned.index("HOME=/home")] = "HOME=/tmp"
        # Pool workers mount no installation-owned /tmp, but the worker handler
        # still needs a writable transfer root (SHARED_WORKER_FILE_STORAGE_DIR).
        separator = len(cleaned) - 1 - cleaned[::-1].index("--")
        cleaned[separator:separator] = ["--tmpfsmount", "/tmp"]
        return cleaned

    def create_shared_pool_controller(
        self,
        launch_spec: PluginWorkerLaunchSpec,
    ) -> Controller:
        self._require_dependency_environment(launch_spec)
        _, profile = self._require_configuration()
        if profile != "shared":
            raise RuntimeError(
                "Certified shared pools require the shared Runtime profile"
            )
        return stdio_client_controller.StdioClientController(
            command=str(self.nsjail_path),
            args=self.build_shared_pool_nsjail_args(launch_spec),
            env={},
            working_dir="/",
            close_process_on_callback_return=False,
        )

    def _append_readonly_runtime_mounts(
        self,
        args: list[str],
        runtime_prefix_mount: pathlib.Path | None,
    ) -> None:
        for path in _READONLY_SYSTEM_MOUNTS:
            if os.path.exists(path) and not os.path.islink(path):
                args.extend(["--bindmount_ro", f"{path}:{path}"])
        for path in _READONLY_ETC_FILES:
            if os.path.exists(path):
                args.extend(["--bindmount_ro", f"{os.path.realpath(path)}:{path}"])
        if runtime_prefix_mount is not None:
            args.extend(
                [
                    "--bindmount_ro",
                    f"{runtime_prefix_mount}:{runtime_prefix_mount}",
                ]
            )

    @staticmethod
    def _append_device_mounts(args: list[str]) -> None:
        for device in _DEV_NODES:
            if os.path.exists(device):
                args.extend(["--bindmount", f"{device}:{device}"])

    def _append_policy_limits(
        self,
        args: list[str],
        policy: PluginWorkerPolicy,
    ) -> None:
        if self.cgroup_v2_available:
            if self.cgroup_v2_mount is not None:
                args.extend(["--cgroupv2_mount", str(self.cgroup_v2_mount)])
            args.extend(
                [
                    "--use_cgroupv2",
                    "--cgroup_mem_max",
                    str(policy.max_memory_mb * 1024 * 1024),
                    "--cgroup_mem_swap_max",
                    "0",
                    "--cgroup_pids_max",
                    str(policy.max_pids),
                    "--cgroup_cpu_ms_per_sec",
                    str(max(1, int(policy.max_cpus * 1000))),
                ]
            )
        args.extend(
            [
                "--rlimit_as",
                "hard",
                "--rlimit_nproc",
                str(policy.max_pids),
                "--rlimit_nofile",
                str(policy.max_open_files),
                "--rlimit_fsize",
                str(policy.max_file_size_mb),
            ]
        )

    def _require_configuration(
        self,
    ) -> tuple[PluginWorkerPolicy, Literal["oss_dev", "shared"]]:
        if (
            self.policy is None
            or self.runtime_profile is None
            or self.effective_profile is None
        ):
            raise RuntimeError("Plugin worker launcher is not configured")
        return self.policy, self.effective_profile

    @staticmethod
    def _require_dependency_environment(
        launch_spec: PluginWorkerLaunchSpec,
    ) -> PluginDependencyEnvironment:
        dependency_environment = launch_spec.dependency_environment
        if dependency_environment is None:
            raise RuntimeError("Plugin worker dependency environment is missing")
        if dependency_environment.artifact_digest != launch_spec.artifact.digest:
            raise RuntimeError(
                "Plugin worker dependency environment does not match artifact"
            )
        return dependency_environment

    def _runtime_site_packages_path(self) -> pathlib.Path:
        if self.platform == "win32":
            return self.python_prefix / "Lib" / "site-packages"
        return (
            self.python_prefix
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )

    def _windows_worker_environment(self) -> dict[str, str]:
        if self.platform != "win32":
            return {}
        return {
            **{
                name: value
                for name in _WINDOWS_WORKER_ENV_ALLOWLIST
                if (value := os.environ.get(name)) is not None
            },
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }

    def _write_dependency_requirements(
        self,
        staging: DependencyEnvironmentStaging,
        requirements: Sequence[str],
    ) -> pathlib.Path:
        requirements_path = (
            self._absolute_runtime_path(staging.tmp_path) / "requirements.txt"
        )
        requirements_path.write_text(
            "".join(f"{requirement}\n" for requirement in requirements),
            encoding="utf-8",
        )
        requirements_path.chmod(0o600)
        return requirements_path

    @staticmethod
    def _direct_dependency_installer_environment(
        tmp_path: pathlib.Path,
    ) -> dict[str, str]:
        environment = {
            name: value
            for name in _DEPENDENCY_INSTALL_ENV_ALLOWLIST
            if (value := os.environ.get(name)) is not None
        }
        environment.update(
            {
                "HOME": str(tmp_path),
                "PIP_CACHE_DIR": str(tmp_path / "pip-cache"),
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
                "PYTHONUNBUFFERED": "1",
                "TEMP": str(tmp_path),
                "TMP": str(tmp_path),
                "TMPDIR": str(tmp_path),
            }
        )
        return environment

    @staticmethod
    def _ensure_jail_mount_targets(
        root_path: pathlib.Path,
        *,
        extra_targets: tuple[pathlib.Path, ...] = (),
    ) -> None:
        targets = {
            "/plugin",
            "/plugin-dependencies",
            "/home",
            "/tmp",
            "/data",
            "/proc",
            "/dev",
            *_READONLY_SYSTEM_MOUNTS,
            *_READONLY_ETC_FILES,
            *(str(path) for path in extra_targets),
        }
        for target_path in targets:
            host_target = root_path / target_path.lstrip("/")
            # Resolver files commonly point into /run, which is deliberately
            # not exposed to workers. Bind the allowlisted file itself.
            if target_path in _READONLY_ETC_FILES and os.path.exists(target_path):
                host_target.parent.mkdir(parents=True, exist_ok=True)
                if host_target.is_symlink():
                    host_target.unlink()
                if os.path.isdir(target_path):
                    host_target.mkdir(exist_ok=True)
                else:
                    host_target.touch(exist_ok=True)
            elif os.path.islink(target_path):
                host_target.parent.mkdir(parents=True, exist_ok=True)
                link_value = os.readlink(target_path)
                if os.path.lexists(host_target):
                    if (
                        host_target.is_symlink()
                        and os.readlink(host_target) == link_value
                    ):
                        continue
                    if host_target.is_dir():
                        host_target.rmdir()
                    else:
                        host_target.unlink()
                host_target.symlink_to(link_value)
            elif os.path.isfile(target_path):
                host_target.parent.mkdir(parents=True, exist_ok=True)
                host_target.touch(exist_ok=True)
            else:
                host_target.mkdir(parents=True, exist_ok=True)

    def _validate_python_runtime(self) -> None:
        if (
            not self.python_executable.is_absolute()
            or not self.python_prefix.is_absolute()
        ):
            raise RuntimeError("Shared plugin worker Python paths must be absolute")
        if not self.python_executable.exists():
            raise RuntimeError("Shared plugin worker Python executable does not exist")
        if not self.python_prefix.is_dir():
            raise RuntimeError("Shared plugin worker Python prefix does not exist")
        if self._path_covered_by_system_mount(self.python_executable):
            return
        try:
            self.python_executable.relative_to(self.python_prefix)
        except ValueError as exc:
            raise RuntimeError(
                "Shared plugin worker Python executable must be inside its mounted prefix"
            ) from exc

    def _python_prefix_mount(self) -> pathlib.Path | None:
        if self._path_covered_by_system_mount(self.python_prefix):
            return None
        return self.python_prefix

    @staticmethod
    def _absolute_runtime_path(path: str | os.PathLike[str]) -> pathlib.Path:
        """Freeze Runtime-owned mount sources before nsjail changes cwd to root."""

        return pathlib.Path(path).absolute()

    @staticmethod
    def _path_covered_by_system_mount(path: pathlib.Path) -> bool:
        return any(
            path == pathlib.Path(root) or pathlib.Path(root) in path.parents
            for root in _READONLY_SYSTEM_MOUNTS
        )


def _read_cgroup_list(path: pathlib.Path) -> list[str]:
    return path.read_text().split()


def _enable_cgroup_controllers(cgroup: pathlib.Path) -> None:
    enabled = set(_read_cgroup_list(cgroup / "cgroup.subtree_control"))
    missing = [c for c in _CGROUP_V2_CONTROLLERS if c not in enabled]
    if missing:
        (cgroup / "cgroup.subtree_control").write_text(
            " ".join(f"+{c}" for c in missing)
        )


def _runtime_memory_reserve_bytes() -> int:
    raw = os.environ.get(RUNTIME_MEMORY_RESERVE_MB_ENV, "")
    try:
        reserve_mb = int(raw) if raw else _DEFAULT_RUNTIME_MEMORY_RESERVE_MB
    except ValueError:
        logger.warning(
            f"Ignoring invalid {RUNTIME_MEMORY_RESERVE_MB_ENV}={raw!r}; "
            f"using {_DEFAULT_RUNTIME_MEMORY_RESERVE_MB} MiB"
        )
        reserve_mb = _DEFAULT_RUNTIME_MEMORY_RESERVE_MB
    return max(reserve_mb, 0) * 1024 * 1024


def prepare_worker_cgroup_v2_parent(
    cgroup_root: pathlib.Path = _CGROUP_V2_ROOT,
    proc_self_cgroup: pathlib.Path = _PROC_SELF_CGROUP,
    pid: int | None = None,
) -> pathlib.Path | None:
    """Create a delegated cgroup v2 parent for worker sandboxes.

    nsjail creates ``NSJAIL.<pid>`` cgroups directly below its
    ``--cgroupv2_mount``. Pointing that at the cgroup v2 mount root lets
    sandboxes escape the Runtime container when the host cgroup tree is
    mounted, so their memory is neither accounted to nor limited by the
    container. Instead the Runtime moves its own processes into a leaf and
    creates a sibling workers cgroup below its *own* cgroup:

        <runtime cgroup>/
            langbot-runtime/          Runtime processes
            langbot-plugin-workers/   nsjail NSJAIL.<pid> cgroups

    The workers cgroup is capped below the Runtime cgroup's ``memory.max`` so
    sandbox pressure triggers OOM inside the workers subtree instead of
    killing the Runtime itself. Returns ``None`` when delegation is
    impossible or would place sandboxes outside the Runtime's cgroup.
    """

    pid = os.getpid() if pid is None else pid
    try:
        relative = None
        for line in proc_self_cgroup.read_text().splitlines():
            if line.startswith("0::"):
                relative = line[3:].strip()
                break
        if relative is None:
            logger.warning("cgroup v2 unified hierarchy not found for the Runtime")
            return None

        runtime_cgroup = cgroup_root / relative.lstrip("/")
        if not (runtime_cgroup / "cgroup.procs").is_file():
            logger.warning(
                f"Runtime cgroup {relative!r} is not visible under {cgroup_root}; "
                "the mounted cgroup tree does not match the Runtime's cgroup "
                "namespace (do not bind-mount the host /sys/fs/cgroup)"
            )
            return None
        if not (runtime_cgroup / "memory.max").is_file():
            # Only the real host root cgroup lacks memory.max. Worker
            # sandboxes there would escape every container limit.
            logger.warning(
                "Runtime runs in the host root cgroup; refusing to create "
                "plugin worker cgroups outside a bounded parent"
            )
            return None
        procs = _read_cgroup_list(runtime_cgroup / "cgroup.procs")
        if str(pid) not in procs:
            leaf = runtime_cgroup / _RUNTIME_CGROUP_NAME
            if not (
                (leaf / "cgroup.procs").is_file()
                and str(pid) in _read_cgroup_list(leaf / "cgroup.procs")
            ):
                logger.warning(
                    f"Runtime process is not a member of {runtime_cgroup}; "
                    "the mounted cgroup tree does not match the Runtime's "
                    "cgroup namespace (do not bind-mount the host /sys/fs/cgroup)"
                )
                return None
            # Already delegated by an earlier launcher in this process.
            runtime_cgroup_is_leaf = False
        else:
            runtime_cgroup_is_leaf = True

        available = set(_read_cgroup_list(runtime_cgroup / "cgroup.controllers"))
        if not set(_CGROUP_V2_CONTROLLERS).issubset(available):
            logger.warning(
                f"cgroup v2 controllers {_CGROUP_V2_CONTROLLERS} are not all "
                f"delegated to {runtime_cgroup} (available: {sorted(available)})"
            )
            return None

        if runtime_cgroup_is_leaf:
            # cgroup v2 forbids enabling controllers for children while the
            # cgroup itself still holds processes.
            leaf = runtime_cgroup / _RUNTIME_CGROUP_NAME
            leaf.mkdir(exist_ok=True)
            for member in procs:
                try:
                    (leaf / "cgroup.procs").write_text(member)
                except ProcessLookupError:
                    continue
        _enable_cgroup_controllers(runtime_cgroup)

        workers = runtime_cgroup / _WORKERS_CGROUP_NAME
        workers.mkdir(exist_ok=True)
        _enable_cgroup_controllers(workers)

        parent_limit = (runtime_cgroup / "memory.max").read_text().strip()
        if parent_limit != "max":
            workers_limit = int(parent_limit) - _runtime_memory_reserve_bytes()
            if workers_limit > 0:
                (workers / "memory.max").write_text(str(workers_limit))
            else:
                logger.warning(
                    f"Runtime cgroup memory.max ({parent_limit}) leaves no room "
                    "after the Runtime reserve; workers share the Runtime limit"
                )
        else:
            logger.warning(
                f"Runtime cgroup {runtime_cgroup} has no memory.max; plugin "
                "workers have no aggregate memory limit"
            )
    except OSError as exc:
        logger.warning(f"cgroup v2 delegation for plugin workers failed: {exc}")
        return None

    logger.info(f"Plugin worker sandboxes use cgroup v2 parent {workers}")
    return workers
