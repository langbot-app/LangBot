# Independent plugin releases

Core and plugins share a source checkout, not a release train. Never add plugin
dependencies to Core's `pyproject.toml`, bundle plugin sources in Core artifacts,
or use a Core release event to publish plugins.

## Develop and test

Choose one plugin from [catalog.json](catalog.json). Run its tests in its own
environment following its README. CI entrypoints are the five `plugins-*-tests`
workflows and the catalog workflow in `../.github/workflows/`, using independent
interpreters. LocalAgent requires `langbot-plugin>=0.7.18`; its CI installs the
latest stable PyPI SDK with `uv sync --extra dev --upgrade-package langbot-plugin`
and reports the installed version before checking contracts and tests. Its lockfile
is a resolution snapshot. The other Runner tests retain their published SDK pins;
keep these environments and lockfiles separate.

From the repository root:

```sh
python plugins/scripts/check_catalog.py
python plugins/scripts/test_repository.py
```

## Build only

Run the **Plugins / Build package** workflow manually, selecting a relative
catalog path such as `Runner/LocalAgent` or `misc/HelloPlugin`. It builds only
that plugin and uploads an unsigned `.lbpkg` artifact. It neither creates a
GitHub release nor contacts Marketplace. Review the selected revision and test
results before requesting publication.

The equivalent local flow, using an independently installed SDK CLI, is:

```sh
cd plugins/misc/HelloPlugin
lbp build
```

The repository root and the `plugins/` root are not plugin packages. Never run
`lbp build` or `lbp publish` from either root.

## Marketplace publication

The existing per-plugin SDK flow remains unchanged:

1. Review the plugin tests, compatibility, release notes and certification
   requirements. Increment that plugin's manifest version, and its project
   version where applicable; do not change Core's version.
2. Keep `metadata.author`, `metadata.name` and component IDs stable. Update the
   catalog with `python plugins/scripts/check_catalog.py --write` from the root.
3. In an authorized maintainer environment, use `lbp login` and then run
   `lbp publish` from the selected plugin directory. Do not place credentials
   in the repository or give them to pull-request jobs.
4. Follow the Marketplace draft/review flow and verify the resulting plugin
   version and an upgrade from the prior version in a test Workspace.

No Marketplace submission or existing listing is changed by a source merge.
Moving a repository link changes newly built bytes; previous artifact evidence
must not be treated as certification of the new archive.

If GitHub release assets are also needed, use an explicit plugin namespace such
as `plugins/HelloPlugin/v0.1.1` and upload only that plugin's package. Core release
workflows reject plugin-prefixed release tags; they must not publish Core for a
plugin release.
