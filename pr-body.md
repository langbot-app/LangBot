## Overview

Follow-up fixes for the independent review of the task-scoped execution binding lease in #3193.

The lease remains request-local and task-owned. This revision closes exception and cancellation leaks, invalidates before the first suspension, and preserves Cloud admission and directory projection freshness checks on lease hits.

## Review Fixes

- Nested `ensure_execution_binding_scope()` invalidates an inherited lease when an exception or cancellation escapes the nested boundary.
- `_drive_after_first_yield()` invalidates immediately when the first suspension is observed. This prevents same-task reentry during a long LLM, tool, plugin, or adapter await from seeing the pre-suspension lease.
- `_check_output()` and `_mark_stage_interrupt()` invalidate before every monitoring or adapter await and in `finally` blocks. Error and cancellation paths cannot carry a valid lease into terminal monitoring writes.
- Pipeline run, language resolution, stage execution, cancellation finalization, monitoring, plugin events, and custom async-generator boundaries invalidate before awaiting. Synchronous custom stages returning an `AsyncGenerator` are invalidated before their first `anext()`.
- Lease hits call the existing `WorkspaceService` zero-I/O admission and directory projection guards. Manifest expiry and stale Cloud projection state fail closed without an extra SQL query.

## Regression Tests

`tests/unit_tests/pipeline/test_binding_guard.py` now covers

- notice delivery failure and monitoring cancellation followed by recovery checks;
- same-task reentry after the first suspension with a generation mismatch;
- Cloud synchronous admission/projection expiry on a lease hit;
- synchronous custom stages returning an async generator;
- existing cross-request, concurrent fence, uncommitted Session, child-task, unbind, and call-count regressions.

## Measurements

The existing synthetic Pipeline-only measurements remain unchanged. They cover the full default stage chain with SQLite `WorkspaceService` and use fake runner/model/plugin dependencies.

| Scenario | Before | After | SQL SELECTs before -> after |
| --- | ---: | ---: | ---: |
| Normal chat, one output | 31 | 13 | 32 -> 14 |
| Synthetic two-output reply | 42 | 16 | 43 -> 17 |
| Streaming chat, five chunks | 75 | 25 | 76 -> 26 |
| Streaming chat, ten chunks | 130 | 40 | 131 -> 41 |

These figures measure Pipeline-owned binding lookups. Plugin handler, model manager, and connector lookups remain outside this directory-scoped PR. Linux plus Docker Box 10-minute open-loop load and PostgreSQL verification remain pending.

## Validation

- `pytest tests/unit_tests/pipeline tests/integration/pipeline -q`: **953 passed**
- `pytest tests/unit_tests/pipeline/test_binding_guard.py tests/unit_tests/pipeline/test_pipelinemgr.py tests/unit_tests/pipeline/test_terminal_monitoring.py -q`: **50 passed**
- `ruff check` and `ruff format --check` on all touched files: **passed**
- Existing CI for the previous commit was green. This push triggers a fresh CI run for the review fixes.
