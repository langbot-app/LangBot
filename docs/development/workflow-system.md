# Workflow processors

A Workflow is the fourth processor kind alongside Pipeline, Agent and plugin
event processors. `Bot.event_bindings` selects it with `target_type: workflow`
and a Workspace-owned `target_uuid`. Workflows do not override event routing.
Only `message.received` events are supported.

## Runtime

`LoadConfigStage` loads YAML node metadata. `BuildAppStage` discovers Python
implementations through `NodeTypeRegistry.discover_nodes` and constructs
`WorkflowService`. Each execution owns a fresh `WorkflowExecutor` and a
`WorkflowRuntime` bound through a context variable. The runtime carries the
Workspace execution context, reply sender, explicit-target sender and collected
replies. Resource lookups and provider calls use that execution context.

EBA dispatch converts the event to `MessageContext` and sends replies through
the receiving adapter's legacy-message conversion. Route traces distinguish
incompatible events, unavailable processors and failed executions. The route
scope and processing indicator surround execution. Non-message routes are
rejected at configuration and execution time.

Nested workflows share the caller's senders and increment depth, with a maximum
depth of eight. Pipeline calls enter `query_pool.add_query` and wait for its
completion event. Nodes are not retried by default because sends have side effects.

## Persistence and authorization

Migration `0043_workflow_tables` adds `workflows`, `workflow_versions`,
`workflow_executions` and `workflow_node_executions`. Every table has a Workspace
foreign key. SQLite uses scoped statements; PostgreSQL also enforces Workspace
RLS. Definitions are versioned on change. Execution details include persisted
node inputs, outputs, status and errors. Deletion is rejected while a bot event
binding references the workflow.

HTTP resources live under `/api/v1/workflows`. Reads require `resource.view`,
mutations require `resource.manage`, and `POST /<uuid>/run` requires
`runtime.operate`. Manual runs accept `{message, session_type}` and return
`{execution_uuid, status, replies, error}`. They collect replies without a bot;
explicit-target sends therefore require an event-driven run. MCP exposes
`list_workflows`, `get_workflow` and `run_workflow` with identical authorization.
Existing Pipeline and Agent routes retain their contracts.

## Nodes

The supported set is discovered from `templates/metadata/nodes`: message trigger,
LLM call, question classifier, parameter extractor, condition, switch, loop,
iterator, merge, parallel, variable aggregator, set variable, data transform,
wait, end, HTTP request, reply message, send message, call workflow, call pipeline,
store data and memory store. Memory is execution-local. Wait is capped at 300
seconds. HTTP requests reject non-public destinations, including private DNS
results, and do not follow redirects.

## Validation

Run `uv run pytest tests/unit_tests/workflow tests/unit_tests/platform/test_workflow_routing.py -q`.
Migration round trips are covered by
`tests/integration/persistence/test_workflow_migration.py`; set
`TEST_POSTGRES_URL` to a dedicated test database for PostgreSQL. The manual
`python -m tests.manual.workflow_smoke` starts an isolated instance, creates a
message-trigger → condition → reply workflow, receives an event over a real
OneBot WebSocket, and checks the reply and persisted node records. It requires
an available local port 15344 and Linux `/dev/shm`.
Pass a startup-log path and screenshot path to also verify the real WebUI's
execution history, for example `uv run python -m tests.manual.workflow_smoke
workflow-startup.log workflow-executions.png`. This requires installed Web
dependencies, port 15345 and Chromium (`CHROMIUM_PATH`, default
`/usr/bin/chromium`). The browser and isolated instance stop after verification.
