# Event processors and Pipeline plugin compatibility

Status: implemented in the 4.11 development branches of LangBot and the Plugin SDK,
2026-09-08. The Host uv configuration pins the matching SDK commit. Deploy both
revisions together; older SDK releases do not contain this component. Switch the
development source pin to a published SDK release before a stable PyPI release.
This design supersedes the automatic EBA EventListener observer broadcast in
the earlier EBA documents. Existing Pipeline plugin behavior remains supported.

## Product boundary

Three processor types appear together in the Processors area:

| Product | Implementation | Event entry | Flow ownership |
| --- | --- | --- | --- |
| Pipeline | Existing Pipeline stages and configuration | Received messages | Pipeline stages, including legacy plugin hooks |
| Agent | A configured plugin AgentRunner | Supported EBA events | The selected runner |
| Event processor | A configured plugin EventProcessor | Supported EBA events | Plugin Python handlers |

Use **Event processor** as the product label and **EventProcessor** as the SDK
component name. The localized description should explain that the plugin defines
the processing logic. It must not suggest an LLM, prompt, or visual workflow is
required.

An installed component is a reusable implementation. A processor instance is a
user-created configuration of that component. A Bot event binding selects an
instance, not an installed plugin package directly.

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

## EventProcessor SDK contract

Introduce a distinct component kind instead of changing what an existing
EventListener manifest means. One package may contain both kinds; only the legacy
EventListener participates in Pipeline hook dispatch.

Retain the familiar authoring shape:

```python
from langbot_plugin.api.definition.components.event_processor import EventProcessor, EventProcessorContext
from langbot_plugin.api.entities.builtin.platform.events import MemberJoinedEvent
class WelcomeProcessor(EventProcessor):
    async def initialize(self):
        await super().initialize()

        @self.handler(MemberJoinedEvent)
        async def on_join(ctx: EventProcessorContext):
            await ctx.reply(f"Hello, {ctx.event.member.nickname}")
```

Handlers receive typed EBA events directly. Do not maintain a second, incomplete
mapping into plugin-only EBA wrapper classes. Preserve complete public event
fields; compact log previews must not become the execution payload. Include the
generic platform-specific event contract for adapter-specific events.

The context belongs to one invocation and exposes the event, processor/run
identifiers, instance configuration, logging, and authorized Host APIs. It has no
fabricated Pipeline Query. Reuse Host run tracking, deadlines, installation
authority, platform capabilities, and delivery records where appropriate.

A handler returning normally completes its invocation. There is no implicit LLM
loop, automatic second processor, or hidden retry of side effects. An exception
marks the run failed and retains the associated log. New processing handlers do
not use prevent_default to control another processor; routing has already chosen
the current processor. The legacy methods keep their existing Pipeline meaning.

## Activation and routing

The activation sequence is explicit:

1. Install a plugin containing an EventProcessor component.
2. Create an Event processor in the Processors area.
3. Open its detail page, select a plugin component, and save its configuration.
4. Bind a Bot event to that processor instance in the existing event routing UI.

Installation and processor creation alone do not subscribe to Bot events.
The component declares the event types it handles; Bot bindings select the subset
of supported events to deliver. One package may supply multiple components, and
multiple instances may use the same component with independent configuration.

Extend the existing single-target route arbitration with `event_processor`.
There is no automatic EBA broadcast to installed EventListeners. Keep Pipeline hook dispatch inside the Pipeline path. Existing observer
plugins must explicitly adopt the new component and be bound by the user; do not
create subscriptions during migration.

An unconfigured instance has no supported events and cannot execute. Validate
component availability, event compatibility, Workspace ownership, and instance
identity when configuring the instance and again at invocation. A disabled or
unavailable plugin leaves the instance visible with an actionable unavailable
status. It must not silently fall back to Agent or Pipeline.

## Compact UI

Creation adds a third type next to Agent and Pipeline and asks only for basic
instance information. Select the plugin component in the detail-page header.
Keep component-defined configuration in the adjacent Plugin settings popover.
If no component is installed, show a relevant plugin installation entry point;
installing still does not create a binding.

The detail page shows event debugging on the left and logs on the right without
view-switching tabs. A compact run list shows event type, time, status and known
processing duration. Selecting a row shows that run's identity, input, logs,
actions and outcome below. There is no shared timeline between unrelated runs.
The additive `created_at_ms`, `started_at_ms`, and `finished_at_ms` fields retain
Host lifecycle precision for elapsed-time display.
Keep payloads and error details collapsed until expanded. Distinguish attempted
delivery from confirmed delivery and display the actual destination.

