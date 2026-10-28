# Shared runtime placement (`shared-runtime-v1` + `stateless-v1`)

This source declares `execution.sharedRuntime: shared-runtime-v1` and
`execution.componentModel: stateless-v1` in `manifest.yaml`. It is a source
declaration only: it is **not certified**, has no signed archive, and has not been
accepted against a live multi-Workspace deployment. The exact archive still needs
independent review and acceptance runs.

Under shared placement one `MCBotPlugin` object and one `MCBot` command component
serve every installation of the artifact digest. Installation attachments are
lightweight contexts; they do not create another object graph.

## Per invocation

- `track_interval` and `ping_timeout` are read through `self.get_config()` inside
  the invocation that needs them (the `!mcbot status` ping, and the invocation that
  starts an installation's tracker). No config value is stored on the shared object.
- `get_installation_binding()` is read per invocation and never retained past the
  call; it is the only authority for which installation's bindings, records and
  storage rows are served. Commands, `bind_server`, `unbind_server`,
  `get_bound_server` and `count_playtime` all resolve it on entry.
- `initialize()` is process-scoped and only logs: it runs once per worker with an
  empty config, before any installation is known, so nothing tenant-bearing (and no
  tracker) is created there.

## Per binding, released on revocation

- `_states` is keyed by the installation scope
  `<instance_uuid>:<workspace_uuid>:<installation_uuid>` and holds that
  installation's `bindings`, `records` and pending-flush flag. `runtime_revision` is
  deliberately excluded so a worker upgrade does not orphan a tenant's playtime
  history.
- `_track_tasks` holds one playtime tracker per installation scope, and
  `_state_locks` one load lock per scope.
- `BasePlugin.on_installation_revoked(binding)` cancels that installation's tracker
  (bounded 5 s wait), drops its state and its lock, and touches process-local state
  only — no Host API is available during revocation.
- Durable state is written under `mcbot_bindings:<scope>` and
  `mcbot_records:<scope>`. The Host row key
  (`[instance_uuid, workspace_uuid, owner_type, owner, key]`) has no installation
  dimension, so the installation identity has to live in the plugin's own key;
  without it, two installations in one Workspace share one row (and the second bind
  overwrote the first).
- Dedicated (binding-less) workers keep the legacy `mcbot_bindings`/`mcbot_records`
  keys and a single in-process state, i.e. their existing behaviour and existing data.

## The detached playtime tracker

The tracker is a detached task, so it is registered per installation and stopped by
revocation. It is started by the first invocation of an installation that has a
bound server, with the sampling interval and ping timeout read from that
invocation's config; a config revision revokes the binding and its task, and the
successor binding reads config again.

It runs in a **fresh context** (`contextvars.Context()`), not the context it was
created in. A task created inside an invocation inherits that invocation's
authority, which is revoked when the invocation returns; every Host call such a
task makes afterwards fails with "Plugin invocation has ended" (the SDK test in
`tests/` asserts exactly that). The tracker therefore performs no Host call at all:
it only pings servers and appends samples to its installation's in-memory records.
Persistence happens later, in an invocation of the same installation, which owns
the authority for that installation's storage row.

## Known limits

- Samples collected by the tracker reach storage on the next invocation of the same
  installation. An installation that has a server bound but never invokes again
  loses its unflushed samples with the process (pre-existing semantics: the
  plugin's records were always process-lifetime data until flushed).
- The tracker only stops on revocation; it keeps running (and short-circuits) while
  an installation has no bound servers, as before.
- The per-installation cache is unbounded apart from the 14-day record retention and
  is only freed by revocation. The runtime revokes on uninstall, disable, Workspace
  removal and upgrade.
- No migration of a pre-existing unscoped `mcbot_bindings`/`mcbot_records` row is
  performed: under shared placement each installation starts from its own empty
  state. Dedicated workers keep reading the legacy rows unchanged.
- Revocation is serialized per installation but may overlap with sibling
  installations' invocations; per-installation state is isolated, nothing is shared.
- Servers are pinged with `mcstatus` only; the plugin makes no other network call.

## Tests

`tests/test_installation_scope.py` drives two distinct `InstallationBinding`s (same
instance and Workspace, different installation uuids) through one plugin object with
the installed SDK's `bind_invocation`, over a stub Host whose row key mirrors
LangBot's flat shape. It asserts that B cannot see A's binding or playtime records,
that the Host receives two distinct binding rows (pre-fix: one shared row that B
overwrote), that records flush only to the owning installation's row, that the
tracker is registered per binding and stopped (and its records dropped) by
revocation while a sibling tracker keeps running, that dedicated binding-less
workers keep the legacy key, and that a task inheriting an invocation context is
rejected by the SDK while the tracker's fresh context is not.
