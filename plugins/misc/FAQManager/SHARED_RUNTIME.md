# Shared runtime placement (`shared-runtime-v1` + `stateless-v1`)

This source declares `execution.sharedRuntime: shared-runtime-v1` and
`execution.componentModel: stateless-v1` in `manifest.yaml`. It is a source
declaration only: it is **not certified**, has no signed archive, and has not been
accepted against a live multi-Workspace deployment. The exact archive still needs
independent review and acceptance runs.

Under shared placement one `FAQManagerPlugin` object serves every installation of
the artifact digest, and the manager Page, dashboard Page, `search_faq` Tool and
EventListener all reach their data through that single object.

## Per invocation

- `get_installation_binding()` is read per invocation and never retained beyond
  the call; it is the only authority for whose entries are served.
- Every entry point (`get_entries`, `search`, `add_entry`, `update_entry`,
  `delete_entry`, `persist`, and therefore every Page/Tool call) resolves the
  invoking installation's state on entry, so no request can be answered from
  another installation's cache.
- This plugin declares no config, so no tenant configuration is captured on the
  shared object.
- The manager page renders entry text through DOM nodes and element properties
  (`textContent` / `value`) and binds its controls with `addEventListener`; no
  entry field is interpolated into markup, so a stored question or answer cannot
  add attributes or event handlers to the page.

## Per binding, released on revocation

- `_states` is keyed by the installation scope
  `<instance_uuid>:<workspace_uuid>:<installation_uuid>` and holds that
  installation's `entries` list and its async lock. `runtime_revision` is
  deliberately excluded from the token so a worker upgrade does not orphan a
  tenant's data.
- `BasePlugin.on_installation_revoked(binding)` pops exactly that key. It touches
  process-local state only, because no Host API is available during revocation.
- Durable state is written under `faq_entries:<instance>:<workspace>:<installation>`.
  The Host row key (`[instance_uuid, workspace_uuid, owner_type, owner, key]`) has
  no installation dimension, so the installation identity has to live in the
  plugin's own key; without it, two installations in one Workspace would share a
  row.
- Dedicated (binding-less) workers keep the legacy `faq_entries` key and a single
  in-process list, i.e. their existing behaviour.

## Known limits

- `initialize()` is process-scoped and does nothing: it runs once per worker with
  an empty config and, under shared placement, before any installation is known.
- A shared worker that gets an invocation without a trusted installation binding
  raises instead of falling back to a binding-less key, so such a request is
  refused rather than served with shared entries. A route that does not carry the
  installation binding therefore cannot work under shared placement.
- Legacy data migration is not performed: on shared placement a pre-existing
  shared `faq_entries` row is no longer read (each installation starts empty).
  Dedicated workers keep reading the legacy key unchanged.
- The entries list handed to a Page response is the live cached list; it is not
  copied, so a concurrent writer for the same installation can change it while a
  response is being serialized.
- The per-installation cache is unbounded in size until revocation; the runtime
  revokes on uninstall, disable, Workspace removal and upgrade.
- Revocation is serialized per installation but may overlap with sibling
  installations' invocations; per-installation state is locked, cross-installation
  state is not shared.

## Tests

`tests/test_installation_scoped_faq.py` drives two distinct
`InstallationBinding`s (same instance and Workspace, different installation
uuids) through one plugin object with the installed SDK's `bind_invocation`, over
a synthetic Host KV whose row key mirrors LangBot's. It asserts that a write from
one installation never appears in the other's entries, search results, Page or
Tool output, that a fresh object ("restart of the loader") reloads each
installation's own row, that revocation drops only the revoked binding, and that
dedicated binding-less workers keep the legacy key.

`tests/test_page_attribute_injection.py` renders
`components/pages/manager/index.html` with `tests/page_dom_probe.js` (Node)
against a recording DOM, with a question of `" onfocus="alert(1)" data-x="` and an
answer containing `</textarea><img src=x onerror=...>`. It asserts that no markup
string carries the entry text, that parsing every markup string yields no
event-handler attribute, and that the list and the edit form still show the entry
through element properties (pre-fix, the edit form produced an `onfocus`
attribute).
