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
