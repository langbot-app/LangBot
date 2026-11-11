from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import io
import os
import pathlib
import sys
import zipfile

import pytest

from langbot_plugin.cli.commands.runplugin import should_load_artifact_dotenv
from langbot_plugin.entities.io.context import InstallationBinding, PluginWorkerPolicy
from langbot_plugin.runtime.plugin import worker_launcher as worker_launcher_module
from langbot_plugin.runtime.plugin.artifact import PluginArtifact, PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import (
    DependencyEnvironmentStaging,
    PluginDependencyEnvironment,
)
from langbot_plugin.runtime.plugin.worker_launcher import (
    PluginWorkerProcessController,
    PluginWorkerLauncher,
    PluginWorkerLaunchSpec,
)
from langbot_plugin.runtime.security import (
    PLUGIN_FILE_STORAGE_DIR_ENV,
    PLUGIN_REGISTRATION_CAPABILITY_ENV,
    PLUGIN_RUNTIME_PROFILE_ENV,
)


def _policy(*, require_hard_limits=True) -> PluginWorkerPolicy:
    return PluginWorkerPolicy(
        max_cpus=1.5,
        max_memory_mb=384,
        max_pids=73,
        max_open_files=211,
        max_file_size_mb=97,
        require_hard_limits=require_hard_limits,
    )


def _launch_spec(tmp_path) -> PluginWorkerLaunchSpec:
    package_io = io.BytesIO()
    with zipfile.ZipFile(package_io, "w") as archive:
        archive.writestr(
            "manifest.yaml",
            """
kind: Plugin
metadata:
  author: tester
  name: demo
  version: 1.0.0
spec:
  worker:
    max_cpus: 999
    max_memory_mb: 999999
""",
        )
    package = package_io.getvalue()
    digest = hashlib.sha256(package).hexdigest()
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest=digest,
    )
    store = PluginArtifactStore(tmp_path / "plugin-runtime")
    artifact = store.install_package(package, digest)
    dependency_root = tmp_path / "plugin-runtime" / "environment"
    dependency_path = dependency_root / "site-packages"
    dependency_path.mkdir(parents=True)
    return PluginWorkerLaunchSpec(
        binding=binding,
        artifact=artifact,
        paths=store.ensure_installation_paths(binding),
        registration_capability="capability-value",
        runtime_ws_url="ws://localhost:5401/plugin/ws",
        dependency_environment=PluginDependencyEnvironment(
            digest="b" * 64,
            artifact_digest=digest,
            requirements_digest="c" * 64,
            runtime_fingerprint="d" * 64,
            root_path=dependency_root,
            site_packages_path=dependency_path,
        ),
    )


def test_shared_launcher_maps_only_trusted_policy_to_nsjail(tmp_path):
    python_prefix = tmp_path / "runtime" / ".venv"
    python_executable = python_prefix / "bin" / "python"
    python_executable.parent.mkdir(parents=True)
    python_executable.touch()
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
        python_executable=str(python_executable),
        python_prefix=str(python_prefix),
        runtime_import_root=str(
            python_prefix
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        ),
    )
    launcher.configure(_policy(), "shared")

    args = launcher.build_nsjail_args(_launch_spec(tmp_path))

    assert args[args.index("--cgroup_mem_max") + 1] == str(384 * 1024 * 1024)
    assert args[args.index("--cgroup_mem_swap_max") + 1] == "0"
    assert args[args.index("--cgroup_pids_max") + 1] == "73"
    assert args[args.index("--cgroup_cpu_ms_per_sec") + 1] == "1500"
    assert args[args.index("--time_limit") + 1] == "0"
    assert args[args.index("--rlimit_nofile") + 1] == "211"
    assert args[args.index("--rlimit_fsize") + 1] == "97"
    assert "999" not in args
    assert "999999" not in args
    assert any(value.endswith(":/plugin") for value in args)
    assert any(value.endswith(":/plugin-dependencies") for value in args)
    assert any(value.endswith(":/home") for value in args)
    assert any(value.endswith(":/tmp") for value in args)
    assert any(value.endswith(":/data") for value in args)
    assert f"{python_prefix}:{python_prefix}" in args
    assert args[args.index("--") + 1] == str(python_executable)
    assert f"{PLUGIN_RUNTIME_PROFILE_ENV}=shared" in args
    assert f"{PLUGIN_REGISTRATION_CAPABILITY_ENV}=capability-value" in args
    runtime_site_packages = (
        python_prefix
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    assert f"PYTHONPATH={runtime_site_packages}:/plugin-dependencies" in args
    assert "PYTHONDONTWRITEBYTECODE=1" in args


def test_certified_shared_launcher_mounts_no_installation_writable_paths(tmp_path):
    python_prefix = tmp_path / "runtime" / ".venv"
    python_executable = python_prefix / "bin" / "python"
    python_executable.parent.mkdir(parents=True)
    python_executable.touch()
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
        python_executable=str(python_executable),
        python_prefix=str(python_prefix),
    )
    launcher.configure(_policy(), "shared")
    launch_spec = _launch_spec(tmp_path)

    args = launcher.build_shared_pool_nsjail_args(launch_spec)

    for private_path in (
        launch_spec.paths.home_path,
        launch_spec.paths.tmp_path,
        launch_spec.paths.data_path,
        launch_spec.paths.root_path / "rpc-transfer",
    ):
        assert not any(str(private_path) in value for value in args)
    assert "HOME=/tmp" in args
    assert "TMPDIR=/tmp" in args
    assert f"{PLUGIN_REGISTRATION_CAPABILITY_ENV}=capability-value" in args
    writable_targets = [
        value.split(":", 1)[-1]
        for index, value in enumerate(args)
        if index > 0 and args[index - 1] == "--bindmount"
    ]
    assert "/home" not in writable_targets
    assert "/data" not in writable_targets


