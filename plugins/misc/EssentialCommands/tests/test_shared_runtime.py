"""Two installations drive one EssentialCommands object graph under shared-runtime-v1.

There is no full SDK worker harness for misc plugins, so this drives the real
``bind_invocation`` + ``InstallationBinding`` envelope against one process-wide
plugin object and its real command components (the objects the shared runtime
reuses for every installation).

Assertions that fail on the pre-fix revision 0.1.9 (each was executed against it):

* ``test_two_installations_render_their_own_language_from_one_object_graph`` --
  the old ``initialize()`` copied ``self.config`` (empty under shared placement)
  into ``self.language``, so installation B rendered English:
  ``["Session reset"]`` instead of ``["会话已重置"]``; ``vars(plugin)`` also held
  the captured ``language`` key.
* ``test_component_modules_do_not_mutate_sys_path_per_import`` -- every command
  module ran ``sys.path.insert(...)`` at import time, so importing the six
  command modules added six duplicate plugin-root entries (the package
  initializer now performs the single guarded insertion).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
from langbot_plugin.api.entities.builtin.command.context import ExecuteContext
from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes, Session
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from components.commands.help import Help  # noqa: E402
from components.commands.reset import Reset  # noqa: E402
from main import EssentialCommands  # noqa: E402

# Per-installation settings as the Host persists them.
CONFIGS = {"a": {"language": "en_US"}, "b": {"language": "zh_Hans"}}

EXPECTED = {
    "a": {"reset": "Session reset", "help_title": "LangBot - Production-grade IM bot development platform"},
    "b": {"reset": "会话已重置", "help_title": "LangBot - 生产级 IM 机器人开发平台"},
}


def _binding(
    installation: str,
    *,
    workspace: str | None = None,
    instance: str = "instance-1",
    revision: int = 1,
) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid=instance,
        workspace_uuid=workspace or f"workspace-{installation}",
        installation_uuid=f"installation-{installation}",
        runtime_revision=revision,
        artifact_digest="a" * 64,
    )


def _shared_plugin(handler) -> EssentialCommands:
    """One process-wide plugin object, as the shared worker builds it."""
    plugin = EssentialCommands()
    plugin.plugin_runtime_handler = handler
    plugin.config = {}  # ATTACH binds an empty config for the shared object graph
    return plugin


def _context(command: str) -> ExecuteContext:
    return ExecuteContext(
        query_id=1,
        session=Session(launcher_type=LauncherTypes.PERSON, launcher_id="10001"),
        command_text=command,
        full_command_text=f"!{command}",
        command=command,
        crt_command=command,
        params=[],
        crt_params=[],
        privilege=0,
    )


async def _render(component, command: str) -> list[str]:
    return [ret.text async for ret in component._execute(_context(command))]


def test_two_installations_render_their_own_language_from_one_object_graph():
    async def scenario():
        handler = SimpleNamespace()
        plugin = _shared_plugin(handler)
        await plugin.initialize()  # process-scoped; must capture no tenant language
        reset, help_cmd = Reset(), Help()
        for component in (reset, help_cmd):
            component.plugin = plugin
            await component.initialize()

        rendered = {}
        for owner in ("a", "b"):
            with bind_invocation(handler, config=CONFIGS[owner], binding=_binding(owner)):
                rendered[owner] = {
                    "reset": (await _render(reset, "reset"))[0],
                    "help_title": (await _render(help_cmd, "help"))[0].splitlines()[0],
                }
        return plugin, rendered

    plugin, rendered = asyncio.run(scenario())

    assert rendered["a"] == EXPECTED["a"]
    assert rendered["b"] == EXPECTED["b"]
    # Nothing tenant-scoped was captured on the shared plugin object.
    assert set(vars(plugin)) == {"_legacy_config", "plugin_runtime_handler"}


def test_component_modules_do_not_mutate_sys_path_per_import():
    code = textwrap.dedent(
        f"""
        import json
        import sys

        root = {str(PLUGIN_ROOT)!r}
        before = sum(1 for entry in sys.path if entry == root)

        import components.commands.cmd
        import components.commands.func
        import components.commands.help
        import components.commands.plugin
        import components.commands.reset
        import components.commands.version

        from i18n import get_text

        after = sum(1 for entry in sys.path if entry == root)
        print(json.dumps({{"before": before, "after": after,
                           "reset": get_text("zh_Hans", "reset.success")}}))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PLUGIN_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    observed = json.loads(result.stdout.strip().splitlines()[-1])
    # Exactly the package initializer may add the plugin root; the six command
    # modules used to add one entry each.
    assert observed["after"] - observed["before"] <= 1
    assert observed["after"] >= 1
    assert observed["reset"] == "会话已重置"


def test_dedicated_worker_config_is_still_honoured_without_a_binding():
    """Dedicated placement has no installation binding: the instance config applies."""
    handler = SimpleNamespace()
    plugin = EssentialCommands()
    plugin.plugin_runtime_handler = handler
    plugin.config = {"language": "zh_Hans"}

    assert plugin.get_language() == "zh_Hans"

    with bind_invocation(handler, config={"language": "en_US"}, binding=_binding("a")):
        assert plugin.get_language() == "en_US"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
