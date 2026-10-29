"""Keep plugin suites isolated, as in their production processes.

Every plugin here owns a `pkg`/`components` tree with generic module names, so a
suite that imports them must run in its own interpreter; the Runner process
collects only `tests/` (see `[tool.pytest.ini_options]`).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

# Migrated runners plus the shared agents that carry installation-scoped identity
# tests; all of them import `pkg.*` and must not share this interpreter.
PLUGINS = [
    "LocalAgent",
    "RunnerDemo",
    "coze-agent",
    "dashscope-agent",
    "deerflow-agent",
    "dify-agent",
    "langflow-agent",
    "n8n-agent",
    "tbox-agent",
    "weknora-agent",
]


@pytest.mark.parametrize("plugin", PLUGINS)
def test_migrated_runner_suite(plugin, tmp_path):
    plugin_root = ROOT / plugin
    manifest = yaml.safe_load((plugin_root / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["metadata"]["repository"] == (
        f"https://github.com/langbot-app/LangBot/tree/master/plugins/Runner/{plugin}"
    )
    evidence_dir = Path(os.environ.get("RUNNER_EVIDENCE_DIR") or tmp_path)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            os.environ.get("LOCALAGENT_TEST_PYTHON", sys.executable) if plugin == "LocalAgent" else sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={evidence_dir / (plugin + '.xml')}",
        ],
        cwd=plugin_root,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
        capture_output=True,
        timeout=180,
    )
    (evidence_dir / f"{plugin}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
