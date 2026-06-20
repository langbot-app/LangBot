# LangBot QA Agent 文档导航

这个目录记录 `langbot-skills` 当前的 QA 方向和后续建设顺序。

## 当前判断

当前重点是 LangBot 的黑盒 E2E QA，不是 LangBot core 的单测覆盖率建设。

`langbot-skills` 要帮助开发者和 QA agent 做接近人工测试的 WebUI 验证：

- 打开真实 LangBot WebUI；
- 按用户路径点击和输入；
- 检查用户可见的 UI 结果；
- 查看 console、network、截图、后端和前端日志；
- 输出可复用的测试报告；
- 把稳定 feature 路径沉淀为 case；
- 把重复故障沉淀为 troubleshooting。

API 和 curl 只做诊断。它们可以解释失败原因，但不能让一个 UI case 通过。

## 文档状态

| 文档 | 状态 | 用途 |
| --- | --- | --- |
| `04-black-box-e2e-roadmap.md` | 当前主路线图 | 决定下一步建设什么。 |
| `03-agent-browser-qa-principles.md` | 当前原则文档 | 定义 browser-first QA 的通过标准。 |
| `02-log-guard-plan.md` | 当前活跃设计 | 设计 `lbs test report` 里的日志守卫。 |
| `../user-guide.md` | 当前使用手册 | 开发者日常使用。 |
| `00-technology-options.md` | 背景文档 | 选择 Computer Use、Playwright MCP 或未来直接 Playwright。 |
| `01-qa-agent-harness-plan.md` | 历史规划，部分过时 | 解释最初分层和目录设计；使用前先看状态说明。 |

## 已过时的点

`01-qa-agent-harness-plan.md` 还保留早期规划状态。现在结构化 cases、
结构化 troubleshooting、`validate`、`index`、`lbs test plan` 都已经落地。

已经补上第一版 `lbs test start`、`lbs test run`、`lbs test report` 和日志守卫文件扫描。
`webui-login-state`、`pipeline-debug-chat` 已经绑定直接 Playwright 自动化脚本。后续重点是：

- 报告 evidence 字段继续打磨；
- case success/failure signal 和日志守卫规则继续补充；
- 报告产物和 evidence 约定；
- 等 LangBot 当前开发状态稳定后跑真实 sample report。

不要再把旧阶段列表当成当前 source of truth。后续排序以
`04-black-box-e2e-roadmap.md` 为准。
