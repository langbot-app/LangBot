# Workspace Release Testing

Use the workspace gates when changes span LangBot core, the plugin SDK, AgentRunner, or multiple first-party plugins.

## Cost Ladder

1. Run `langbot-workspace-contract-gate` after each coherent change. It catches wrong branches, wrong SDK imports, protocol drift, and repository regressions without model calls.
2. Run the narrow browser case for the changed surface, such as `workspace-plugin-pages-smoke`, before broad release testing.
3. Run `langbot-workspace-release-gate` before merging or publishing coordinated releases. It deliberately uses one complex LocalAgent coding task rather than many low-value model conversations.
4. Audit the persisted run with `agent-run-ledger-audit`. Set `LANGBOT_AGENT_RUN_ID` when other traffic may have created a newer run.

Run the browser-driven `langrag-parser-golden-e2e` separately when Parser,
LangRAG ingestion, document upload, or parser selection changes. It intentionally
remains a manual deep case until its full WebUI setup path is automated; it is
not listed in the automated release gate where it could be silently skipped.

Do not add Space model concurrency to these gates. Provider concurrency mixes external quota and latency into product results and is covered separately by optional performance cases.

## Failure Triage

- Compatibility preflight failure: correct the checkout, virtualenv, or local SDK import before testing behavior.
- Repository contract failure: fix the owning repository and add the narrowest deterministic regression.
- Browser workflow failure: correlate the screenshot, console, network, and backend log from the same run.
- Complex Agent failure: inspect `ledger-audit.json` before blaming the model. Tool pairing, authorization, JSON, and timeout failures are product signals.
- A provider-origin malformed tool-argument payload is a recovery warning only when the ledger keeps a paired error result, a later tool call succeeds, and the run completes. Malformed persisted event JSON and unrecovered tool-argument errors remain release failures.
- Packaging `env_issue`: restore isolated build dependency access, then rerun packaging only. It must not mask passing or failing runtime contracts.
