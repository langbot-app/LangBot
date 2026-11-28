"""Managed upgrades must not execute or display the legacy copy as well."""

from types import SimpleNamespace

import pytest

from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.runtime.context import RuntimeContext
from langbot_plugin.runtime.plugin.mgr import PluginManager


def binding(**overrides):
    data = dict(
        instance_uuid="instance",
        workspace_uuid="workspace",
        placement_generation=1,
        installation_uuid="bridge",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    data.update(overrides)
    return InstallationBinding(**data)


def make_manager(managed_binding, *, enabled=True):
    context = RuntimeContext()
    context.ws_debug_port = 18080
    context.control_handler = SimpleNamespace(current_action_context=binding())
    manager = PluginManager(context)
    old = SimpleNamespace(
        manifest=SimpleNamespace(metadata=SimpleNamespace(author="team", name="plugin"))
    )
    unrelated = SimpleNamespace(
        manifest=SimpleNamespace(metadata=SimpleNamespace(author="team", name="other"))
    )
    manager.plugins = [old, unrelated]
    manager._installations[managed_binding] = SimpleNamespace(
        binding=managed_binding,
        enabled=enabled,
        plugin_container=None,
        artifact=SimpleNamespace(plugin_author="team", plugin_name="plugin"),
    )
    return manager, old, unrelated


@pytest.mark.parametrize("enabled", [True, False])
def test_managed_installation_suppresses_legacy_copy_even_before_ready(enabled):
    manager, old, unrelated = make_manager(
        binding(installation_uuid="managed"), enabled=enabled
    )
    assert manager.plugins_for_current_scope() == [unrelated]
    # Targeted managed scope must not silently fall back to the stale worker.
    manager.context.control_handler.current_action_context = binding(
        installation_uuid="managed"
    )
    assert manager.plugins_for_current_scope() == []


@pytest.mark.parametrize(
    "other_scope",
    [
        dict(instance_uuid="other"),
        dict(workspace_uuid="other"),
        dict(placement_generation=2),
    ],
)
def test_managed_installation_does_not_shadow_another_scope(other_scope):
    manager, old, unrelated = make_manager(
        binding(installation_uuid="managed", **other_scope)
    )
    assert manager.plugins_for_current_scope() == [old, unrelated]


def test_removing_managed_installation_restores_legacy_visibility():
    manager, old, unrelated = make_manager(binding(installation_uuid="managed"))
    manager._installations.clear()
    assert manager.plugins_for_current_scope() == [old, unrelated]
