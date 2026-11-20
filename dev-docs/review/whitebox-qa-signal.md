# White-box test quality sweep

Baseline: `1f227f7aa8e3f4e3f1e5c7d5019e4d8a128d00ec`. This PR changes tests
and developer guidance only. It does not add a workflow, alter branch protection,
or change production behavior.

## Inventory and stopping rule

The tracked Python test files were screened across Core, SDK, plugins, and test
tooling; the WebUI test tree was inventoried separately. The baseline file inventory
used `git ls-files`, Python `test_*.py` / `*_test.py` names and Python AST
definitions named `test_*`. Browser and WebUI entries used `*.test.*` or
`*.spec.*` script names. Definitions are not pytest case counts; parameterization,
markers and dependencies affect collection and execution.

| Baseline pool | Files | Python test definitions |
| --- | ---: | ---: |
| Core unit | 442 | 5,077 |
| Core integration | 74 | 526 |
| Core E2E / legacy integration / smoke | 22 | 90 |
| SDK | 133 | 1,911 |
| Plugins | 168 | 1,499 |
| WebUI | 112 | n/a |
| Regression tooling / skills | 32 | 256 |

Whole-tree screening is not a verdict on each individual test. Repeated names and
white-box assertions are leads, not removal rules. Change only clusters where
an independent boundary can own the check or where the observable result stays
equivalent. Keep distinct cases for different callers, tenant isolation, cancellation,
transactions, boundaries, binary payloads and recovery. A fake dependency used to
control time or a fault does not by itself make a test a duplicate.

## Edited boundaries

- **HTTP and API:** Passkey now sends real Quart requests through each registered
  route and requires the precise refusal and no credential-service dispatch.
  Credential TTL combines shared setup without removing the expiration boundary
  or real asyncio cancellation check. The operation docs use the actual registered
  catalog and exact published metadata rather than parallel fixed totals.
- **Storage and regression tools:** shared S3/Moto lifecycle verifies independent
  byte readback and deletion. Provider initialization must be awaited. The
  regression tool must not accept a stale passing summary when its real child
  exits nonzero, or a failing business verdict when its child exits zero.
  See [storage and tool evidence](whitebox-qa-storage.md).
- **Pipeline and provider:** one shared log formatter has exact boundary cases;
  separate handler tests still check full user output even when the log is cut.
  Request history retains adjacent messages and original input when legacy files
  are filtered. Document routing still distinguishes native support, alias and denial.
- **Telemetry, Survey and RAG:** verify real encoded requests via in-process
  HTTPX transport, not internal config fields alone. A failed Survey response
  must retain pending state, and disabled/no endpoint must send nothing.
  RAG retains real cache-generation and missing-KB behavior after removal of
  constructor-only assertions.
- **Deployment:** parse Compose and Kubernetes and verify actual Core/Box and
  Core/Runtime references. Equivalent formatting stays green; a changed
  reference is rejected even if documentation comments are unchanged.
- **SDK, plugin and WebUI:** preserve independent roots in usage accounting,
  exact parse failure/recovery statistics, and hidden nested values across
  successive runner edits. WebUI unit checks do not establish browser behavior.

For asset discovery, chosen commands, evidence status and safe consolidation,
see [developer acceptance](../CROSS_COMPONENT_TESTING.md#test-assets-for-developers-and-agents).

## Second pass: broaden the changed test surface

Compared against the first-pass PR head `6c7b468cccdeeafc49bb7ae05228bcd44a2f52b1`.
The additional edits cover six pools. This is targeted strengthening after a
broader inventory, not a rewrite of every file.

| Pool | Newly exercised behavior | Local evidence |
| --- | --- | --- |
| Core | Real package imports and packaged resource content; exact log cursors, eviction, truncation and retention limits; independent YAML/JSON disk readback for synchronous and asynchronous saves | Focused 49 → 28 passed. The neighboring config/utilities run had the same existing DNS failure on both sides; no speedup claim. |
| SDK | Runner history/event cursors and typed payload handling, Box storage rescan and totals, byte-level plugin archive contents and failed-build cleanup, RSS, and recovery after clipping a UTF-8 log line | Python 3.12 standalone CI suite: 2,648 → 2,650 passed, 15 skipped on both, 84.61% coverage on both. Five installed-wheel packaging tests passed separately. |
| Core + SDK | Shared protocol contracts in the same source checkout | 40 passed, 13 deselected by the suite selector. Source paths were verified locally; the release-version compatibility lanes are unchanged. |
| Official plugins | RunnerDemo reply payloads, StickerHub byte readback/shared blobs and pagination, LangRAG event order, persistence and clear/readback | RunnerDemo, StickerHub and LangRAG: 156 tests passed on each side, plus 11 subtests. |
| WebUI | Render migration diagnostics; test exact HTTP status boundaries, all eight locale catalogs and ordered embed reply contents | Full Web unit suite: 203 → 206 passed, no skips. SSR/unit only; no browser E2E. |
| Regression tools | Real child process and request-file delivery to a CLI fixture, exact case identities, full rename/diff inventory and isolation of optional state scenarios | All 232 tool tests passed on both sides. The child process is a fixture, not a released `lbctl` binary. |
| Documentation | Verify localized GitHub Wiki page bytes and links from both Home and the sidebar rather than file presence alone | 22 Python docs tests passed, one skipped. No static site build claim. |

Controlled substitutions were run outside the PR tree. The strengthened
checks caught stale log offsets, exact-limit truncation, dropped config fields,
disappearing payload/archive bytes, RSS mix-ups, clip-recovery mistakes, wrong
plugin replies and order, invalid HTTP status handling, missing locale
interpolation, lost CLI arguments/case identity, and missing localized wiki
content. These are targeted counterexamples, not a repository-wide mutation
score. No live provider/Docker acceptance, daily endurance, new CI job, or new
required merge check is implied.
