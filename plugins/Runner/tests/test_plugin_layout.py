from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shlex
import sys
import types
from pathlib import Path

from langbot_plugin.api.entities.builtin.runner import (
    AgentEventContext,
    AgentInput,
    AgentResources,
    AgentRunState,
    AgentRuntimeContext,
    AgentTrigger,
    DeliveryContext,
    InteractionSubmission,
    RunnerContext,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_runner_module(plugin_dir: str):
    return _load_plugin_module(plugin_dir, "components/runner/default.py", "runner")


def _load_plugin_module(plugin_dir: str, relative_path: str, suffix: str):
    for module_name in list(sys.modules):
        if module_name == "pkg" or module_name.startswith("pkg."):
            del sys.modules[module_name]

    plugin_root = ROOT / plugin_dir
    sys.path.insert(0, str(plugin_root))
    try:
        module_path = plugin_root / relative_path
        spec = importlib.util.spec_from_file_location(f"test_{plugin_dir.replace('-', '_')}_{suffix}", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(plugin_root))


def test_acp_prompt_blocks_include_runtime_supported_image_data() -> None:
    module = _load_plugin_module("acp-agent-runner", "pkg/prompt.py", "prompt")

    blocks = module.acp_prompt_blocks(
        "Describe the image.",
        {
            "attachments": [
                {
                    "type": "image",
                    "content": "data:image/png;base64,aGVsbG8=",
                }
            ]
        },
        {"image": True, "audio": False, "embedded_context": False},
    )

    assert blocks == [
        {"type": "text", "text": "Describe the image."},
        {"type": "image", "mimeType": "image/png", "data": "aGVsbG8="},
    ]


def test_acp_prompt_blocks_use_resource_link_for_url_images_without_image_capability() -> None:
    module = _load_plugin_module("acp-agent-runner", "pkg/prompt.py", "prompt")

    blocks = module.acp_prompt_blocks(
        "Check the attachment.",
        {
            "contents": [
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/a.png"},
                }
            ]
        },
        {"image": False, "audio": False, "embedded_context": False},
    )

    assert blocks == [
        {"type": "text", "text": "Check the attachment."},
        {
            "type": "resource_link",
            "uri": "https://example.com/a.png",
            "name": "image",
            "mimeType": "image/png",
        },
    ]


def test_acp_prompt_blocks_embed_text_file_when_runtime_supports_embedded_context() -> None:
    module = _load_plugin_module("acp-agent-runner", "pkg/prompt.py", "prompt")

    blocks = module.acp_prompt_blocks(
        "Read the file.",
        {
            "contents": [
                {
                    "type": "file_base64",
                    "file_base64": "data:text/plain;base64,aGk=",
                    "file_name": "hello.txt",
                }
            ]
        },
        {"image": False, "audio": False, "embedded_context": True},
    )

    assert blocks == [
        {"type": "text", "text": "Read the file."},
        {
            "type": "resource",
            "resource": {
                "uri": "langbot-input://hello.txt",
                "mimeType": "text/plain",
                "text": "hi",
            },
        },
    ]


def test_acp_prompt_blocks_note_unsupported_inline_image() -> None:
    module = _load_plugin_module("acp-agent-runner", "pkg/prompt.py", "prompt")

    blocks = module.acp_prompt_blocks(
        "",
        {"attachments": [{"type": "image", "content": "data:image/png;base64,aGVsbG8="}]},
        {"image": False, "audio": False, "embedded_context": False},
    )

    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert "image attachment(s) were not sent" in blocks[0]["text"]


def test_acp_runner_validates_daemon_location_config() -> None:
    module = _load_runner_module("acp-agent-runner")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {
        "daemon-host": "0.0.0.0",
        "daemon-port": 18766,
        "daemon-token": "secret",
    }

    ctx = types.SimpleNamespace(
        config={
            "provider": "codex",
            "location": "daemon",
            "daemon-id": "alice-laptop",
            "workspace": "/tmp/project",
        }
    )
    config = runner._validate_config(ctx)

    assert config["location"] == "daemon"
    assert config["daemon_id"] == "alice-laptop"
    assert config["daemon_hub"] == {
        "enabled": False,
        "host": "0.0.0.0",
        "port": 18766,
        "token": "secret",
    }

    ctx.config["daemon-id"] = ""
    try:
        runner._validate_config(ctx)
    except module.AcpError as exc:
        assert exc.code == "acp.config_invalid"
        assert "daemon-id is required" in exc.message
    else:
        raise AssertionError("daemon-id should be required when location=daemon")


def test_acp_claude_sessions_only_load_explicit_mcp_servers() -> None:
    module = _load_runner_module("acp-agent-runner")
    runner = object.__new__(module.DefaultRunner)
    mcp_servers = [
        {
            "name": "langbot_agent",
            "type": "stdio",
            "command": "python",
            "args": ["-m", "langbot_plugin.api.agent_tools.mcp_stdio"],
            "env": [{"name": "LANGBOT_AGENT_MCP_ENDPOINT", "value": "http://127.0.0.1:12345"}],
        }
    ]
    base_config = {
        "provider": "claude-code",
        "session_cwd": "/workspace",
        "timeout": 10.0,
        "reuse_session": True,
        "create_session_if_missing": True,
    }

    class FakeClient:
        def __init__(self) -> None:
            self.requests = []

        async def request(self, method, params, *, timeout):
            self.requests.append((method, params, timeout))
            return {"sessionId": params.get("sessionId") or "new-session"}

        async def drain_updates(self):
            return None

    async def exercise():
        calls = []
        scenarios = [
            ({}, ""),
            ({"sessionCapabilities": {"resume": True}}, "resume-session"),
            ({"loadSession": True}, "load-session"),
        ]
        for capabilities, stored_session_id in scenarios:
            client = FakeClient()
            await runner._create_or_resume_session(
                client,
                {"agentCapabilities": capabilities},
                object(),
                base_config,
                mcp_servers,
                stored_session_id,
            )
            calls.extend(client.requests)
        return calls

    calls = asyncio.run(exercise())

    assert [method for method, _, _ in calls] == ["session/new", "session/resume", "session/load"]
    for _, params, timeout in calls:
        assert params["cwd"] == "/workspace"
        assert params["mcpServers"] == []
        assert params["_meta"] == {
            "claudeCode": {
                "options": {
                    "strictMcpConfig": True,
                    "mcpServers": {
                        "langbot_agent": {
                            "type": "stdio",
                            "command": "python",
                            "args": ["-m", "langbot_plugin.api.agent_tools.mcp_stdio"],
                            "env": {"LANGBOT_AGENT_MCP_ENDPOINT": "http://127.0.0.1:12345"},
                            "alwaysLoad": True,
                        }
                    },
                    "tools": ["Bash", "Read", "Edit", "Write", "Glob", "Grep", "Agent"],
                }
            }
        }
        assert timeout == 10.0


def test_acp_non_claude_sessions_keep_provider_mcp_behavior() -> None:
    module = _load_plugin_module("acp-agent-runner", "pkg/session.py", "session")

    params = module.build_session_params(
        provider="codex",
        session_id="session-1",
        cwd="/workspace",
        mcp_servers=[],
    )

    assert params == {
        "sessionId": "session-1",
        "cwd": "/workspace",
        "mcpServers": [],
    }


