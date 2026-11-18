from __future__ import annotations

import asyncio
import dotenv
import logging
import os

from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine
from langbot_plugin.utils.log import configure_process_logging
from langbot_plugin.cli.run.controller import PluginRuntimeController
from langbot_plugin.cli.i18n import cli_print
from langbot_plugin.cli.utils.page_components import (
    discover_plugin_components,
    populate_plugin_pages,
)
from langbot_plugin.runtime.security import PLUGIN_RUNTIME_PROFILE_ENV
from langbot_plugin.runtime.bounded_executor import (
    configure_bounded_default_executor_from_env,
)


logger = logging.getLogger(__name__)


def should_load_artifact_dotenv(runtime_profile: str) -> bool:
    return runtime_profile != "shared"


def apply_process_label(tag: str) -> None:
    """Record the process label carried by the worker command line.

    The launcher passes ``--tag author/name`` so an operator can tell which
    plugin a worker belongs to from ps/htop; this helper keeps the same value in
    the worker log. It makes no syscalls and changes no process attribute, so it
    behaves identically on every platform.

    The label is cosmetic only: it is never an identity, an authorization input
    or a routing key. The Runtime owns the real installation identity, and this
    value may be forged by whoever starts the process.
    """

    label = "".join(ch for ch in str(tag or "") if ch.isprintable()).strip()
    if not label:
        return
    logger.info("Plugin worker process label: %s", label)


async def arun_plugin_process(
    stdio: bool = False,
    prod_mode: bool = False,
    plugin_debug_key: str = "",
    pypi_index_url: str = "",
    pypi_trusted_host: str = "",
) -> None:
    configure_bounded_default_executor_from_env(
        thread_name_prefix="langbot-plugin-worker-blocking",
    )
    # Shared/production artifacts are immutable code and must never inject
    # process environment. OSS development keeps the historical .env behavior.
    runtime_profile = os.environ.get(PLUGIN_RUNTIME_PROFILE_ENV, "oss_dev")
    if should_load_artifact_dotenv(runtime_profile):
        dotenv.load_dotenv(".env")

    # Set plugin debug key from command line argument if provided
    if plugin_debug_key:
        os.environ["PLUGIN_DEBUG_KEY"] = plugin_debug_key
    if pypi_index_url:
        os.environ["LANGBOT_PLUGIN_PYPI_INDEX_URL"] = pypi_index_url
    if pypi_trusted_host:
        os.environ["LANGBOT_PLUGIN_PYPI_TRUSTED_HOST"] = pypi_trusted_host

    discovery_engine = ComponentDiscoveryEngine()

    if not os.path.exists("manifest.yaml"):
        cli_print("manifest_not_found")
        return

    plugin_manifest = discovery_engine.load_component_manifest(
        path="manifest.yaml",
        owner="builtin",
        no_save=True,
    )

    if plugin_manifest is None:
        cli_print("manifest_not_found")
        return

    ws_debug_url = ""

    if not stdio:
        ws_debug_url = os.getenv(
            "DEBUG_RUNTIME_WS_URL", os.getenv("RUNTIME_WS_URL", "")
        )
        if ws_debug_url == "":
            cli_print("debug_url_not_set")
            return

    component_manifests = discover_plugin_components(plugin_manifest, discovery_engine)
    populate_plugin_pages(plugin_manifest, component_manifests)

    controller = PluginRuntimeController(
        plugin_manifest,
        component_manifests,
        stdio,
        ws_debug_url,
        prod_mode,
    )

    await controller.mount()
    await controller.run()


def run_plugin_process(
    stdio: bool = False,
    prod_mode: bool = False,
    plugin_debug_key: str = "",
    pypi_index_url: str = "",
    pypi_trusted_host: str = "",
    tag: str = "",
) -> None:
    configure_process_logging()
    apply_process_label(tag)

    try:
        asyncio.run(
            arun_plugin_process(
                stdio,
                prod_mode,
                plugin_debug_key,
                pypi_index_url,
                pypi_trusted_host,
            )
        )
    except asyncio.CancelledError:
        cli_print("plugin_process_cancelled")
        return
    except KeyboardInterrupt:
        cli_print("keyboard_interrupt")
        return
