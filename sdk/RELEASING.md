# Releasing the plugin SDK (`langbot-plugin`)

The SDK shares the LangBot repository with Core and the official plugins, but it
has its own version (`sdk/pyproject.toml` and `src/langbot_plugin/version.py`),
its own CI (`.github/workflows/sdk-*.yml`) and its own PyPI package.

## Rules

- Release by pushing a tag named `sdk/vX.Y.Z` (pre-releases: `sdk/vX.Y.ZrcN`).
  `.github/workflows/sdk-publish.yml` checks that the tag matches
  `sdk/pyproject.toml`, builds `sdk/` and publishes `langbot-plugin` to PyPI. If the
  version is already on PyPI it uploads nothing.
- **Never create a GitHub Release for the SDK.** Every `release: published`
  event in this repository belongs to Core: Docker `latest`, Core PyPI, release
  assets, fnOS, Discord and changelog sync listen to it, and LangBot Space's
  update check reads this repository's release list. Core release workflows only
  accept `v*` tags, but a SDK release in the list would still hide Core updates
  from deployed instances. Write SDK release notes in the PR that bumps the version.
- Never use plain `vX.Y.Z` tags for the SDK; those are Core releases.
- Core installs the SDK from PyPI through the exact pin `langbot-plugin==X` in
  the root `pyproject.toml`. Core artifacts (wheel, sdist, Docker context,
  release ZIP, fnOS package) exclude `sdk/`.

## Steps

1. Bump `version` in `sdk/pyproject.toml` and `src/langbot_plugin/version.py`
   (`tests/packaging/test_release_metadata.py` checks they match) and merge.
2. Tag the merged commit and push the tag:

   ```sh
   git tag sdk/v0.7.25 <commit>
   git push origin sdk/v0.7.25
   ```

3. Confirm the **SDK / Publish to PyPI** run and the new version on
   https://pypi.org/project/langbot-plugin/.
4. When Core needs the release, bump `langbot-plugin==X` in the root
   `pyproject.toml`, run `uv lock`, and release Core as usual.

## Core release gate

`scripts/check_sdk_release_pin.py` runs in the Core PyPI and Docker release
workflows. It fails when:

- Core's pin differs from `sdk/pyproject.toml`;
- that version is not on PyPI;
- the tag `sdk/v<pin>` is missing, or `sdk/src` / `sdk/pyproject.toml` changed
  after it (unreleased SDK code in the Core release commit).

When it fails, release the SDK first and bump the pin, or revert the unreleased
SDK change on the release branch.

## History

The SDK was imported as a snapshot of `langbot-app/langbot-plugin-sdk` v0.7.24
(`sdk/SOURCE.json`). Older history, issues, pull requests and the `v0.x` tags
remain in that archived repository. The baseline tag `sdk/v0.7.24` marks the
import in this repository.