def test_acp_client_closes_spawned_process_group(tmp_path: Path) -> None:
    if os.name == "nt":
        return

    module = _load_plugin_module("acp-agent-runner", "pkg/acp_client.py", "acp_client_process_group")
    child_pid_path = tmp_path / "child.pid"
    script = tmp_path / "process_tree.py"
    script.write_text(
        "\n".join(
            [
                "import subprocess",
                "import sys",
                "import time",
                "from pathlib import Path",
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])",
                f"Path({str(child_pid_path)!r}).write_text(str(child.pid), encoding='utf-8')",
                "time.sleep(60)",
            ]
        ),
        encoding="utf-8",
    )

    async def exercise():
        client = module.AcpStdioClient(command=sys.executable, args=[str(script)])
        await client.start()
        for _ in range(100):
            if child_pid_path.exists():
                break
            await asyncio.sleep(0.01)
        assert child_pid_path.exists()
        parent_pid = client.process.pid
        child_pid = int(child_pid_path.read_text(encoding="utf-8"))
        await client.close()
        return parent_pid, child_pid

    parent_pid, child_pid = asyncio.run(exercise())

    for pid in (parent_pid, child_pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        raise AssertionError(f"ACP process {pid} survived client.close()")


def test_acp_client_unsets_child_environment(tmp_path: Path, monkeypatch) -> None:
    module = _load_plugin_module("acp-agent-runner", "pkg/acp_client.py", "acp_client_unset_env")
    output_path = tmp_path / "env.txt"
    script = tmp_path / "print_env.py"
    script.write_text(
        "\n".join(
            [
                "import os",
                "from pathlib import Path",
                f"Path({str(output_path)!r}).write_text(",
                "    os.environ.get('CLAUDE_CODE_COORDINATOR_MODE', 'missing'),",
                "    encoding='utf-8',",
                ")",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CODE_COORDINATOR_MODE", "1")

    async def exercise():
        client = module.AcpStdioClient(
            command=sys.executable,
            args=[str(script)],
            env={"CLAUDE_CODE_COORDINATOR_MODE": "1"},
            unset_env=["CLAUDE_CODE_COORDINATOR_MODE"],
        )
        await client.start()
        await client.process.wait()
        await client.close()

    asyncio.run(exercise())

    assert output_path.read_text(encoding="utf-8") == "missing"


def test_acp_remote_shell_unsets_claude_coordination_modes() -> None:
    module = _load_runner_module("acp-agent-runner")

    command = module._remote_shell_command(
        remote_shell="bash",
        workspace="/workspace",
        acp_command="npx -y @agentclientprotocol/claude-agent-acp",
        unset_env=module.CLAUDE_ENV_VARS_TO_UNSET,
    )

    assert "env -u CLAUDE_CODE_COORDINATOR_MODE -u ENABLE_TOOL_SEARCH" in command


def test_acp_remote_shell_applies_configured_environment_after_login_shell() -> None:
    module = _load_runner_module("acp-agent-runner")

    command = module._remote_shell_command(
        remote_shell="bash",
        workspace="/workspace",
        acp_command="npx -y @agentclientprotocol/claude-agent-acp",
        env={"HTTP_PROXY": "", "LANGBOT_TEST_VALUE": "configured"},
    )

    shell_argv = shlex.split(command)
    assert shell_argv[:2] == ["bash", "-lc"]
    script = shell_argv[2]
    assert "export HTTP_PROXY=''" in script
    assert "export LANGBOT_TEST_VALUE=configured" in script
    assert script.index("export HTTP_PROXY='' ") < script.index("mkdir -p /workspace")


class _CompletedAcpRequest:
    def __init__(self) -> None:
        self.future = asyncio.get_running_loop().create_future()
        self.future.set_result({"stopReason": "end_turn"})

    async def wait(self, timeout=None):
        return self.future.result()


class _QueuedAcpClient:
    def __init__(self, updates):
        self.updates = list(updates)

    def send_request(self, method, params):
        assert method == "session/prompt"
        return _CompletedAcpRequest()

    def next_update_nowait(self):
        return self.updates.pop(0) if self.updates else None


def _acp_message_update(message_id: str, text: str) -> dict:
    return {
        "update": {
            "sessionUpdate": "agent_message_chunk",
            "messageId": message_id,
            "content": {"type": "text", "text": text},
        }
    }


def test_acp_runner_uses_latest_agent_message_as_final_answer() -> None:
    module = _load_runner_module("acp-agent-runner")
    runner = object.__new__(module.DefaultRunner)
    client = _QueuedAcpClient(
        [
            _acp_message_update("message-1", "Working"),
            _acp_message_update("message-1", "..."),
            _acp_message_update("message-2", "FINAL_ONLY"),
        ]
    )

    async def exercise():
        results = []
        async for result in runner._stream_prompt_results(
            client,
            types.SimpleNamespace(run_id="run-1"),
            "session-1",
            [{"type": "text", "text": "test"}],
            timeout=1.0,
            streaming=True,
        ):
            results.append(result)
        return results

    results = asyncio.run(exercise())
    deltas = [result.data["chunk"] for result in results if result.type == "message.delta"]

    assert [chunk["all_content"] for chunk in deltas] == ["Working", "Working...", "FINAL_ONLY"]
    assert results[-2].type == "message.completed"
    assert results[-2].data["message"]["content"] == "FINAL_ONLY"
    assert results[-1].type == "run.completed"


def test_acp_daemon_uses_latest_agent_message_as_final_answer() -> None:
    module = _load_plugin_module("acp-agent-runner", "daemon.py", "daemon_message_boundaries")
    daemon = object.__new__(module.RunnerDaemon)
    events = []

    async def fake_emit(job_id, event):
        events.append(event)

    daemon.emit_event = fake_emit
    client = _QueuedAcpClient(
        [
            _acp_message_update("message-1", "Working"),
            _acp_message_update("message-2", "FINAL_ONLY"),
        ]
    )

    asyncio.run(
        daemon._stream_prompt_results(
            client,
            "job-1",
            "session-1",
            [{"type": "text", "text": "test"}],
            {"timeout": 1.0, "streaming": True},
        )
    )

    deltas = [event["data"]["chunk"] for event in events if event["type"] == "message.delta"]
    assert [chunk["all_content"] for chunk in deltas] == ["Working", "FINAL_ONLY"]
    assert events[-2] == {
        "type": "message.completed",
        "data": {"message": {"role": "assistant", "content": "FINAL_ONLY"}},
    }
    assert events[-1] == {"type": "run.completed", "data": {"finish_reason": "stop"}}


def test_acp_daemon_tool_events_match_agent_run_result_schema() -> None:
    import asyncio

    from langbot_plugin.api.entities.builtin.runner import RunnerResult

    module = _load_plugin_module("acp-agent-runner", "daemon.py", "daemon")
    daemon = object.__new__(module.RunnerDaemon)
    events = []

    async def fake_emit(job_id, event):
        events.append((job_id, event))

    daemon.emit_event = fake_emit

    asyncio.run(
        daemon._emit_tool_update(
            "job-1",
            {"toolCallId": "tool-1", "name": "read_file", "status": "pending"},
            {},
        )
    )

    assert events == [
        (
            "job-1",
            {
                "type": "tool.call.started",
                "data": {
                    "tool_call_id": "tool-1",
                    "tool_name": "read_file",
                    "parameters": {},
                },
            },
        )
    ]

    event = dict(events[0][1])
    event["run_id"] = "run-1"
    RunnerResult.model_validate(event)


def test_acp_daemon_tool_events_keep_stable_name_across_updates() -> None:
    module = _load_plugin_module("acp-agent-runner", "daemon.py", "daemon")
    daemon = object.__new__(module.RunnerDaemon)
    events = []

    async def fake_emit(job_id, event):
        events.append((job_id, event))

    daemon.emit_event = fake_emit
    active_tool_calls = {}

    async def emit_lifecycle() -> None:
        await daemon._emit_tool_update(
            "job-1",
            {
                "_meta": {"claudeCode": {"toolName": "Read"}},
                "toolCallId": "tool-1",
                "title": "Read TASK.md",
                "status": "pending",
            },
            active_tool_calls,
        )
        await daemon._emit_tool_update(
            "job-1",
            {
                "_meta": {"claudeCode": {"toolName": "Read"}},
                "toolCallId": "tool-1",
                "status": "completed",
                "rawOutput": "contents",
            },
            active_tool_calls,
        )

    asyncio.run(emit_lifecycle())

    assert [event[1]["type"] for event in events] == [
        "tool.call.started",
        "tool.call.completed",
    ]
    assert [event[1]["data"]["tool_name"] for event in events] == ["Read", "Read"]
    assert active_tool_calls == {"tool-1": "Read"}


def test_acp_runner_uses_sdk_mcp_bridge_helper(monkeypatch) -> None:
    module = _load_runner_module("acp-agent-runner")
    calls = {}

    class FakeAccess:
        def __init__(
            self,
            api,
            ctx,
            *,
            enabled,
            location,
            mode,
            transport,
            bridge_host,
            bridge_port,
            bridge_public_url,
            bridge_request_timeout,
            gateway_host,
            gateway_port,
            gateway_public_url,
            gateway_request_timeout,
            gateway_token_ttl,
        ):
            calls["api"] = api
            calls["ctx"] = ctx
            calls["enabled"] = enabled
            calls["location"] = location
            calls["mode"] = mode
            calls["transport"] = transport
            calls["bridge_host"] = bridge_host
            calls["bridge_port"] = bridge_port
            calls["bridge_public_url"] = bridge_public_url
            calls["bridge_request_timeout"] = bridge_request_timeout
            calls["gateway_host"] = gateway_host
            calls["gateway_port"] = gateway_port
            calls["gateway_public_url"] = gateway_public_url
            calls["gateway_request_timeout"] = gateway_request_timeout
            calls["gateway_token_ttl"] = gateway_token_ttl
            self.server_config = module.AgentMCPServerConfig.stdio(
                name="langbot_agent",
                command="python",
                args=["-m", "langbot_plugin.api.agent_tools.mcp_stdio"],
                env={"LANGBOT_AGENT_MCP_ENDPOINT": "http://127.0.0.1:12345"},
            )
            self.reverse_tunnel = None

        def start(self):
            calls["started"] = True

    runner = object.__new__(module.DefaultRunner)
    runner.get_run_api = lambda ctx: "run-api"
    ctx = object()

    monkeypatch.setattr(module, "AgentRunMCPAccess", FakeAccess)
    access, servers = runner._mcp_servers(
        ctx,
        {
            "mcp_servers": [],
            "mcp_bridge_enabled": True,
            "mcp_bridge_transport": "stdio",
            "mcp_bridge_host": "127.0.0.1",
            "mcp_bridge_port": 0,
            "mcp_bridge_request_timeout": 15.0,
            "mcp_public_url": "",
            "location": "local",
            "langbot_assets_mode": "ephemeral",
            "asset_gateway_host": "127.0.0.1",
            "asset_gateway_port": 0,
            "asset_gateway_request_timeout": 60.0,
            "asset_gateway_token_ttl": 3600.0,
            "asset_gateway_public_url": "",
        },
    )

    assert isinstance(access, FakeAccess)
    assert calls == {
        "api": "run-api",
        "ctx": ctx,
        "enabled": True,
        "location": "local",
        "mode": "ephemeral",
        "transport": "stdio",
        "bridge_host": "127.0.0.1",
        "bridge_port": 0,
        "bridge_public_url": "",
        "bridge_request_timeout": 15.0,
        "gateway_host": "127.0.0.1",
        "gateway_port": 0,
        "gateway_public_url": "",
        "gateway_request_timeout": 60.0,
        "gateway_token_ttl": 3600.0,
        "started": True,
    }
    assert servers == [
        {
            "name": "langbot_agent",
            "type": "stdio",
            "command": "python",
            "args": ["-m", "langbot_plugin.api.agent_tools.mcp_stdio"],
            "env": [{"name": "LANGBOT_AGENT_MCP_ENDPOINT", "value": "http://127.0.0.1:12345"}],
        }
    ]


def test_acp_runner_can_use_sdk_asset_gateway(monkeypatch) -> None:
    module = _load_runner_module("acp-agent-runner")
    calls = {}

    class FakeAccess:
        def __init__(
            self,
            api,
            ctx,
            *,
            enabled,
            location,
            mode,
            transport,
            bridge_host,
            bridge_port,
            bridge_public_url,
            bridge_request_timeout,
            gateway_host,
            gateway_port,
            gateway_public_url,
            gateway_request_timeout,
            gateway_token_ttl,
        ):
            calls["api"] = api
            calls["ctx"] = ctx
            calls["enabled"] = enabled
            calls["location"] = location
            calls["mode"] = mode
            calls["transport"] = transport
            calls["bridge_host"] = bridge_host
            calls["bridge_port"] = bridge_port
            calls["bridge_public_url"] = bridge_public_url
            calls["bridge_request_timeout"] = bridge_request_timeout
            calls["gateway_host"] = gateway_host
            calls["gateway_port"] = gateway_port
            calls["gateway_public_url"] = gateway_public_url
            calls["gateway_request_timeout"] = gateway_request_timeout
            calls["gateway_token_ttl"] = gateway_token_ttl
            self.server_config = module.AgentMCPServerConfig.http(
                name="langbot_agent",
                url=gateway_public_url,
                headers={"Authorization": "Bearer token_1"},
            )
            self.reverse_tunnel = None

        def start(self):
            calls["started"] = True

    runner = object.__new__(module.DefaultRunner)
    runner.get_run_api = lambda ctx: "run-api"
    ctx = object()

    monkeypatch.setattr(module, "AgentRunMCPAccess", FakeAccess)
    access, servers = runner._mcp_servers(
        ctx,
        {
            "mcp_servers": [],
            "mcp_bridge_enabled": True,
            "mcp_bridge_transport": "auto",
            "mcp_bridge_host": "127.0.0.1",
            "mcp_bridge_port": 0,
            "mcp_bridge_request_timeout": 15.0,
            "mcp_public_url": "",
            "location": "local",
            "langbot_assets_mode": "gateway",
            "asset_gateway_host": "127.0.0.1",
            "asset_gateway_port": 8765,
            "asset_gateway_request_timeout": 12.0,
            "asset_gateway_token_ttl": 120.0,
            "asset_gateway_public_url": "http://gateway.example/mcp",
        },
    )

    assert isinstance(access, FakeAccess)
    assert calls == {
        "api": "run-api",
        "ctx": ctx,
        "enabled": True,
        "location": "local",
        "mode": "gateway",
        "transport": "auto",
        "bridge_host": "127.0.0.1",
        "bridge_port": 0,
        "bridge_public_url": "",
        "bridge_request_timeout": 15.0,
        "gateway_host": "127.0.0.1",
        "gateway_port": 8765,
        "gateway_public_url": "http://gateway.example/mcp",
        "gateway_request_timeout": 12.0,
        "gateway_token_ttl": 120.0,
        "started": True,
    }
    assert servers == [
        {
            "name": "langbot_agent",
            "type": "http",
            "url": "http://gateway.example/mcp",
            "headers": [{"name": "Authorization", "value": "Bearer token_1"}],
        }
    ]


def _native_ctx(
    config: dict,
    *,
    text: str = "hello native",
    conversation_state: dict | None = None,
    interaction: InteractionSubmission | None = None,
) -> RunnerContext:
    return RunnerContext(
        run_id="run_native",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="evt_1", event_type="message.received", source="test"),
        input=AgentInput(text=text, interaction=interaction),
        delivery=DeliveryContext(surface="test"),
        resources=AgentResources(),
        state=AgentRunState(conversation=conversation_state or {}),
        runtime=AgentRuntimeContext(),
        config=config,
    )


def _write_fake_native_cli(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import json",
                "import os",
                "import sys",
                "session_id = 'missing-session'",
                "if '--session-id' in sys.argv:",
                "    session_id = sys.argv[sys.argv.index('--session-id') + 1]",
                "prompt = sys.stdin.read()",
                "if 'hello native' in sys.argv:",
                "    print('prompt leaked into argv', file=sys.stderr)",
                "    raise SystemExit(2)",
                "if '--mcp-config' in sys.argv:",
                "    config_path = sys.argv[sys.argv.index('--mcp-config') + 1]",
                "    if config_path.startswith('{'):",
                "        print('mcp config passed as raw json', file=sys.stderr)",
                "        raise SystemExit(3)",
                "    if os.name != 'nt' and os.stat(config_path).st_mode & 0o777 != 0o600:",
                "        print('mcp config mode is not 0600', file=sys.stderr)",
                "        raise SystemExit(4)",
                "    config = open(config_path, encoding='utf-8').read()",
                "    servers = json.loads(config).get('mcpServers', {})",
                "    if len(servers) > 1 and 'Bearer test-secret-token' not in config:",
                "        print('mcp config file missing expected token', file=sys.stderr)",
                "        raise SystemExit(5)",
                "    if 'Bearer test-secret-token' in ' '.join(sys.argv):",
                "        print('mcp token leaked into argv', file=sys.stderr)",
                "        raise SystemExit(6)",
                "print(json.dumps({'type': 'session.started', 'session_id': session_id}), flush=True)",
                "if 'ASK_INTERACTION' in prompt:",
                "    print(json.dumps({'type': 'assistant', 'session_id': session_id, 'message': {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'toolu-question-1', 'name': 'mcp__langbot_agent__ask_user_question', 'input': {'title': 'Need details', 'questions': [{'id': 'environment', 'question': 'Choose an environment', 'options': [{'label': 'staging', 'description': 'Use staging'}, {'label': 'production', 'description': 'Use production'}], 'multiSelect': False}]}}]}}), flush=True)",
                "    print(json.dumps({'type': 'message.completed', 'text': 'WAITING_FOR_INTERACTION'}), flush=True)",
                "else:",
                "    print(json.dumps({'type': 'message.completed', 'text': 'FAKE_NATIVE_OK:' + prompt}), flush=True)",
            ]
        ),
        encoding="utf-8",
    )


def _write_fake_codex_app_server(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import json",
                "import sys",
                "thread_id = 'thread-123'",
                "pending_approval_prompt = ''",
                "def send(payload):",
                "    print(json.dumps(payload), flush=True)",
                "for line in sys.stdin:",
                "    request = json.loads(line)",
                "    method = request.get('method')",
                "    request_id = request.get('id')",
                "    params = request.get('params') or {}",
                "    if request_id == 701 and method is None and pending_approval_prompt:",
                "        decision = (request.get('result') or {}).get('decision')",
                "        if decision == 'accept':",
                "            send({'jsonrpc': '2.0', 'method': 'item/completed', 'params': {'threadId': thread_id, 'item': {'id': 'command-1', 'type': 'commandExecution', 'command': 'Write approval-probe.txt', 'cwd': '.', 'commandActions': [], 'status': 'completed', 'aggregatedOutput': 'created'}}})",
                "            send({'jsonrpc': '2.0', 'method': 'item/completed', 'params': {'threadId': thread_id, 'item': {'id': 'approval-result', 'type': 'agentMessage', 'text': 'APPROVAL_EXECUTED', 'phase': 'final_answer'}}})",
                "            send({'jsonrpc': '2.0', 'method': 'turn/completed', 'params': {'threadId': thread_id, 'turn': {'id': 'turn-approval', 'status': 'completed'}}})",
                "        pending_approval_prompt = ''",
                "        continue",
                "    if request_id is not None and method == 'initialize':",
                "        send({'jsonrpc': '2.0', 'id': request_id, 'result': {}})",
                "    elif method == 'initialized':",
                "        pass",
                "    elif request_id is not None and method == 'thread/resume':",
                "        thread_id = params.get('threadId') or thread_id",
                "        send({'jsonrpc': '2.0', 'id': request_id, 'result': {'threadId': thread_id}})",
                "    elif request_id is not None and method == 'thread/start':",
                "        approval_pair = (params.get('approvalPolicy'), params.get('sandbox'))",
                "        if approval_pair not in {('never', 'danger-full-access'), ('on-request', 'read-only')}:",
                "            send({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32602, 'message': 'interactive approval is not disabled'}})",
                "        else:",
                "            send({'jsonrpc': '2.0', 'id': request_id, 'result': {'threadId': thread_id}})",
                "    elif request_id is not None and method == 'turn/start':",
                "        prompt = params.get('input', [{}])[0].get('text', '')",
                "        send({'jsonrpc': '2.0', 'id': request_id, 'result': {}})",
                "        send({'jsonrpc': '2.0', 'method': 'turn/started', 'params': {'threadId': thread_id, 'turn': {'id': 'turn-1'}}})",
                "        if 'rejected the previously paused Codex operation' in prompt:",
                "            send({'jsonrpc': '2.0', 'method': 'item/completed', 'params': {'threadId': thread_id, 'item': {'id': 'rejection-result', 'type': 'agentMessage', 'text': 'APPROVAL_REJECTED', 'phase': 'final_answer'}}})",
                "            send({'jsonrpc': '2.0', 'method': 'turn/completed', 'params': {'threadId': thread_id, 'turn': {'id': 'turn-rejected', 'status': 'completed'}}})",
                "            continue",
                "        if 'TRIGGER_COMMAND_APPROVAL' in prompt or 'approved exactly one retry' in prompt:",
                "            pending_approval_prompt = prompt",
                "            send({'jsonrpc': '2.0', 'method': 'item/started', 'params': {'threadId': thread_id, 'item': {'id': 'command-1', 'type': 'commandExecution', 'command': 'Write approval-probe.txt', 'cwd': '.', 'commandActions': [], 'status': 'inProgress'}}})",
                "            send({'jsonrpc': '2.0', 'id': 701, 'method': 'item/commandExecution/requestApproval', 'params': {'threadId': thread_id, 'turnId': 'turn-approval', 'itemId': 'command-1', 'startedAtMs': 1700000000000, 'command': 'Write approval-probe.txt', 'cwd': '.', 'reason': 'Create the requested test file'}})",
                "            continue",
                "        if 'ASK_INTERACTION' in prompt:",
                "            send({'jsonrpc': '2.0', 'id': 700, 'method': 'item/tool/call', 'params': {'threadId': thread_id, 'turnId': 'turn-1', 'callId': 'call-question-1', 'tool': 'ask_user_question', 'arguments': {'title': 'Need details', 'questions': [{'id': 'environment', 'question': 'Choose an environment', 'options': [{'label': 'staging', 'value': 'staging'}, {'label': 'production', 'value': 'production'}]}]}}})",
                "            continue",
                "        if 'INTERMEDIATE_THEN_FINAL' in prompt:",
                "            send({'jsonrpc': '2.0', 'method': 'item/completed', 'params': {'threadId': thread_id, 'item': {'id': 'progress-1', 'type': 'agentMessage', 'text': 'working...', 'phase': 'commentary'}}})",
                "            send({'jsonrpc': '2.0', 'method': 'item/completed', 'params': {'threadId': thread_id, 'item': {'id': 'final-1', 'type': 'agentMessage', 'text': 'FINAL_ONLY', 'phase': 'final_answer'}}})",
                "            send({'jsonrpc': '2.0', 'method': 'turn/completed', 'params': {'threadId': thread_id, 'turn': {'id': 'turn-1', 'status': 'completed'}}})",
                "            continue",
                "        send({'jsonrpc': '2.0', 'method': 'item/completed', 'params': {'threadId': thread_id, 'item': {'id': 'item-1', 'type': 'agentMessage', 'text': 'FAKE_CODEX_APP_SERVER_OK:' + prompt, 'phase': 'final_answer'}}})",
                "        send({'jsonrpc': '2.0', 'method': 'item/completed', 'params': {'threadId': thread_id, 'item': {'id': 'item-1', 'type': 'agentMessage', 'text': 'FAKE_CODEX_APP_SERVER_OK:' + prompt, 'phase': 'final_answer'}}})",
                "        send({'jsonrpc': '2.0', 'method': 'item/completed', 'params': {'threadId': thread_id, 'item': {'id': 'item-2', 'type': 'agentMessage', 'text': 'FAKE_CODEX_APP_SERVER_OK:' + prompt, 'phase': 'final_answer'}}})",
                "        send({'jsonrpc': '2.0', 'method': 'turn/completed', 'params': {'threadId': thread_id, 'turn': {'id': 'turn-1', 'status': 'completed'}}})",
            ]
        ),
        encoding="utf-8",
    )


