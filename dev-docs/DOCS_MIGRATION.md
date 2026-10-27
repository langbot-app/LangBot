# Documentation subtree and publication

Public docs live in `LangBot/docs/`. The former internal `docs/` directory is
`dev-docs/` (27 top-level entries, 87 tracked files at migration). Do not merge
this migration using GitHub squash or rebase: use a merge commit to retain the
subtree parent and original signed commits. Imported history is reachable through
the subtree merge's second parent; `git log --follow docs/<file>` or
`git log <imported-docs-sha>` exposes original authors. A plain path-limited log
need not show pre-import paths.

## Local checks

With Node.js 24, run `npm ci`, `npm run typecheck`, `npm test`, and `npm run build`
inside `docs/`. Output is `docs/dist/`. The site remains mounted at `/docs/` with
canonical URL `https://langbot.app/docs`.

## Cutover after the PR is reviewed and merged

1. Pause the legacy `sync-blog-articles.yml` workflow in `langbot-app/langbot-docs`
   and let any running writer finish. Freeze direct commits to that repository.
   Pause its legacy Wiki and landing sync workflows too, avoiding duplicate
   publishers while switching ownership. Do not push disabling commits directly
   to the mirror.
2. Fetch mirror `main` and confirm it is an ancestor of the new subtree split.
   If it advanced since import, integrate it with an **unsquashed**
   `git subtree pull --prefix=docs <mirror-url> main` through another reviewed PR
   before cutover; reapply the inert mirror workflow files if necessary. Never
   force-push or rewrite the mirror history.
3. Verify `LANGBOT_WIKI_PUSH_TOKEN` is configured in LangBot with existing access
   to the docs mirror, LangBot Wiki, landing upstream and production fork. The
   blog job additionally needs to push to LangBot main and trigger workflows.
   Repository workflow-file updates must be permitted by that token. Do not
   weaken branch protection to accommodate this migration; use a separately
   reviewed publication approach if the current token cannot perform the push.
4. Set LangBot repository variable `DOCS_MIRROR_ENABLED=true`. Dispatch
   `sync-landing-submodule.yml` on main. It fetches full main history, runs
   `git subtree split --prefix=docs`, verifies the current mirror head is an
   ancestor, pushes without force, then advances only landing's `docs` gitlink.
   The first split replaces legacy mirror workflows with inert manual stubs.
5. Dispatch `sync-github-wiki.yml` and `sync-blog-articles.yml` in LangBot.
   The blog job now commits only docs article paths to LangBot main using the
   dedicated token, so its push triggers the mirror and Wiki workflows.
6. Confirm the `docs` gitlink in `langbot-app/langbot-landing-page`, then confirm
   production fork `RockChinQ/LangBot-LandingPage-Vue` matches upstream. This is
   the actual fork in the existing sync script (not the similarly named fork
   mentioned in the original migration proposal). Observe Cloudflare Pages
   deployment and check `https://langbot.app/docs/`, localized pages, assets,
   sitemap and canonical URLs. Verify Wiki pages after publication.

The four root workflows own publication and validation. Nested workflow stubs
are intentionally inert when split into the mirror. No direct writes should be
made to the mirror after cutover; all edits belong in LangBot `docs/`.

`docs/context7.json` continues to identify `langbot-app/langbot-docs` because that
repository remains available with the same tree layout and original history.
Verify Context7 ingestion after the first mirror update; no library re-registration
is needed merely to relocate the authoring source.

Disable `DOCS_MIRROR_ENABLED` to pause publishers if cutover fails. A failed
mirror ancestry check must be investigated and reconciled, never bypassed by a
force push. Do not restore direct mirror writers while LangBot is authoritative.
