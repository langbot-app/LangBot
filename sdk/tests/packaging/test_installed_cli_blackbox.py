from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml


@dataclass(frozen=True)
class InstalledWheel:
    root: Path
    python: Path
    lbp: Path


@pytest.fixture(scope="session")
def installed_wheel(tmp_path_factory: pytest.TempPathFactory) -> InstalledWheel:
    uv = shutil.which("uv")
    if uv is None:
        pytest.fail("uv is required for installed wheel smoke tests")

    root = tmp_path_factory.mktemp("installed-wheel")
    dist = root / "dist"
    venv = root / "venv"
    repo_root = Path(__file__).resolve().parents[2]

    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(dist)],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    wheel_paths = sorted(dist.glob("*.whl"))
    assert wheel_paths, f"no wheel built in {dist}"

    subprocess.run(
        [uv, "venv", "--python", sys.executable, str(venv)],
        check=True,
        text=True,
        capture_output=True,
    )
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    lbp = venv / ("Scripts/lbp.exe" if os.name == "nt" else "bin/lbp")
    subprocess.run(
        [uv, "pip", "install", "--python", str(python), str(wheel_paths[0])],
        check=True,
        text=True,
        capture_output=True,
    )

    return InstalledWheel(root=root, python=python, lbp=lbp)


def run_installed_lbp(
    installed: InstalledWheel,
    *args: str,
    cwd: Path,
    stdin: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(installed.lbp), *args],
        cwd=cwd,
        input=stdin,
        text=True,
        capture_output=True,
        timeout=30,
    )


def init_demo_plugin(
    installed: InstalledWheel,
    tmp_path: Path,
    plugin_name: str,
) -> Path:
    init_result = run_installed_lbp(
        installed,
        "init",
        plugin_name,
        cwd=tmp_path,
        stdin="tester\nDemo plugin\n",
    )
    assert init_result.returncode == 0, init_result.stderr
    return tmp_path / plugin_name


def write_json_line(
    process: subprocess.Popen[str],
    payload: dict[str, object],
) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()


def read_json_line(
    process: subprocess.Popen[str],
    *,
    timeout: float = 10.0,
) -> dict[str, object]:
    assert process.stdout is not None
    deadline = time.monotonic() + timeout
    non_json_lines: list[str] = []

    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        readable, _, _ = select.select([process.stdout], [], [], remaining)
        if not readable:
            continue

        line = process.stdout.readline()
        if line == "":
            stderr = ""
            if process.poll() is not None and process.stderr is not None:
                stderr = process.stderr.read()
            pytest.fail(
                "lbp run exited before a JSON protocol message was emitted; "
                f"stdout={non_json_lines!r} stderr={stderr!r}"
            )

        line = line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            non_json_lines.append(line)
            continue

        assert isinstance(message, dict)
        return message

    pytest.fail(
        f"timed out waiting for JSON protocol message; stdout={non_json_lines!r}"
    )


