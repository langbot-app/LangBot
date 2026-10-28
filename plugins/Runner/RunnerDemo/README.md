# Runner Workshop

[简体中文](README.zh-CN.md)

A complete, deterministic **Runner** example for LangBot 4.11. It runs
plugin Python handlers directly, with no model, API subscription, or extra runtime
dependency. This is a developer example for the `dev/4.11.x` Host and SDK;
it does not work with older SDKs that lack `Runner`.

## Two selectable components

| Component | Events | Behavior |
|---|---|---|
| Community concierge | Member joined/left, message received/reaction, feedback, friend request | Typed handlers, profile lookups, replies, branching, progress and errors |
| Event observer | `*` | A fallback `EBAEvent` handler that records summaries and optionally the typed payload; never calls tools |

Installing the plugin does **not** activate either component. Create a processor
configuration, select its component in the detail-page header, and save. Add the configuration under **Plugin processor** in a
bot and save; declared events are delivered automatically. Subscriptions run
independently alongside the primary Agent/Pipeline route, and one failed
subscriber does not prevent other deliveries. The observer only receives events
from explicitly bound bots. Old Pipeline `EventListener` hooks are unchanged.

## Install and try

1. Use a running LangBot 4.11 Host and matching Plugin Runtime.
2. In this directory, run `lbp build` with that SDK. The package is written to
   `dist/langbot-team-RunnerDemo-0.2.1.lbpkg`.
3. Upload it with **Add extension → local plugin installation** in LangBot.
4. Create two **Plugin processor** configurations. On each detail page, select
   **Community concierge** or **Event observer** from the component selector.
5. Open the **Configuration** tab on the right, customize settings, and save.
6. Use the in-page event debugger. Select the event type from an example file,
   switch the event editor to **Full JSON**, and paste **only its `data` object**.
   The surrounding `{ "event_type": ..., "data": ... }` is the HTTP debug payload.
7. Click **Run test**. The plugin executes for real; platform actions use Mock.
   Inspect its logs, action parameters/results, run status and elapsed time.

To receive real platform events, bind the processor configuration to a bot. You can
also create a configuration directly from the bot binding dialog.
Community replies then send real messages. Feedback/reaction/friend-request
handlers record logs only; this example never auto-approves friend requests.

## Scenarios

`examples/scenarios.json` enumerates 12 copyable HTTP debug payloads.

| File | Expected result |
|---|---|
| 01-member-joined | Query actor → query group → welcome reply; 3 traced actions |
| 02-member-left | Warning log; reply only if departure announcements are enabled |
| 03-help | List available `/demo` commands |
| 04-profile | Query the event actor and group, then acknowledge completion |
| 05-slow | Three progress logs over the configured delay, then reply |
| 06-failure | Warning only by default; with failure demo enabled, an error log and failed run |
| 07-feedback | Classify negative feedback; warning and details, no reply |
| 08-reaction | Record added/removed reaction; no reply |
| 09-friend-request | Record the request and a manual-review warning; no approval |
| 10-observer-custom | Observer handles `platform.specific`; enable payload logging to see custom fields |
| 11-echo-with-image | Unicode text is echoed; image type is logged without downloading it |
| 12-ignored-message | Normal non-command message completes without a reply |

Optional lookup failures are recorded as failed actions plus warning logs. The
welcome flow continues with the event's own data. Reply failures propagate and
fail the run, preserving previous logs.

## Configuration

Community settings: output language, welcome text, command prefix, departure
announcements (off by default), demo delay (600 ms by default; clamped to 0–2000),
and intentional failure (off by default). `/demo fail` is an explicit test hook,
not a random error. Welcome text is verbatim configuration and is not translated
automatically when changing output language.

Observer settings: output language and payload logging (off by default). Payload
logging includes typed event data but excludes the raw platform object.

## Shared-runtime certification profile

RunnerDemo declares `execution.sharedRuntime: shared-runtime-v1` and keeps its
runtime modules free of process-wide or mutable module state; configuration and
per-run data stay on `RunnerContext`. `tests/test_shared_runtime.py` reproduces
the two-binding proof locally with the released SDK: one real worker
(`PluginRuntimeController` + the `RunnerDemo` instance + one instance per
component) is attached twice, as workspace-A/installation-A and
workspace-B/installation-B, and both installations are driven concurrently
through the `community` component with distinct configuration, events and
results. The same test detaches one installation and checks that the sibling
graph survives, so a regression to per-installation object graphs fails it
instead of passing vacuously. Only Host/backend RPC responses are fixtures. A
local `lbp build` archive is still unsigned and has no certification comment.
Space approval is the separate gate that may issue and sign a certification
envelope; this repository does not claim that approval or certificate.

## Development and repeatable verification

```bash
# Use the matching SDK environment first.
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
lbp build

# Optional: install and run all examples through the real Host HTTP API.
# Use a token or API key with resource manage and operate permissions.
export LANGBOT_API_KEY='your-key'
python scripts/smoke.py --base-url http://127.0.0.1:5399
```

`LANGBOT_TOKEN` can be used instead of an API key; optionally set
`LANGBOT_WORKSPACE_ID`. The smoke script installs the package, creates/reuses two
clearly named demo configurations, sets their parameters, executes 12 scenarios and verifies
that debug replies are Mock. It deliberately creates one failed run, then turns
the failure option off in `finally`. It enables departure announcements and
observer payload logging on its demo configurations. It creates no Bot bindings.
The receipt is saved to ignored `data/smoke-results.json`; credentials are never
saved. Re-running adds another set of run records.

## Source map

- `components/runner/community.py`: typed `@self.handler(...)` examples.
- `components/runner/observer.py`: generic event fallback handler.
- Matching YAML files: independent component configs, event declarations and permissions.
- `tests/test_processors.py`: all samples, trace pairing, fault handling, Unicode and config isolation.
- `tests/test_shared_runtime.py`: real SDK worker with two installation bindings — object-graph identity, per-binding configuration/results, slot detach.
- `scripts/smoke.py`: actual package installation and Host/runtime integration check.

The component API exposes `ctx.event`, `ctx.config`, `ctx.run_id`, `ctx.log()`,
`ctx.reply()` and `ctx.get_available_tools()`. Platform and LangBot APIs use `self.plugin` and automatically retain invocation grants. There is no legacy Pipeline Query or
Agent loop to construct; returning from the handler ends that invocation.

## Full event matrix

Create a dedicated **Event observer** configuration with payload logging enabled and
no Bot bindings. With the same authentication environment as above, run:

```bash
python scripts/event_matrix.py --base-url http://127.0.0.1:5399 --processor-id YOUR_PROCESSOR_UUID
```

`examples/event-matrix.json` covers all 17 standard events with minimal and
populated payloads, eight extra variants (including empty/image-only messages,
feedback values and temporary bans), and six invalid inputs: 48 cases total.
The script checks typed payload preservation, exactly one completed run per valid
input, persisted run status, no action calls, and rejection of invalid inputs.
It adds debug run records and writes an ignored receipt to
`data/event-matrix-results.json`. It does not install plugins or modify bindings.
This validates the Host/runtime processing path; platform-specific event support
and actual delivery must still be verified against each adapter.

Observer declares `usages: [agent, event]` and can be selected by either an Agent or a Plugin processor. Community declares `usages: [event]`. Both use the same Runner context and event handlers.
