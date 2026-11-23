# LangBot Agent Testing 技术选型

## 状态

这是技术选型背景文档，不是当前路线图。当前黑盒 E2E QA 的实施顺序见：

```text
docs/qa-agent/04-black-box-e2e-roadmap.md
```

## 目标

`langbot-skills` 的目标不是替代测试框架，而是沉淀 agent 可复用的测试资产，让开发者 clone 仓库后，可以让 Codex、Claude Code、Computer Use 或 Playwright MCP 复用已有路径完成 LangBot 功能验证。

核心原则：

- Skill 负责路由和少量规则。
- Reference 负责可读流程和背景知识。
- Case 负责结构化测试路径。
- Troubleshooting 负责结构化故障资产。
- `lbs` 负责结构校验、索引、资产创建和未来的运行/报告能力。
- UI/browser 是产品 QA 的主路径；API/curl 只用于诊断。

## 浏览器控制层

不同开发者可用的浏览器控制能力不同，所以浏览器层必须可替换。

| 方案 | 适用场景 | 优点 | 代价 |
|---|---|---|---|
| Codex / Claude Computer Use | agent 可以直接控制可见浏览器 | 登录和交互路径最自然，通常不需要额外 MCP 浏览器桥接 | 依赖具体 agent 工具能力 |
| Playwright MCP | 没有 Computer Use，但有 MCP 浏览器工具 | 稳定、可脚本化、适合回归路径 | OAuth 登录通常需要额外 visible profile |
| 直接 Playwright 脚本 | 测试路径非常稳定，适合 CI | 可重复性强 | 需要维护脚本和 selector |
| 商业 AI QA 平台 | 团队希望外包测试运行平台 | 报告和 PR 集成完整 | 成本和平台绑定 |

## 当前推荐

先采用分层降级：

```text
有 Computer Use？
  是 -> 使用 Computer Use 控制浏览器
  否 -> 使用 Playwright MCP

需要 GitHub OAuth？
  是 -> 使用持久浏览器 profile，让用户手动完成登录
  否 -> 直接使用已有登录态或测试账号状态
```

具体选择逻辑沉淀在：

```text
skills/langbot-env-setup/references/browser-access-selection.md
```

测试原则固定在：

```text
docs/qa-agent/03-agent-browser-qa-principles.md
```

## 环境变量层

测试文档不应写死端口。共享默认值放在：

```text
skills/.env
```

关键变量：

```text
LANGBOT_FRONTEND_URL
LANGBOT_BACKEND_URL
LANGBOT_DEV_FRONTEND_URL
LANGBOT_REPO
LANGBOT_WEB_REPO
LANGBOT_BROWSER_PROFILE
```

Agent 执行测试前应先读取 `skills/.env`，再用用户提供的当前环境或已启动服务覆盖默认值。

## 测试资产层

测试资产分两类：

```text
skills/<skill>/
  references/        # Markdown 流程说明
  cases/             # 结构化测试用例
  troubleshooting/   # 结构化故障记录
```

当前已实现：

- `SKILL.md` 路由
- `references/*.md`
- `lbs case new/list/show`
- `lbs trouble show/search`
- `lbs test plan`
- `lbs test report`
- `lbs list / validate / index`

下一步重点：

- 日志守卫规则补充
- 报告产物管理

## 关键判断

不要强制所有内容只能通过 CLI 修改。更好的模式是：

- 新增 case/troubleshooting：优先使用 `lbs`
- 大段流程说明：允许直接编辑 Markdown
- 结构性变更后：必须运行 `lbs validate`
- 任何生成索引的变更后：运行 `lbs index`

这样既能沉淀结构化资产，又不会在 schema 未稳定时拖慢迭代。
