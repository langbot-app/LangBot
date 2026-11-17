# Phase-five candidate validation

Implementation started from `0d5a5eea1` (PR #3065 merged). The branch was then
refreshed onto `3d67a88025f81a0167a86467a8d9d5308469d3c8`, which removes the old
30-hour native soak mode. Implementation candidate: `62e32bc378686532a56bf494da151b68faeb474e`.
The following evidence-only commit changes no production behavior; use the PR head for delivery. No SDK version,
release tag, production deployment or merge is part of this delivery.

Environment: Linux, Python 3.12.14, checkout-local editable SDK 0.7.25.
The SDK-only environment also uses Python 3.12.14; Python 3.10 is not locally tested.

| Verification | Result | Evidence |
| --- | --- | --- |
| RAG, Artifact/storage, migration, API and legacy upload regression | 353 passed, 221 skipped | [log](evidence/broad-regression.log) |
| Required Core with SDK, including new real SQLite bridge and revocation/cancellation contracts | 59 passed, 13 unrelated deselected, zero skips | [log](evidence/sdk-core.log) |
| Isolated SDK proxy/Workspace/Runtime protocol subset | 121 passed, one expected Core-import skip | [log](evidence/sdk-isolated.log) |
| Real TCP HTTP → installed Plugin Runtime Runner → host Box → HTTP delivery | 1 passed, 42.99 seconds | [log](evidence/network-process.log) |
| Candidate-SDK KnowledgeEngine and LocalAgent consumers | 217 passed | [log](evidence/plugin-consumers.log) |
| Independent final 0053 migration and KB review | 12 passed, 16 skipped | [log](evidence/independent-migration-kb.log) |
| Legacy alias collision/cancel rollback and independent-Core retain/delete contention | 7 passed, 14 skipped | [log](evidence/legacy-races.log) |
| Structured plugin response expansion/budget boundary | 3 passed, 6 skipped | [log](evidence/response-budget.log) |
| Documentation | Node 40 passed; opt-in static Python 23 passed; full build and 31 static checks passed | Local docs build |
| Backend localized errors | 30 passed | `tests/unit_tests/test_backend_i18n.py` |
| Lint / generated contracts | Ruff, action consistency, Workspace proxy drift check, skill index/validation passed | Reproduction below |

Counts overlap and must not be summed. The broad regression preceded the final
FK-on migration preservation test and response-envelope safety margin; those
changes were rerun in the independent/response-budget rows. Logs replace only
local workspace paths; no credentials, config files or database snapshots are included.

## Reproduction

```sh
.venv/bin/python -m pytest tests/unit_tests/rag tests/unit_tests/api/service/test_knowledge_service.py tests/unit_tests/storage/test_content_store.py tests/integration/storage tests/integration/persistence/test_rag_document_identity.py tests/integration/persistence/test_knowledge_artifact_migration.py tests/integration/persistence/test_migrations.py tests/integration/persistence/test_migration_branch_convergence.py tests/unit_tests/api/test_operation_docs.py tests/unit_tests/api/test_file_upload_scoping.py tests/unit_tests/api/test_knowledge_artifact_mcp.py -q
.venv/bin/pytest tests/integration/plugin --required-suite sdk_core -q -rs
LANGBOT_NETWORK_PLUGIN_E2E=1 LANGBOT_CORE_NETWORK_BACKEND=host .venv/bin/python -m pytest tests/e2e/test_network_file_plugin_runtime.py --required-suite network_plugin -q -rs
.venv/bin/python -m pytest plugins/KnowledgeEngine/certification-tests plugins/Runner/LocalAgent/tests/test_agent_core.py -q
.venv/bin/python scripts/generate_plugin_workspace_api.py --check
(cd sdk && .venv/bin/pytest tests/api/proxies/test_artifacts_api.py tests/api/test_workspace_operations.py tests/api/test_workspace_domains.py tests/runtime/io/handlers/test_plugin_handler.py tests/api/proxies/test_box_api.py tests/api/proxies/test_runner_tool_content_trace.py -q)
(cd sdk && .venv/bin/python scripts/check_action_consistency.py)
(cd docs && npm test && npm run build && TELEMETRY_POLICY_STATIC=1 python3 -m unittest discover -s tests -p 'test_*.py')
```

## Review repairs and limits

Initial focused/broad attempts failed on stale minimal test fixtures (new database
locks/columns), expected catalog counts/exposure and one HTTP relative import.
These were corrected and rerun without weakening source ownership or denial assertions.
Review also fixed: upstream KB delete exceptions losing recovery material;
cross-Core deletion versus admission; SQLite alias read-to-write upgrade contention;
post-IO plugin/engine/holder revocation; uninstall orphan pins; rendered response
expansion; and FK-on migration batch recreation losing legacy Chunk children.
SQLite migration uses bounded schema-time autocommit to switch FK enforcement;
it restores enforcement and checks integrity, but does not promise atomic rollback
of the entire migration. Existing live Artifact files or pending KB deletion block downgrade.

Skipped PostgreSQL/named-S3 cases are unverified locally, not passes. The successful
network test covers the existing installed candidate Runtime file-delivery path,
not every new SDK helper across an independently installed historical Runtime.
No old Runtime mixed-version acceptance, real-model image/PDF understanding,
long-duration load/fault/restart soak or non-host Box backend acceptance is claimed.
Candidate plugin tests do not replace their separate released-SDK CI checks.
KB import deliberately accepts ordinary account/API-owned upload Artifacts only;
Skill sources, run outputs and installation-owned sources are not implicitly shared.
Legacy nonpersistent upload mode retains its original handle-only response.

## Refreshed candidate verification

After rebasing onto `3d67a8802`, the final implementation candidate passed:

- Required SDK/Core: 59 passed, 13 unrelated deselected ([log](evidence/postrebase-sdk.log)).
- New migration, KB, legacy, plugin, and i18n regression: 56 passed, 44 unavailable-backend skips ([log](evidence/postrebase-targeted.log)).
- Actual installed Runtime/host Box delivery: 1 passed, 35.52 seconds ([log](evidence/postrebase-network.log)).
- The final migration test was rerun after formatting: 4 passed.
- Full source/tests Ruff lint, source/tools format, generated proxy drift and SDK action consistency passed. Changed Python files pass format checks. Existing unrelated test-file formatting drift is not changed by this PR.
