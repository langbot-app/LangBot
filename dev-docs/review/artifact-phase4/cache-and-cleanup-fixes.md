# Bounded archive reuse and soak process cleanup

Two additional confirmed review findings are corrected:

- Artifact continuation now uses the existing per-Core bounded archive LRU
  (32 MiB / 256 entries), shared with legacy Skill resources. Every call still
  checks live scoped version/content metadata, digest, manifest and upstream
  authorization; it does not cache permissions or extracted response files.
  The existing Workspace lock and blocking scope coalesce cold fetches and keep
  cancellation safe. Oversized archives remain uncached by design.
- Every soak round runs below a dedicated Linux subreaper supervisor. Cleanup
  handles detached `setsid()` descendants, TERM-ignoring children, timeout and
  SIGINT/SIGTERM. It signals only current direct/adopted children through pidfds
  after identity/parent checks; `ECHILD`, not an empty /proc snapshot, confirms
  completion. A nominally successful pytest with leaked descendants is cleaned
  and marked failed. Unsupported Linux/pidfd capability fails before launch.
  Timeout/report/cleanup failures remain visible in the manifest.

## Validation

Combined changed-boundary regression: **129 passed / 30 skipped / 0 failed**
(29.11 seconds). [Console](cache-cleanup-evidence/regression.log),
[JUnit](cache-cleanup-evidence/regression.xml).

Independent review reran cache tests (**51 passed**) and real process-cleanup
regressions (**13 passed**), including detached TERM-ignoring descendants and an
unrelated process that must remain alive. No blocking issue remained.

Actual supervisor-backed repeat smoke: **2 rounds / 6 cases passed**, no skips or
failures; 10-second target with the final complete round allowed to finish.
[Manifest](cache-cleanup-evidence/rounds.ndjson). This is development-checkout
smoke, explicitly recorded as dirty, not long-duration or final-SHA acceptance.
Ruff check/format and whitespace checks passed. Missing PG/S3 backend cases stay
unverified locally and must be checked in CI/reviewer services.

## Authorized attribution correction

At the owner's request, all four existing PR commits were reconstructed with
exactly the author/committer identity from repository commit
`5f76347902604dac6345f870af99434505cae052`:
`huanghuoguoguo <60681390+huanghuoguoguo@users.noreply.github.com>`.
GitHub associates that historical author and committer with the authenticated
owner account. No private email or guessed address was used. Each reconstructed
commit has exactly the same tree as its predecessor; the [mapping](cache-cleanup-evidence/identity-map.json)
preserves auditability of historical validation SHAs. New work uses the same
identity. Publication uses an explicit force-with-lease against the previously
verified remote head; no CLA was signed and no merge is performed.
