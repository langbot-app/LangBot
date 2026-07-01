# EBA Productization and Release Plan

> Status: planning draft, 2026-07-01
>
> Scope: productizing the merged AgentRunner pluginization and Event Based Agent adapter work into a product that non-technical users can start with quickly. This document focuses on product gaps, release gates, and SaaS multi-namespace tenancy. It does not introduce new protocol schema; protocol facts remain in [PROTOCOL_V1.md](./PROTOCOL_V1.md) and host model facts remain in [HOST_SDK_INFRASTRUCTURE.md](./HOST_SDK_INFRASTRUCTURE.md).

## 1. Product Direction

The current technical direction is correct: LangBot should treat platform input as events, resolve one effective route for each event, and invoke a processing asset through the AgentRunner host boundary. However, this is not yet a product that non-technical users can adopt without understanding internal architecture.

The product-level model should be:

- **Bot**: the platform connection and event routing surface. A bot owns adapter credentials, platform permissions, incoming event visibility, and the route table for those events.
- **Processor**: a reusable processing asset that can handle routed events. Current processor types are **Agent** and **Pipeline**. Future types can include **Workflow**.
- **Pipeline**: a first-class no-code message processor kept for compatibility and low-code users. It is message-only and should be bindable only to `message.*` events.
- **Agent**: a runner-backed processor for event-first processing. It can handle message and non-message events according to its declared supported event range.
- **Solution**: a future distribution/export unit containing processors, route templates, dependency manifests, variables, and docs. A solution must not include concrete bot credentials, tenant secrets, or installed UUID bindings.

`EBA` is an internal engineering term. It can appear in internal design documents, but it should not be visible in primary product flows. User-facing language should prefer terms such as "channel", "event routing", "processor", "message pipeline", "automation", and "route template".

## 2. Current Foundation

The merged branch has enough technical foundation for internal smoke testing:

- EBA adapters can normalize platform activity into stable host event names.
- Bots can persist `event_bindings` and route events to an Agent, Pipeline, or discard target.
- Legacy message input can be projected into the canonical `message.received` event path.
- Pipeline remains available as a message-only no-code processor.
- AgentRunner pluginization provides the host-runner contract, event-first context, result stream, and runtime integration boundary.
- Official local and external runner plugins can validate that runner behavior is no longer hard-coded into LangBot core.
- The WebUI has an Agent/processor management surface and bot-side event routing surface.

This is a technical convergence milestone, not a product-ready release.

## 3. Gap to a Non-Technical Product

### 3.1 Conceptual Load

Current users still need to understand too many internal concepts: EBA, adapter event names, runner identifiers, plugin runtime health, event patterns, priority, and binding targets. A non-technical product should guide users through intent and outcomes:

- "When a message is received, reply with this processor."
- "When a new group member joins, send a welcome message."
- "When a friend request arrives, ask an Agent to decide whether to accept."

Raw event patterns such as `group.member_joined` should remain available in advanced mode, but the default UI should group events by friendly names and platform capability.

### 3.2 Onboarding

The first-run path needs to start from a use case, not from architecture:

1. Choose a channel.
2. Connect the account or webhook.
3. Pick an event preset supported by that channel.
4. Choose or create a processor.
5. Send a test event.
6. Read a simple run trace if it fails.

The current product still assumes users can diagnose whether the backend, plugin runtime, box runtime, adapter, and runner plugin are all connected. That is acceptable for developers, but not for non-technical users.

### 3.3 Adapter Readiness

Each adapter needs a product capability manifest, not only an engineering implementation:

- supported event list with friendly labels;
- supported outgoing actions;
- required credentials and setup steps;
- local/self-host/SaaS availability;
- test signal availability;
- deprecated/legacy status;
- known limitations.

Deprecated adapters should be clearly marked as "deprecated" or "legacy" in the product. New event-based adapters should be described by channel name and capability, not by the EBA acronym.

### 3.4 Processor UX

The Agent page should manage reusable processors, not make users think about all event routing decisions at once.

- Agent creation should provide opinionated runner templates.
- Pipeline creation should remain a no-code message pipeline path.
- Future Workflow creation can be introduced as another processor type when execution semantics are stable.
- Supported event range should be shown as capability information and advanced constraints, not as the main creation concept.
- Dependency health should be visible: runner plugin installed, runtime connected, required model configured, required resource accessible.

### 3.5 Bot Event Routing UX

The Bot page should be the primary place for platform-specific event routing because platform events are easiest to understand in the context of the connected channel.

Minimum product requirements:

