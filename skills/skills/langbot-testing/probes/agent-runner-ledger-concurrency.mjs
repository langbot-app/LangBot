#!/usr/bin/env node

import { runPytestProbe } from "./pytest-probe.mjs";

await runPytestProbe({
  caseId: "agent-runner-ledger-concurrency",
  repoEnvKey: "LANGBOT_REPO",
  defaultRepo: "..",
  pythonPathEnvKeys: ["LANGBOT_PLUGIN_SDK_REPO"],
  defaultPythonPaths: ["../../langbot-plugin-sdk/src"],
  description: "LangBot AgentRunner run ledger claim, lease, authorization, and runtime-admin pytest probe.",
  testTargets: [
    "tests/unit_tests/agent/test_run_ledger_store.py::test_create_queued_run_claim_renew_release",
    "tests/unit_tests/agent/test_run_ledger_store.py::test_expired_claim_can_be_reclaimed",
    "tests/unit_tests/agent/test_run_ledger_api_auth.py::test_runtime_admin_can_register_list_and_claim_with_own_run_session",
    "tests/unit_tests/agent/test_run_ledger_api_auth.py::test_run_append_result_basic_path",
    "tests/unit_tests/agent/test_run_ledger_api_auth.py::test_run_finalize_basic_path",
    "tests/unit_tests/agent/test_run_ledger_api_auth.py::test_run_claim_renew_and_release_actions",
  ],
});
