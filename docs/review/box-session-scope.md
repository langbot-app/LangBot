# Box Session Scope

> Last reviewed: 2026-07-12
> Status: implemented Host-owned, hashed execution scope; Runner/Pipeline session templates are removed.
> Related: [Box Architecture](./box-architecture.md) | [Box vs Plugin Runtime](./box-vs-plugin-runtime.md)

## 1. Decision

The LangBot Host owns the Box session used by an event run. A Pipeline, Agent,
or AgentRunner cannot choose a global, per-user, per-conversation, or per-query
sandbox mode.

`BoxService.resolve_box_session_id(query)` always returns this shape:

```text
lb-box-<64 lowercase SHA-256 hex characters>
```

The result is exactly 71 ASCII characters. Raw platform, user, group,
conversation, thread, and event identifiers never appear in the Box session
id. This avoids unsafe path characters, unbounded identifier length, and
identity leakage through runtime/container metadata.

This rule replaces all former concepts of:

- Pipeline or Runner `box-session-id-template` fields;
- a global forced session template;
- API fields that let a caller supply sandbox scope;
- LocalAgent-specific Host injection of Box availability, scope, or Pipeline id.

## 2. Canonical Host scope

Before hashing, the Host creates a canonical, sorted JSON scope with these
dimensions:

| Dimension | Purpose |
| --- | --- |
| `instance_id` | Isolate separate LangBot installations |
| `workspace_id` | Preserve workspace/tenant boundary when available |
| `bot_id` | Prevent two bots from sharing a sandbox accidentally |
| `platform_adapter` | Separate identical target ids from different adapters |
| `target_type` / `target_id` | Identify the platform session or event target |
| `thread_id` | Isolate threads within a target when available |

The canonical JSON is domain-separated and hashed by the Host. Runner input,
runner config, and tool parameters are not trusted sources for this scope.

### 2.1 Target identity priority

The Host resolves `target_type` / `target_id` in this order:

1. For a Pipeline-backed run, use the exact Query launcher tuple.
2. For a pure EBA run, use `delivery.reply_target.target_type/target_id`
   (`launcher_type/launcher_id` aliases are accepted).
3. If there is no delivery target, use `conversation_id`.
4. For a non-message event without a conversation, use `event_id`, producing
   an event-scoped sandbox.

The adapter class or declared adapter capability supplies platform adapter
identity. The Host includes the active LangBot instance, workspace, bot, and
thread dimensions when they exist.

### 2.2 Stability and isolation

The same normalized scope always produces the same hash, so repeated runs in
the same platform conversation reuse the same Box workspace. A rotating
transcript/conversation id does not change the scope when an explicit platform
reply target remains the same.

A different target, thread, workspace, bot, platform adapter, or LangBot
instance changes the hash. If delivery target is unavailable and
`conversation_id` is the fallback, different conversations also produce
different hashes. Event-scoped fallback isolates unrelated non-message events.

### 2.3 Fail closed

If the private Host scope marker is present but empty or malformed, Box rejects
execution with `BoxValidationError`. A direct Query without either a valid
Host scope or launcher/session identity is also rejected. There is no
`unknown`, raw query id, global, or caller-selected fallback.

## 3. Host execution Query

AgentRunner callbacks need a Host-owned Query view because model/tool loaders
already consume that type. The Query is internal and is never exposed as a
Runner-controlled object.

- A Pipeline run stores the exact current Query in `AgentRunSession`.
- A pure EBA run builds a minimal Query with a valid Session and
  `pipeline_config=None`, `pipeline_uuid=None`.
- The Host attaches canonical `_host_box_scope` and the authorized skill names
  in `_pipeline_bound_skills`.
- `PluginToRuntimeAction.CALL_TOOL` restores this Query from the active
  `run_id` before dispatching to `ToolManager`.

This gives Pipeline and pure EBA execution the same Host tool path without
inventing a fake Pipeline for an independent Agent.

## 4. AgentRunner callback paths

AgentRunner implementations may use either callback transport:

1. SDK/Python runners call `AgentRunAPIProxy.call_tool`.
2. External harnesses call the SDK-owned scoped MCP bridge.

Both transports emit the same `PluginToRuntimeAction.CALL_TOOL`. The Host then
validates the same run authorization, restores the same execution Query, and
dispatches to the same ToolManager and BoxService.

```text
AgentRunner
  +-- AgentRunAPIProxy.call_tool --------+
  |                                      |
  +-- SDK-owned scoped MCP bridge -------+--> PluginToRuntimeAction.CALL_TOOL
                                              --> run authorization
                                              --> execution Query
                                              --> ToolManager
                                              --> BoxService
                                              --> lb-box-<sha256>
```

An AgentRunner is not required to use MCP. Local Python runners can use the SDK
directly; code-agent harnesses can use the bridge. The transports do not define
different authorization or sandbox semantics.

## 5. Skills and mounts

Native exec and skill-backed exec for one Host scope use the same hashed
session. `BoxService.build_skill_extra_mounts(query)` adds visible, authorized
skill packages under `/workspace/.skills/<name>` when the session is created.

Skill activation controls which skill-backed tools and paths are available. It
does not create a different session and does not grant the Runner authority to
change the session id.

## 6. `mcp-shared` is a different session

LangBot can host configured stdio MCP servers as managed processes inside Box.
Those long-lived infrastructure processes share the dedicated `mcp-shared`
session and are isolated from one another by `process_id`.

This is separate from the scoped MCP bridge above:

| Path | Purpose | Session rule |
| --- | --- | --- |
| AgentRunner scoped MCP bridge | Call authorized Host tools for one active run | Host-owned `lb-box-<sha256>` from the run execution Query |
| MCP-in-Box stdio server | Keep configured MCP server processes running | Dedicated persistent `mcp-shared` session |

Calling a sandbox tool through the AgentRunner bridge never redirects the run
workspace into `mcp-shared`. Conversely, an MCP server's managed-process
lifecycle does not inherit the current event scope.

## 7. Configuration and compatibility

There is no Box session scope field in Pipeline metadata, AgentRunner config,
or the public Pipeline/Runner API. Operators configure the Box subsystem itself
(`box.enabled`, backend/runtime settings, profiles, mount allowlists, quotas,
and workspace roots), not per-Runner session templates.

Old configuration containing `box-session-id-template` is unsupported in the
4.x contract. LangBot 4.x does not migrate LangBot 3.x configuration or
databases, so the removed field is not read as a compatibility fallback.

## 8. Regression coverage

Release tests should prove:

- every event-run session id matches `lb-box-[0-9a-f]{64}` and contains no raw
  identity;
- the same canonical Host scope is stable while different targets,
  conversations, threads, bots, adapters, workspaces, or instances are
  isolated;
- Pipeline and pure EBA runs representing the same platform session produce
  the same canonical scope;
- missing Host/Query identity fails closed;
- SDK/Python `call_tool` and the scoped MCP bridge both enter
  `PluginToRuntimeAction.CALL_TOOL` and restore the run execution Query;
- Runner payload/config cannot override the session id;
- stdio MCP processes remain in `mcp-shared` and are isolated by process id;
- authorized skills are mounted into the hashed run session without creating
  per-skill sessions.
