# Shared runtime source candidate (SDK >=0.7.4)

This source declares `shared-runtime-v1` and `stateless-v1`. It is **not certified**
and is not a claim of live acceptance. The exact archive requires independent
review, signer approval, and two-Workspace invocation acceptance.

## What is per invocation

- `get_language()` resolves the language from the invocation snapshot
  (`self.get_config()`) on every call. It is never captured in `initialize()` or
  in an instance field, so two installations of the same artifact digest render
  their own language through one process object graph.
- `initialize()` is no longer overridden: this plugin has no process-scoped
  initialization and therefore no place where an (empty) shared config could be
  mistaken for tenant configuration. Dedicated placement still works: inside a
  command invocation the SDK binds the installation config, and outside one
  `get_config()` falls back to the instance config the dedicated worker set.
- Every command renders through `get_text(self.plugin.get_language(), ...)`;
  nothing is stored on the plugin or the command objects.

## Import path handling

- The plugin-root `i18n` module is still imported as a top-level module named
  `i18n` (the layout the plugin ships with), but the `sys.path` entry that makes
  it importable is now added **once**, in the guarded, idempotent insertion in
  `components/__init__.py` (a package initializer runs exactly once per process,
  before any command module body). The six command modules do not mutate
  `sys.path` at import time any more.
- One artifact digest runs in its own worker process, so the top-level `i18n`
  name cannot be shadowed by another plugin.

## What is binding-keyed and released on revocation

- Nothing. The plugin keeps no tenant state in process memory, so
  `on_installation_revoked()` is intentionally not overridden: there is no cache
  or task registry to release. All tenant data (conversations, plugin/tool
  manifests) comes from Host APIs inside the invocation.

## Known limits

- `language` must be a key of `i18n.TRANSLATIONS` (`en_US`, `zh_Hans`); other
  values fall back to `en_US` inside `get_text`.
- The `cmd` / `func` / `plugin` listings index the *other* plugins' manifest
  `metadata.description` dict by the invocation language. A manifest that does
  not provide that language raises `KeyError` (pre-existing behaviour, unchanged
  by this revision).
- No certification claim is made here.

## Evidence

`tests/test_shared_runtime.py` drives two installation bindings through one
plugin object and its real `Reset` / `Help` command components with the real SDK
`bind_invocation` + `InstallationBinding` envelope: each installation renders
its own language, the shared plugin object keeps no tenant attribute, and
importing all six command modules adds at most one `sys.path` entry (the package
initializer's). Every assertion in that file was executed against revision
0.1.9 and fails there.
