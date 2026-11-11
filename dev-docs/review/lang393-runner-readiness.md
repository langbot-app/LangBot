# Runner availability verification

An enabled plugin can still be initializing after its permission-confirmation request returns. The SDK omits that plugin from Runner discovery until initialization completes. Core previously performed two immediate discoveries and raised `RunnerNotFoundError`, dropping messages during this window.

## Coverage of existing fixes

The baseline was Core master `9a65a9c5b` (version 4.11.5) with SDK 0.7.23. The Runner registry and error classes are unchanged between the v4.11.5 tag and this baseline. SDK main still excludes plugins that are not ready from `RunnerRuntimeService.list_runners`.

| Path | Existing behavior and remaining work |
| --- | --- |
| Runtime transport reconnect | Core #2968 waits for transport recovery. An available transport does not imply that installed plugins have initialized. |
| Migration installs a Runner | #2934 waits before applying migrated configuration. It does not protect every subsequent message. |
| Member confirms plugin permissions | #2961 fixes installation tasks stalling on confirmation. Activation still launches the plugin asynchronously. |
| Marketplace sweep saturates at startup | #2918 retries the sweep. Missing packages, download failures and dependency failures still require diagnosis or retry. |
| Installed plugin starts or restarts | A registry miss now waits up to 30 seconds for the enabled installation, then discovers again. |
| Plugin absent, disabled or awaiting permission confirmation | Fail without waiting for initialization or changing installation state. The diagnostic distinguishes these causes. |
| Plugin initialized but selected component absent | Report the plugin-version/pipeline-selection recovery steps. |

The wait uses existing workspace-scoped installation lookup and readiness polling. Request cancellation propagates. Invocation still enforces enablement and permissions. No message execution is retried after it has started. The localized user notice points to Plugins, installation tasks and runtime logs; the detailed exception is retained by monitoring and the telemetry execution chain.

## Docker reproduction

Environment: Linux amd64, Docker 20.10.24, `python:3.12-slim-bookworm`, Python 3.12.15, SDK 0.7.23. Core and the standalone WebSocket Plugin Runtime run in the test container, using an isolated data directory and dynamically allocated ports. `SPACE__DISABLE_TELEMETRY=true` prevents sending test data to Space. No model provider or paid API is used.

Command inside the container:

```sh
.venv/bin/python -m pytest tests/e2e/test_runner_availability.py -q -s -m e2e --no-cov
```

The real plugin fixture delays `initialize()` by five seconds. The test installs its package, confirms permissions and immediately sends a message through `POST /api/v1/pipelines/{id}/run`. Another test points a pipeline to an uninstalled `langbot-team/LocalAgent/default`.

| Scenario | Baseline | Fixed |
| --- | --- | --- |
| Message immediately after permission confirmation | `failed`, `Agent runner not found: plugin:e2e/agent-runner-qa/default` | `completed`, `e2e echo: initialization window` |
| Missing LocalAgent | Bare Runner ID in reply | Actionable Plugins/log guidance; monitoring error contains `not installed in this Workspace` |

Both baseline assertions failed (27.79 s). Both fixed tests passed (37.30 s), including the persisted monitoring diagnostic assertion.

## Regression checks

91 tests passed across Runner registry, chat handler, connector reconciliation/readiness, backend i18n and pipeline telemetry. Coverage includes missing/disabled/pending installations, eventual initialization, a stalled RPC deadline, cancellation, unavailable components and preservation of the detailed error in the execution chain's `error` field. Full `ruff check src/langbot/ tests/ tools/` and `ruff format src tools --check` passed.

## Limitations

The Docker reproduction uses a deterministic Runner fixture to exercise actual asynchronous plugin initialization; it does not attribute individual production telemetry samples to this cause. Network outages, broken dependencies, unconfirmed permissions and missing plugin packages are not repaired automatically. Initialization beyond the bounded wait still fails with recovery guidance. No Windows-specific claim, SDK release, plugin publication or Core release is part of this change.