def test_dependency_preparation_uses_isolated_writable_staging_only(tmp_path):
    python_prefix = tmp_path / "runtime" / ".venv"
    python_executable = python_prefix / "bin" / "python"
    python_executable.parent.mkdir(parents=True)
    python_executable.touch()
    staging_root = tmp_path / "staging"
    staging = DependencyEnvironmentStaging(
        root_path=staging_root,
        site_packages_path=staging_root / "site-packages",
        scratch_path=staging_root / ".scratch",
        jail_root_path=staging_root / ".scratch" / "root",
        tmp_path=staging_root / ".scratch" / "tmp",
    )
    staging.site_packages_path.mkdir(parents=True)
    staging.jail_root_path.mkdir(parents=True)
    staging.tmp_path.mkdir(parents=True)
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
        python_executable=str(python_executable),
        python_prefix=str(python_prefix),
    )
    launcher.configure(_policy(), "shared")

    args = launcher.build_dependency_prepare_nsjail_args(
        staging,
        ["third-party-demo==1.0.0"],
    )

    assert f"{staging.site_packages_path}:/dependency-env" in args
    assert f"{staging.tmp_path}:/tmp" in args
    assert "--ignore-installed" in args
    assert "--target" in args
    assert args[args.index("--target") + 1] == "/dependency-env"
    assert "-r" in args
    assert args[args.index("-r") + 1] == "/tmp/requirements.txt"
    assert (staging.tmp_path / "requirements.txt").read_text(encoding="utf-8") == (
        "third-party-demo==1.0.0\n"
    )
    assert "third-party-demo==1.0.0" not in args
    assert not any(value.endswith(":/plugin") for value in args)


def test_shared_launcher_absolutizes_runtime_paths_before_fixed_root_cwd(
    tmp_path,
    monkeypatch,
):
    runtime_cwd = tmp_path / "runtime-cwd"
    runtime_cwd.mkdir()
    monkeypatch.chdir(runtime_cwd)
    launch_spec = _launch_spec(pathlib.Path("state"))
    staging_root = pathlib.Path("dependency-staging")
    staging = DependencyEnvironmentStaging(
        root_path=staging_root,
        site_packages_path=staging_root / "site-packages",
        scratch_path=staging_root / ".scratch",
        jail_root_path=staging_root / ".scratch" / "root",
        tmp_path=staging_root / ".scratch" / "tmp",
    )
    staging.site_packages_path.mkdir(parents=True)
    staging.jail_root_path.mkdir(parents=True)
    staging.tmp_path.mkdir(parents=True)
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")

    controller = launcher.create_controller(launch_spec)
    dependency_args = launcher.build_dependency_prepare_nsjail_args(
        staging,
        ["third-party-demo==1.0.0"],
    )

    assert controller.working_dir == "/"
    assert not launch_spec.paths.jail_root_path.is_absolute()
    assert controller.args[controller.args.index("--chroot") + 1] == str(
        launch_spec.paths.jail_root_path.absolute()
    )
    assert f"{launch_spec.artifact.code_path.absolute()}:/plugin" in controller.args
    assert (
        f"{launch_spec.dependency_environment.site_packages_path.absolute()}"
        ":/plugin-dependencies"
    ) in controller.args
    for source, target in (
        (launch_spec.paths.home_path, "/home"),
        (launch_spec.paths.tmp_path, "/tmp"),
        (launch_spec.paths.data_path, "/data"),
    ):
        assert f"{source.absolute()}:{target}" in controller.args

    assert dependency_args[dependency_args.index("--chroot") + 1] == str(
        staging.jail_root_path.absolute()
    )
    assert f"{staging.site_packages_path.absolute()}:/dependency-env" in dependency_args
    assert f"{staging.tmp_path.absolute()}:/tmp" in dependency_args


