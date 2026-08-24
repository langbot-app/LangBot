#!/usr/bin/env node

import { runPytestProbe } from "./pytest-probe.mjs";

await runPytestProbe({
  caseId: "agent-runner-runtime-chaos",
  repoEnvKey: "LANGBOT_PLUGIN_SDK_REPO",
  defaultRepo: "../../langbot-plugin-sdk",
  description: "LangBot plugin SDK AgentRunner runtime failure, timeout, forwarding, and pull API pytest probe.",
  testTargets: [
    "tests/runtime/plugin/test_mgr_agent_runner.py",
    "tests/runtime/test_pull_api_handlers.py",
  ],
});
