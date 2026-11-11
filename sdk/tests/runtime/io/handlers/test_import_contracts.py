from __future__ import annotations

import subprocess
import sys


def test_plugin_connection_handler_should_be_directly_importable():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from langbot_plugin.runtime.io.handlers.plugin "
                "import PluginConnectionHandler\n"
                "print(PluginConnectionHandler.__name__)\n"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PluginConnectionHandler"