def test_shared_pool_controller_transfers_process_lifetime_ownership(tmp_path):
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")

    controller = launcher.create_shared_pool_controller(_launch_spec(tmp_path))

    assert getattr(controller, "close_process_on_callback_return") is False
    # A shared pool's stderr mixes every attached tenant; never buffer it.
    assert controller.capture_stderr is False


def test_shared_launcher_fails_without_nsjail_or_required_cgroup():
    no_nsjail = PluginWorkerLauncher(
        nsjail_path="",
        cgroup_v2_available=True,
        platform="linux",
    )
    with pytest.raises(RuntimeError, match="require nsjail"):
        no_nsjail.configure(_policy(), "shared")

    no_cgroup = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=False,
        platform="linux",
    )
    with pytest.raises(RuntimeError, match="delegated cgroup v2"):
        no_cgroup.configure(_policy(require_hard_limits=True), "shared")


def test_shared_launcher_rejects_unmounted_python_executable(tmp_path):
    python_prefix = tmp_path / "runtime" / ".venv"
    python_prefix.mkdir(parents=True)
    python_executable = tmp_path / "other" / "python"
    python_executable.parent.mkdir()
    python_executable.touch()
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
        python_executable=str(python_executable),
        python_prefix=str(python_prefix),
    )

    with pytest.raises(RuntimeError, match="inside its mounted prefix"):
        launcher.configure(_policy(), "shared")


@pytest.mark.skipif(
    os.name == "nt",
    reason="Shared workers require Linux and Windows may not permit symlinks",
)
def test_shared_launcher_recreates_system_symlinks_instead_of_binding_them(
    tmp_path, monkeypatch
):
    host_root = tmp_path / "host"
    (host_root / "usr" / "bin").mkdir(parents=True)
    host_link = host_root / "bin"
    host_link.symlink_to("usr/bin")
    monkeypatch.setattr(
        worker_launcher_module, "_READONLY_SYSTEM_MOUNTS", (str(host_link),)
    )
    monkeypatch.setattr(worker_launcher_module, "_READONLY_ETC_FILES", ())

    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")
    launch_spec = _launch_spec(tmp_path / "state")
    args = launcher.build_nsjail_args(launch_spec)

    jail_link = launch_spec.paths.jail_root_path / str(host_link).lstrip("/")
    assert jail_link.is_symlink()
    assert jail_link.readlink() == host_link.readlink()
    assert f"{host_link}:{host_link}" not in args


def test_artifact_dotenv_is_disabled_only_for_shared_profile():
    assert should_load_artifact_dotenv("oss_dev") is True
    assert should_load_artifact_dotenv("") is True
    assert should_load_artifact_dotenv("shared") is False


def test_launcher_builds_profile_specific_controllers(tmp_path):
    shared = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    shared.configure(_policy(), "shared")
    launch_spec = _launch_spec(tmp_path)

    shared_controller = shared.create_controller(launch_spec)

    assert shared_controller.command == "/usr/bin/nsjail"
    assert shared_controller.env == {}
    assert shared_controller.working_dir == "/"
    assert "--chroot" in shared_controller.args
    assert shared_controller.capture_stderr is True

    oss = PluginWorkerLauncher(
        nsjail_path="",
        cgroup_v2_available=False,
        platform="darwin",
    )
    oss.configure(_policy(require_hard_limits=False), "oss_dev")

    oss_controller = oss.create_controller(launch_spec)

    assert oss_controller.command == sys.executable
    assert oss_controller.working_dir == str(launch_spec.artifact.code_path)
    assert oss_controller.capture_stderr is True
    runtime_import_root = (
        pathlib.Path(worker_launcher_module.__file__).resolve().parents[3]
    )
    assert oss_controller.env == {
        PLUGIN_FILE_STORAGE_DIR_ENV: str(launch_spec.paths.root_path / "rpc-transfer"),
        PLUGIN_REGISTRATION_CAPABILITY_ENV: "capability-value",
        PLUGIN_RUNTIME_PROFILE_ENV: "oss_dev",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join(
            (
                str(runtime_import_root),
                str(launch_spec.dependency_environment.site_packages_path.resolve()),
            )
        ),
        "PYTHONUNBUFFERED": "1",
    }


