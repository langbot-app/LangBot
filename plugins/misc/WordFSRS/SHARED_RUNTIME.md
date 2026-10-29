# Shared runtime source candidate (SDK >=0.7.4)

This source declares `shared-runtime-v1` and `stateless-v1`. It is **not certified**
and is not a claim of live acceptance. The exact archive requires independent
review, signer approval, and two-Workspace invocation acceptance.

## What is per invocation

- Tenant settings are read from the invocation snapshot on every use
  (`self.get_config()`), never captured in `initialize()` or in an instance
  field: `language`, `daily_new_limit` and `desired_retention`.
- One `Scheduler(desired_retention=...)` is built per graded card, so two
  installations of the same artifact digest can schedule with different
  retention targets through one process object.
- `initialize()` is process-scoped only; under shared placement it runs once per
  worker with an empty config and it must not read tenant settings.
- Card decks stay in Host KV storage and are loaded/saved per command. No
  installation config, credential or deck is cached on the shared object.
- Deck rows are keyed with the installation scope: Host rows are
  `[instance_uuid, workspace_uuid, owner_type, owner, key]` with **no**
  installation dimension, so the installation identity is carried in the
  plugin's own key.

## Storage key scope

- Shared/bound invocation:
  `deck:<instance_uuid>:<workspace_uuid>:<installation_uuid>:<launcher_type>:<launcher_id>`
  (`runtime_revision` is excluded so a worker upgrade does not orphan the
  tenant's decks).
- Binding-less placement (dedicated worker, or a runtime that sends no
  installation binding): the legacy unscoped row
  `deck:<launcher_type>:<launcher_id>` is used unchanged.
- **No migration is performed.** A legacy row is simply left alone: the scoped
  path never reads it, and the binding-less path never reads a scoped row.
  A deployment that switches from binding-less placement to shared placement
  therefore starts with empty decks; the old rows remain in the Host store.

## What is binding-keyed and released on revocation

- One `asyncio.Lock` per full installation binding
  (`instance:workspace:installation`) serialises the deck read-modify-write of
  `add` / `del` / `grade`, so overlapping commands of one installation cannot
  lose a card (load → modify → save) to each other.
- The lock registry is the only process-local per-tenant state.
  `BasePlugin.on_installation_revoked(binding)` pops that binding's entry.
  Invocations of other installations are unaffected because every lock is
  independent.
- Dedicated workers (no binding) use a single `__unbound__` entry; that process
  state disappears when the dedicated worker shuts down.

## Known limits

- Deck rows are installation-scoped (see above). Two installations of this
  plugin inside one Workspace — even sharing a launcher id — keep separate
  decks, and the binding-less legacy row is reachable only without a binding.
  The trade-off is that the legacy row is not migrated into the scoped
  namespace when placement changes.
- The read-modify-write lock is per installation, not per session: commands of
  one installation are serialised against each other. This is intentionally
  coarse (a few JSON bytes of work) and never crosses installations.
- The lock is in-process only. A crash between the storage read and the write
  still loses the last update; the Host KV store offers no transaction.
- `language` must be one of the message languages shipped in `i18n.py`
  (`en_US`, `zh_Hans`); any other value falls back to the raw key path of
  `get_text`.

## Evidence

`tests/test_shared_runtime.py` drives two installation bindings through one
plugin object with the real SDK `bind_invocation` + `InstallationBinding`
envelope: per-installation language/daily limit, per-installation retention in
the scheduled due date, two concurrent grades on one session (no card lost),
two installations in one Workspace sharing a launcher id (separate deck rows),
the binding-less legacy row, and revocation releasing only the revoked
installation's lock. Every assertion in that file was executed against revision
0.2.2 and fails there.
