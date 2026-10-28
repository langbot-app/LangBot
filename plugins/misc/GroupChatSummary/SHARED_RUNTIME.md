# Shared runtime source candidate (SDK >=0.7.4)

`manifest.yaml` declares `execution.sharedRuntime: shared-runtime-v1` **and**
`execution.componentModel: stateless-v1`. This source is **not certified** and
makes no claim of live acceptance: the archive still needs independent review,
signer approval, and two-Workspace invocation acceptance.

Under shared placement one process serves every installation of the artifact
digest and `initialize()` runs once per worker with an empty config, so the
plugin treats its own object as a process-wide singleton.

## Per invocation

- `max_messages`, `default_summary_count`, `auto_summary_enabled`,
  `auto_summary_threshold`, `model` and `language` are read from `get_config()`
  on every invocation; none of them are stored on the plugin object.
- `initialize()` only returns: it loads no buffers and reads no config.
- Message buffers and auto-summary watermarks are loaded lazily on the first
  invocation of each installation (`ensure_loaded()`), not at worker start.

## Binding-keyed, released on revocation

- Buffers and watermarks are cached per installation in a state object keyed by
  the full binding, so the listener, command and tool components sharing this
  object always read the invoking installation's groups.
- They are persisted per installation under
  `message_buffers:<instance>:<workspace>:<installation>` and
  `auto_summary_watermark:<instance>:<workspace>:<installation>`, because Host
  storage rows have no installation dimension. A shared worker without a trusted
  binding refuses to read or write tenant state instead of falling back to a
  shared key.
- The detached auto-summary task is registered under its installation scope and
  re-enters an invocation carrying the config and binding captured when it was
  spawned (detached tasks do not inherit a live invocation), so its LLM and send
  calls cannot escape to another tenant.
- `on_installation_revoked(binding)` drops that installation's buffers and
  cancels/awaits its detached tasks before returning.

## Known limits

- Reads that go through the components (`summary status`, `summary clear`, the
  `summarize_group_chat` tool) call `ensure_loaded()` first; a direct read of
  `plugin.message_buffer` outside an invocation sees the invoking scope only.
- Buffer writes are trimmed to `max_messages` per group; no cross-installation
  aggregation is performed.
- Pre-upgrade buffers written under the legacy unscoped `message_buffers` /
  `auto_summary_watermark` rows are not adopted by a shared worker. Dedicated
  (binding-less) placement keeps using the legacy keys unchanged.
- Tests use the installed SDK and a synthetic Host KV that mirrors the real row
  key; they exercise the real `_auto_summarize` binding re-entry with a stubbed
  summary. They are not a live LLM or LangBot database test.
