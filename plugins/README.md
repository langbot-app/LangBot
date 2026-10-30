# LangBot Plugins

Official and example plugins, maintained in the `plugins/` directory of [LangBot](https://github.com/langbot-app/LangBot).

Each plugin is an independent package with its own `manifest.yaml`, dependencies, and README. Install plugins from [LangBot Space](https://space.langbot.app/market?type=plugin), or run `lbp build` inside a plugin directory.

## Directory layout

See [catalog.json](catalog.json) for the generated source index and
[RELEASING.md](RELEASING.md) for independent testing, packaging and Marketplace
publication. Plugins are not included in Core release artifacts.

- `Runner/` — agent runners and event processors.
- `KnowledgeEngine/` — knowledge engine integrations.
- `misc/` — commands, tools, event listeners, pages, and other plugins.

## Runner

- [ACPAgentRunner](Runner/acp-agent-runner/README.md)
- [ClaudeCodeAgent](Runner/claude-code-agent/README.md)
- [CodexAgent](Runner/codex-agent/README.md)
- [CozeAgent](Runner/coze-agent/README.md)
- [DashScopeAgent](Runner/dashscope-agent/README.md)
- [DeerFlowAgent](Runner/deerflow-agent/README.md)
- [DifyAgent](Runner/dify-agent/README.md)
- [LangflowAgent](Runner/langflow-agent/README.md)
- [LocalAgent](Runner/LocalAgent/README.md)
- [N8nAgent](Runner/n8n-agent/README.md)
- [RunnerDemo](Runner/RunnerDemo/README.md)
- [TboxAgent](Runner/tbox-agent/README.md)
- [WeKnoraAgent](Runner/weknora-agent/README.md)

## KnowledgeEngine

- [DifyDatasetsConnector](KnowledgeEngine/DifyDatasetsConnector/README.md)
- [FastGPTConnector](KnowledgeEngine/FastGPTConnector/README.md)
- [LangRAG](KnowledgeEngine/LangRAG/README.md)
- [LongTermMemory](KnowledgeEngine/LongTermMemory/README.md)
- [RAGFlowConnector](KnowledgeEngine/RAGFlowConnector/README.md)

## misc

- [AgenticRAG](misc/AgenticRAG/README.md)
- [AIImagePlugin](misc/AIImagePlugin/README.md)
- [AutoTranslate](misc/AutoTranslate/README.md)
- [DailyLimitPlugin](misc/DailyLimitPlugin/README.md)
- [EssentialCommands](misc/EssentialCommands/README.md)
- [FAQManager](misc/FAQManager/README.md)
- [GeneralParsers](misc/GeneralParsers/README.md)
- [GitHubKit](misc/GitHubKit/README.md)
- [GoogleSearch](misc/GoogleSearch/README.md)
- [GroupChatSummary](misc/GroupChatSummary/README.md)
- [HelloPlugin](misc/HelloPlugin/README.md)
- [HumanTakeover](misc/HumanTakeover/README.md)
- [KeywordAlert](misc/KeywordAlert/README.md)
- [MCBotPlugin](misc/MCBotPlugin/README.md)
- [PowerContext](misc/PowerContext/README.md)
- [QWeather](misc/QWeather/README.md)
- [ScheNotify](misc/ScheNotify/README.md)
- [SysStatPlugin](misc/SysStatPlugin/README.md)
- [TavilySearch](misc/TavilySearch/README.md)
- [URLSummary](misc/URLSummary/README.md)
- [WebSearch](misc/WebSearch/README.md)
- [WordFSRS](misc/WordFSRS/README.md)

## Deployment: dedicated and shared placement

A plugin runs either **dedicated** (its own worker per installation) or **shared** (one `BasePlugin` and one object
per declared component serve every installation of an artifact digest in a single worker). Shared placement is
opted into per plugin with both manifest fields:

```yaml
execution:
  python: {path: main.py, attr: Plugin}
  sharedRuntime: shared-runtime-v1
  componentModel: stateless-v1
```

`sharedRuntime` without `componentModel: stateless-v1` is not eligible. The normative contract is
[`langbot-plugin-sdk/docs/stateless-components.md`](https://github.com/langbot-app/langbot-plugin-sdk/blob/main/docs/stateless-components.md):
component objects are process-wide singletons, `initialize()` runs once per worker and sees no tenant config,
configuration and credentials are resolved per invocation, tenant state in a process cache is keyed by the full
installation binding and released in `on_installation_revoked()`, components must be re-entrant, and blocking work
must stay off the shared event loop. Adding the manifest fields alone is not sufficient — source review and
concurrency tests must prove the implementation.

37 of the 40 plugins here declare shared placement. `Runner/acp-agent-runner`, `Runner/claude-code-agent` and
`Runner/codex-agent` stay dedicated: each launches a process-global daemon hub, symlinks worker-`HOME` credentials
into every run home and shares one workspace root, so serving two installations from one process needs the
Host/SDK broker and duplex-process API first (see `Runner/acp-agent-runner/docs/SHARED_RUNTIME_BLOCKERS.md`); shared
adaptation is deliberately not planned for them, and their dedicated manifests are the supported configuration.

Every plugin that declares shared placement ships a `SHARED_RUNTIME.md` stating what is per invocation, what is
binding-keyed and released on revocation, and its known limits, plus a test that drives two installation bindings
through one object graph. `misc/*` suites run in CI through `../.github/workflows/plugins-misc-tests.yml` (one venv and one
interpreter per plugin, dependencies from that plugin's `requirements.txt`); Runner plugin suites run through the
isolated-interpreter harness in `Runner/tests/test_migrated_runners.py`. Declaration is not certification:
[`SHARED_SOURCE_LEDGER.md`](SHARED_SOURCE_LEDGER.md) records the committed source tree of each candidate and no
plugin is claimed certified or live-accepted there.

## Development

Use a plugin directory as the working directory when building or running it; the repository root is not a plugin. Runner development and tests are documented in [Runner/README.md](Runner/README.md).

The complete official plugin catalog now lives in LangBot. See [MIGRATION.md](MIGRATION.md) for provenance and release boundaries. The previous demo repository was renamed in place. External runner, LocalAgent, and LangRAG source histories were imported with Git subtree; existing plugin IDs and authors are unchanged.

[Plugin documentation](https://docs.langbot.app)
