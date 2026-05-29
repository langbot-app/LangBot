# Agent Runner Phase 1 QA Report - 2026-05-29

本文档记录 2026-05-29 对 agent-runner plugin 协议闭环的本地验收。它不改写
[PHASE1_QA_REPORT_2026-05-18.md](./PHASE1_QA_REPORT_2026-05-18.md) 的历史结论。

## 1. 验收结论

当前分支可以认为完成了本地协议闭环 smoke：

- `local-agent` 插件可以通过 Pipeline Debug Chat 走插件化 `AgentRunOrchestrator` 主链路。
- `claude-code-agent` 可以作为外部 harness runner 通过同一条 `run(event, binding)` 路径执行。
- Claude Code runner 可以接收 LangBot event-first context，并把 context / skill / MCP 配置投影给本地 Claude Code CLI。
- Claude Code runner 可以把外部 session id 和 working directory 写回 LangBot host-owned state，用于后续 resume。
- `codex-agent` 可以作为外部 harness runner 通过同一条 `run(event, binding)` 路径执行，并把 Codex `thread_id` 写回 host-owned state。

这表示当前架构足以支撑 `local-agent`、最小 Claude Code runner 与最小 Codex runner 的联调；不表示安全发布级 hardening 已完成。

## 2. 环境

| 项 | 值 |
| --- | --- |
| LangBot commit | `58e4b357` |
| `langbot-agent-runner` commit | `d681dda` |
| `langbot-local-agent` commit | `573cc00` |
| Claude Code CLI | `2.1.137 (Claude Code)` |
| Frontend | `http://127.0.0.1:3000` |
| Backend | `http://127.0.0.1:5300` |

## 3. Pipeline 与 Runner

| Runner | Pipeline | Runner ID | 结果 |
| --- | --- | --- | --- |
| local-agent | `dc75c543-70f9-4d2a-9467-968628e6ca01` | `plugin:langbot/local-agent/default` | PASS |
| Claude Code | `f5c6d8e0-0c5a-4f3f-b7d4-0c1a0dec0de1` | `plugin:langbot/claude-code-agent/default` | PASS |
| Codex | `57eb0cc8-5a5a-4865-9f3e-8b3ad070fbc2` | `plugin:langbot/codex-agent/default` | PASS |

## 4. 证据

### 4.1 local-agent UI E2E

- 报告：`/home/glwuy/langbot-app/langbot-skills/reports/2026-05-29-17-59-00-462-08-00-pipeline-debug-chat.md`
- 后端日志成功信号：
  - `Processing request from person_websocket`
  - `Conversation(1) Streaming completed: 1 chunks, 2 chars`
- 验收点：Debug Chat 用户可见回复正常，后台 log guard 未发现失败信号。

### 4.2 Claude Code runner UI E2E

- 报告：`/home/glwuy/langbot-app/langbot-skills/reports/2026-05-29-18-03-31-169-08-00-pipeline-debug-chat.md`
- 后端日志成功信号：
  - `Processing request from person_websocket`
  - `Conversation(3) Streaming completed: 1 chunks, 22 chars`
- 验收点：Debug Chat 用户可见回复 `LANGBOT_CLAUDE_E2E_OK2`。

### 4.3 Claude Code context / skill / MCP projection

- 报告：`/home/glwuy/langbot-app/langbot-skills/reports/claude-code-agent-resource-context-20260529.md`
- 通过点：
  - 生成的 context JSON schema 为 `langbot.agent_runner.external_harness_context.v1`。
  - context JSON 包含 `event`、`actor`、`delivery`、`input`、`resources`、`context` 和 `state`。
  - Claude Code 可读取 LangBot 注入的 context 文件并输出 `LANGBOT_CLAUDE_CONTEXT_RESOURCE_OK`。
  - skill 文件投影到 `.claude/skills/langbot-e2e-context/SKILL.md`。

### 4.4 Claude Code resume state

- 报告：`/home/glwuy/langbot-app/langbot-skills/reports/claude-code-agent-real-workdir-20260529.md`
- 通过点：
  - `agent_runner_state` 中记录了 `external.session_id`。
  - `agent_runner_state` 中记录了 `external.working_directory`。
  - 使用保存的 session id 在对应工作目录执行 Claude Code resume 成功。

### 4.5 Codex runner UI E2E

- 报告：`/home/glwuy/langbot-app/langbot-skills/reports/codex-agent-real-20260529-fifth.md`
- 截图：`/home/glwuy/langbot-app/langbot-skills/reports/evidence/codex-agent-real-20260529-fifth/screenshot.png`
- 后端日志成功信号：
  - `Processing request from person_websocket`
  - `Conversation(0) Streaming completed: 1 chunks, 21 chars`
- Codex JSONL 事件：
  - `thread.started`
  - `item.completed` with `agent_message`
  - `turn.completed`
- 通过点：
  - Debug Chat 用户可见回复 `LANGBOT_CODEX_E2E_OK5`。
  - `agent_runner_state` 中记录了 `external.session_id` 和 `external.working_directory`。
  - `environment-json` 可以显式传入代理环境，避免插件 worker 环境缺失导致本地 Codex CLI 卡住。
  - timeout/cancel 路径会清理 Codex 子进程，避免 orphan `codex exec`。

## 5. 当前未关闭项

以下不应作为当前协议闭环的阻塞项：

- 发布级安全 hardening：见 [SECURITY_HARDENING.md](./SECURITY_HARDENING.md)。
- 完整 EBA 分支联调和 EventGateway 迁移。
- 完整异步队列、issue-centric 产品模型和复杂 workflow engine。
- Codex 发布级能力 / Kimi runner 全量接入。

## 6. 建议状态

- 本地 `local-agent` 协议闭环：PASS。
- 本地 Claude Code external harness smoke：PASS。
- 本地 Codex external harness smoke：PASS。
- Phase 1 是否整体关闭：可以关闭本地协议闭环；若定义为所有官方外部服务 runner 都必须有真实凭据，则外部服务 runner 仍按凭据可用性分别 PASS / BLOCKED。
