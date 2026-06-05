# Agent Runner Security Hardening

本文档记录 agent-runner 插件化进入生产发布前需要补齐的安全与稳定加固项。

## 状态

**当前结论：暂不塞进本阶段 agent-runner plugin 协议闭环。**

本阶段目标是验证 LangBot 可以通过统一的 `run(event, binding)` 协议接入 `local-agent` 与外部 harness runner（如 Claude Code runner），并能传递事件、上下文、资源句柄、状态和结果流。

安全发布级 hardening 是后续 release gate，不应阻塞当前协议闭环，但必须作为进入生产默认启用前的验收条件。

> **硬规则**：能执行代码 / 访问工作目录的外部 harness runner（Claude Code、Codex、Kimi Code 等）在本文 Release Gate Checklist 完成前，**不得在生产环境默认启用**。本地 smoke 通过不等于可生产默认开启。

## 责任边界

### LangBot Host 负责

- 资源授权：决定某个 `run_id` / binding 可以访问哪些模型、RAG、MCP、skill、artifact、history、state。
- 资源投影：只把授权后的资源句柄、配置片段或上下文文件传给 runner。
- 路径策略：限制 workspace / context file / artifact 的允许路径和清理策略。
- Secret 策略：过滤环境变量、配置、日志和 transcript 中的 secret。
- 运行约束：配置超时、轮次、并发、配额、输出大小和取消路径。
- 审计记录：记录事件、绑定、资源授权、runner 调用、外部 harness session id、关键错误和结果摘要。

### Runner Plugin 负责

- 遵守 LangBot 下发的 Agent/runner config、授权资源和运行约束。
- 将 LangBot 资源投影成目标 runner 可消费的形式，例如 context 文件、MCP 配置、环境变量或 CLI 参数。
- 遵守 PROTOCOL_V1 §13 的插件实例边界；需要跨轮次保存的外部 session id / working directory 等状态应写入 host-owned state。
- 对外部进程做最小必要封装，包括命令参数构造、超时、取消、输出解析和错误映射。

### 外部 Harness 负责

Claude Code、Codex、Kimi Code 等外部 harness 可以继续使用自身的权限模型、工具 allow / deny 规则、MCP 加载策略、session/resume 机制和沙箱能力。

但外部 harness 不是 LangBot 的唯一安全边界。LangBot 仍必须在调用前完成资源授权、路径限制、secret 过滤和审计记录。

## 当前 MVP 可接受边界

当前阶段可以接受以下前提：

- 由可信管理员配置 runner binding。
- 工作目录和 context 输出目录为显式配置或 host 生成路径。
- 外部 runner 默认使用保守权限，例如 plan / no-write 模式或禁用高风险工具。
- 通过 timeout、max turns、输出长度和进程取消降低失控风险。
- 通过 host-owned state 保存 `external.session_id`、`external.working_directory` 等 resume 所需指针。

这些前提足够做本地 E2E 与协议验收，不等同于生产发布完成。

## Release Gate Checklist

进入生产默认启用前，需要补齐：

- Path isolation：workspace allowlist、路径规范化、防止 `..` 逃逸、context / artifact 清理。
- Permission boundary：runner 能力声明、binding 级资源授权、run 级权限校验。
- Secret handling：环境变量白名单、配置脱敏、日志和 transcript redaction。
- MCP policy：MCP server allowlist、scoped token、tool allow / deny、危险工具审计。
- Skill projection policy：skill 来源验证、只读投影、版本和摘要记录。
- Process isolation：进程组管理、取消、超时、CPU / 内存 / 输出配额。
- State lifecycle：session id、workspace、artifact 的过期、清理、迁移和审计。
- Audit first-class：事件、资源授权、外部命令、session id、结果摘要可追踪。
- UI / Admin control：管理员能看到 runner 权限、风险提示、资源绑定和禁用入口。
- Test matrix：路径逃逸、secret 泄漏、权限拒绝、timeout、取消、MCP deny、resume、cleanup、audit 完整性。

## 非当前范围

以下内容不属于本阶段协议闭环：

- 完整异步队列与 issue-centric 产品模型。
- 复杂 workflow engine。
- Codex / Kimi runner 全量接入。
- EBA 分支完整迁移和联调。
- 发布级安全 hardening 的完整实现。
