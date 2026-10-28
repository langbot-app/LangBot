# Shared runtime placement (`shared-runtime-v1` + `stateless-v1`)

This source declares `execution.sharedRuntime: shared-runtime-v1` and
`execution.componentModel: stateless-v1` in `manifest.yaml`. It is a source
declaration only: it is **not certified**, has no signed archive, and has not been
accepted against a live multi-Workspace deployment. The exact archive still needs
independent review and acceptance runs.

Under shared placement one `KeywordAlert` object and one `KeywordMonitor` event
listener serve every installation of the artifact digest. Installation attachments
are lightweight contexts; they do not create another object graph.

## Per invocation

- `keywords`, `group_ids`, `admin_id`, `bot`, `case_sensitive` and
  `cooldown_seconds` are read through `self.get_config()` on every group-message
  invocation, from the plugin or from the listener component's
  `get_plugin_config()`. No config value is stored on the shared object.
- `get_installation_binding()` is read per invocation and never retained past the
  call; it is read when the cooldown table for the current installation is resolved.
- `initialize()` is process-scoped and only logs: it runs once per worker with an
  empty config, before any installation is known.

## Per binding, released on revocation

- `_cooldowns` is keyed by the installation scope
  `<instance_uuid>:<workspace_uuid>:<installation_uuid>` and then by
  `(group_id, keyword)`. `runtime_revision` is deliberately excluded from the token
  so a worker upgrade does not hand a tenant a fresh cooldown window.
- `BasePlugin.on_installation_revoked(binding)` pops exactly that scope and touches
  process-local state only — no Host API is available during revocation. Nothing is
  persisted, so no durable row is involved.
- Dedicated (binding-less) workers keep a single binding-less cooldown table, i.e.
  their existing behaviour.

## Known limits

- Cooldowns are in-memory and process-lifetime only (unchanged pre-existing
  behaviour): a worker restart clears them, and revocation clears a revoked
  installation's window.
- The per-installation cooldown table grows with the number of distinct
  (group, keyword) pairs seen by that installation; it is freed by revocation. The
  runtime revokes on uninstall, disable, Workspace removal and upgrade.
- Revocation is serialized per installation but may overlap with sibling
  installations' invocations; per-installation state is isolated, nothing is shared.
- Alert delivery runs inside the group-message invocation and therefore uses that
  invocation's authority; the plugin creates no detached task.

## Tests

`tests/test_installation_cooldown.py` drives one plugin object plus one real
`KeywordMonitor` component object through two distinct `InstallationBinding`s (same
instance and Workspace, different installation uuids) with the installed SDK's
`bind_invocation`, over a stub Host that records alert relays. It asserts that the
same message in the same group produces one alert **per** installation (pre-fix:
one relay total, because A's process-global `(group, keyword)` cooldown suppressed
B), that the cooldown still suppresses a repeat inside one installation, that
revocation releases only the revoked installation's table (so its next alert is
allowed again while a sibling is untouched), and that the scope token is the full
binding.
