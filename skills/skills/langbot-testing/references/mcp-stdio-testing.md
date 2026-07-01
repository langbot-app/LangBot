# MCP Stdio Testing

Use this reference when validating MCP server creation, tool discovery, and local-agent tool calls.

## Minimal Fixture

Use the bundled test server:

```text
fixtures/mcp/qa_mcp_echo_server.py
```

It exposes one tool:

```text
qa_mcp_echo(text: str) -> str
```

Expected tool result:

```text
qa_mcp_echo:<input>
```

Older versions of this fixture used the visible name `qa_echo`, which collides
with the `qa-plugin-smoke` plugin tool. This fixture now uses the unique
`qa_mcp_echo` name. If a run still returns the plugin sentinel:

```text
qa-plugin-smoke:<input>
```

that proves the run used the plugin tool or a stale MCP registration, not the
current MCP fixture. Refresh the MCP server/tool registration before treating
the result as MCP coverage.

## Browser Flow

1. Open `LANGBOT_FRONTEND_URL`.
2. Navigate to `MCP Servers`.
3. Create a new MCP server.
4. Set mode to `Stdio`.
5. Fill the command and each argument separately:
   - Command: `python`
   - Arg 1: absolute path to `fixtures/mcp/qa_mcp_echo_server.py`
6. Click `Test`.
7. Submit the server.
8. Confirm the server page shows `Tools: 1` and `qa_mcp_echo`.

Do not paste `python ...` into the command field as one string. LangBot stores `command` and `args` separately.

## Tool Discovery Checks

- UI: MCP detail page shows status connected and `qa_mcp_echo`.
- API diagnostic: `GET /api/v1/mcp/servers` shows `runtime_info.status=connected`.
- API diagnostic: `GET /api/v1/tools` contains `qa_mcp_echo`.

## Provider-Independent Fixture Check

Use this diagnostic before blaming Local Agent or a model provider:

```bash
node scripts/e2e/mcp-stdio-fixture.mjs
```

It launches the bundled stdio server directly, lists tools over MCP, and calls
`qa_mcp_echo` without invoking a LangBot model. A pass proves the fixture and MCP
stdio framing work; it does not prove the provider-backed Local Agent tool loop.

## LangBot Runtime Registration Check

Use this diagnostic when the direct fixture passes but LangBot still lists an old
tool name or the saved MCP server may be stale:

```bash
node scripts/e2e/mcp-stdio-register.mjs
```

It upserts `qa-local-stdio` through the authenticated WebUI session, points it at
the bundled `qa_mcp_echo_server.py`, then checks `/api/v1/tools` and the MCP
runtime info. A pass proves LangBot has refreshed the saved server and exposes
`qa_mcp_echo` before any model provider is involved. It also writes the resolved
server UUID to `LANGBOT_MCP_QA_STDIO_SERVER_UUID` in `skills/.env.local`; pipeline
extension binding uses this UUID, not the human-readable server name.

## Local-Agent Tool Call Check

1. Open the target pipeline.
2. Confirm `Extensions` allows the MCP server, or that all MCP servers are enabled.
3. Use runner `Default` or the pluginized `langbot/local-agent` runner.
4. Select a model with function-calling ability that is known to work with tools in the current environment.
5. Open `Debug Chat`.
6. Ask:

```text
Call the qa_mcp_echo tool with exactly this text: mcp-ok-local-agent. Return only the tool result.
```

Pass when the bot response contains:

```text
qa_mcp_echo:mcp-ok-local-agent
```

Do not count this case as passed when the bot returns:

```text
qa-plugin-smoke:mcp-ok-local-agent
```

That proves a plugin tool was called, not the MCP server.

If the provider returns `model_not_found` or `no available channel` only when tools are supplied, switch to a known-good function-calling model before diagnosing MCP or local-agent. That failure means the selected model route is unavailable for the requested tool-call shape.
