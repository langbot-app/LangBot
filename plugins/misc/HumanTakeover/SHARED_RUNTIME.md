# Shared runtime source candidate (SDK >=0.7.4)

`manifest.yaml` declares `execution.sharedRuntime: shared-runtime-v1` **and**
`execution.componentModel: stateless-v1`. This source is **not certified** and
makes no claim of live acceptance: the archive still needs independent review,
signer approval, and two-Workspace invocation acceptance.

Under shared placement one process serves every installation of the artifact
digest and `initialize()` runs once per worker with an empty config, so the
plugin treats its own object as a process-wide singleton.

## Per invocation

- `takeover_timeout`, `trigger_words` and `auto_takeover_on_trigger` are read
  from `get_config()` on every invocation; none of them are stored on the plugin
  object.
- `initialize()` only returns: it reads no config and performs no storage IO.
- Sessions and message history are loaded lazily on the first invocation of each
  installation (`load_state()`), so the EventListener and the console Page
  sharing this object always see the invoking installation's sessions.
- One installation may serve several bots/adapters, so a session key carries the
  trusted bot identity resolved from the event query
  (`<bot_uuid>:<launcher_type>_<launcher_id>`). Events without a trusted bot uuid
  are not recorded, a session refuses another bot's or adapter's identity, and
  pre-identity (unscoped) keys are frozen rather than merged into a bot's session.

## Binding-keyed, released on revocation

- The `sessions` / `messages` caches live in per-installation state keyed by the
  full binding; the class attributes are read-only properties resolving to the
  current invocation's state.
- Durable rows are namespaced per installation:
  `<instance>:<workspace>:<installation>:ht_storage_schema`,
  `...:ht_session_v2_<sha256(session_key)>`, and the legacy
  `ht_sessions` / `ht_messages` backup keys under the same scope prefix. Host
  storage rows have no installation dimension, so the scope has to live in the
  plugin's own key. A shared worker without a trusted binding refuses to read or
  write tenant state instead of falling back to a shared key.
- The per-session write lock and the ambiguous-write fence
  (`storage_uncertain` / `load_failed`) are per installation: one installation's
  failed write never blocks a sibling. Every state-changing path re-checks the
  fence after acquiring the installation lock, so a caller already queued for that
  lock cannot cross a failure that landed while it waited; only the explicit
  recovery path (`reconcile()`, which re-reads that installation's rows) lifts the
  barrier, and an ordinary load never clears it.
- `on_installation_revoked(binding)` drops that installation's cached sessions,
  history, lock and fence before returning.

## Known limits

- Pre-upgrade rows written under the legacy unscoped `ht_storage_schema` /
  `ht_session_v2_*` keys are not adopted by a shared worker. Dedicated
  (binding-less) placement keeps using the legacy keys unchanged.
- A cancelled load stays retryable, and a cancelled write keeps the lock until
  the shielded remote commit settles; an ambiguous remote outcome fences that
  installation until `reconcile()`.
- `HumanTakeover` keeps no detached tenant-bearing task, so revocation only has
  to release the cache.
- Tests use the installed SDK and a synthetic Host KV that mirrors the real row
  key; the stdio regression test uses the real SDK over an OS subprocess. They
  are not a live LangBot database test.
