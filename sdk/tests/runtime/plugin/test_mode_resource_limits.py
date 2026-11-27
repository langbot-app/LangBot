import pytest

from langbot_plugin.entities.io.context import PluginWorkerPolicy
from langbot_plugin.runtime.plugin.worker_launcher import PluginWorkerLauncher
from tests.runtime.plugin.test_worker_launcher import _launch_spec, _policy


def split_policy():
    data = _policy().model_dump()
    data.update(
        dedicated={"max_cpus": 0.5, "max_memory_mb": 256},
        shared={"max_cpus": 1.0, "max_memory_mb": 512},
    )
    return PluginWorkerPolicy.model_validate(data)


def test_cloud_worker_modes_get_distinct_hard_limits(tmp_path):
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail", cgroup_v2_available=True, platform="linux"
    )
    launcher.configure(split_policy(), "shared")
    spec = _launch_spec(tmp_path)
    for args, cpu, memory in [
        (launcher.build_nsjail_args(spec), "500", 256),
        (launcher.build_shared_pool_nsjail_args(spec), "1000", 512),
    ]:
        assert args[args.index("--cgroup_cpu_ms_per_sec") + 1] == cpu
        assert args[args.index("--cgroup_mem_max") + 1] == str(memory * 1024 * 1024)
        assert args[args.index("--cgroup_pids_max") + 1] == "73"


def test_oss_policy_resolution_ignores_cloud_overrides():
    policy = split_policy()
    for mode in ("dedicated", "shared-runtime-v1"):
        resolved = policy.for_execution_mode(mode, "oss_dev")
        assert resolved.max_cpus == 1.5
        assert resolved.max_memory_mb == 384
    assert policy.effective_worker_capacity == _policy().effective_worker_capacity


@pytest.mark.parametrize("value", [0, -1, True, "1", float("inf"), float("nan")])
def test_mode_cpu_overrides_are_strict(value):
    data = _policy().model_dump()
    data["shared"] = {"max_cpus": value}
    with pytest.raises(ValueError):
        PluginWorkerPolicy.model_validate(data)


def test_legacy_cloud_policy_is_unchanged(tmp_path):
    launcher = PluginWorkerLauncher(
        nsjail_path="/usr/bin/nsjail", cgroup_v2_available=True, platform="linux"
    )
    launcher.configure(_policy(), "shared")
    spec = _launch_spec(tmp_path)
    for args in (
        launcher.build_nsjail_args(spec),
        launcher.build_shared_pool_nsjail_args(spec),
    ):
        assert args[args.index("--cgroup_cpu_ms_per_sec") + 1] == "1500"
        assert args[args.index("--cgroup_mem_max") + 1] == str(384 * 1024 * 1024)