def test_claude_code_runner_executes_fake_native_cli(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_native_cli.py"
    _write_fake_native_cli(fake_cli)
    module = _load_runner_module("claude-code-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None

    ctx = _native_ctx(
        {
            "location": "local",
            "command": sys.executable,
            "args-json": [str(fake_cli)],
            "workspace": str(tmp_path),
            "langbot-assets-enabled": False,
        }
    )
    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [item.type for item in results] == [
        "state.updated",
        "message.delta",
        "message.delta",
        "run.completed",
    ]
    assert results[1].data["chunk"]["content"] == "FAKE_NATIVE_OK:hello native"
    assert results[2].data["chunk"]["content"] == "FAKE_NATIVE_OK:hello native"
    assert results[2].data["chunk"]["is_final"] is True
    assert "message" not in results[3].data
    assert results[0].data["key"] == "external.claude_code_session_id"


def test_claude_code_runner_defaults_to_non_interactive_permissions(tmp_path: Path) -> None:
    module = _load_runner_module("claude-code-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}

    config = runner._validate_config(
        _native_ctx(
            {
                "location": "local",
                "workspace": str(tmp_path),
                "langbot-assets-enabled": False,
            }
        )
    )

    assert config["dangerously_skip_permissions"] is True
    argv = runner._argv(config, session_id="session-1", mcp_config_path="/tmp/mcp.json", resume=False)
    assert argv.count("--dangerously-skip-permissions") == 1
    assert argv[argv.index("--allowedTools") + 1] == "ToolSearch,mcp__langbot_agent__*"
    system_prompt = argv[argv.index("--append-system-prompt") + 1]
    assert "ToolSearch-then-call flow" in system_prompt
    assert "In coordinator mode" in system_prompt
    assert "delegate the MCP request to one worker" in system_prompt


def test_claude_code_runner_can_restore_interactive_permissions(tmp_path: Path) -> None:
    module = _load_runner_module("claude-code-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}

    config = runner._validate_config(
        _native_ctx(
            {
                "location": "local",
                "workspace": str(tmp_path),
                "dangerously-skip-permissions": False,
                "langbot-assets-enabled": False,
            }
        )
    )

    assert config["dangerously_skip_permissions"] is False
    argv = runner._argv(config, session_id="session-1", mcp_config_path="", resume=False)
    assert "--dangerously-skip-permissions" not in argv


def test_claude_code_runner_resumes_an_existing_session(tmp_path: Path) -> None:
    module = _load_runner_module("claude-code-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    config = runner._validate_config(
        _native_ctx(
            {
                "location": "local",
                "workspace": str(tmp_path),
                "langbot-assets-enabled": False,
            }
        )
    )

    argv = runner._argv(config, session_id="session-1", mcp_config_path="", resume=True)

    assert argv[argv.index("--resume") + 1] == "session-1"
    assert "--session-id" not in argv


def test_claude_code_runner_passes_mcp_config_by_temp_file(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_native_cli.py"
    _write_fake_native_cli(fake_cli)
    module = _load_runner_module("claude-code-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None

    ctx = _native_ctx(
        {
            "location": "local",
            "command": sys.executable,
            "args-json": [str(fake_cli)],
            "workspace": str(tmp_path),
            "langbot-assets-enabled": False,
            "mcp-servers-json": [
                {
                    "name": "langbot",
                    "type": "http",
                    "url": "http://127.0.0.1:1234/mcp",
                    "headers": {"Authorization": "Bearer test-secret-token"},
                }
            ],
        }
    )
    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [item.type for item in results] == [
        "state.updated",
        "message.delta",
        "message.delta",
        "run.completed",
    ]
    assert results[1].data["chunk"]["content"] == "FAKE_NATIVE_OK:hello native"
    assert results[2].data["chunk"]["content"] == "FAKE_NATIVE_OK:hello native"
    assert results[2].data["chunk"]["is_final"] is True
    assert "message" not in results[3].data


def test_claude_code_runner_uses_terminal_result_as_clean_final_text(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_claude_result.py"
    fake_cli.write_text(
        "\n".join(
            [
                "import json",
                "print(json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'working...'}]}}))",
                "print(json.dumps({'type': 'result', 'subtype': 'success', 'result': 'FINAL_ONLY'}))",
            ]
        ),
        encoding="utf-8",
    )
    module = _load_runner_module("claude-code-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None
    ctx = _native_ctx(
        {
            "location": "local",
            "command": sys.executable,
            "args-json": [str(fake_cli)],
            "workspace": str(tmp_path),
            "langbot-assets-enabled": False,
        }
    )

    results = asyncio.run(_collect_async(runner.run(ctx)))

    deltas = [item.data["chunk"] for item in results if item.type == "message.delta"]
    assert [chunk["content"] for chunk in deltas] == ["working...", "FINAL_ONLY"]
    assert deltas[-1]["all_content"] == "FINAL_ONLY"
    assert deltas[-1]["is_final"] is True
    assert results[-1].type == "run.completed"


def test_claude_code_runner_non_streaming_emits_one_message(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_native_cli.py"
    _write_fake_native_cli(fake_cli)
    module = _load_runner_module("claude-code-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None

    ctx = _native_ctx(
        {
            "location": "local",
            "command": sys.executable,
            "args-json": [str(fake_cli)],
            "workspace": str(tmp_path),
            "langbot-assets-enabled": False,
            "streaming": False,
        }
    )
    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [item.type for item in results] == [
        "state.updated",
        "message.completed",
        "run.completed",
    ]
    assert results[1].data["message"]["content"] == "FAKE_NATIVE_OK:hello native"
    assert "message" not in results[2].data


def test_claude_code_runner_pauses_for_question_and_resumes_with_tool_result(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_native_cli.py"
    _write_fake_native_cli(fake_cli)
    module = _load_runner_module("claude-code-agent")
    native = sys.modules["pkg.native_cli"]
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None
    config = {
        "location": "local",
        "command": sys.executable,
        "args-json": [str(fake_cli)],
        "workspace": str(tmp_path),
        "langbot-assets-enabled": False,
    }

    paused = asyncio.run(_collect_async(runner.run(_native_ctx(config, text="ASK_INTERACTION"))))

    assert [item.type for item in paused] == ["state.updated", "state.updated", "action.requested"]
    pending = paused[1].data["value"]
    request = paused[2].data["payload"]
    assert paused[2].data["action"] == "interaction.requested"
    assert request["fields"][0]["type"] == "select"
    assert request["fields"][0]["label"] == "Choose an environment"

    resumed = asyncio.run(
        _collect_async(
            runner.run(
                _native_ctx(
                    config,
                    conversation_state={
                        native.SESSION_STATE_KEY: "fake-session",
                        native.PENDING_INTERACTION_STATE_KEY: pending,
                    },
                    interaction=InteractionSubmission(
                        interaction_id=request["interaction_id"],
                        action_id="submit",
                        values={"environment": "staging"},
                    ),
                )
            )
        )
    )

    assert resumed[0].data == {
        "key": native.PENDING_INTERACTION_STATE_KEY,
        "value": None,
        "scope": "conversation",
    }
    assert resumed[-1].type == "run.completed"
    message_text = "".join(
        str(item.data.get("chunk", {}).get("content") or "") for item in resumed if item.type == "message.delta"
    )
    assert "authoritative response" in message_text
    assert '"answer": "staging"' in message_text


def test_codex_runner_executes_fake_native_cli(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_codex_app_server.py"
    _write_fake_codex_app_server(fake_cli)
    module = _load_runner_module("codex-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None

    ctx = _native_ctx(
        {
            "location": "local",
            "command": f"{sys.executable} {fake_cli}",
            "workspace": str(tmp_path),
            "langbot-assets-enabled": False,
        }
    )
    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [item.type for item in results] == [
        "state.updated",
        "message.delta",
        "run.completed",
    ]
    assert results[1].data["chunk"]["content"] == "FAKE_CODEX_APP_SERVER_OK:hello native"
    assert results[1].data["chunk"]["is_final"] is True
    assert "message" not in results[2].data
    assert results[0].data["key"] == "external.codex_session_id"
    assert results[0].data["value"] == "thread-123"
    assert [item.sequence for item in results] == [1, 2, 3]


def test_codex_runner_final_answer_replaces_intermediate_text(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_codex_app_server.py"
    _write_fake_codex_app_server(fake_cli)
    module = _load_runner_module("codex-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None
    ctx = _native_ctx(
        {
            "location": "local",
            "command": f"{sys.executable} {fake_cli}",
            "workspace": str(tmp_path),
            "langbot-assets-enabled": False,
        },
        text="INTERMEDIATE_THEN_FINAL",
    )

    results = asyncio.run(_collect_async(runner.run(ctx)))

    deltas = [item.data["chunk"] for item in results if item.type == "message.delta"]
    assert [chunk["content"] for chunk in deltas] == ["working...", "FINAL_ONLY"]
    assert deltas[-1]["all_content"] == "FINAL_ONLY"
    assert deltas[-1]["is_final"] is True
    assert results[-1].type == "run.completed"


def test_codex_runner_defaults_to_non_interactive_full_access(tmp_path: Path) -> None:
    module = _load_runner_module("codex-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}

    config = runner._validate_config(
        _native_ctx(
            {
                "location": "local",
                "workspace": str(tmp_path),
                "langbot-assets-enabled": False,
            }
        )
    )

    assert config["approval_policy"] == "never"
    assert config["sandbox_mode"] == "danger-full-access"


def test_codex_runner_pauses_for_dynamic_question_and_resumes_thread(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_codex_app_server.py"
    _write_fake_codex_app_server(fake_cli)
    module = _load_runner_module("codex-agent")
    native = sys.modules["pkg.native_cli"]
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None
    config = {
        "location": "local",
        "command": f"{sys.executable} {fake_cli}",
        "workspace": str(tmp_path),
        "langbot-assets-enabled": False,
        "approval-policy": "on-request",
        "sandbox-mode": "read-only",
    }

    paused = asyncio.run(_collect_async(runner.run(_native_ctx(config, text="ASK_INTERACTION"))))

    assert [item.type for item in paused] == ["state.updated", "state.updated", "action.requested"]
    pending = paused[1].data["value"]
    request = paused[2].data["payload"]
    assert paused[2].data["action"] == "interaction.requested"
    assert request["fields"][0]["type"] == "select"
    assert pending["provider_call_id"] == "call-question-1"

    resumed = asyncio.run(
        _collect_async(
            runner.run(
                _native_ctx(
                    config,
                    conversation_state={
                        native.SESSION_STATE_KEY: "thread-123",
                        native.PENDING_INTERACTION_STATE_KEY: pending,
                    },
                    interaction=InteractionSubmission(
                        interaction_id=request["interaction_id"],
                        action_id="submit",
                        values={"environment": "production"},
                    ),
                )
            )
        )
    )

    assert resumed[0].data["key"] == native.PENDING_INTERACTION_STATE_KEY
    assert resumed[0].data["value"] is None
    assert resumed[-1].type == "run.completed"
    assert any(
        "production" in str(item.data.get("chunk", {}).get("content") or "")
        for item in resumed
        if item.type == "message.delta"
    )


def test_codex_runner_pauses_for_native_approval_and_approves_exact_retry(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_codex_app_server.py"
    _write_fake_codex_app_server(fake_cli)
    module = _load_runner_module("codex-agent")
    native = sys.modules["pkg.native_cli"]
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None
    config = {
        "location": "local",
        "command": f"{sys.executable} {fake_cli}",
        "workspace": str(tmp_path),
        "langbot-assets-enabled": False,
        "approval-policy": "on-request",
        "sandbox-mode": "read-only",
    }

    paused = asyncio.run(_collect_async(runner.run(_native_ctx(config, text="TRIGGER_COMMAND_APPROVAL"))))

    assert [item.type for item in paused] == ["state.updated", "state.updated", "action.requested"]
    pending = paused[1].data["value"]
    request = paused[2].data["payload"]
    assert pending["kind"] == "approval"
    assert pending["approval_category"] == "command"
    assert request["kind"] == "confirmation"
    assert request["fields"] == []
    assert [action["id"] for action in request["actions"]] == ["approve_once", "reject"]
    assert "Write approval-probe.txt" in request["description"]

    resumed = asyncio.run(
        _collect_async(
            runner.run(
                _native_ctx(
                    config,
                    conversation_state={
                        native.SESSION_STATE_KEY: "thread-123",
                        native.PENDING_INTERACTION_STATE_KEY: pending,
                    },
                    interaction=InteractionSubmission(
                        interaction_id=request["interaction_id"],
                        action_id="approve_once",
                    ),
                )
            )
        )
    )

    assert resumed[0].data["key"] == native.PENDING_INTERACTION_STATE_KEY
    assert resumed[0].data["value"] is None
    assert resumed[-1].type == "run.completed"
    assert any(
        "APPROVAL_EXECUTED" in str(item.data.get("chunk", {}).get("content") or "")
        for item in resumed
        if item.type == "message.delta"
    )


def test_codex_runner_resumes_after_native_approval_rejection(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_codex_app_server.py"
    _write_fake_codex_app_server(fake_cli)
    module = _load_runner_module("codex-agent")
    native = sys.modules["pkg.native_cli"]
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None
    config = {
        "location": "local",
        "command": f"{sys.executable} {fake_cli}",
        "workspace": str(tmp_path),
        "langbot-assets-enabled": False,
        "approval-policy": "on-request",
        "sandbox-mode": "read-only",
    }
    paused = asyncio.run(_collect_async(runner.run(_native_ctx(config, text="TRIGGER_COMMAND_APPROVAL"))))
    pending = paused[1].data["value"]
    request = paused[2].data["payload"]

    resumed = asyncio.run(
        _collect_async(
            runner.run(
                _native_ctx(
                    config,
                    conversation_state={
                        native.SESSION_STATE_KEY: "thread-123",
                        native.PENDING_INTERACTION_STATE_KEY: pending,
                    },
                    interaction=InteractionSubmission(
                        interaction_id=request["interaction_id"],
                        action_id="reject",
                    ),
                )
            )
        )
    )

    assert resumed[-1].type == "run.completed"
    assert any(
        "APPROVAL_REJECTED" in str(item.data.get("chunk", {}).get("content") or "")
        for item in resumed
        if item.type == "message.delta"
    )


def test_codex_approval_fingerprint_changes_with_operation() -> None:
    _load_runner_module("codex-agent")
    native = sys.modules["pkg.native_cli"]
    category, first = native._approval_evidence(
        "item/commandExecution/requestApproval",
        {"command": "git status", "cwd": "K:/repo"},
        {},
    )
    _, second = native._approval_evidence(
        "item/commandExecution/requestApproval",
        {"command": "git push", "cwd": "K:/repo"},
        {},
    )

    assert native._approval_fingerprint(category, first) != native._approval_fingerprint(category, second)


def test_codex_runner_resolves_bare_windows_command_to_npm_cli(tmp_path: Path, monkeypatch) -> None:
    _load_runner_module("codex-agent")
    native = sys.modules["pkg.native_cli"]
    npm_root = tmp_path / "npm"
    npm_shim = npm_root / "codex.cmd"
    codex_js = npm_root / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    codex_js.parent.mkdir(parents=True)
    npm_shim.write_text("", encoding="utf-8")
    codex_js.write_text("", encoding="utf-8")

    def fake_which(command: str, *, path: str | None = None) -> str | None:
        del path
        if command == "codex.cmd":
            return str(npm_shim)
        if command == "node.exe":
            return "C:/node.exe"
        return None

    monkeypatch.setattr(native.os, "name", "nt")
    monkeypatch.setattr(native, "Path", type(tmp_path))
    monkeypatch.setattr(native.shutil, "which", fake_which)

    argv = native._resolve_local_codex_argv(
        ["codex", "app-server", "--listen", "stdio://"],
        {"PATH": "C:/fake"},
    )

    assert argv == ["C:/node.exe", str(codex_js), "app-server", "--listen", "stdio://"]


def test_codex_file_change_approval_uses_cached_item_details() -> None:
    _load_runner_module("codex-agent")
    native = sys.modules["pkg.native_cli"]
    request, continuation = native._interaction_from_codex_approval(
        "item/fileChange/requestApproval",
        {
            "threadId": "thread-123",
            "turnId": "turn-1",
            "itemId": "patch-1",
            "reason": "Update the requested configuration",
        },
        {
            "id": "patch-1",
            "type": "fileChange",
            "changes": [
                {"path": "config.yaml", "kind": {"type": "update"}},
                {"path": "README.md", "kind": {"type": "update"}},
            ],
        },
    )

    assert request.kind == "confirmation"
    assert "config.yaml" in str(request.description)
    assert "README.md" in str(request.description)
    assert continuation["approval_category"] == "file_change"
    assert len(continuation["approval_fingerprint"]) == 64


def test_codex_runner_non_streaming_emits_one_message(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_codex_app_server.py"
    _write_fake_codex_app_server(fake_cli)
    module = _load_runner_module("codex-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None

    ctx = _native_ctx(
        {
            "location": "local",
            "command": f"{sys.executable} {fake_cli}",
            "workspace": str(tmp_path),
            "langbot-assets-enabled": False,
            "streaming": False,
        }
    )
    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [item.type for item in results] == [
        "state.updated",
        "message.completed",
        "run.completed",
    ]
    assert results[1].data["message"]["content"] == "FAKE_CODEX_APP_SERVER_OK:hello native"
    assert "message" not in results[2].data
    assert [item.sequence for item in results] == [1, 2, 3]


def test_codex_app_server_auto_approves_permission_profile() -> None:
    module = _load_plugin_module("codex-agent", "pkg/native_cli.py", "native_cli_permissions")

    class CaptureStdin:
        def __init__(self) -> None:
            self.data = bytearray()

        def write(self, data: bytes) -> None:
            self.data.extend(data)

        async def drain(self) -> None:
            return None

    async def approve() -> dict:
        stdin = CaptureStdin()
        process = types.SimpleNamespace(stdin=stdin)
        client = module._CodexAppServerClient(
            process,
            streaming=True,
            approval_grant=None,
            approval_policy="never",
        )
        requested = {
            "fileSystem": {"read": ["/tmp/input"], "write": ["/tmp/output"]},
            "network": {"enabled": True},
        }
        await client.handle_server_request(
            {
                "jsonrpc": "2.0",
                "id": 41,
                "method": "item/permissions/requestApproval",
                "params": {"permissions": requested},
            }
        )
        return json.loads(stdin.data.decode("utf-8"))

    response = asyncio.run(approve())

    assert response == {
        "jsonrpc": "2.0",
        "id": 41,
        "result": {
            "permissions": {
                "fileSystem": {"read": ["/tmp/input"], "write": ["/tmp/output"]},
                "network": {"enabled": True},
            },
            "scope": "session",
            "strictAutoReview": False,
        },
    }


def test_codex_app_server_auto_approves_legacy_request_when_policy_is_never() -> None:
    module = _load_plugin_module("codex-agent", "pkg/native_cli.py", "native_cli_legacy_approval")

    class CaptureStdin:
        def __init__(self) -> None:
            self.data = bytearray()

        def write(self, data: bytes) -> None:
            self.data.extend(data)

        async def drain(self) -> None:
            return None

    async def approve() -> tuple[dict, object]:
        stdin = CaptureStdin()
        process = types.SimpleNamespace(stdin=stdin)
        client = module._CodexAppServerClient(
            process,
            streaming=True,
            approval_grant=None,
            approval_policy="never",
        )
        await client.handle_server_request(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "method": "item/commandExecution/requestApproval",
                "params": {"command": "touch probe.txt", "cwd": "/workspace"},
            }
        )
        return json.loads(stdin.data.decode("utf-8")), client.interaction_request

    response, interaction_request = asyncio.run(approve())

    assert response == {"jsonrpc": "2.0", "id": 42, "result": {"decision": "accept"}}
    assert interaction_request is None


def test_codex_local_home_is_unique_per_resumed_run(tmp_path: Path) -> None:
    module = _load_plugin_module("codex-agent", "pkg/native_cli.py", "native_cli_home")
    shared_home = tmp_path / "shared-codex"
    shared_home.mkdir()
    (shared_home / "auth.json").write_text("{}", encoding="utf-8")
    (shared_home / "sessions").mkdir()
    (shared_home / "sessions" / "shared-session.jsonl").write_text("session", encoding="utf-8")
    workspace = tmp_path / "workspace"

    env_one, _ = module._prepare_local_codex_home(
        str(workspace),
        "thread-123",
        {"CODEX_HOME": str(shared_home)},
        "",
    )
    first_home = Path(env_one["CODEX_HOME"])
    marker = first_home / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    env_two, _ = module._prepare_local_codex_home(
        str(workspace),
        "thread-123",
        {"CODEX_HOME": str(shared_home)},
        "",
    )
    second_home = Path(env_two["CODEX_HOME"])

    assert first_home != second_home
    assert first_home.exists()
    assert second_home.exists()
    assert marker.read_text(encoding="utf-8") == "keep"
    assert (first_home / "sessions" / "shared-session.jsonl").exists()
    assert (second_home / "sessions" / "shared-session.jsonl").exists()
    assert (shared_home / "sessions" / "shared-session.jsonl").read_text(encoding="utf-8") == "session"


def test_codex_detects_persisted_tool_calls_without_outputs(tmp_path: Path) -> None:
    module = _load_plugin_module("codex-agent", "pkg/native_cli.py", "native_cli_session_validation")
    shared_home = tmp_path / "shared-codex"
    sessions = shared_home / "sessions" / "2026" / "07" / "21"
    sessions.mkdir(parents=True)
    session_id = "thread-123"
    rollout = sessions / f"rollout-2026-07-21T20-00-00-{session_id}.jsonl"
    records = [
        {"payload": {"type": "custom_tool_call", "call_id": "call-complete"}},
        {"payload": {"type": "custom_tool_call_output", "call_id": "call-complete"}},
        {"payload": {"type": "function_call", "call_id": "call-pending"}},
    ]
    rollout.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )

    assert module._pending_session_tool_calls(shared_home, session_id) == {"call-pending"}


def test_codex_app_server_accepts_json_lines_larger_than_asyncio_default(tmp_path: Path) -> None:
    module = _load_plugin_module("codex-agent", "pkg/native_cli.py", "native_cli_large_line")
    fake_cli = tmp_path / "fake_codex_large_line.py"
    fake_cli.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "thread_id = 'thread-large-line'",
                "def send(payload):",
                "    print(json.dumps(payload), flush=True)",
                "for line in sys.stdin:",
                "    request = json.loads(line)",
                "    method = request.get('method')",
                "    request_id = request.get('id')",
                "    if request_id is not None and method == 'initialize':",
                "        send({'jsonrpc': '2.0', 'id': request_id, 'result': {}})",
                "    elif request_id is not None and method == 'thread/start':",
                "        send({'jsonrpc': '2.0', 'id': request_id, 'result': {'threadId': thread_id}})",
                "    elif request_id is not None and method == 'turn/start':",
                "        send({'jsonrpc': '2.0', 'id': request_id, 'result': {}})",
                "        send({'jsonrpc': '2.0', 'method': 'turn/started', 'params': {'threadId': thread_id}})",
                "        text = 'x' * 70000",
                "        send({'jsonrpc': '2.0', 'method': 'item/completed', 'params': {'threadId': thread_id, 'item': {'id': 'large', 'type': 'agentMessage', 'text': text, 'phase': 'final_answer'}}})",
                "        send({'jsonrpc': '2.0', 'method': 'turn/completed', 'params': {'threadId': thread_id, 'turn': {'status': 'completed'}}})",
            ]
        ),
        encoding="utf-8",
    )

    async def collect():
        return [
            event
            async for event in module._run_cli_process_events(
                sys.executable,
                [str(fake_cli), "app-server", "--listen", "stdio://"],
                cwd=str(tmp_path),
                env=dict(os.environ),
                timeout=10,
                streaming=True,
                resume_session_id="",
                prompt="hello",
                agent_cwd=str(tmp_path),
            )
        ]

    events = asyncio.run(collect())

    delta = next(event for event in events if event["type"] == "message.delta")
    assert len(delta["data"]["chunk"]["content"]) == 70000
    assert events[-1]["type"] == "run.completed"


def test_codex_remote_mcp_config_is_not_embedded_in_ssh_command() -> None:
    module = _load_plugin_module("codex-agent", "pkg/native_cli.py", "native_cli_remote")
    mcp_toml = module._mcp_config_toml(
        {
            "langbot": {
                "type": "http",
                "url": "http://127.0.0.1:1234/mcp",
                "headers": {"Authorization": "Bearer remote-secret-token"},
            }
        }
    )

    command = module._remote_shell_command(
        "/workspace",
        ["codex", "app-server", "--listen", "stdio://"],
        {},
        home_key="thread-123",
        read_mcp_from_stdin=True,
    )

    assert "remote-secret-token" not in command
    assert "Authorization" not in command
    assert b"remote-secret-token" not in module._remote_mcp_stdin_prelude(mcp_toml)


def test_native_cli_startup_failures_are_run_failed(tmp_path: Path) -> None:
    claude_module = _load_runner_module("claude-code-agent")
    claude_runner = object.__new__(claude_module.DefaultRunner)
    claude_runner.get_plugin_config = lambda: {}
    claude_runner.get_run_api = lambda ctx: None
    claude_results = asyncio.run(
        _collect_async(
            claude_runner.run(
                _native_ctx(
                    {
                        "location": "local",
                        "command": str(tmp_path / "missing-claude"),
                        "workspace": str(tmp_path),
                        "langbot-assets-enabled": False,
                    }
                )
            )
        )
    )

    assert [item.type for item in claude_results] == ["state.updated", "run.failed"]
    assert claude_results[-1].data["code"] == "claude_code.command_not_found"

    codex_module = _load_runner_module("codex-agent")
    codex_runner = object.__new__(codex_module.DefaultRunner)
    codex_runner.get_plugin_config = lambda: {}
    codex_runner.get_run_api = lambda ctx: None
    codex_results = asyncio.run(
        _collect_async(
            codex_runner.run(
                _native_ctx(
                    {
                        "location": "local",
                        "command": str(tmp_path / "missing-codex"),
                        "workspace": str(tmp_path),
                        "langbot-assets-enabled": False,
                    }
                )
            )
        )
    )

    assert [item.type for item in codex_results] == ["run.failed"]
    assert codex_results[0].data["code"] == "codex.command_not_found"


def test_claude_code_runner_redacts_stderr_secrets(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_secret_stderr.py"
    fake_cli.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import sys",
                "sys.stdin.read()",
                "print('Authorization: Bearer stderr-secret-token run_token=run-secret-value', file=sys.stderr)",
                "raise SystemExit(7)",
            ]
        ),
        encoding="utf-8",
    )
    module = _load_runner_module("claude-code-agent")
    runner = object.__new__(module.DefaultRunner)
    runner.get_plugin_config = lambda: {}
    runner.get_run_api = lambda ctx: None

    results = asyncio.run(
        _collect_async(
            runner.run(
                _native_ctx(
                    {
                        "location": "local",
                        "command": sys.executable,
                        "args-json": [str(fake_cli)],
                        "workspace": str(tmp_path),
                        "langbot-assets-enabled": False,
                    }
                )
            )
        )
    )

    assert [item.type for item in results] == ["state.updated", "run.failed"]
    error = results[-1].data["error"]
    assert "stderr-secret-token" not in error
    assert "run-secret-value" not in error
    assert "[REDACTED]" in error


async def _collect_async(stream):
    return [item async for item in stream]


def test_dify_runner_injects_langbot_asset_run_token(monkeypatch) -> None:
    module = _load_runner_module("dify-agent")
    calls = {}

    class FakeRegistration:
        token = "token_1"

        def stop(self):
            calls["stopped"] = True

    async def fake_register_assets(owner, api, ctx, config):
        assert owner is runner
        calls.update(
            host=config["asset_gateway_host"],
            port=config["asset_gateway_port"],
            request_timeout=config["asset_gateway_request_timeout"],
            api=api,
            ctx=ctx,
            ttl_seconds=config["asset_gateway_token_ttl"],
        )
        return FakeRegistration()

    runner = object.__new__(module.DefaultRunner)
    runner.get_run_api = lambda ctx: "run-api"
    ctx = types.SimpleNamespace(adapter=types.SimpleNamespace(extra={"params": {"existing": "value"}}))

    monkeypatch.setattr(module, "register_assets", fake_register_assets)
    registration, inputs = asyncio.run(
        runner._prepare_dify_inputs(
            ctx,
            {
                "langbot_assets_enabled": True,
                "asset_gateway_host": "0.0.0.0",
                "asset_gateway_port": 8765,
                "asset_gateway_request_timeout": 12.0,
                "asset_gateway_token_ttl": 120.0,
                "asset_gateway_input_name": "langbot_asset_run_token",
            },
        )
    )

    assert isinstance(registration, FakeRegistration)
    assert inputs == {"existing": "value", "langbot_asset_run_token": "token_1"}
    assert ctx.adapter.extra == {"params": {"existing": "value"}}
    assert calls == {
        "host": "0.0.0.0",
        "port": 8765,
        "request_timeout": 12.0,
        "api": "run-api",
        "ctx": ctx,
        "ttl_seconds": 120.0,
    }

    registration.stop()
    assert calls["stopped"] is True


def test_dify_runner_only_reuses_dify_uuid_conversation_id() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)

    ctx = types.SimpleNamespace(
        state=types.SimpleNamespace(
            conversation={
                "external.conversation_id": "550e8400-e29b-41d4-a716-446655440000",
            },
        ),
        conversation=types.SimpleNamespace(conversation_id="person_websocket_local_session"),
    )
    assert runner._get_external_conversation_id(ctx) == "550e8400-e29b-41d4-a716-446655440000"

    ctx.state.conversation = {}
    assert runner._get_external_conversation_id(ctx) == ""

    ctx.state.conversation = {"external.conversation_id": "person_websocket_local_session"}
    assert runner._get_external_conversation_id(ctx) == ""


def test_acp_resource_summary_includes_run_scoped_bridge_tools() -> None:
    from langbot_plugin.api.entities.builtin.runner import (
        AgentEventContext,
        AgentInput,
        AgentResources,
        AgentRuntimeContext,
        AgentTrigger,
        ContextAccess,
        ContextAPICapabilities,
        DeliveryContext,
        RunnerContext,
    )

    module = _load_runner_module("acp-agent-runner")
    ctx = RunnerContext(
        run_id="run_1",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(
            event_id="event_1",
            event_type="message.received",
            source="host_adapter",
        ),
        input=AgentInput(text="hello"),
        delivery=DeliveryContext(surface="webui"),
        resources=AgentResources.model_validate(
            {
                "knowledge_bases": [{"kb_id": "kb_1", "kb_name": "Docs"}],
                "tools": [
                    {"tool_name": "weather", "description": "lookup weather"},
                    {
                        "tool_name": "event_reply",
                        "tool_type": "platform",
                        "description": "reply to the current event",
                    },
                ],
            }
        ),
        context=ContextAccess(available_apis=ContextAPICapabilities(history_page=True)),
        runtime=AgentRuntimeContext(),
    )

    assert module._resource_summary(ctx)["mcp_bridge_tools"] == [
        {"tool_name": "langbot_get_current_event"},
        {"tool_name": "langbot_list_assets"},
        {"tool_name": "langbot_history_page"},
        {"tool_name": "langbot_retrieve_knowledge"},
        {"tool_name": "langbot_get_tool_detail"},
        {"tool_name": "langbot_call_tool"},
    ]
    assert module._resource_summary(ctx)["tools"] == [
        {"tool_name": "weather", "type": None, "description": "lookup weather"}
    ]
    assert module._resource_summary(ctx)["platform_tools"] == [
        {"tool_name": "event_reply", "description": "reply to the current event"}
    ]

    prompt = object.__new__(module.DefaultRunner)._with_run_scope_prompt(ctx, "call langbot_get_current_event")
    assert "Call LangBot MCP tools directly in this ACP session" in prompt
    assert "Do not launch background agents, workflows, or tasks" in prompt
    assert "launch at most one Agent with run_in_background=false and wait for it to finish" in prompt
    assert "Wait for each LangBot MCP tool result before replying" in prompt


def test_multimodal_runners_decode_data_url_attachments_and_derive_from_contents() -> None:
    for plugin_dir in {"coze-agent", "dify-agent", "tbox-agent"}:
        module = _load_runner_module(plugin_dir)

        assert module._decode_content("data:text/plain;base64,aGk=") == b"hi"

        attachments = module._attachments_from_contents(
            [
                {
                    "type": "file_base64",
                    "file_base64": "data:text/plain;base64,aGk=",
                    "file_name": "hello.txt",
                }
            ]
        )

        assert attachments == [
            {
                "type": "file",
                "name": "hello.txt",
                "content": "data:text/plain;base64,aGk=",
                "content_type": "text/plain",
            }
        ]


def test_external_runner_usage_normalizers_preserve_provider_usage() -> None:
    coze = _load_runner_module("coze-agent")
    assert coze._usage_from_payload({"usage": {"input_count": 11, "output_count": 7, "token_count": 18}}) == {
        "input_count": 11,
        "output_count": 7,
        "token_count": 18,
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }

    dify = _load_runner_module("dify-agent")
    assert dify._usage_from_payload(
        {
            "metadata": {
                "usage": {
                    "prompt_tokens": 13,
                    "completion_tokens": 5,
                    "total_tokens": 18,
                    "total_price": "0.0001",
                }
            }
        }
    ) == {
        "prompt_tokens": 13,
        "completion_tokens": 5,
        "total_tokens": 18,
        "total_price": "0.0001",
    }

    remove_dashscope_stub = "dashscope" not in sys.modules
    if remove_dashscope_stub:
        sys.modules["dashscope"] = types.SimpleNamespace(Application=object())
    try:
        dashscope = _load_runner_module("dashscope-agent")
    finally:
        if remove_dashscope_stub:
            sys.modules.pop("dashscope", None)
    assert dashscope._usage_from_payload({"usage": {"input_tokens": 3, "output_tokens": 4}}) == {
        "input_tokens": 3,
        "output_tokens": 4,
        "prompt_tokens": 3,
        "completion_tokens": 4,
        "total_tokens": 7,
    }

    tbox = _load_runner_module("tbox-agent")
    assert tbox._usage_from_payload({"data": {}}, {"usage": {"prompt_tokens": "2", "completion_tokens": "8"}}) == {
        "prompt_tokens": 2,
        "completion_tokens": 8,
        "total_tokens": 10,
    }


def test_runners_use_protocol_v1_actor_fields_for_user_identity() -> None:
    from langbot_plugin.api.entities.builtin.runner import (
        ActorContext,
        AgentEventContext,
        AgentInput,
        AgentResources,
        AgentRuntimeContext,
        AgentTrigger,
        DeliveryContext,
        RunnerContext,
    )

    ctx = RunnerContext(
        run_id="run_1",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(
            event_id="evt_1",
            event_type="message.received",
            source="host_adapter",
        ),
        input=AgentInput(text="hello"),
        delivery=DeliveryContext(surface="pipeline"),
        resources=AgentResources(),
        runtime=AgentRuntimeContext(),
        actor=ActorContext(actor_type="user", actor_id="user_1"),
    )

    for plugin_dir, method_name in {
        "coze-agent": "_get_user_id",
        "dify-agent": "_get_user_tag",
        "n8n-agent": "_get_user_tag",
        "tbox-agent": "_get_user_id",
        "weknora-agent": "_get_user_tag",
    }.items():
        module = _load_runner_module(plugin_dir)
        runner = object.__new__(module.DefaultRunner)
        assert getattr(runner, method_name)(ctx) == "user_user_1"


def test_deerflow_and_langflow_runners_derive_no_upstream_identity() -> None:
    # These runners send no upstream user identity (unlike coze/dify/n8n/tbox/
    # weknora), so they must not carry an identity helper. The removed
    # `_get_user_tag` returned an unscoped tag with a per-run `user_{run_id}`
    # fallback, which is exactly what shared placement forbids; nothing called it.
    for plugin_dir in ("deerflow-agent", "langflow-agent"):
        module = _load_runner_module(plugin_dir)
        assert not hasattr(module.DefaultRunner, "_get_user_tag")
        assert not hasattr(module.DefaultRunner, "_get_user_id")


def test_non_streaming_capability_metadata_is_honored_when_supported() -> None:
    from langbot_plugin.api.entities.builtin.runner import (
        AgentEventContext,
        AgentInput,
        AgentResources,
        AgentRuntimeContext,
        AgentTrigger,
        DeliveryContext,
        RunnerContext,
    )

    for plugin_dir in {"langflow-agent", "tbox-agent"}:
        module = _load_runner_module(plugin_dir)
        runner = object.__new__(module.DefaultRunner)
        ctx = RunnerContext(
            run_id="run_1",
            trigger=AgentTrigger(type="message.received"),
            event=AgentEventContext(
                event_id="evt_1",
                event_type="message.received",
                source="host_adapter",
            ),
            input=AgentInput(text="hello"),
            delivery=DeliveryContext(surface="pipeline"),
            resources=AgentResources(),
            runtime=AgentRuntimeContext(metadata={"streaming_supported": False}),
            config={},
        )

        assert runner._should_stream(ctx) is False
