from __future__ import annotations

import asyncio
import types
from types import SimpleNamespace

from langbot_plugin.cli.run import hotreload
from langbot_plugin.cli.run.hotreload import (
    HotReloader,
    PythonFileChangeHandler,
    reload_plugin_modules,
)


class FakeObserver:
    instances: list["FakeObserver"] = []

    def __init__(self):
        self.scheduled = []
        self.started = False
        self.stopped = False
        self.joined = False
        self.__class__.instances.append(self)

    def schedule(self, handler, path, recursive=False):
        self.scheduled.append((handler, path, recursive))

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def join(self):
        self.joined = True


async def test_python_file_change_handler_debounces_python_file_events():
    calls = []

    async def on_change():
        calls.append("reload")

    handler = PythonFileChangeHandler(on_change, debounce_delay=0.01)

    handler.on_modified(SimpleNamespace(is_directory=True, src_path="plugin.py"))
    handler.on_modified(SimpleNamespace(is_directory=False, src_path="README.md"))
    handler.on_modified(
        SimpleNamespace(is_directory=False, src_path="__pycache__/plugin.py")
    )
    handler.on_modified(
        SimpleNamespace(
            is_directory=False,
            src_path=".langbot-codex-home/run/skills/tool.py",
        )
    )
    handler.on_modified(
        SimpleNamespace(is_directory=False, src_path="node_modules/pkg/plugin.py")
    )
    handler.on_modified(SimpleNamespace(is_directory=False, src_path="plugin.pyc"))

    assert handler._pending_reload is None

    handler.on_modified(SimpleNamespace(is_directory=False, src_path="plugin.py"))
    first_reload = handler._pending_reload
    handler.on_modified(SimpleNamespace(is_directory=False, src_path="components/a.py"))

    assert first_reload.cancelled()

    await asyncio.wrap_future(handler._pending_reload)
    assert calls == ["reload"]


async def test_python_file_change_handler_cancels_existing_pending_reload():
    calls = []

    async def on_change():
        calls.append("reload")

    handler = PythonFileChangeHandler(on_change, debounce_delay=10)

    handler.on_modified(SimpleNamespace(is_directory=False, src_path="plugin.py"))
    first_reload = handler._pending_reload
    assert first_reload is not None

    handler.on_modified(SimpleNamespace(is_directory=False, src_path="plugin.py"))

    assert first_reload.cancelled()
    handler._pending_reload.cancel()
    try:
        await asyncio.wrap_future(handler._pending_reload)
    except asyncio.CancelledError:
        pass
    assert calls == []


async def test_hot_reloader_start_and_stop_lifecycle(monkeypatch, tmp_path):
    FakeObserver.instances = []
    monkeypatch.setattr(hotreload, "Observer", FakeObserver)

    async def on_reload():
        pass

    reloader = HotReloader(str(tmp_path), on_reload)
    reloader.start()

    observer = FakeObserver.instances[0]
    assert observer.started is True
    assert observer.scheduled == [(reloader.event_handler, str(tmp_path), True)]
    assert isinstance(reloader.event_handler, PythonFileChangeHandler)

    reloader.stop()

    assert observer.stopped is True
    assert observer.joined is True
    assert reloader.observer is None
    assert reloader.event_handler is None

    reloader.stop()
    assert observer.stopped is True


def test_reload_plugin_modules_only_reloads_modules_under_plugin_path(
    monkeypatch,
    tmp_path,
):
    plugin_root = tmp_path / "plugin"
    plugin_pkg = plugin_root / "pkg"
    sibling_pkg = tmp_path / "plugin-extra"
    sdk_pkg = tmp_path / "sdk"
    plugin_pkg.mkdir(parents=True)
    sibling_pkg.mkdir()
    sdk_pkg.mkdir()

    plugin_module = types.ModuleType("plugin.main")
    plugin_module.__file__ = str(plugin_pkg / "main.py")
    nested_module = types.ModuleType("plugin.pkg.module")
    nested_module.__file__ = str(plugin_pkg / "module.py")
    sibling_module = types.ModuleType("plugin_extra.main")
    sibling_module.__file__ = str(sibling_pkg / "main.py")
    sdk_module = types.ModuleType("langbot_plugin.api")
    sdk_module.__file__ = str(sdk_pkg / "api.py")
    builtin_like_module = types.ModuleType("json")
    builtin_like_module.__file__ = None

    modules = {
        "plugin.main": plugin_module,
        "plugin.pkg.module": nested_module,
        "plugin_extra.main": sibling_module,
        "langbot_plugin.api": sdk_module,
        "json": builtin_like_module,
        "none_module": None,
    }
    reloaded = []

    monkeypatch.setattr(hotreload.sys, "modules", modules)
    monkeypatch.setattr(
        hotreload.importlib,
        "reload",
        lambda module: reloaded.append(module.__name__),
    )

    reload_plugin_modules(str(plugin_root))

    assert reloaded == ["plugin.pkg.module", "plugin.main"]


def test_reload_plugin_modules_continues_when_reload_fails(monkeypatch, tmp_path):
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    first = types.ModuleType("plugin.first")
    first.__file__ = str(plugin_root / "first.py")
    second = types.ModuleType("plugin.second")
    second.__file__ = str(plugin_root / "second.py")
    modules = {"plugin.first": first, "plugin.second": second}
    attempted = []

    def fake_reload(module):
        attempted.append(module.__name__)
        if module is second:
            raise RuntimeError("reload failed")
        return module

    monkeypatch.setattr(hotreload.sys, "modules", modules)
    monkeypatch.setattr(hotreload.importlib, "reload", fake_reload)

    reload_plugin_modules(str(plugin_root))

    assert attempted == ["plugin.second", "plugin.first"]