def test_oss_launcher_passes_absolute_rpc_storage_when_store_base_is_relative(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    store = PluginArtifactStore()
    binding = InstallationBinding(
        instance_uuid="instance-1",
        runtime_revision=1,
        artifact_digest="0" * 64,
        installation_uuid="installation-1",
        workspace_uuid="workspace-1",
        placement_generation=1,
    )
    paths = store.ensure_installation_paths(binding)
    artifact_code = tmp_path / "data/plugin-runtime/artifacts/sha256/digest/code"
    artifact_code.mkdir(parents=True)
    artifact = PluginArtifact(
        digest="0" * 64,
        root_path=artifact_code.parent,
        code_path=artifact_code,
        plugin_author="author",
        plugin_name="plugin",
        plugin_version="1.0.0",
    )
    original_spec = _launch_spec(tmp_path)
    dependency_environment = original_spec.dependency_environment
    assert dependency_environment is not None
    launch_spec = dataclasses.replace(
        original_spec,
        artifact=artifact,
        paths=paths,
        dependency_environment=dataclasses.replace(
            dependency_environment,
            artifact_digest=artifact.digest,
        ),
    )
    launcher = PluginWorkerLauncher(
        nsjail_path="",
        cgroup_v2_available=False,
        platform="linux",
    )
    launcher.configure(_policy(require_hard_limits=False), "oss_dev")

    controller = launcher.create_controller(launch_spec)
    storage_path = pathlib.Path(controller.env[PLUGIN_FILE_STORAGE_DIR_ENV])

    assert storage_path.is_absolute()
    assert storage_path == (paths.root_path / "rpc-transfer").resolve()


def test_windows_oss_worker_keeps_required_system_env_without_runtime_secrets(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("SYSTEMROOT", r"C:\Windows")
    monkeypatch.setenv("WINDIR", r"C:\Windows")
    monkeypatch.setenv("COMSPEC", r"C:\Windows\System32\cmd.exe")
    monkeypatch.setenv("PATH", r"C:\Windows\System32")
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT")
    monkeypatch.setenv("LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN", "control-secret")
    monkeypatch.setenv("LANGBOT_BOX_CONTROL_TOKEN", "box-secret")
    launcher = PluginWorkerLauncher(
        cgroup_v2_available=False,
        platform="win32",
    )
    launcher.configure(_policy(require_hard_limits=False), "oss_dev")

    controller = launcher.create_controller(_launch_spec(tmp_path))

    assert controller.env["SYSTEMROOT"] == r"C:\Windows"
    assert controller.env["WINDIR"] == r"C:\Windows"
    assert controller.env["COMSPEC"] == r"C:\Windows\System32\cmd.exe"
    assert controller.env["PATH"] == r"C:\Windows\System32"
    assert controller.env["PATHEXT"] == ".COM;.EXE;.BAT"
    assert controller.env["RUNTIME_WS_URL"] == "ws://localhost:5401/plugin/ws"
    assert controller.env["PYTHONUTF8"] == "1"
    assert controller.env["PYTHONIOENCODING"] == "utf-8"
    assert "-s" not in controller.args
    assert "LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN" not in controller.env
    assert "LANGBOT_BOX_CONTROL_TOKEN" not in controller.env


async def test_windows_oss_worker_controller_reaps_process_when_cancelled(
    tmp_path,
    monkeypatch,
):
    launcher = PluginWorkerLauncher(
        cgroup_v2_available=False,
        platform="win32",
    )
    launcher.configure(_policy(require_hard_limits=False), "oss_dev")
    controller = launcher.create_controller(_launch_spec(tmp_path))
    assert isinstance(controller, PluginWorkerProcessController)
    wait_started = asyncio.Event()
    stop_calls = []
    callback_called = False

    class FakeProcess:
        returncode = None

        async def wait(self):
            wait_started.set()
            await asyncio.Future()

    process = FakeProcess()

    async def create_subprocess_exec(*args, **kwargs):
        assert args == (controller.command, *controller.args)
        assert kwargs == {
            "env": controller.env,
            "cwd": controller.working_dir,
            "stdout": sys.stderr,
        }
        return process

    async def stop_process(owned_process):
        stop_calls.append(owned_process)
        owned_process.returncode = 0
        return True

    async def callback(connection):
        nonlocal callback_called
        callback_called = True

    monkeypatch.setattr(
        worker_launcher_module.asyncio,
        "create_subprocess_exec",
        create_subprocess_exec,
    )
    monkeypatch.setattr(
        worker_launcher_module.stdio_client_controller,
        "stop_process",
        stop_process,
    )

    task = asyncio.create_task(controller.run(callback))
    await wait_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert controller.process is process
    assert stop_calls == [process]
    assert callback_called is False


async def test_prepare_dependency_environment_selects_profile_installer(
    tmp_path,
):
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")
    launch_spec = _launch_spec(tmp_path)
    captured = {}

    class FakeStore:
        async def prepare(
            self,
            artifact,
            *,
            runtime_fingerprint,
            installer,
            execution_mode=None,
        ):
            captured.update(
                artifact=artifact,
                runtime_fingerprint=runtime_fingerprint,
                installer=installer,
            )
            return launch_spec.dependency_environment

    result = await launcher.prepare_dependency_environment(
        FakeStore(),
        launch_spec.artifact,
    )

    assert result is launch_spec.dependency_environment
    assert captured["artifact"] is launch_spec.artifact
    assert len(captured["runtime_fingerprint"]) == 64
    assert captured["installer"] == launcher._install_dependency_environment
    shared_fingerprint = captured["runtime_fingerprint"]

    oss = PluginWorkerLauncher(
        cgroup_v2_available=False,
        platform="darwin",
    )
    oss.configure(_policy(require_hard_limits=False), "oss_dev")
    oss_result = await oss.prepare_dependency_environment(
        FakeStore(),
        launch_spec.artifact,
    )

    assert oss_result is launch_spec.dependency_environment
    assert captured["installer"] == oss._install_dependency_environment_direct
    assert captured["runtime_fingerprint"] != shared_fingerprint


async def test_oss_dependency_installer_targets_environment_without_control_secrets(
    tmp_path,
    monkeypatch,
):
    staging_root = tmp_path / "staging"
    staging = DependencyEnvironmentStaging(
        root_path=staging_root,
        site_packages_path=staging_root / "site-packages",
        scratch_path=staging_root / ".scratch",
        jail_root_path=staging_root / ".scratch" / "root",
        tmp_path=staging_root / ".scratch" / "tmp",
    )
    staging.site_packages_path.mkdir(parents=True)
    staging.tmp_path.mkdir(parents=True)
    launcher = PluginWorkerLauncher(
        cgroup_v2_available=False,
        platform="win32",
    )
    launcher.configure(_policy(require_hard_limits=False), "oss_dev")
    monkeypatch.setenv("LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN", "control-secret")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid")

    class FakeProcess:
        returncode = 0
        waited = False

        async def wait(self):
            self.waited = True
            return self.returncode

    process = FakeProcess()
    captured = {}

    async def create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return process

    monkeypatch.setattr(
        worker_launcher_module.asyncio,
        "create_subprocess_exec",
        create_subprocess_exec,
    )

    await launcher._install_dependency_environment_direct(
        staging,
        ["private-package==1.0.0"],
    )

    args = captured["args"]
    kwargs = captured["kwargs"]
    assert process.waited is True
    assert args[0] == sys.executable
    assert args[args.index("--target") + 1] == str(
        staging.site_packages_path.absolute()
    )
    assert args[args.index("-r") + 1] == str(
        (staging.tmp_path / "requirements.txt").absolute()
    )
    assert "private-package==1.0.0" not in args
    assert (staging.tmp_path / "requirements.txt").read_text(encoding="utf-8") == (
        "private-package==1.0.0\n"
    )
    assert kwargs["cwd"] == str(staging.tmp_path.absolute())
    assert kwargs["env"]["HTTPS_PROXY"] == "http://proxy.invalid"
    assert "LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN" not in kwargs["env"]
    assert kwargs["env"]["HOME"] == str(staging.tmp_path.absolute())


@pytest.mark.parametrize("returncode", [0, 7])
async def test_dependency_installer_reaps_nsjail_and_redacts_failures(
    tmp_path,
    monkeypatch,
    returncode,
):
    staging_root = tmp_path / "staging"
    staging = DependencyEnvironmentStaging(
        root_path=staging_root,
        site_packages_path=staging_root / "site-packages",
        scratch_path=staging_root / ".scratch",
        jail_root_path=staging_root / ".scratch" / "root",
        tmp_path=staging_root / ".scratch" / "tmp",
    )
    staging.site_packages_path.mkdir(parents=True)
    staging.jail_root_path.mkdir(parents=True)
    staging.tmp_path.mkdir(parents=True)
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")

    class FakeProcess:
        def __init__(self):
            self.returncode = returncode
            self.waited = False

        async def wait(self):
            self.waited = True
            return self.returncode

    process = FakeProcess()
    captured = {}

    async def create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return process

    monkeypatch.setattr(
        worker_launcher_module.asyncio,
        "create_subprocess_exec",
        create_subprocess_exec,
    )

    if returncode:
        with pytest.raises(
            worker_launcher_module.DependencyEnvironmentPreparationError,
            match="exited with code 7",
        ) as exc_info:
            await launcher._install_dependency_environment(
                staging,
                ["private-package==1.0.0"],
            )
        assert "private-package==1.0.0" not in str(exc_info.value)
    else:
        await launcher._install_dependency_environment(
            staging,
            ["private-package==1.0.0"],
        )

    assert process.waited is True
    assert captured["args"][0] == "/usr/bin/nsjail"
    assert captured["kwargs"]["env"] == {}


async def test_dependency_installer_kills_timed_out_nsjail(
    tmp_path,
    monkeypatch,
):
    staging_root = tmp_path / "staging"
    staging = DependencyEnvironmentStaging(
        root_path=staging_root,
        site_packages_path=staging_root / "site-packages",
        scratch_path=staging_root / ".scratch",
        jail_root_path=staging_root / ".scratch" / "root",
        tmp_path=staging_root / ".scratch" / "tmp",
    )
    staging.site_packages_path.mkdir(parents=True)
    staging.jail_root_path.mkdir(parents=True)
    staging.tmp_path.mkdir(parents=True)
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")

    class TimeoutProcess:
        def __init__(self):
            self.returncode = None
            self.wait_calls = 0
            self.killed = False

        async def wait(self):
            self.wait_calls += 1
            if self.wait_calls == 1:
                await asyncio.Event().wait()
            self.returncode = -9
            return self.returncode

        def kill(self):
            self.killed = True

    process = TimeoutProcess()

    async def create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(
        worker_launcher_module.asyncio,
        "create_subprocess_exec",
        create_subprocess_exec,
    )
    monkeypatch.setattr(
        worker_launcher_module,
        "_DEPENDENCY_INSTALL_TIMEOUT_SECONDS",
        0.001,
    )

    with pytest.raises(
        worker_launcher_module.DependencyEnvironmentPreparationError,
        match="timed out",
    ):
        await launcher._install_dependency_environment(
            staging,
            ["private-package==1.0.0"],
        )

    assert process.killed is True
    assert process.wait_calls == 2


async def test_dependency_installer_cancellation_kills_and_reaps_nsjail(
    tmp_path,
    monkeypatch,
):
    staging_root = tmp_path / "staging"
    staging = DependencyEnvironmentStaging(
        root_path=staging_root,
        site_packages_path=staging_root / "site-packages",
        scratch_path=staging_root / ".scratch",
        jail_root_path=staging_root / ".scratch" / "root",
        tmp_path=staging_root / ".scratch" / "tmp",
    )
    staging.site_packages_path.mkdir(parents=True)
    staging.jail_root_path.mkdir(parents=True)
    staging.tmp_path.mkdir(parents=True)
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")

    class HangingProcess:
        def __init__(self):
            self.returncode = None
            self.wait_started = asyncio.Event()
            self.exit_requested = asyncio.Event()
            self.killed = False

        async def wait(self):
            self.wait_started.set()
            await self.exit_requested.wait()
            self.returncode = -9
            return self.returncode

        def kill(self):
            self.killed = True
            self.exit_requested.set()

    process = HangingProcess()

    async def create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(
        worker_launcher_module.asyncio,
        "create_subprocess_exec",
        create_subprocess_exec,
    )
    task = asyncio.create_task(
        launcher._install_dependency_environment(
            staging,
            ["private-package==1.0.0"],
        )
    )
    await process.wait_started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert process.killed is True
    assert process.returncode == -9


async def test_dependency_installer_skips_empty_requirements(tmp_path, monkeypatch):
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")
    create_process = pytest.fail
    monkeypatch.setattr(
        worker_launcher_module.asyncio,
        "create_subprocess_exec",
        create_process,
    )

    await launcher._install_dependency_environment(
        DependencyEnvironmentStaging(
            root_path=tmp_path,
            site_packages_path=tmp_path / "site-packages",
            scratch_path=tmp_path / ".scratch",
            jail_root_path=tmp_path / ".scratch" / "root",
            tmp_path=tmp_path / ".scratch" / "tmp",
        ),
        [],
    )


def test_launcher_configuration_is_required_immutable_and_platform_fenced(tmp_path):
    launch_spec = _launch_spec(tmp_path)
    unconfigured = PluginWorkerLauncher(
        cgroup_v2_available=False,
        platform="darwin",
    )
    with pytest.raises(RuntimeError, match="not configured"):
        unconfigured.create_controller(launch_spec)

    policy = _policy(require_hard_limits=False)
    unconfigured.configure(policy, "oss_dev")
    assert unconfigured.cgroup_v2_available is False
    with pytest.raises(ValueError, match="policy cannot be changed"):
        unconfigured.configure(
            policy.model_copy(update={"max_memory_mb": 1024}),
            "oss_dev",
        )
    with pytest.raises(ValueError, match="profile cannot be changed"):
        unconfigured.configure(policy, "shared")

    non_linux = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="darwin",
    )
    with pytest.raises(RuntimeError, match="require Linux"):
        non_linux.configure(_policy(), "shared")


def test_windows_shared_profile_executes_per_plugin_workers(tmp_path):
    """Windows cannot isolate workers with nsjail, so the launcher degrades.

    The shared *authorization* contract is unchanged (the launcher keeps
    reporting the requested profile); only the execution mechanism falls back
    to per-plugin workers, which is what the surrounding runtime expects on a
    development host.
    """

    if sys.platform != "win32":
        pytest.skip("Windows-only development fallback")

    launcher = PluginWorkerLauncher(
        platform="win32",
        cgroup_v2_available=False,
    )
    launcher.configure(_policy(), "shared")

    assert launcher.runtime_profile == "shared"
    assert launcher._require_configuration()[1] == "oss_dev"


def test_linux_shared_profile_keeps_hard_limit_fence():
    """The production fence must survive future platform relaxations."""

    if sys.platform != "linux":
        pytest.skip("Linux-only production fence")

    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=False,
        platform="linux",
    )
    with pytest.raises(RuntimeError, match="require delegated cgroup v2"):
        launcher.configure(_policy(), "shared")


