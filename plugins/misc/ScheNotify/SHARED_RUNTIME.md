# Shared runtime placement (`shared-runtime-v1` + `stateless-v1`)

This source declares `execution.sharedRuntime: shared-runtime-v1` and
`execution.componentModel: stateless-v1` in `manifest.yaml`. It is a source
declaration only: it is **not certified**, has no signed archive, and has not been
accepted against a live multi-Workspace deployment. The exact archive still needs
independent review and acceptance runs.

Under shared placement one `ScheNotify` object and one of every declared component
serve every installation of the artifact digest. Installation attachments are
lightweight contexts; they do not create another object graph.

## Per invocation

- The `language` config is read through `self.plugin.get_config()` inside the
  command and Tool components that use it. No config value is stored on the shared
  object or in a scheduled event.
- `get_installation_binding()` is read per invocation and never retained past the
  call; it decides which installation's schedule `add_scheduled_event`,
  `get_scheduled_events` and `delete_scheduled_event` read and write.
- Inside one installation a reminder belongs to the full session identity
  `(bot_uuid, target_type, target_id)` derived from the trusted platform session.
  The `!sche` and `!dsche` commands pass that key, and `delete_scheduled_event`
  refuses to remove a record that does not belong to the caller's session, so two
  bots of one installation, or the person/group namespaces with the same id, are
  never treated as the same session.
- `initialize()` is process-scoped and only logs: it runs once per worker with an
  empty config, before any installation is known, so it starts no scheduler.

## Per binding, released on revocation

- `_events` is keyed by the installation scope
  `<instance_uuid>:<workspace_uuid>:<installation_uuid>` and holds that
  installation's pending reminders only. `runtime_revision` is deliberately excluded
  from the token, so a worker upgrade does not orphan a tenant's pending reminders
  within the process lifetime.
- `_loops` holds one minute-scheduler task per installation scope.
- `BasePlugin.on_installation_revoked(binding)` cancels that installation's
  scheduler (bounded 5 s wait) and drops its pending reminders, so a revoked
  installation can never fire an already-scheduled notification afterwards.
- The schedule is in-memory only (unchanged pre-existing behaviour): nothing about a
  reminder is written to Host storage, so revocation has no durable row to clean up.
- Dedicated (binding-less) workers keep a single binding-less schedule and their
  existing behaviour; their schedulers are stopped by process shutdown.

## The detached scheduler

Each installation's scheduler is a detached task, registered per installation and
stopped by revocation. It carries its installation scope as an explicit argument
and re-enters the invocation it was started from: the handler, config and binding
captured at scheduling time are passed back into `bind_invocation(...)` for the
whole life of the loop, so every `SEND_MESSAGE` a firing reminder makes is
attributable to the installation that scheduled it instead of falling back to the
worker's connection default. `on_installation_revoked(binding)` cancels the task,
which exits that scope and drops the authority with it; the same hook drops the
installation's pending reminders, so a revoked (or upgraded) installation can
neither fire nor send afterwards. Because the scope token excludes
`runtime_revision`, a worker upgrade presents a new binding for the same token;
the next scheduling invocation then cancels the superseded task and starts the
loop again under the new binding, while the installation's pending reminders are
kept. The scheduler never reads config or any other invocation-scoped API itself:
delivery is language-independent (`NOTIFY_PREFIX`).

## Known limits

- The scheduler is in-memory: pending reminders are lost on process restart (also
  the pre-existing behaviour).
- Editing the `language` config only affects messages produced by later
  invocations; notification delivery itself reads no config, because the prefix is
  language-independent (the previous per-language lookup produced the same literal
  for both supported languages and was removed).
- `get_scheduled_events()` returns a new list of the pending event records; the
  records themselves are the live dicts, so callers must not mutate them.
- One installation's queue holds at most `MAX_EVENTS_PER_INSTALLATION` (100)
  reminders and each stored message is capped at `MAX_MESSAGE_LENGTH` (2000)
  characters; further reminders are rejected with a message instead of growing the
  worker's memory. A delivery that the Host refuses is kept queued with its failure
  count recorded, so it is retried on the next pass instead of being dropped.
- Per-installation state is only freed by revocation. The runtime revokes on
  uninstall, disable, Workspace removal and upgrade.
- Revocation is serialized per installation but may overlap with sibling
  installations' invocations; per-installation state is isolated, nothing is shared.

## Tests

`tests/test_installation_schedule.py` drives two distinct `InstallationBinding`s
(same instance and Workspace, different installation uuids) through one plugin
object with the installed SDK's `bind_invocation`, over a stub Host that records
notification relays. It asserts that B's `get_scheduled_events` returns only B's
reminder (pre-fix it returned both, from one shared list), that A's scheduler fires
only A's due reminder and leaves B's pending, that the scheduler is registered per
binding and stopped by revocation with the revoked installation's schedule dropped
(no late delivery) while a sibling's schedule survives, that `initialize()` starts
no scheduler, and that the scope token is the full binding.

The second-round tests add: the detached relay's Host call carries the scheduling
installation's binding (pre-fix `None`); a worker upgrade restarts the loop under
the new binding instead of delivering with the superseded task; `!sche`/`!dsche`
and the Tool use the full session identity, so another bot or namespace with the
same id is neither listed nor deleted (pre-fix the command listed and deleted the
other session's reminder); a refused send stays queued with its failure count; a
sibling delete during the awaited send no longer raises `ValueError` from
`list.remove`; and the queue is bounded while the reminder text is no longer
written to the debug log.