- friendly event selector generated from adapter capability;
- target selector filtered by event compatibility;
- Pipeline hidden for non-message events;
- conflict warnings for overlapping routes;
- priority explained visually rather than as a raw number first;
- route test button that can inject or replay a sample event;
- per-route status showing last matched run and last failure reason;
- safe fallback route, including explicit discard.

### 3.6 Observability

Non-technical users need a short run trace rather than raw logs:

```text
Event received -> Route matched -> Processor started -> Action delivered
```

When something fails, the UI should point to the failing layer:

- channel not connected;
- event unsupported by adapter;
- no route matched;
- processor disabled;
- runner plugin unavailable;
- model/resource missing;
- delivery permission denied.

### 3.7 Documentation and Templates

The release needs product docs and templates for common scenarios:

- customer service bot;
- group welcome and moderation;
- friend request review;
- Dify-backed external Agent;
- local Agent with LangBot model and knowledge base;
- message Pipeline for compatibility.

The docs should describe the product model first and expose internal terms only in advanced architecture sections.

## 4. Recommended UX Boundary

The previous "put all event orchestration in Agent" direction should be narrowed. The better boundary is:

- **Bot page owns event routing**, because the event surface is platform-specific and users naturally expect channel behavior to be configured on the bot.
- **Agent page owns processor assets**, because processors should be reusable across bots and can later be packaged into solutions.
- **Pipeline remains a processor type**, not a historical object hidden behind Agent terminology.

This gives a lower mental load:

- A user asks "what should this bot do when something happens?" on the Bot page.
- A user asks "what logic do I want to reuse?" on the Agent page.

It also supports the requirement that different events on the same bot can use different processor types: one event can use Pipeline, another can use Agent, and a future event can use Workflow.

## 5. Future Export, Distribution, and Import Unit

Export/import is not in the current implementation scope, but the product boundary should not block it.

The correct future distribution unit is **Solution**, not Bot and not Agent alone.

A Solution should contain:

- processors: Agent, Pipeline, future Workflow definitions;
- route templates: event patterns, friendly names, target logical references, default priority, and optional conditions;
- dependency manifest: required runner plugins, adapter capability requirements, models, tools, and resources;
- variables: user-provided values such as API keys, channel choices, model selections, and prompt parameters;
- docs: setup intent and expected behavior.

A Solution should not contain:

- concrete bot credentials;
- installed runtime tokens;
- tenant or namespace UUIDs;
- secrets;
- raw platform account identifiers;
- resolved bot event binding UUIDs.

During import, route templates should be resolved inside the target namespace after the user chooses a bot/channel and grants required permissions.

## 6. SaaS Multi-Namespace Architecture

The product must support a multi-namespace SaaS architecture before public SaaS release. The event routing model is sensitive because adapters, credentials, processors, runtimes, state, and logs all cross trust boundaries.

### 6.1 Namespace Model

Use a layered namespace model:

| Scope | Purpose |
| --- | --- |
| Tenant | Billing, legal ownership, top-level isolation. |
| Workspace | Collaboration and product workspace inside a tenant. |
| Namespace | Deployable isolation boundary for bots, processors, runtime tokens, resources, and logs. A self-host deployment can have one default namespace. |
| Bot scope | Platform adapter instance and event route table. |
| Processor scope | Agent, Pipeline, Workflow, and related config. |
| Runtime scope | Plugin runtime, runner registrations, leases, and execution permissions. |
| Resource scope | Knowledge bases, model credentials, files, state, and secrets. |

Core persisted objects should carry `tenant_id`, `workspace_id`, and `namespace_id` before SaaS GA. Self-hosted deployments can seed a default tenant/workspace/namespace during migration.

### 6.2 Event Ingress Isolation

Every incoming event must resolve namespace before route matching:

```text
adapter ingress -> tenant/workspace/namespace resolution -> event normalization -> event log append -> route match -> processor run
```

Webhook and callback endpoints should encode or look up a namespace-scoped adapter installation. A platform event from one namespace must never match a route from another namespace, even if adapter names, bot names, or raw platform IDs collide.

### 6.3 Route Target Rules

Runtime route bindings can use installed UUIDs, but exported route templates must use logical references. In SaaS:

- a bot route can target only processors in the same namespace by default;
- cross-namespace targets are forbidden unless explicitly shared by policy;
- Pipeline targets remain message-only;
- route conflict evaluation is namespace-local;
- route audit events must include tenant, workspace, namespace, bot, route, target, and run identifiers.

### 6.4 Runtime and Plugin Isolation

The plugin runtime and runner registry need namespace-scoped authority:

