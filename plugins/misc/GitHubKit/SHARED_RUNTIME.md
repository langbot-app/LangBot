# Shared runtime source candidate (SDK >=0.7.4)

`manifest.yaml` declares `execution.sharedRuntime: shared-runtime-v1` **and**
`execution.componentModel: stateless-v1`. This source is **not certified** and
makes no claim of live acceptance: the archive still needs independent review,
signer approval, and two-Workspace invocation acceptance.

Under shared placement one process serves every installation of the artifact
digest and `initialize()` runs once per worker with an empty config, so the
plugin treats its own object as a process-wide singleton.

## Per invocation

- `language`, `github_token`, `poll_interval` and `max_events_per_push` are read
  from `get_config()` on every command invocation; none of them are stored on the
  plugin object.
- `initialize()` only returns: it starts no poller and reads no tenant config or
  storage.
- Every GitHub API call builds a per-request `httpx.AsyncClient` and uses the
  invoking installation's token.

## Binding-keyed, released on revocation

- Subscriptions are persisted per installation under
  `subscriptions:<instance>:<workspace>:<installation>`, because Host storage
  rows are keyed by `[instance, workspace, owner_type, owner, key]` with no
  installation dimension. A shared worker without a trusted binding refuses to
  read or write tenant state instead of falling back to a shared key.
- One background poller task per installation, registered under the full
  binding. It re-enters an invocation carrying the config and binding captured
  when it started (detached tasks do not inherit a live invocation) and polls
  only that installation's subscriptions, pushing with that installation's
  credentials.
- `on_installation_revoked(binding)` cancels that installation's poller and
  drops its registry entry (task, lock, config snapshot) before returning.
- A worker upgrade keeps the same installation scope (only
  `runtime_revision` changes), so next-invocation poller startup restarts the
  task with the new binding.

## Known limits

- Event push does not self-resume after a worker restart until that installation
  next invokes a GitHubKit command (a query or `!gh sub`); shared placement has
  no per-installation `initialize()` hook.
- A config change (for example a rotated token) takes effect on that
  installation's next invocation; a poller that is already running keeps its
  captured poll interval until then.
- Pre-upgrade subscriptions written under the legacy unscoped `subscriptions`
  row are not adopted by a shared worker. Dedicated (binding-less) placement
  keeps using the legacy key unchanged.
- Tests use the installed SDK, a synthetic Host KV that mirrors the real row
  key, and a stubbed GitHub transport. They are not a live GitHub or LangBot
  database test, and no network-egress acceptance ran here.
