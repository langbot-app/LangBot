from __future__ import annotations

import asyncio
import logging
import sys

import pytest

from langbot_plugin.cli.commands import runplugin


class FakeDiscoveryEngine:
    manifest = object()
    load_calls = []

    def load_component_manifest(self, **kwargs):
        self.load_calls.append(kwargs)
        return self.manifest


class FakeRuntimeController:
    instances = []

    def __init__(
        self,
        plugin_manifest,
        component_manifests,
        stdio,
        ws_debug_url,
        prod_mode,
    ):
        self.plugin_manifest = plugin_manifest
        self.component_manifests = component_manifests
        self.stdio = stdio
        self.ws_debug_url = ws_debug_url
        self.prod_mode = prod_mode
        self.calls = []
        self.instances.append(self)

    async def run(self):
        self.calls.append("run")

    async def mount(self):
        self.calls.append("mount")


async def test_arun_plugin_process_reports_missing_manifest(tmp_path, monkeypatch):
    prints = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runplugin, "cli_print", lambda *args: prints.append(args))

    await runplugin.arun_plugin_process(stdio=True)

    assert prints == [("manifest_not_found",)]


async def test_arun_plugin_process_reports_manifest_load_failure(tmp_path, monkeypatch):
    prints = []
    (tmp_path / "manifest.yaml").write_text("kind: Plugin\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runplugin, "cli_print", lambda *args: prints.append(args))
    monkeypatch.setattr(
        runplugin,
        "ComponentDiscoveryEngine",
        lambda: type(
            "MissingManifestDiscovery",
            (),
            {"load_component_manifest": lambda self, **kwargs: None},
        )(),
    )

    await runplugin.arun_plugin_process(stdio=True)

    assert prints == [("manifest_not_found",)]


async def test_arun_plugin_process_requires_debug_url_for_websocket_mode(
    tmp_path, monkeypatch
):
    prints = []
    (tmp_path / "manifest.yaml").write_text("kind: Plugin\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEBUG_RUNTIME_WS_URL", raising=False)
    monkeypatch.delenv("RUNTIME_WS_URL", raising=False)
    monkeypatch.setattr(runplugin, "cli_print", lambda *args: prints.append(args))
    monkeypatch.setattr(runplugin, "ComponentDiscoveryEngine", FakeDiscoveryEngine)

    await runplugin.arun_plugin_process(stdio=False)

    assert prints == [("debug_url_not_set",)]


async def test_arun_plugin_process_builds_controller_and_sets_runtime_env(
    tmp_path, monkeypatch
):
    calls = []
    manifest = object()
    components = [object()]
    (tmp_path / "manifest.yaml").write_text("kind: Plugin\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PLUGIN_DEBUG_KEY", raising=False)
    monkeypatch.delenv("LANGBOT_PLUGIN_PYPI_INDEX_URL", raising=False)
    monkeypatch.delenv("LANGBOT_PLUGIN_PYPI_TRUSTED_HOST", raising=False)
    monkeypatch.setattr(
        runplugin.dotenv,
        "load_dotenv",
        lambda path: calls.append(("load_dotenv", path)),
    )
    monkeypatch.setattr(
        runplugin,
        "ComponentDiscoveryEngine",
        lambda: type(
            "Discovery",
            (),
            {
                "load_component_manifest": (
                    lambda self, **kwargs: (
                        calls.append(("load_manifest", kwargs)) or manifest
                    )
                )
            },
        )(),
    )
    monkeypatch.setattr(
        runplugin,
        "discover_plugin_components",
        lambda plugin_manifest, engine: (
            calls.append(("discover_components", plugin_manifest, engine)) or components
        ),
    )
    monkeypatch.setattr(
        runplugin,
        "populate_plugin_pages",
        lambda plugin_manifest, component_manifests: calls.append(
            ("populate_pages", plugin_manifest, component_manifests)
        ),
    )
    monkeypatch.setattr(runplugin, "PluginRuntimeController", FakeRuntimeController)

    await runplugin.arun_plugin_process(
        stdio=True,
        prod_mode=True,
        plugin_debug_key="debug-key",
        pypi_index_url="https://mirror",
        pypi_trusted_host="mirror",
    )

    controller = FakeRuntimeController.instances[-1]
    assert calls[0] == ("load_dotenv", ".env")
    assert calls[1] == (
        "load_manifest",
        {"path": "manifest.yaml", "owner": "builtin", "no_save": True},
    )
    assert calls[2][0] == "discover_components"
    assert calls[3] == ("populate_pages", manifest, components)
    assert controller.plugin_manifest is manifest
    assert controller.component_manifests is components
    assert controller.stdio is True
    assert controller.ws_debug_url == ""
    assert controller.prod_mode is True
    assert controller.calls == ["mount", "run"]
    assert runplugin.os.environ["PLUGIN_DEBUG_KEY"] == "debug-key"
    assert runplugin.os.environ["LANGBOT_PLUGIN_PYPI_INDEX_URL"] == "https://mirror"
    assert runplugin.os.environ["LANGBOT_PLUGIN_PYPI_TRUSTED_HOST"] == "mirror"


async def test_arun_plugin_process_uses_debug_runtime_ws_url(tmp_path, monkeypatch):
    components = []
    manifest = object()
    (tmp_path / "manifest.yaml").write_text("kind: Plugin\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEBUG_RUNTIME_WS_URL", "ws://debug")
    monkeypatch.setenv("RUNTIME_WS_URL", "ws://runtime")
    monkeypatch.setattr(
        runplugin,
        "ComponentDiscoveryEngine",
        lambda: type(
            "Discovery",
            (),
            {"load_component_manifest": lambda self, **kwargs: manifest},
        )(),
    )
    monkeypatch.setattr(
        runplugin,
        "discover_plugin_components",
        lambda plugin_manifest, engine: components,
    )
    monkeypatch.setattr(runplugin, "populate_plugin_pages", lambda *args: None)
    monkeypatch.setattr(runplugin, "PluginRuntimeController", FakeRuntimeController)

    await runplugin.arun_plugin_process(stdio=False)

    assert FakeRuntimeController.instances[-1].ws_debug_url == "ws://debug"


async def test_arun_plugin_process_does_not_start_run_task_when_mount_fails(
    tmp_path, monkeypatch
):
    calls = []
    (tmp_path / "manifest.yaml").write_text("kind: Plugin\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEBUG_RUNTIME_WS_URL", "ws://debug")
    monkeypatch.setattr(runplugin, "ComponentDiscoveryEngine", FakeDiscoveryEngine)
    monkeypatch.setattr(runplugin, "discover_plugin_components", lambda *_args: [])
    monkeypatch.setattr(runplugin, "populate_plugin_pages", lambda *_args: None)

    class FailingRuntimeController:
        def __init__(self, *_args):
            pass

        async def mount(self):
            calls.append("mount")
            raise ValueError("missing debug credential")

        async def run(self):
            calls.append("run")

    monkeypatch.setattr(runplugin, "PluginRuntimeController", FailingRuntimeController)

    with pytest.raises(ValueError, match="missing debug credential"):
        await runplugin.arun_plugin_process(stdio=False)

    await asyncio.sleep(0)
    assert calls == ["mount"]


def test_run_plugin_process_configures_logging_and_runs_async_entry(monkeypatch):
    calls = []
    monkeypatch.setattr(
        runplugin,
        "configure_process_logging",
        lambda: calls.append(("configure_logging",)),
    )
    monkeypatch.setattr(
        runplugin,
        "arun_plugin_process",
        lambda *args: calls.append(("arun", args)) or "coroutine",
    )
    monkeypatch.setattr(
        runplugin.asyncio,
        "run",
        lambda coroutine: calls.append(("asyncio_run", coroutine)),
    )

    runplugin.run_plugin_process(
        stdio=True,
        prod_mode=True,
        plugin_debug_key="debug-key",
        pypi_index_url="https://mirror",
        pypi_trusted_host="mirror",
    )

    assert calls == [
        ("configure_logging",),
        (
            "arun",
            (True, True, "debug-key", "https://mirror", "mirror"),
        ),
        ("asyncio_run", "coroutine"),
    ]


def test_run_plugin_process_reports_cancelled_error(monkeypatch):
    prints = []
    monkeypatch.setattr(runplugin, "configure_process_logging", lambda: None)
    monkeypatch.setattr(runplugin, "arun_plugin_process", lambda *args: "coroutine")
    monkeypatch.setattr(
        runplugin.asyncio,
        "run",
        lambda coroutine: (_ for _ in ()).throw(asyncio.CancelledError()),
    )
    monkeypatch.setattr(runplugin, "cli_print", lambda *args: prints.append(args))

    runplugin.run_plugin_process()

    assert prints == [("plugin_process_cancelled",)]


def test_run_plugin_process_reports_keyboard_interrupt(monkeypatch):
    prints = []
    monkeypatch.setattr(runplugin, "configure_process_logging", lambda: None)
    monkeypatch.setattr(runplugin, "arun_plugin_process", lambda *args: "coroutine")
    monkeypatch.setattr(
        runplugin.asyncio,
        "run",
        lambda coroutine: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(runplugin, "cli_print", lambda *args: prints.append(args))

    runplugin.run_plugin_process()

    assert prints == [("keyboard_interrupt",)]


def test_apply_process_label_sanitizes_and_logs_the_tag(caplog):
    with caplog.at_level(logging.INFO, logger=runplugin.__name__):
        runplugin.apply_process_label("langbot-team/LangRAG")
        runplugin.apply_process_label("   ")
        runplugin.apply_process_label("bad\nname\x00")

    messages = [record.getMessage() for record in caplog.records]

    assert "Plugin worker process label: langbot-team/LangRAG" in messages
    assert "Plugin worker process label: badname" in messages
    # A blank label records nothing.
    assert len(messages) == 2


def test_cli_run_forwards_the_process_tag(monkeypatch):
    from langbot_plugin import cli as cli_module

    forwarded: list = []
    monkeypatch.setattr(
        cli_module,
        "run_plugin_process",
        lambda *args, **kwargs: forwarded.append(kwargs),
    )
    monkeypatch.setattr(sys, "argv", ["lbp", "run", "--tag", "langbot-team/LangRAG"])

    cli_module.main()

    assert forwarded and forwarded[0].get("tag") == "langbot-team/LangRAG"
