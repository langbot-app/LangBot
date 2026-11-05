# AGENTS.md (plugins/)

Official LangBot plugins, migrated from the archived `langbot-app/langbot-plugins` repository (see `MIGRATION.md`). Repository-wide rules are in `../AGENTS.md`; plugin authoring workflow is the `langbot-plugin-dev` skill; author docs are `../docs/en/plugin/dev/`.

## Layout

- `Runner/`, `KnowledgeEngine/`, `misc/<plugin>/`: one independent package per directory with its own `manifest.yaml`, dependencies, tests and README.
- `catalog.json`: generated machine index (`python plugins/scripts/check_catalog.py --write` from the repository root). `README.md` is the human index.
- `RELEASING.md`: testing, packaging and Marketplace publication rules.
- `MIGRATION.md`, `SHARED_SOURCE_LEDGER.md`, `SOURCE.json`: historical migration evidence; do not edit them for ordinary changes.

## Rules

- Core and plugins share a checkout, not a release. Never add plugin dependencies to Core's `pyproject.toml`, import plugin code from Core, or bundle this tree in Core artifacts.
- Never run `lbp build` / `lbp publish` from the repository root or `plugins/`; run them inside one plugin directory.
- Keep `metadata.author`, `metadata.name` and component IDs stable. Bump the plugin's manifest (and project) version for a release; never bump Core's version for a plugin change.
- Each plugin keeps its own environment and lockfile; run its tests in isolation following its README. CI: `.github/workflows/plugins-*.yml`.
- Bridges combining a Pipeline EventListener and an event Runner stay in `misc/`; Runner-only plugins belong in `Runner/`.
- Declare the minimal `spec.permissions` (`workspace_operations`, `capabilities`) the plugin needs; Runners must expose only `ctx.resources.workspace_operations` to models. See `../docs/en/plugin/dev/permissions.mdx`.
- Use the Workspace API (`self.plugin.workspace`), the standard platform APIs and `call_platform_api` documented in `../docs/en/plugin/dev/apis/`; plugin runtime code must not import Core (`langbot.*`) or call LangBot's own HTTP routes to bypass installation grants (test scripts may drive a test instance).
- Marketplace README convention: English root `README.md`, translations in `readme/README_{lang}.md`, eight-locale `metadata.label` / `description`, live `repository` URL.

## Checks

```sh
python plugins/scripts/check_catalog.py
python plugins/scripts/test_repository.py
```
