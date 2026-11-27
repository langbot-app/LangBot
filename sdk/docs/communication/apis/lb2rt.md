# LangBot to Plugin Runtime API Definition

## Connection and authorization contract

The control transport is authenticated before action RPC begins. The newest
authenticated handler takes ownership immediately; any older handler is fenced
and closed.

LangBot must then call the instance-scoped `set_runtime_config` action without a
`context` envelope:

```json
{
  "runtime_identity": {
    "instance_uuid": "instance-id",
    "runtime_id": "short-lived-runtime-id"
  },
  "worker_policy": {
    "max_cpus": 1.0,
    "max_memory_mb": 512,
    "max_pids": 128,
    "max_open_files": 256,
    "max_file_size_mb": 512,
    "require_hard_limits": true
  },
  "runtime_profile": "shared",
  "cloud_service_url": "https://space.langbot.app"
}
```

`runtime_identity` and `worker_policy` are frozen for the lifetime of the
Runtime process. Reconnects may replay the exact values; a changed value is
rejected.

`get_debug_info` and `reconcile_plugin_installations` are also instance-scoped
and do not accept tenant context. Every tenant-scoped LangBot-to-Runtime action
must carry this full context envelope alongside (not inside) its request data:

```json
{
  "instance_uuid": "instance-id",
  "workspace_uuid": "workspace-id",
  "placement_generation": 1,
  "installation_uuid": "installation-id",
  "runtime_revision": 1,
  "artifact_digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

`placement_generation` is the compatibility wire name for execution generation.
The Runtime rejects missing fields, cross-instance actions, cross-Workspace
installation moves, and stale generation or revision transitions. Artifact
digest changes are accepted only as part of a newer revision or generation.

### Runtime profiles and worker isolation

The `shared` profile indexes plugins by the complete installation binding. Code
is digest-verified and shared read-only by digest, while every installation has
its own process and writable `home`, `tmp`, and `data` directories. Worker
registration uses a short-lived, one-use capability bound to that same tuple.
When `worker_policy.require_hard_limits` is true, configuration fails if nsjail
or delegated cgroup v2 controllers are unavailable. The `oss_dev` profile is the
default and retains direct local processes and artifact `.env` loading.
The legacy `install_plugin`, `restart_plugin`, `delete_plugin`, and
`upgrade_plugin` actions are rejected in `shared`; shared lifecycle changes use
only `apply_plugin_installation`, `remove_plugin_installation`, and reconcile.

## `reconcile_plugin_installations`

This instance-scoped action replays the authoritative desired state and carries
no context envelope.

### Request

```json
{
  "installations": [
    {
      "binding": {
        "instance_uuid": "instance-id",
        "workspace_uuid": "workspace-id",
        "placement_generation": 1,
        "installation_uuid": "installation-id",
        "runtime_revision": 1,
        "artifact_digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      },
      "enabled": true
    }
  ]
}
```

### Response

```json
{
  "applied": ["installation-id"],
  "removed": [],
  "missing_artifacts": ["installation-id"],
  "failed_installations": [
    {
      "installation_uuid": "installation-id",
      "error_code": "dependency_prepare_failed",
      "message": "Plugin dependency installer exited with code 1"
    }
  ]
}
```

## `apply_plugin_installation`

This tenant-scoped action carries the installation binding in the context
envelope. If the artifact is not cached, transfer it first with `file_chunk`
using the same context and pass the resulting opaque file key.

### Request

```json
{
  "artifact_file_key": "opaque-transfer-key.zip",
  "enabled": true
}
```

`artifact_file_key` may be omitted when the digest is already cached.

### Response

```json
{
  "installation_uuid": "installation-id",
  "state": "starting",
  "artifact_path": "data/plugin-runtime/artifacts/sha256/0123.../code"
}
```

`state` is `starting`, `disabled`, `artifact_missing`, `failed`, or `superseded`.
The artifact path is omitted for `artifact_missing`. `superseded` means a newer
concurrent desired-state transition fenced the apply while its dependencies were
being prepared. A dependency preparation failure returns the stable
`error_code=dependency_prepare_failed` plus a safe message and never launches a
worker. Reapplying the same desired revision retries the preparation.

## `remove_plugin_installation`

This tenant-scoped action carries the exact current binding in the context
envelope. A stale removal is rejected.

### Request

```json
{}
```

### Response

```json
{
  "installation_uuid": "installation-id",
  "state": "removed"
}

## `list_plugins`

### Request

```json
{}
```

### Response

```json
{
    "plugins": [
        {
            "id": "plugin_id",
            "name": "plugin_name",
            "version": "plugin_version"
        }
    ]
}
```

## `install_plugin`

### Request

```json
```

### Response

```json
```

## `emit_event`

### Request

```json
{
    "event_context": {},
    "include_plugins": ["author/name"]
}
```

### Response

```json
{
    "emitted_plugins": [],
    "response_sources": [
        {
            "kind": "reply_message_chain",
            "plugin": {
                "author": "plugin_author",
                "name": "plugin_name"
            }
        }
    ],
    "event_context": {}
}
```

`emitted_plugins` contains plugins whose event handlers ran. `response_sources`
attributes event-context changes to the plugin that made them:

- `reply_message_chain`: the plugin changed the deferred reply on the event.
- `prevent_default`: the plugin turned on `prevent_default`, i.e. took the
  message over from the pipeline. Only the first plugin that sets the flag is
  reported.

Consumers must ignore `kind` values they do not know.

When the Host sets `origin_attribution: true` on the event context, plugin-level
`invoke_llm`, `invoke_llm_stream` and `send_message` calls made while the event
handler runs add `origin_query_uuid` (the event's `query_uuid`) to their action
payload. Hosts that do not set the flag never receive the field, so their strict
input schemas keep working. LangBot uses it only to attribute monitoring records to the
triggering message, never for authorization. Calls made after the handler
returns (for example from a detached task) do not carry it.

## `list_tools`

### Request

```json
```

### Response

```json
```

## `call_tool`

### Request

```json
```

### Response

```json
```
