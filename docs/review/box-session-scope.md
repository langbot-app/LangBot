# Box Session Scope Design

> Date: 2026-04-18
> Branch: `feat/sandbox` (LangBot + langbot-plugin-sdk)
> Related: [Box Architecture](./box-architecture.md) | [Box vs Plugin Runtime](./box-vs-plugin-runtime.md)

---

## 1. Problems

### 1.1 Default exec: per-message containers

Currently, `BoxService.execute_tool()` sets `session_id = str(query.query_id)` — an
auto-incrementing integer per incoming message. Every user message creates a new sandbox
container. Dependencies installed and in-container state are lost between messages.

### 1.2 Three isolated container pools

Default exec, skills, and MCP servers each manage their own containers with
independent session IDs:

| Path         | Session ID                                    | Container   |
|--------------|-----------------------------------------------|-------------|
| Default exec | `str(query_id)` (per message)                 | Ephemeral   |
| Skill exec   | `skill-{launcher}_{id}-{skill_name}`          | Per skill   |
| MCP stdio    | `mcp-{server_uuid}`                           | Per server  |

This means a single logical user interaction can spawn 3+ containers that cannot
share state, see each other's files, or reuse installed dependencies.

### 1.3 Single bind mount limitation

`BoxSpec` currently supports only **one** `host_path` → `mount_path` bind mount.
This prevents mounting both a default workspace and skill directories into the
same container.

---

## 2. Concept Model

```
Platform Message
  → Query (query_id: int, auto-increment, per message)
    → Session (launcher_type + launcher_id, per chat window)
      → Conversation (uuid, per dialogue context within a Session)
```

| Concept       | Key                                 | Example                    | Scope                        |
|---------------|-------------------------------------|----------------------------|------------------------------|
| Query         | `query_id`                          | `42`                       | Single message               |
| Session       | `launcher_type` + `launcher_id`     | `group_123456`             | Chat window (group or PM)    |
| Conversation  | `conversation_id` (UUID)            | `a1b2c3d4-...`             | Dialogue context within a Session |
| Sender        | `sender_id`                         | `789`                      | Individual user              |

Note: in a **group chat**, all users share the same Session (keyed by `group_id`). The
individual sender is tracked as `sender_id` but does not affect Session/Conversation routing.

---

## 3. Target Scenarios

| #  | Scenario                       | Box Granularity                          | Desired `session_id`                                   |
|----|--------------------------------|------------------------------------------|---------------------------------------------------------|
| 1  | Personal assistant             | 1 Box per user, long-lived               | `{launcher_type}_{launcher_id}`                          |
| 2  | Customer service               | 1 Box per customer, cross-pipeline       | `{launcher_type}_{launcher_id}`                          |
| 3  | Internal employee tool         | 1 Box per employee                       | `{launcher_type}_{launcher_id}`                          |
| 4  | Group chat shared assistant    | 1 Box per group                          | `{launcher_type}_{launcher_id}`                          |
| 5  | Group chat isolated per user   | 1 Box per user within a group            | `{launcher_type}_{launcher_id}_{sender_id}`              |
| 6  | Teaching (cross-channel)       | 1 Box per student across groups/PMs      | `{sender_id}`                                           |
| 7  | One-off execution              | 1 Box per message (current behavior)     | `{query_id}`                                            |
| 8  | Multi-project development      | 1 Box per conversation context           | `{launcher_type}_{launcher_id}_{conversation_id}`        |

No single fixed granularity covers all scenarios. A template-based approach is needed.

---

## 4. Design Overview

Two key changes:

1. **Unified container**: exec, skills, and MCP all share the same container per
   session scope. No more separate container pools.
2. **Configurable session scope**: `session_id` is generated from a template with
   pipeline variables, configurable per pipeline.

### 4.1 Unified Container with Multiple Mounts

A single container per session scope is created on first use. It has:

- **Primary mount**: default workspace at `/workspace` (from `default_host_workspace`)
- **Skill mounts**: each pipeline-bound skill's `package_root` mounted at
  `/workspace/.skills/{skill_name}/`
- **MCP servers**: run as managed processes inside the same container

```
Container (session_id = "group_123456")
  /workspace/                          ← default workspace (bind mount, rw)
  /workspace/.skills/web-search/       ← skill package (bind mount, rw)
  /workspace/.skills/data-analysis/    ← skill package (bind mount, rw)
  [managed process: mcp-server-a]      ← MCP server running inside
  [managed process: mcp-server-b]      ← MCP server running inside
```

This requires extending `BoxSpec` to support multiple mounts (see §5).

### 4.2 Session ID Template

A new field `box-session-id-template` in the `local-agent` pipeline runner config
controls the session scope:

```yaml
# templates/metadata/pipeline/ai.yaml (under local-agent.config)
- name: box-session-id-template
  label:
    en_US: Sandbox Scope
    zh_Hans: 沙箱作用域
  description:
    en_US: >-
      Determines how sandbox environments are shared. Use variables to
      control isolation granularity.
    zh_Hans: >-
      决定沙箱环境的共享方式。使用变量控制隔离粒度。
  type: select
  required: false
  default: "{launcher_type}_{launcher_id}"
  options:
    - value: "{launcher_type}_{launcher_id}"
      label:
        en_US: Per chat (Recommended)
        zh_Hans: 每个会话（推荐）
    - value: "{launcher_type}_{launcher_id}_{sender_id}"
      label:
        en_US: Per user in chat
        zh_Hans: 会话中每个用户
    - value: "{launcher_type}_{launcher_id}_{conversation_id}"
      label:
        en_US: Per conversation context
        zh_Hans: 每个对话上下文
    - value: "{query_id}"
      label:
        en_US: Per message (isolated)
        zh_Hans: 每条消息（完全隔离）
```

Available template variables (populated by PreProcessor in `query.variables`):

| Variable            | Source                          | Example              |
|---------------------|---------------------------------|----------------------|
| `{launcher_type}`   | `query.session.launcher_type`   | `person` / `group`   |
| `{launcher_id}`     | `query.session.launcher_id`     | `123456`             |
| `{sender_id}`       | `query.sender_id`               | `789`                |
| `{conversation_id}` | `conversation.uuid`             | `a1b2c3d4-...`       |
| `{query_id}`        | `query.query_id`                | `42`                 |

Default `{launcher_type}_{launcher_id}` covers scenarios 1–4 out of the box.

---

## 5. SDK Changes: Multi-Mount BoxSpec

### 5.1 Model Extension

```python
# box/models.py

class BoxMountSpec(pydantic.BaseModel):
    """A single bind mount specification."""
    host_path: str
    mount_path: str
    mode: BoxHostMountMode = BoxHostMountMode.READ_WRITE

class BoxSpec(pydantic.BaseModel):
    # ... existing fields ...
    host_path: str | None = None              # Primary mount (backward compat)
    host_path_mode: BoxHostMountMode = BoxHostMountMode.READ_WRITE
    mount_path: str = DEFAULT_BOX_MOUNT_PATH
    extra_mounts: list[BoxMountSpec] = []     # NEW: additional mounts
```

`extra_mounts` is additive — the existing `host_path` / `mount_path` pair remains
the primary mount for backward compatibility.

### 5.2 Backend: Apply Extra Mounts

```python
# box/backend.py — CLISandboxBackend.start_session()

# Primary mount (unchanged)
if spec.host_path is not None and spec.host_path_mode != BoxHostMountMode.NONE:
    args.extend(['-v', f'{spec.host_path}:{spec.mount_path}:{spec.host_path_mode.value}'])

# Extra mounts (NEW)
for mount in spec.extra_mounts:
    if mount.mode != BoxHostMountMode.NONE:
        args.extend(['-v', f'{mount.host_path}:{mount.mount_path}:{mount.mode.value}'])
```

Same pattern for nsjail backend.

---

## 6. LangBot Changes

### 6.1 Session ID Resolution

In `BoxService.execute_tool()`:

```python
# Before:
spec_payload.setdefault('session_id', str(query.query_id))

# After:
template = (query.pipeline_config or {}).get('ai', {}) \
    .get('local-agent', {}).get('box-session-id-template',
         '{launcher_type}_{launcher_id}')
variables = query.variables or {}
session_id = template.format_map(collections.defaultdict(
    lambda: 'unknown', variables
))
spec_payload.setdefault('session_id', session_id)
```

### 6.2 Skill Exec: Use Same Container

Currently `native.py:_invoke_exec` creates a separate `BoxWorkspaceSession` per
skill with `host_path=package_root`. Instead:

1. Use the **same session_id** as default exec (from the template).
2. Pass the skill's `package_root` as an **extra mount** at
   `/workspace/.skills/{skill_name}/` instead of replacing `/workspace`.
3. The container already has the default workspace at `/workspace`.

```python
# native.py — _invoke_exec, skill branch (REVISED)

# Same session_id as default exec
session_id = resolve_box_session_id(query)

spec_payload = {
    'cmd': rewritten_command,
    'workdir': rewritten_workdir,
    'session_id': session_id,
    'extra_mounts': [{
        'host_path': package_root,
        'mount_path': f'/workspace/.skills/{selected_skill_name}',
        'mode': 'rw',
    }],
}
result = await self.ap.box_service.execute_spec_payload(spec_payload, query)
```