def test_installed_wheel_exposes_cli_and_packaged_templates(
    installed_wheel: InstalledWheel,
) -> None:
    help_result = run_installed_lbp(installed_wheel, "--help", cwd=installed_wheel.root)
    assert help_result.returncode == 0, help_result.stderr
    assert "init" in help_result.stdout
    assert "build" in help_result.stdout

    probe = subprocess.run(
        [
            str(installed_wheel.python),
            "-c",
            (
                "from importlib.metadata import version; "
                "import importlib.resources as r; "
                "from langbot_plugin.version import __version__; "
                "from langbot_plugin.cli.gen.renderer import render_template; "
                "assert __version__ == version('langbot-plugin'); "
                "template = r.files('langbot_plugin').joinpath("
                "'assets/templates/manifest.yaml.example'"
                "); "
                "assert template.is_file(), template; "
                "assert 'kind: Plugin' in render_template("
                "'manifest.yaml.example', "
                "plugin_name='demo', "
                "plugin_author='tester', "
                "plugin_description='Demo', "
                "plugin_label='Demo', "
                "plugin_attr='Demo', "
                "lbp_path='lbp'"
                ")"
            ),
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert probe.returncode == 0, probe.stderr


def test_installed_lbp_init_comp_build_blackbox(
    installed_wheel: InstalledWheel,
    tmp_path: Path,
) -> None:
    plugin_dir = init_demo_plugin(installed_wheel, tmp_path, "demo-plugin")
    assert (plugin_dir / "manifest.yaml").is_file()
    assert (plugin_dir / "main.py").is_file()
    assert (plugin_dir / "assets" / "icon.svg").is_file()

    tool_result = run_installed_lbp(
        installed_wheel,
        "comp",
        "Tool",
        cwd=plugin_dir,
        stdin="weather\nWeather lookup\n",
    )
    assert tool_result.returncode == 0, tool_result.stderr

    command_result = run_installed_lbp(
        installed_wheel,
        "comp",
        "Command",
        cwd=plugin_dir,
        stdin="hello\nSay hello\n",
    )
    assert command_result.returncode == 0, command_result.stderr

    page_result = run_installed_lbp(
        installed_wheel,
        "comp",
        "Page",
        cwd=plugin_dir,
        stdin="settings\n",
    )
    assert page_result.returncode == 0, page_result.stderr

    manifest = yaml.safe_load((plugin_dir / "manifest.yaml").read_text())
    assert manifest["metadata"]["author"] == "tester"
    assert manifest["spec"]["components"] == {
        "Tool": {"fromDirs": [{"path": "components/tools/"}]},
        "Command": {"fromDirs": [{"path": "components/commands/"}]},
        "Page": {"fromDirs": [{"path": "components/pages/"}]},
    }
    assert (plugin_dir / "components" / "tools" / "weather.py").is_file()
    assert (plugin_dir / "components" / "commands" / "hello.py").is_file()
    assert (plugin_dir / "components" / "pages" / "settings.html").is_file()

    build_result = run_installed_lbp(
        installed_wheel,
        "build",
        "--output",
        str(tmp_path / "dist"),
        cwd=plugin_dir,
    )
    assert build_result.returncode == 0, build_result.stderr

    package_path = tmp_path / "dist" / "tester-demo-plugin-0.1.0.lbpkg"
    assert package_path.is_file()
    with zipfile.ZipFile(package_path) as package:
        names = set(package.namelist())
    assert "manifest.yaml" in names
    assert "components/tools/weather.py" in names
    assert "components/commands/hello.py" in names
    assert "components/pages/settings.html" in names
    assert ".env" not in names


def test_installed_lbp_run_stdio_runtime_protocol(
    installed_wheel: InstalledWheel,
    tmp_path: Path,
) -> None:
    if os.name == "nt":
        pytest.skip("stdio subprocess protocol smoke uses select on POSIX pipes")

    plugin_dir = init_demo_plugin(installed_wheel, tmp_path, "runtime-plugin")
    process = subprocess.Popen(
        [str(installed_wheel.lbp), "run", "-s", "--prod"],
        cwd=plugin_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        register_request = read_json_line(process)
        assert register_request["action"] == "register_plugin"
        assert register_request["data"]["prod_mode"] is True
        plugin_container = register_request["data"]["plugin_container"]
        manifest = plugin_container["manifest"]["manifest"]
        assert manifest["metadata"]["name"] == "runtime-plugin"
        assert manifest["metadata"]["author"] == "tester"
        assert plugin_container["status"] == "mounted"

        write_json_line(
            process,
            {
                "seq_id": register_request["seq_id"],
                "code": 0,
                "message": "success",
                "data": {},
            },
        )

        write_json_line(
            process,
            {
                "seq_id": 1001,
                "action": "initialize_plugin",
                "data": {
                    "plugin_settings": {
                        "enabled": True,
                        "priority": 0,
                        "plugin_config": {},
                    }
                },
            },
        )
        initialize_response = read_json_line(process)
        assert initialize_response["seq_id"] == 1001
        assert initialize_response["code"] == 0

        write_json_line(
            process,
            {
                "seq_id": 1002,
                "action": "get_plugin_container",
                "data": {},
            },
        )
        container_response = read_json_line(process)
        assert container_response["seq_id"] == 1002
        assert container_response["code"] == 0
        assert container_response["data"]["status"] == "initialized"
        assert (
            container_response["data"]["manifest"]["manifest"]["execution"]["python"][
                "path"
            ]
            == "main.py"
        )

        write_json_line(
            process,
            {
                "seq_id": 1003,
                "action": "shutdown",
                "data": {},
            },
        )
        shutdown_response = read_json_line(process)
        assert shutdown_response["seq_id"] == 1003
        assert shutdown_response["code"] == 0
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


@pytest.mark.parametrize(
    ("component_type", "directory", "component_name", "class_name"),
    [
        ("Runner", "runner", "echo_runner", "EchoRunner"),
    ],
)
def test_installed_processor_scaffold_builds_and_executes(
    installed_wheel, tmp_path, component_type, directory, component_name, class_name
):
    plugin = init_demo_plugin(installed_wheel, tmp_path, "ProcessorTutorial")
    generated = run_installed_lbp(
        installed_wheel,
        "comp",
        component_type,
        cwd=plugin,
        stdin=f"{component_name}\nTutorial processor\n",
    )
    assert generated.returncode == 0, generated.stderr
    manifest = yaml.safe_load((plugin / "manifest.yaml").read_text())
    assert manifest["spec"]["components"][component_type] == {
        "fromDirs": [{"path": f"components/{directory}/"}]
    }
    built = run_installed_lbp(installed_wheel, "build", cwd=plugin)
    assert built.returncode == 0, built.stderr
    packages = list((plugin / "dist").glob("*.lbpkg"))
    assert len(packages) == 1
    with zipfile.ZipFile(packages[0]) as archive:
        assert f"components/{directory}/{component_name}.py" in archive.namelist()
        assert f"components/{directory}/{component_name}.yaml" in archive.namelist()
    script = f"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from components.{directory}.{component_name} import {class_name}

async def main():
    component = {class_name}()
    await component.initialize()
    api = SimpleNamespace(call_tool=AsyncMock(return_value={{"ok": True, "mock": True}}))
    component.get_run_api = Mock(return_value=api)
    ctx = SimpleNamespace(
        run_id="tutorial", config={{}},
        input=SimpleNamespace(to_text=lambda: "你好"),
        event=SimpleNamespace(data={{"type": "group.member_joined", "member": {{"id": "one", "nickname": "Alice"}}}}),
    )
    results = [item async for item in component.run(ctx)]
    assert sum(item.type == "run.completed" for item in results) == 1
    assert results[-1].data["message"]["content"] == "Received: 你好"
asyncio.run(main())
"""
    result = subprocess.run(
        [str(installed_wheel.python), "-c", script],
        cwd=plugin,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
