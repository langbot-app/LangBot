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

from components.commands.cmd import Cmd  # noqa: E402
from components.commands.func import Func  # noqa: E402
from components.commands.help import Help  # noqa: E402
from components.commands.plugin import Plugin  # noqa: E402
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


def test_func_command_supports_flat_tools_and_mcp_builtin_tools():
    handler = SimpleNamespace()
    plugin = _shared_plugin(handler)
    asyncio.run(plugin.initialize())

    func = Func()
    func.plugin = plugin
    asyncio.run(func.initialize())

    mock_tools = [
        # 1. Plugin tool with flat structure
        {
            "name": "get_weather_alerts",
            "label": {"en_US": "GetWeatherAlerts", "zh_Hans": "GetWeatherAlerts"},
            "description": {
                "en_US": "Get weather alerts for a US state.",
                "zh_Hans": "获取美国某个州的天气预警",
            },
            "icon": None,
            "spec": {
                "parameters": {"type": "object"},
                "llm_prompt": "Get weather alerts for a US state.",
            },
        },
        # 2. Builtin / sandbox tool
        {
            "name": "exec",
            "description": "Run shell commands in an isolated execution environment.",
            "human_desc": "Execute a command in an isolated environment",
            "parameters": {},
            "source": "builtin",
            "source_name": "LangBot",
        },
        # 3. MCP tool with only name / source / source_id
        {
            "name": "mcp_custom_tool",
            "source": "mcp",
            "source_id": "mcp-server-uuid",
        },
        # 4. Legacy nested manifest tool
        {
            "manifest": {
                "metadata": {
                    "name": "legacy_tool",
                    "description": {
                        "en_US": "Legacy tool description",
                        "zh_Hans": "旧工具描述",
                    },
                },
                "spec": {
                    "llm_prompt": "Legacy prompt",
                },
            }
        },
    ]

    async def mock_list_tools():
        return mock_tools

    plugin.list_tools = mock_list_tools

    # Test under zh_Hans
    with bind_invocation(handler, config={"language": "zh_Hans"}, binding=_binding("b")):
        output_zh = asyncio.run(_render(func, "func"))[0]
        assert "可用的 LLM 工具:" in output_zh
        assert "get_weather_alerts - 获取美国某个州的天气预警" in output_zh
        assert "提示词: Get weather alerts for a US state." in output_zh
        assert "exec - Run shell commands in an isolated execution environment." in output_zh
        assert "mcp_custom_tool -" in output_zh
        assert "legacy_tool - 旧工具描述" in output_zh
        assert "提示词: Legacy prompt" in output_zh

    # Test under en_US
    with bind_invocation(handler, config={"language": "en_US"}, binding=_binding("a")):
        output_en = asyncio.run(_render(func, "func"))[0]
        assert "Available LLM Tools:" in output_en
        assert "get_weather_alerts - Get weather alerts for a US state." in output_en
        assert "Prompt: Get weather alerts for a US state." in output_en
        assert "exec - Run shell commands in an isolated execution environment." in output_en
        assert "mcp_custom_tool -" in output_en
        assert "legacy_tool - Legacy tool description" in output_en
        assert "Prompt: Legacy prompt" in output_en


def test_cmd_and_plugin_commands():
    handler = SimpleNamespace()
    plugin = _shared_plugin(handler)
    asyncio.run(plugin.initialize())

    cmd = Cmd()
    cmd.plugin = plugin
    asyncio.run(cmd.initialize())

    plugin_cmd = Plugin()
    plugin_cmd.plugin = plugin
    asyncio.run(plugin_cmd.initialize())

    mock_commands = [
        {
            "manifest": {
                "metadata": {
                    "name": "test_cmd",
                    "description": {
                        "en_US": "Test command description",
                        "zh_Hans": "测试命令描述",
                    },
                }
            }
        }
    ]

    async def mock_list_commands():
        return mock_commands

    plugin.list_commands = mock_list_commands

    mock_plugins = [
        {
            "manifest": {
                "metadata": {
                    "name": "TestPlugin",
                    "description": {
                        "en_US": "Test plugin description",
                        "zh_Hans": "测试插件描述",
                    },
                }
            }
        }
    ]

    async def mock_list_plugins():
        return mock_plugins

    plugin.list_plugins_manifest = mock_list_plugins

    # Test cmd under zh_Hans
    with bind_invocation(handler, config={"language": "zh_Hans"}, binding=_binding("b")):
        output_cmd = asyncio.run(_render(cmd, "cmd"))[0]
        assert "可用命令:" in output_cmd
        assert "!test_cmd - 测试命令描述" in output_cmd

        output_plugin = asyncio.run(_render(plugin_cmd, "plugin"))[0]
        assert "已加载的插件:" in output_plugin
        assert "TestPlugin - 测试插件描述" in output_plugin

        # Test cmd man
        async def run_man():
            ctx_man = _context("cmd man test_cmd")
            ctx_man.params = ["man", "test_cmd"]
            ctx_man.crt_params = ["man", "test_cmd"]
            return [ret.text async for ret in cmd._execute(ctx_man)]

        output_man = (asyncio.run(run_man()))[0]
        assert "命令 test_cmd 手册:\n测试命令描述" in output_man


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
