# Follow-up: continuation budgets, PDF fixtures and shared process acceptance

This follow-up corrects three confirmed problems in `a5459e02`:

1. A 256 KiB text resource exhausted the 1 MiB run source budget after four
   8 KiB slices. Successful verified source registration is now charged once per
   immutable Artifact/run. Returned JSON UTF-8 (including media) has its own
   cumulative 1 MiB ceiling. Every continuation still reauthorizes and rereads.
   Host-private per-run counters cannot be reset through Runner variables.
   Registration itself receives the remaining/per-file limit; manifest size is
   checked before archive IO or reference insertion. Successful registration stays
   charged when a subsequent read/render/cancellation fails.
2. The native PDF fixtures were only header-shaped bytes. Both now use genuine
   single-page PdfWriter output. Against PR #3064's strict reader at
   `ea29df737d22c1b744590754812fd490636e045e`, loaded only in memory without changing
   the checkout or merging that PR, the targeted suite passed 18 cases; 2 unavailable
   PostgreSQL/MinIO variants skipped. This checks fixture/reader compatibility, not
   the entire combined branch or actual-model understanding.
3. The new process test started a second function-scoped Core pair with another
   instance UUID against the same database. Both phases now run in one marked
   acceptance entry using the same pair and database binding. Stage four fetches
   the actual current revision and preserves its independent assertions. A unit
   regression locks in same-pair execution and ordering. No database deletion,
   binding rewrite, or relaxed instance fence was introduced.

## Validation

- Broader changed-boundary regression: **240 passed, 63 skipped, 0 failures**,
  74.86 seconds. [Console](followup-evidence/regression.log),
  [JUnit](followup-evidence/regression.xml).
- Strict #3064 reader compatibility: **18 passed, 2 skipped**.
  [Console](followup-evidence/strict-pdf-compatibility.log),
  [JUnit](followup-evidence/strict-pdf-compatibility.xml).
- Independent read-only review and focused run: **38 passed**, no additional
  blocking issue in the changed paths.
- Ruff check/format, whitespace and generated Workspace proxy checks passed.

The regression includes large-file end-to-end 32-slice continuation, actual
source/output exhaustion, UTF-8 accounting, concurrent requests, variable
mutation, query reuse across runs, failed registration/read/render, cancellation,
pre-registration byte-limit/no-row behavior, SQLite loader integration, existing
Artifact/Skill behavior and migrations. Historical evidence is preserved, not
rewritten to suggest earlier failures or skipped cases passed.

Real PostgreSQL/two-Core execution must be confirmed by the new CI run. Local
skips and the mocked process-entry unit regression do not establish that it passed.
The existing real-model and long-lived endurance gaps remain. Do not merge yet.