Place component identity, availability, bindings, and configuration in a compact
secondary area. Do not add a prompt editor, model selector, or flow designer.
The plugin implements the processing flow in code.

## Delivery sequence and acceptance

1. Repair and regression-test Pipeline EventContext handling and legacy payload
   conversion independently of the new processor feature.
2. Add the SDK component, context, manifest/scaffolding, and explicit invocation
   contract; verify registration, event coverage, and process isolation.
3. Add Host instance management, event routing, execution tracking, and matching
   HTTP/MCP/skill surfaces. Turn off automatic EBA observer dispatch in this step.
4. Add creation, binding, availability, logs, and delivery trace UI with i18n.
5. Exercise a real packaged plugin through installation, explicit instance
   creation, Bot binding, invocation, logging, and reply delivery.

Acceptance must prove that installation alone invokes no handlers; one matching
binding invokes exactly the chosen component; instance configuration and run
history remain separate; all declared EBA events retain their fields; unavailable
components fail visibly; and legacy plugins keep the documented Pipeline hook
order and behavior. Unit tests alone do not establish a successful live plugin
installation or platform delivery.


## Implemented transport and APIs

`lbp comp EventProcessor` scaffolds a component in `components/event_processor`.
Its manifest uses `kind: EventProcessor` and `spec.events`, for example
`[group.member_joined]`. `spec.config` defines instance parameters. A component
that calls `ctx.reply()` declares `spec.permissions.tools: [detail, call]`.

References use `event_processor:author/plugin/component`, separate from
`plugin:author/plugin/runner`. Both kinds share the existing run transport,
installation authorization, deadlines and run ledger. The trusted Host selects
the component kind; the worker invokes only that exact kind and name.
There is no model invocation in the EventProcessor base class.

`EventProcessorContext` provides `event`, `run_id`, `config`, `api`, `log()` and
`reply()`. `api` is the existing run-scoped Host proxy. Use `ctx.config` for instance
parameters; plugin installation configuration remains separate. Handlers may
register the `EBAEvent` base class as a catch-all. An exact typed handler takes
precedence over that fallback. Multiple handlers for the same type run in their
registration order, within one invocation.

HTTP instance management uses `/api/v1/agents` with `kind: event_processor`.
Metadata at `/api/v1/agents/_/metadata` lists installed `event_processors`.
Creation accepts `component_ref` and `parameters`; the Host derives the supported
event patterns from the component. Bot bindings use `target_type: event_processor`
and the created instance UUID as `target_id`.

- `GET /api/v1/agents/{id}/runs?before_id=...` lists this instance's runs.
- `GET /api/v1/agents/{id}/runs/{run_id}/events?after_sequence=...` pages its logs
  and action results. A run from another instance or Workspace is rejected.
- The corresponding MCP tools are `get_processor_metadata`, `list_processor_runs`
  and `get_processor_run_events`, alongside processor CRUD.
- `/api/v1/agents/{id}/debug` accepts a full typed EBA event in `data`. Platform
  actions use Mock; other authorized tools retain their configured behavior.

The detail page polls run updates, keeps payload details collapsed and separates
logs from platform delivery. Completed handlers produce no synthetic reply text.


## Verification (2026-09-08)

- SDK API, scaffolding and Plugin Runtime suites: 684 passed.
- Host runner, service, controller, MCP and adapter regression suites: 971 passed.
- Pipeline and registry regression suites: 243 passed, one environment-dependent skip.
- Frontend unit suite: 74 passed; TypeScript and changed-file lint checks passed.
- Real packaged-plugin tests cover installation, component-kind separation,
  invocation, mock platform delivery, instance isolation and persisted logs.
- Authenticated Edge testing created an instance and a loopback OneBot bot, saved
  a member-join binding, injected one native notice and received exactly one
  `send_group_msg` response. The detail page displayed the completed run,
  localized action name, destination and returned message ID. No external IM
  account or live model was involved.
- Browser regression covers expanding long payloads, reaching the last log and
  pagination without duplication. Eight unrelated existing browser failures were
  reproduced against the pre-change commit; the full suite is not green.
- Repository-wide lint also retains the pre-existing duplicate `send_image_msg`
  in the WeCom customer-service library and existing formatting failures outside
  this change. The i18n check has the same pre-existing diagnostics as its baseline.

Native Agent interaction-resumption is not enabled for EventProcessor bindings;
its input contract is the platform EBA event collection, not a synthetic Agent
continuation. Plugins should handle platform events through their typed handlers.
