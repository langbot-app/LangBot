# Documentation publication after the repository migration

Public docs live in `LangBot/docs/`; internal notes live in `dev-docs/`. The
original 27 top-level internal entries (87 files) were moved without loss.
The unsquashed subtree import retains all 888 commits, including 452 signed
objects, from `51dddcb3f891d60bc38645e88b2dbd515344da81`. Use
`git log 51dddcb3f891d60bc38645e88b2dbd515344da81 -- <original-path>` to inspect
the original authors. The import is already merged; do not rewrite that history.

## Publication source

`langbot-app/langbot-docs` is a historical archive, not a writable mirror.
No publication step splits or pushes to that repository. The landing repository
keeps its submodule **path** `docs`, but its **URL** is
`https://github.com/langbot-app/LangBot.git`, tracking `master`. Consequently,
the landing build runs the documentation package inside `docs/docs/` and copies
`docs/docs/dist/public` to `public/docs`. The public URL stays
`https://langbot.app/docs/`; Vite's base path and canonical site URL are unchanged.

The main-repository synchronization job advances only the landing gitlink to
LangBot `master` and then synchronizes `RockChinQ/LangBot-LandingPage-Vue`.
It checks `.gitmodules` on the exact landing revision it updates, refuses old
repository configurations, and rejects rewinds/divergence. It never force-pushes.

## Cutover order

1. Merge the paired landing PR: change `.gitmodules`, the pinned `docs` gitlink,
   and `scripts/build-embedded-docs.mjs` together. Verify its full `pnpm build`.
2. Merge the main-repository publication changes. Keep publishers disabled until
   both repositories are ready; the new flag is `DOCS_PUBLISH_ENABLED`, not
   `DOCS_MIRROR_ENABLED`. The old flag does not enable these jobs.
3. Stop the old repository's Blog, Wiki and landing workflows and let any active
   writers finish. The owner can archive `langbot-app/langbot-docs` once the
   new publication chain is verified. Never write disabling commits to it as
   part of the new publication chain.
4. Verify `LANGBOT_WIKI_PUSH_TOKEN`, or the existing `RELEASE_UPLOAD_GITHUB_TOKEN`
   fallback, has access to LangBot, landing, production fork and Wiki. No token
   value belongs in logs. Publication only updates gitlinks/content, never
   workflow files in another repository, and no docs-mirror permission is needed.
5. Set `DOCS_PUBLISH_ENABLED=true` in LangBot. Dispatch
   `sync-landing-submodule.yml` on **master**. It also brings the production fork
   up to date; confirm the fork matches landing main and observe Cloudflare's
   resulting deployment before accepting the cutover.
6. Dispatch `sync-github-wiki.yml` and `sync-blog-articles.yml` on **master**.
   The Blog job commits only `docs/` article paths to LangBot using a token whose
   pushes trigger subsequent landing/Wiki workflows. Wiki images and attribution
   now point to LangBot `master/docs`, so new assets do not depend on the archive.
7. Check `/docs/`, the en/zh/ja guide pages, assets, sitemap, Markdown exports,
   Wiki content and Blog idempotency. A successful Wiki build is not proof of
   publication: inspect the separate publish job.

## Context7

The root `context7.json` follows the published Context7 schema and selects
`master:docs/en`. Context7's current parser indexes English documentation.
The old nested ownership configuration belonged to the legacy repository and
has been removed; it does not transfer ownership of a Context7 library.
The owner must add/refresh `https://github.com/langbot-app/LangBot` in Context7
and verify a result from `docs/en` after merge. The existing
`/langbot-app/langbot-docs` index is only a historical snapshot after archival.
Do not report an index refresh as complete solely because this config exists.

## Local validation and recovery

Use Node.js 24. In `docs/`, run `npm ci`, `npm run typecheck`, `npm test`, and
`npm run build`. In landing, initialize the submodule and run `pnpm install
--frozen-lockfile`, `pnpm test`, and `pnpm build`.

Disable `DOCS_PUBLISH_ENABLED` to pause publication. If landing still points at
the legacy repository or the production fork has diverged, reconcile through
reviewed changes; do not bypass the synchronization checks. Keep the last
working deployment available until the replacement passes verification.