The virtual path `/workspace/.skills/{name}` no longer needs rewriting at the
command level — it maps directly to the bind mount path inside the container.

### 6.3 MCP: Use Same Container

MCP servers should run inside the same container as exec and skills. Changes:

1. `BoxStdioSessionRuntime` uses the pipeline's session_id template instead of
   `mcp-{server_uuid}`.
2. MCP server's working directory is a subdirectory (e.g. `/workspace/.mcp/{name}/`).
3. MCP server's dependencies are mounted or installed into that subdirectory.
4. The MCP server runs as a managed process inside the shared container.

Since MCP servers start at LangBot boot (not per-query), the session must be
created eagerly. The container will be kept alive by the managed process
exemption in TTL reaping (`runtime.py:259`).

**Note**: MCP sessions are pipeline-scoped (not per-launcher), so their session_id
should be a **fixed identifier per pipeline** rather than the user-facing template.
This means one shared MCP container per pipeline, with user exec sessions separate.

Alternatively, in a future iteration, MCP managed processes could be launched
lazily into the user's container on first MCP tool call. This is more complex
but maximizes sharing. For V1, keeping MCP containers at pipeline scope is
simpler and more predictable.

---

## 7. Mount Layout Summary

### Default exec (no skills activated)

```
Container (session_id from template)
  /workspace/          ← default_host_workspace (rw)
```

### Exec with activated skills

```
Container (same session_id)
  /workspace/                          ← default_host_workspace (rw)
  /workspace/.skills/web-search/       ← skill package_root (rw)
  /workspace/.skills/data-analysis/    ← skill package_root (rw)
```

Extra mounts are **additive** — they are added when the container is first
created (or on the first exec that references a skill). Since Docker bind
mounts are specified at container creation time, skills must be known at
creation time.

**Resolution**: When creating a container, inject `extra_mounts` for **all
pipeline-bound skills** (from `extensions_preferences`), not just the
currently activated one. This way any skill can be activated later without
recreating the container.

### MCP servers (V1: pipeline-scoped)

```
Container (session_id = "mcp-pipeline-{pipeline_uuid}")
  /workspace/                    ← MCP shared workspace
  /workspace/.mcp/server-a/      ← MCP server A files
  /workspace/.mcp/server-b/      ← MCP server B files
  [managed process: server-a]
  [managed process: server-b]
```

---

## 8. Data Migration

Existing pipelines do not have `box-session-id-template`. The backend uses
`.get(..., default)` so missing keys fall back to `{launcher_type}_{launcher_id}`.
This changes behavior from per-message to per-launcher for existing pipelines.

Recommendation: **accept the behavior change** — per-launcher is the more
intuitive default, and the old per-message behavior was rarely desired.

---

## 9. Cloud Quota Implications

| Scope                                         | Typical concurrent containers |
|-----------------------------------------------|-------------------------------|
| `{query_id}` (per message)                    | Many, short-lived             |
| `{launcher_type}_{launcher_id}` (per chat)    | = active chat count           |
| `{sender_id}` (per user)                      | = active user count           |
| `{conversation_id}` (per conversation)        | Between per-chat and per-msg  |

With the unified container model, each scope value maps to exactly **one**
container (instead of potentially 3+ per-message). This significantly reduces
resource usage.

Quota enforcement point: `BoxRuntime._get_or_create_session()` in the SDK.

---

## 10. Implementation Phases

### Phase 1: Session scope + skill unification (this PR)

1. **SDK**: Extend `BoxSpec` with `extra_mounts: list[BoxMountSpec]`.
2. **SDK**: Update Docker/nsjail backends to apply extra mounts.
3. **LangBot**: Add `box-session-id-template` to `local-agent` YAML metadata
   and default pipeline config JSON.
4. **LangBot**: Update `BoxService.execute_tool()` to use template interpolation.
5. **LangBot**: Update `native.py:_invoke_exec` skill branch to use same
   session_id + extra mounts instead of separate `BoxWorkspaceSession`.
6. **LangBot**: On container creation, inject extra mounts for all
   pipeline-bound skills.
7. **Frontend**: No code change — `DynamicFormComponent` renders `select` fields.
8. **Tests**: Unit tests for template interpolation and multi-mount specs.

### Phase 2: MCP unification (future)

1. Refactor `BoxStdioSessionRuntime` to use pipeline-scoped shared container.
2. MCP servers become managed processes in the shared container.
3. Support multiple concurrent managed processes per container.

MCP unification is deferred because it requires changes to the managed process
model (currently 1 managed process per session) and has startup ordering
concerns (MCP servers start at boot, before any user query determines
a session_id).