def test_shared_pool_worker_mounts_a_writable_tmp(tmp_path):
    """Pool workers strip installation mounts, so /tmp must stay writable.

    The shared worker handler creates its transfer root under /tmp
    (SHARED_WORKER_FILE_STORAGE_DIR), while nsjail mounts the chroot read-only
    unless the launch asks for a writable mount point.
    """

    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")

    args = launcher.build_shared_pool_nsjail_args(_launch_spec(tmp_path))

    tmpfs_index = args.index("--tmpfsmount")
    assert args[tmpfs_index + 1] == "/tmp"
    # nsjail options must precede the command separator, otherwise they land in
    # the worker argv instead of the sandbox configuration.
    assert tmpfs_index < args.index("--")


def test_shared_pool_worker_carries_the_plugin_process_tag(tmp_path):
    """ps/htop must show which plugin a sandboxed worker belongs to."""

    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
    )
    launcher.configure(_policy(), "shared")

    args = launcher.build_shared_pool_nsjail_args(_launch_spec(tmp_path))

    tag_index = args.index("--tag")
    assert args[tag_index + 1] == "tester/demo"
    # The worker command ends with the production flag.
    assert args.index("--prod") == tag_index + 2


def test_oss_worker_carries_the_plugin_process_tag(tmp_path):
    launcher = PluginWorkerLauncher(
        nsjail_path="",
        cgroup_v2_available=False,
        platform="darwin",
    )
    launcher.configure(_policy(require_hard_limits=False), "oss_dev")

    controller = launcher.create_controller(_launch_spec(tmp_path))

    assert controller.args == [
        "-m",
        "langbot_plugin.cli.__init__",
        "run",
        "--tag",
        "tester/demo",
        "-s",
        "--prod",
    ]


