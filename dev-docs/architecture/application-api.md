# Application API foundation

The application package provides a callable business boundary inside Core. A
consumer supplies a trusted identity and operation arguments, then receives a
validated result or a stable application error. HTTP, MCP, the management
assistant and `lbctl` retain their existing entrypoints in this change; their
adoption of this boundary belongs in separate changes.

## Workspace operations

`ap.application_api.operation_catalog()` returns the explicit operation allowlist,
with version, permission, principal constraints, side effects, execution mode,
and JSON schemas for inputs and results. The catalog covers the existing
Workspace management capabilities:

| Area | Capabilities |
| --- | --- |
| Pipelines and agents | CRUD, metadata, extension configuration, migration preview/execute, diagnostic runs, run history and events |
| Models and providers | LLM/embedding/rerank CRUD and tests, defaults, discovery, provider credential authorization |
| Bots and platforms | CRUD, routes and dry runs, messages, administrators, adapter metadata and credential setup sessions |
| Knowledge | Bases, ingestion tasks, files, retrieval, engine schemas and parser discovery |
| Extensions | Plugin installation/configuration/assets/logs, MCP servers/resources, skills and files, tools |
| Workspace | Current workspace, language, membership, invitations, API keys and webhooks |
| Operations | Monitoring and exports, governance and audit, task status, Box visibility, setup wizard and storage statistics |
| Conversations | Management-assistant conversations/runs and Pipeline chat history, reset, connections and broadcast |

Service-backed operations reuse existing business signatures to build strict
Pydantic inputs. Only methods explicitly listed in `service_operations.py` are
exposed; adding a public service method does not publish an operation. Domain
configuration objects remain dictionaries because their schemas are owned by
providers, plugins or the existing resource services. Those services retain
validation, quotas, secret placeholder restoration and runtime side effects.

```python
# context is established by a trusted authenticator, never from request JSON.
result = await ap.application_api.execute(
    'pipeline.get', context, {'pipeline_uuid': pipeline_uuid}
)

async for frame in ap.application_api.stream(
    'agent.debug.stream', context,
    {'agent_uuid': agent_uuid, 'payload': {'text': 'hello'}},
):
    consume(frame)
```

The Workspace comes only from `RequestContext`. Each invocation checks the
operation permission and the current execution binding/generation, then carries
that tenant and its message language through the business call. Additional
identity constraints remain where required by the business service: membership,
interactive provider authorization, assistant conversations and Pipeline
migration require an account. API-key grants are not replaced by the creator's
role. Authentication, key revocation/expiry and current account membership must
be resolved by the trusted caller before constructing the context.

Secret reads require the corresponding secret-management permission. Mutating
operations preserve the domain's existing authorization and resource ownership
checks. Audit recording uses the existing Workspace configuration and bounded
writer, with operation identity and outcome; raw arguments are not copied into
the generic trace. Queued tasks retain their Workspace/generation and revalidate
runtime admission before accessing plugins.

`ApplicationAPIException.error` carries `code`, `message`, `status_code` and
optional structured `details`. Protocol adapters map that object to their own
response shape. Invalid inputs and outputs fail explicitly. Cancellation is not
converted into success, and writes are never automatically retried. Pipeline
run timeouts retain the existing `unknown` outcome: a timeout does not establish
that execution failed or was rolled back.

Streaming scopes live in isolated producer tasks with bounded queues. Closing
an Agent debug stream cancels its execution. Management-assistant streaming
retains its existing detached-run behavior; use the explicit stop operation to
cancel an assistant run. Consumers should close partially consumed iterators
with `contextlib.aclosing`.

## Execution-context operations

`ExecutionAPI` publishes the existing Core business actions available to an
installed plugin or a running processor. Its catalog describes each action's
input/output schema, streaming mode and required plugin/run scope. It includes
model and RAG access, tools, event replies and platform actions, state/history,
run control and interactions, and Box/file operations.

```python
from langbot.pkg.api.application.execution import ExecutionAPI, ExecutionAPIContext

api = ExecutionAPI(ap)
catalog = api.catalog()
context = ExecutionAPIContext(binding=trusted_installation_binding, run_id=run_id)
result = await api.invoke(operation_id, context, arguments)
```

The caller must supply the trusted installation binding established by Core.
The foundation invokes the existing secured action dispatcher, preserving
installation revision/grant checks, active placement and frozen run resources.
A run-bound context also verifies that the run belongs to that installation's
Workspace and plugin. Arguments cannot override the run ID or fall back to the
legacy plugin path by omitting it. Plugin-only operations remain explicit and
cannot be called with a run-bound context. Stream isolation also prevents one
consumer's context from escaping into another consumer's task.

## Scope and adoption

This is the full **existing Workspace and execution business capability**
foundation. Instance administration, account login/bootstrap, public ingress,
OAuth callbacks, transport assets and internal Runtime handshake/chunk/ping
messages remain with their owning boundaries. Composite HTTP response layouts
(such as a combined monitoring page) are consumer projections of these
operations. This does not add new platform APIs or new instance-level powers.

Existing routes do not call the new application dispatcher. No SDK protocol or `lbctl` command is
changed by this foundation.

Consumer adoption should verify the same operation through each selected
transport, including denied access, missing resources, invalid inputs,
cancellation and secret handling. The existing Core smoke exercises current
consumers; it does not by itself prove a new consumer integration.
