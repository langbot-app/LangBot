# Runner components and Pipeline plugin compatibility

## Product boundary

| Product | Implementation | Event entry |
| --- | --- | --- |
| Pipeline | Pipeline stages and an agent-capable Runner | Received messages |
| Agent | A Runner with `spec.usages: [agent]` | Configured events |
| Plugin processor | A Runner with `spec.usages: [event]` | Events declared in `spec.events` |

Runner is the only component for these execution styles. `spec.usages` can contain
both `agent` and `event`; these are selection capabilities, not mutually exclusive
execution modes. An installed component is reusable code. Users create processor
instances, select a Runner and configure it, then bind Bot events to the instance.
Installation alone never subscribes a component to incoming events.

## Legacy EventListener contract

EventListener remains a Pipeline extension. Existing plugins retain their import
paths, handler registration syntax, event classes, Query-based APIs, and Pipeline
plugin selection behavior. No conversion of installed listeners into standalone
processor instances takes place.

Compatibility must cover execution behavior, not just successful deserialization:

| Hook | Required behavior |
| --- | --- |
| PersonMessageReceived / GroupMessageReceived | Read the returned EventContext before later stages; retain message edits and default prevention |
| PromptPreProcessing | Preserve timing and apply returned default_prompt and prompt |
| PersonNormalMessageReceived / GroupNormalMessageReceived | Preserve user_message_alter, default prevention, and replacement replies |
| PersonCommandSent / GroupCommandSent | Preserve command stage timing, default prevention, and replacement replies |
| NormalMessageResponded | Preserve response-stage timing, default prevention, and replacement message chains, including streaming behavior |
| All hooks | Preserve plugin ordering, prevent_postorder across installations, bound-plugin filtering, Query identity, and Workspace scope |

RPC responses are new Python objects. Host code must consume returned values
rather than assume mutations reached the original Query by object identity.
Host-only references, including the active Query and raw adapter message, must
remain available for legacy reply APIs without being exposed in serialized
plugin events.

Preserve source event fields across EBA-to-legacy conversion, including group
member permissions, bot group permissions, and member titles. Missing platform
information must be distinguished from fields that were dropped during conversion.

Direct Agent and Event processor execution must not synthesize Pipeline lifecycle
hooks. Those hooks describe actual Pipeline stages.

## SDK and runtime

`lbp comp Runner` generates `components/runner`. Every component uses
`plugin:author/plugin/name` as its identity. Names are unique within a plugin.
The component can override `async run(ctx)` and yield RunnerResult objects, or
register typed platform callbacks through `@self.handler(EventClass)` in
`initialize()`. Default run dispatches an exact handler, falling back to EBAEvent.
A custom run can delegate to this dispatch with `await super().run(ctx)`.

Both styles share RunnerContext, invocation-bound ctx.api, logs, replies, deadlines,
cancellation, worker isolation and the run ledger. ctx.event is the envelope;
ctx.platform_event is the typed platform payload. Each invocation owns its context;
never put the current context or run ID on a shared component or plugin instance.

The runtime emits completion on normal return unless the Runner already emitted a
terminal result. Exceptions fail the run and retain preceding results. Cancelling
the result stream cancels execution. There is no implicit retry or hidden model
loop. Returned text and logs do not send platform messages: replies are explicit
ctx.reply / ctx.reply_stream actions. Pipeline retains its configured output stage.

`self.plugin` continues to expose ordinary plugin APIs. ctx.api carries run-scoped
resource grants and records tool actions. Workspace and installation authorization
remain Host-enforced. Run identity and API operation scope are separate concepts.

## Selection and observability

Both product selectors discover the same Runner catalog and filter by usage.
Validate usage again before execution. Event-capable Runners must declare events;
users can route a subset, but cannot expand the manifest capability. Unconfigured
instances expose no event subscriptions. Workspace ownership, plugin scope and
instance identity are checked for routing, execution, cancellation and run reads.

Plugin processor details keep event debugging on the left and configuration/logs
on the right. Component settings use the existing schema form. Logs and action
results remain distinct from actual platform delivery; debug delivery is Mock.
Agent-native interactions stay on the Agent product path; typed handlers consume
platform events. Legacy Pipeline lifecycle hooks remain on the Pipeline path.

## Validation

SDK tests cover both execution styles, event matrices, concurrent contexts,
termination, cancellation and permissions. Packaged CLI tests generate, build and
execute the published component. Core tests cover usage-filtered discovery, event
routing, Workspace authorization and real plugin-runtime transport. RunnerDemo
provides multi-step actions, configuration isolation and controlled failures.