def test_shared_launcher_binds_resolver_symlink_target_without_exposing_run(
    tmp_path, monkeypatch
):
    resolver = tmp_path / "run" / "resolv.conf"
    resolver.parent.mkdir()
    resolver.write_text("nameserver 1.1.1.1\n")
    link = tmp_path / "etc" / "resolv.conf"
    link.parent.mkdir()
    link.symlink_to(resolver)
    monkeypatch.setattr(worker_launcher_module, "_READONLY_ETC_FILES", (str(link),))
    monkeypatch.setattr(worker_launcher_module, "_READONLY_SYSTEM_MOUNTS", ())
    root = tmp_path / "jail"
    launcher = PluginWorkerLauncher()
    launcher._ensure_jail_mount_targets(root)
    target = root / str(link).lstrip("/")
    assert target.is_file() and not target.is_symlink()
    args = []
    launcher._append_readonly_runtime_mounts(args, None)
    assert args == ["--bindmount_ro", f"{resolver}:{link}"]
    assert not (root / str(resolver).lstrip("/")).exists()
    # Existing roots from before the fix must also replace dangling links.
    target.unlink()
    target.symlink_to("/run/missing-resolv.conf")
    launcher._ensure_jail_mount_targets(root)
    assert target.is_file() and not target.is_symlink()


