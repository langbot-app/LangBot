# Runtime profile and shared-runtime notes

`execution.sharedRuntime: shared-runtime-v1` and
`execution.componentModel: stateless-v1` mean one plugin worker can host several
installations of the StickerHub artifact. Every Host call is therefore
installation-scoped:

- Storage keys carry the installation scope
  (`instance:workspace:installation`) inside the plugin key, because the Host
  key space has no installation dimension (see `installation_scope` in
  `main.py`). A scope without a trusted binding is refused under the shared
  profile instead of falling back to a shared key.
- `on_installation_revoked` drops that scope's `StickerStore` and lock from the
  process-wide cache, so a revoked installation's memory is released.
- The `StickerStore` lock serialises writes per scope; concurrent uploads to one
  installation cannot interleave.

The plugin never keeps a process-global list of stickers. `list_stickers` reads
the scoped keys from plugin storage and pages them, so a process restart restores
the same catalogue.