- runtime registration token is scoped to one namespace or an explicitly allowed namespace set;
- runner discovery is filtered by namespace permissions;
- leases and heartbeats are namespace-scoped;
- run-scoped API tokens cannot access objects outside the run namespace;
- plugin storage, state, and temporary files include namespace in their storage key;
- shared runtime is acceptable for early SaaS only if every API call is scoped and audited;
- dedicated runtime should be available for enterprise or high-risk tenants.

### 6.5 Secrets, Resources, and State

Secrets and resources must not be globally addressable:

- adapter credentials live in namespace-scoped secret storage;
- model provider credentials can be tenant/workspace/namespace scoped according to policy;
- knowledge resources declare which namespaces can use them;
- Agent persistent state is partitioned by tenant/workspace/namespace/processor unless a sharing policy says otherwise;
- event logs and transcripts are namespace-scoped and subject to retention policy.

### 6.6 Marketplace and Installed Assets

Marketplace package visibility is not the same as installed asset visibility:

- marketplace package can be public, tenant-private, or workspace-private;
- installation creates namespace-local assets or namespace-local references;
- installed processors and route templates are copied by default to avoid accidental cross-tenant mutation;
- updates should be explicit and auditable.

### 6.7 SaaS Test Requirements

Before SaaS beta:

- tenant A event cannot match tenant B routes;
- namespace A runtime cannot claim namespace B runs;
- namespace A processor cannot read namespace B resources;
- solution import cannot preserve source tenant UUIDs or secrets;
- route replay cannot expose raw event payload from another namespace;
- admin users can inspect audit trails without accessing secret values.

## 7. Release Plan

### Phase 0: Technical Convergence

Goal: prove the merged branch can run with event bindings and externalized runners.

Required gates:

- Bot event routing uses `event_bindings` as the single routing source.
- Legacy bot pipeline routing fields are removed or migrated.
- Pipeline works as a message-only processor.
- Agent runner plugin smoke tests pass with local and Dify runners.
- Migration naming and downgrade paths are valid.
- Primary UI no longer exposes "EBA" in user-facing adapter names.

### Phase 1: Private Beta for Technical Users

Goal: make the system usable by contributors and early self-host adopters.

Required gates:

- adapter capability matrix exists in docs and UI;
- route editor filters incompatible targets;
- runner/plugin health checks are visible;
- local Agent and Dify Agent setup has a guided path;
- per-route run trace exists;
- deprecated adapters are marked consistently;
- failure messages identify the failing layer.

### Phase 2: Product Beta for Non-Technical Users

Goal: let users complete common scenarios without reading architecture docs.

Required gates:

- first-run bot wizard starts from use case and channel;
- event presets hide raw event patterns by default;
- route simulation or test event exists;
- common processor templates exist;
- conflict warnings and fallback behavior are clear;
- docs use product language first and advanced terms later;
- SaaS namespace schema is implemented or migration-ready.

### Phase 3: SaaS Beta

Goal: run the product for multiple tenants safely.

Required gates:

- tenant/workspace/namespace fields exist on all routing, runtime, state, log, and resource facts;
- namespace-scoped runtime registration and run claim are enforced;
- namespace-scoped secrets and adapter installs are enforced;
- route matching and audit are namespace-local;
- quotas, retention, and admin audit surfaces exist;
- migration from self-host default namespace is documented.

### Phase 4: GA

Goal: make the product reliable for broad adoption.

Required gates:

- solution export/import is implemented with dependency and variable resolution;
- marketplace distribution supports namespace-local installation;
- cross-namespace sharing policy is explicit;
- security review covers adapters, runtime tokens, runner APIs, secrets, logs, and route replay;
- upgrade and rollback procedures are documented;
- product telemetry measures onboarding drop-off and route failure categories.

## 8. Acceptance Checklist

A release can be considered product-ready only when:

- a non-technical user can connect a supported channel, choose a scenario, bind a processor, test it, and understand the result without editing raw JSON;
- the product UI avoids internal terms such as EBA in primary flows;
- Bot page owns platform event routing and Agent page owns reusable processors;
- Pipeline remains visible as a no-code message processor and is not offered for non-message events;
- different events on one bot can route to different processor types;
- route failures are explained by layer;
- namespace isolation is enforced by schema, service checks, runtime tokens, storage keys, and tests;
- export/import, when implemented, uses Solution packages with route templates rather than concrete bot bindings.

## 9. Open Decisions

- Final user-facing name for the combined processor surface: "Agent", "Processor", or another term.
- Whether Workflow should be a separate persisted processor type or an Agent runner category.
- Whether SaaS namespaces should map one-to-one to workspaces initially, or whether advanced tenants need multiple namespaces per workspace from the first SaaS beta.
- Which adapters are allowed in SaaS shared runtime and which require dedicated runtime isolation.
- Exact package format for future Solution export/import.
