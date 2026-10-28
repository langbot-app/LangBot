"""Real SDK runtime contracts; vendor services are explicitly local fixtures.

Install this checkout's plugin requirements and the intended SDK before running.
No SDK modules are stubbed. Each plugin runs in a fresh interpreter, matching
production module isolation. Optional RUNNER_EVIDENCE_DIR retains raw RPC logs.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CODING_PLUGINS = {"acp-agent-runner", "claude-code-agent", "codex-agent"}
PLUGINS = {
    "acp-agent-runner": "ACPAgentRunner",  # Published identity survives the Runner component-kind rename.
    "claude-code-agent": "ClaudeCodeAgent",
    "codex-agent": "CodexAgent",
    "coze-agent": "CozeAgent",
    "dashscope-agent": "DashScopeAgent",
    "deerflow-agent": "DeerFlowAgent",
    "dify-agent": "DifyAgent",
    "langflow-agent": "LangflowAgent",
    "n8n-agent": "N8nAgent",
    "tbox-agent": "TboxAgent",
    "weknora-agent": "WeKnoraAgent",
}


def plugin_python(plugin):
    # Coding payloads still pin b3. Verify their real RPC/dependencies there,
    # while aggregate compatibility and the HTTP release use the b5 environment.
    return os.environ.get("CODING_RUNNER_TEST_PYTHON", sys.executable) if plugin in CODING_PLUGINS else sys.executable


@pytest.fixture(scope="module", params=sorted(PLUGINS))
def runtime_evidence(request, tmp_path_factory):
    plugin = request.param
    evidence_dir = Path(os.environ.get("RUNNER_EVIDENCE_DIR") or tmp_path_factory.mktemp("runtime-evidence"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    destination = evidence_dir / f"{plugin}.json"
    env = os.environ.copy()
    # Do not inherit provider credentials, proxy configuration, or daemon switches.
    for key in list(env):
        if any(token in key.upper() for token in ("API_KEY", "TOKEN", "SECRET", "PROXY", "DAEMON")):
            env.pop(key)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    result = subprocess.run(
        [plugin_python(plugin), str(ROOT / "tests/fixtures/real_sdk_runtime_probe.py"), str(destination)],
        cwd=ROOT / plugin,
        env=env,
        text=True,
        capture_output=True,
        timeout=40,
    )
    (evidence_dir / f"{plugin}.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    return plugin, json.loads(destination.read_text())


def test_real_sdk_discovers_and_initializes_runner(runtime_evidence):
    plugin, evidence = runtime_evidence
    assert Path(evidence["sdk_path"]).parts[-2:] == ("langbot_plugin", "__init__.py")
    assert evidence["identity"] == f"langbot-team/{PLUGINS[plugin]}"
    assert evidence["status"] == "initialized"
    assert evidence["component_kind"] == "Runner"
    assert evidence["runner_class"] == "DefaultRunner"
    assert evidence["transport"] == "real SDK WebSocketConnection + PluginRuntimeHandler on loopback"


def test_real_sdk_dispatches_config_failure(runtime_evidence):
    _, evidence = runtime_evidence
    results = evidence["invalid_results"]
    assert [item["type"] for item in results] == ["run.failed"]
    assert results[0]["data"]["code"].endswith(".config_invalid"), results
    assert results[0]["sequence"] == 1


def test_real_sdk_dispatches_local_vendor_fixture(runtime_evidence):
    _, evidence = runtime_evidence
    results = evidence["fixture_results"]
    assert results[-1]["type"] == "run.completed", results
    assert not any(item["type"] == "run.failed" for item in results), results
    assert [item["sequence"] for item in results] == list(range(1, len(results) + 1))
    assert all(item["run_id"] == "fixture-run" for item in results)
    assert "FIXTURE_OK" in json.dumps(results), results
    assert any(item["type"] == "state.updated" for item in results), results
    assert evidence["external_live_connectivity_tested"] is False
    assert evidence["fixture_calls"], evidence


@pytest.mark.parametrize("plugin", sorted(PLUGINS))
def test_installed_real_dependencies_satisfy_plugin_requirements(plugin):
    # Resolve every declared dependency inside the same interpreter used by RPC.
    code = """
import importlib.metadata
from pathlib import Path
from packaging.requirements import Requirement
for line in Path("requirements.txt").read_text().splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    requirement = Requirement(line)
    if requirement.marker and not requirement.marker.evaluate():
        continue
    version = importlib.metadata.version(requirement.name)
    assert version in requirement.specifier, f"{requirement.name}=={version} violates {line}"
"""
    result = subprocess.run(
        [plugin_python(plugin), "-c", code],
        cwd=ROOT / plugin,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, f"{plugin}: {result.stdout}{result.stderr}"
