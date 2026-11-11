from __future__ import annotations

import asyncio
import sys
import logging
import importlib
from pathlib import Path
from typing import Callable, Coroutine, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".langbot-codex-home",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}


def _is_ignored_path(path: str) -> bool:
    parts = {part.casefold() for part in Path(path).parts}
    return bool(parts & IGNORED_DIRECTORY_NAMES)


class PythonFileChangeHandler(FileSystemEventHandler):
    """Handler for Python file changes."""

    def __init__(
        self,
        on_change_callback: Callable[[], Coroutine[Any, Any, None]],
        debounce_delay: float = 0.5,
    ):
        super().__init__()
        self.on_change_callback = on_change_callback
        self.debounce_delay = debounce_delay
        self._pending_reload: asyncio.Task | None = None
        self._loop = asyncio.get_event_loop()

    def on_modified(self, event):
        """Called when a file is modified."""
        if event.is_directory:
            return

        # Only handle .py files
        if not event.src_path.endswith(".py"):
            return

        if _is_ignored_path(event.src_path):
            return

        logger.info(f"Detected change in {event.src_path}")

        # Debounce: cancel previous pending reload
        if self._pending_reload is not None and not self._pending_reload.done():
            self._pending_reload.cancel()

        # Schedule a new reload
        self._pending_reload = asyncio.run_coroutine_threadsafe(
            self._debounced_reload(), self._loop
        )

    async def _debounced_reload(self):
        """Debounced reload to avoid multiple reloads for rapid file changes."""
        await asyncio.sleep(self.debounce_delay)
        await self.on_change_callback()


class HotReloader:
    """Hot reloader for plugin code."""

    def __init__(
        self,
        watch_path: str,
        on_reload_callback: Callable[[], Coroutine[Any, Any, None]],
    ):
        self.watch_path = watch_path
        self.on_reload_callback = on_reload_callback
        self.observer: Observer | None = None
        self.event_handler: PythonFileChangeHandler | None = None

    def start(self):
        """Start watching for file changes."""
        logger.info(f"Starting hot reloader, watching {self.watch_path}")

        self.event_handler = PythonFileChangeHandler(self.on_reload_callback)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.watch_path, recursive=True)
        self.observer.start()

    def stop(self):
        """Stop watching for file changes."""
        if self.observer is not None:
            logger.info("Stopping hot reloader")
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.event_handler = None


def reload_plugin_modules(plugin_path: str):
    """Reload all Python modules in the plugin directory.

    Args:
        plugin_path: Path to the plugin directory
    """
    logger.info(f"Reloading plugin modules from {plugin_path}")

    # Get absolute path
    abs_plugin_path = Path(plugin_path).resolve()

    # Find all modules that belong to this plugin
    modules_to_reload = []
    for name, module in list(sys.modules.items()):
        if module is None:
            continue

        # Get module file path
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            continue

        # Check if module belongs to this plugin
        abs_module_path = Path(module_file).resolve()
        try:
            abs_module_path.relative_to(abs_plugin_path)
        except ValueError:
            continue
        else:
            modules_to_reload.append((name, module))

    # Reload modules in reverse order (to handle dependencies)
    logger.info(f"Found {len(modules_to_reload)} modules to reload")
    for name, module in reversed(modules_to_reload):
        try:
            logger.debug(f"Reloading module: {name}")
            importlib.reload(module)
        except Exception as e:
            logger.error(f"Failed to reload module {name}: {e}")
            # Continue with other modules even if one fails

    logger.info("Plugin modules reloaded")