def test_shared_launcher_mounts_editable_sdk_source_readonly(tmp_path):
    prefix = tmp_path / "venv"
    executable = prefix / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.touch()
    source = tmp_path / "sdk" / "src"
    source.mkdir(parents=True)
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        cgroup_v2_available=True,
        platform="linux",
        python_executable=str(executable),
        python_prefix=str(prefix),
        runtime_import_root=str(source),
    )
    launcher.configure(_policy(), "shared")
    spec = _launch_spec(tmp_path)
    args = launcher.build_nsjail_args(spec)
    mount = f"{source}:{source}"
    assert args[args.index(mount) - 1] == "--bindmount_ro"
    assert (spec.paths.jail_root_path / str(source).lstrip("/")).is_dir()
    assert f"{source.parent}:{source.parent}" not in args
    assert f"PYTHONPATH={source}:/plugin-dependencies" in args


def _fake_cgroup_tree(
    tmp_path: pathlib.Path,
    *,
    relative: str = "/kubepods/pod1/ctr",
    procs: str = "1\n42\n",
    memory_max: str | None = "12884901888",
    controllers: str = "cpuset cpu io memory pids",
) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    root = tmp_path / "cgroup"
    runtime = root / relative.lstrip("/")
    runtime.mkdir(parents=True)
    (runtime / "cgroup.procs").write_text(procs)
    (runtime / "cgroup.controllers").write_text(controllers)
    (runtime / "cgroup.subtree_control").write_text("")
    if memory_max is not None:
        (runtime / "memory.max").write_text(memory_max + "\n")
    # The kernel populates interface files when a child cgroup is created;
    # pre-create them because the fake tree is a plain directory.
    for child in ("langbot-runtime", "langbot-plugin-workers"):
        (runtime / child).mkdir()
        (runtime / child / "cgroup.procs").write_text("")
        (runtime / child / "cgroup.subtree_control").write_text("")
    proc_self = tmp_path / "proc-self-cgroup"
    proc_self.write_text(f"0::{relative}\n")
    return root, runtime, proc_self


