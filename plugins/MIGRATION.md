# Official plugin source migration

All 40 plugins and their supporting files were imported from
`langbot-app/langbot-plugins` commit
`50c3ece7cc0a3663383eac31eb8c7a05305b1912` (also recorded in
`SOURCE.json`). The original source repository retains
the pre-migration Git history; this import does not rewrite plugin identities or
claim to have merged that history into Core.

The source layout is `plugins/{Runner,KnowledgeEngine,misc}/<plugin>`.
The six existing CI workflows moved to `.github/workflows/plugins-*.yml` at the
repository root. The plugin request template also moved to the root `.github`.
`catalog.json` is the machine-readable index; `README.md` is the human index.
Historical source trees and certification notes in `SHARED_SOURCE_LEDGER.md`
remain historical evidence, not certification of newly built packages.

## Boundaries

- Source ownership is consolidated; SDK, process isolation, plugin IDs, versions,
  installation, configuration and Marketplace publication remain independent.
- Each plugin retains its dependency declarations and test environment. Core's
  pytest configuration and pre-commit formatting do not apply to plugin suites.
- Core consumer tests use this checkout's `plugins/` and integrity-checked files
  in `tests/fixtures/legacy_plugin_identity_sources.json`. Refresh the relevant
  hashes deliberately when changing those consumer contracts. Published SDK
  compatibility continues to be tested by the independent plugin workflows.
- Core wheels, sdists, Docker contexts, release ZIPs and fnOS staging exclude
  this tree and `.lbpkg` files. Git export archives exclude this tree as well;
  a normal Git checkout still contains all plugin sources.
- Core tags/releases do not build or publish plugin packages. The independent
  manual package workflow has no Marketplace credentials or publication step.

## Cutover

Merge and validate the new source location before retiring the old write entry.
Move open plugin PRs to this repository and point the old README to `plugins/`.
Archiving the old repository and changing live Marketplace metadata require a
separate authorized operation. Existing published artifacts are not modified by
this source migration. Future plugin publications carry the new source links;
version bumps and any required artifact certification remain release decisions.
