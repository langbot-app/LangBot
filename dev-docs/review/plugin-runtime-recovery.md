## Runtime recovery and payload limits

Workspace dispatch waits for an active Plugin Runtime reconnection before synchronizing installation state. The wait is capped at 30 seconds, or the configured connection timeout when shorter. A timeout returns an explicit retry message without cancelling shared recovery. Cancelling one request also leaves recovery running. Already-dispatched actions are not retried.

### Reconnection

Core v4.11.5 and master at `0d3aa694c` have the same connector implementation. `_prepare_workspace_context` checks only for a handler and immediately rejects requests while the disconnect callback is replacing it. A handler being constructed during the handshake is also not yet ready for dispatch. The existing reconnect loop restores the transport, but incoming requests do not wait for it.

The fix uses the managed transport's readiness check and awaits the existing reconnect task through `asyncio.shield`. Workspace validation still precedes the wait; installation synchronization follows readiness. Disabled plugins do not wait. A disconnected connector without active recovery still fails explicitly.

### Action timeouts

An action timeout does not establish a deadlock. A real loopback WebSocket probe with SDK 0.7.23's action handler and a simulated 16-second first model chunk raises `Action invoke_llm_stream call timed out` after approximately 15 seconds. Concurrent ping and ping after timeout both succeed. The public streaming proxy uses the handler's default 15-second idle deadline, while the runtime relay uses 120 seconds. Event dispatch and legacy tool calls use 180-second deadlines.

SDK commit `525d49be` (PR #129), already included in 0.7.23, reserves transport-control executor capacity. Core commit `5ef31d965` (PR #2924), already included in 4.11.5, handles host execution leases. Existing capacity, timeout, response-routing and event-loop monitor tests pass. No additional timeout or executor change is included.

### Payload limits

A 12 MiB inline base64 image becomes 16 MiB before the action envelope is added. The constructed event occupies 16,778,331 bytes and exceeds the 16,777,216-byte transport budget. Streaming responses have a separate 1,048,576-byte frame budget; they are not another instance of the 16 MiB limit.

The SDK preserves both limits. WebSocket and stdio outbound errors report the actual size, the budget, and guidance to reduce attachment size or use references rather than inline base64. Streaming errors report their own budget and recommend smaller chunks or attachment references. Rejection leaves the connection usable for the next message. Third-party plugin payload semantics remain unchanged.

### Verification

`tests/manual/plugin_runtime_reconnect.py` exercises the production Core connector against an isolated Docker Plugin Runtime. Both processes can run in separate Python 3.12 Docker containers on an isolated network. It stops and starts only the named test runtime, dispatches a message during recovery, sends an oversized image event, and dispatches a subsequent normal message. Set `SPACE__DISABLE_TELEMETRY=true` and use independent runtime data and a test-only control token.

| Scenario | v4.11.5 / SDK 0.7.23 | Patched Core / SDK |
| --- | --- | --- |
| Dispatch during runtime restart | Immediate `PluginRuntimeNotConnectedError` | Waits for reconnection and dispatches successfully |
| 12 MiB inline image | Generic 16 MiB limit error | Limit, actual size and actionable guidance |
| Normal message after oversized event | Delivered | Delivered |
| Runtime OOM state in this restart experiment | false | false |

Run focused regression suites with:

```sh
uv run --no-sync pytest tests/unit_tests/plugin -q
# In langbot-plugin-sdk:
uv run --no-sync pytest tests/runtime/io tests/runtime/test_bounded_executor.py tests/runtime/test_event_loop_monitor.py -q
```

Both Python wheels build successfully. Neither package version is changed.

### Limitations

The Docker harness supplies an empty Workspace installation inventory; transport, handshake, event RPC and reconnection are real, but this is not a full bot-platform/UI or installed-plugin end-to-end test. The slow-model probe uses a controlled delay, not a production model account.

Production failure signatures alone cannot attribute individual disconnects to container restart, OOM, network interruption or heartbeat starvation, nor individual timeouts to model latency versus blocking plugin code. Correlating those cases requires the affected runtime's logs, container exit/OOM state and runtime metrics. No environmental cause is inferred from the aggregate telemetry counts. Windows process-output behavior is covered separately by LANG-390.