def _prepare(root, proc_self, pid=42):
    return worker_launcher_module.prepare_worker_cgroup_v2_parent(
        cgroup_root=root, proc_self_cgroup=proc_self, pid=pid
    )


def test_worker_cgroup_parent_is_nested_under_runtime_cgroup(tmp_path, monkeypatch):
    monkeypatch.delenv(
        worker_launcher_module.RUNTIME_MEMORY_RESERVE_MB_ENV, raising=False
    )
    root, runtime, proc_self = _fake_cgroup_tree(tmp_path)

    workers = _prepare(root, proc_self)

    assert workers == runtime / "langbot-plugin-workers"
    # Runtime processes are evacuated into a leaf so controllers can be
    # delegated to the sibling workers subtree.
    assert (runtime / "langbot-runtime" / "cgroup.procs").exists()
    assert (runtime / "cgroup.subtree_control").read_text() == "+cpu +memory +pids"
    assert (workers / "cgroup.subtree_control").read_text() == "+cpu +memory +pids"
    assert int((workers / "memory.max").read_text()) == 12884901888 - 2048 * 1024 * 1024


def test_worker_cgroup_parent_honours_runtime_reserve_env(tmp_path, monkeypatch):
    monkeypatch.setenv(worker_launcher_module.RUNTIME_MEMORY_RESERVE_MB_ENV, "1024")
    root, runtime, proc_self = _fake_cgroup_tree(tmp_path, memory_max="4294967296")

    workers = _prepare(root, proc_self)

    assert int((workers / "memory.max").read_text()) == 3 * 1024 * 1024 * 1024


def test_worker_cgroup_parent_works_in_private_cgroup_namespace(tmp_path):
    root, runtime, proc_self = _fake_cgroup_tree(tmp_path, relative="/")

    assert _prepare(root, proc_self) == root / "langbot-plugin-workers"


def test_worker_cgroup_parent_rejects_host_root_cgroup(tmp_path):
    # The incident shape: host /sys/fs/cgroup mounted, Runtime sees "0::/"
    # from a private namespace, so the mount root is the host root cgroup.
    root, _, proc_self = _fake_cgroup_tree(tmp_path, relative="/", memory_max=None)

    assert _prepare(root, proc_self) is None
    assert (
        root / "langbot-plugin-workers" / "cgroup.subtree_control"
    ).read_text() == ""


def test_worker_cgroup_parent_rejects_mismatched_cgroup_namespace(tmp_path):
    root, _, proc_self = _fake_cgroup_tree(tmp_path, relative="/", procs="1\n7\n")

    assert _prepare(root, proc_self) is None
    assert (
        root / "langbot-plugin-workers" / "cgroup.subtree_control"
    ).read_text() == ""


def test_worker_cgroup_parent_requires_delegated_controllers(tmp_path):
    root, _, proc_self = _fake_cgroup_tree(tmp_path, controllers="cpu pids")

    assert _prepare(root, proc_self) is None


def test_shared_launcher_passes_worker_cgroup_parent_to_nsjail(tmp_path, monkeypatch):
    python_prefix = tmp_path / "runtime" / ".venv"
    python_executable = python_prefix / "bin" / "python"
    python_executable.parent.mkdir(parents=True)
    python_executable.touch()
    workers = tmp_path / "cgroup" / "langbot-plugin-workers"
    monkeypatch.setattr(
        worker_launcher_module,
        "prepare_worker_cgroup_v2_parent",
        lambda: workers,
    )
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail",
        platform="linux",
        python_executable=str(python_executable),
        python_prefix=str(python_prefix),
    )
    launcher.configure(_policy(require_hard_limits=True), "shared")

    args = launcher.build_nsjail_args(_launch_spec(tmp_path))

    assert launcher.cgroup_v2_available is True
    index = args.index("--cgroupv2_mount")
    assert args[index + 1] == str(workers)
    assert "--use_cgroupv2" in args


def test_shared_launcher_fails_closed_without_worker_cgroup_parent(monkeypatch):
    monkeypatch.setattr(
        worker_launcher_module, "prepare_worker_cgroup_v2_parent", lambda: None
    )
    launcher = PluginWorkerLauncher(nsjail_path="/usr/bin/nsjail", platform="linux")

    with pytest.raises(RuntimeError, match="delegated cgroup v2"):
        launcher.configure(_policy(require_hard_limits=True), "shared")
