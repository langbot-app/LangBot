from __future__ import annotations

import os

from langbot_plugin.cli.i18n import cli_print
from langbot_plugin.utils.packaging import (
    build_plugin_package,
    parse_gitignore,
    should_ignore,
)

# Re-exported for backwards compatibility with callers/tests that imported the
# gitignore helpers from this module before they moved to utils.packaging.
__all__ = ["parse_gitignore", "should_ignore", "build_plugin_process"]


def build_plugin_process(output_dir: str) -> str | None:
    """Build the plugin in the current directory into ``output_dir``.

    Discovery errors (e.g. an invalid Runner manifest) intentionally propagate:
    a build must fail loudly rather than emit a package that silently drops a
    component. Only a missing manifest is reported as a soft no-op, matching the
    historical CLI behaviour.
    """

    if not os.path.exists("manifest.yaml"):
        cli_print("manifest_not_found")
        return None

    cli_print("building_plugin", output_dir)

    os.makedirs(output_dir, exist_ok=True)

    package_bytes, filename = build_plugin_package(os.getcwd())

    zipfile_path = os.path.join(output_dir, filename)
    with open(zipfile_path, "wb") as output_file:
        output_file.write(package_bytes)

    cli_print("plugin_built", zipfile_path)
    return zipfile_path
