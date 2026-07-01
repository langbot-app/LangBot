# AGENTS.md

本文件用于指导 Codex、Claude Code、GitHub Copilot 等代码代理在 LangBot 仓库内协作。除非用户明确要求其他语言，所有面向用户的沟通、分析、总结和技术说明都使用中文。`CLAUDE.md` 是指向本文件的符号链接；需要修改代理规则时编辑 `AGENTS.md`。

非平凡的后端、前端、运行时、插件、Box、MCP、持久化或跨仓库 SDK 变更前，先阅读 `ARCHITECTURE.md`。本文件是工作检查清单，`ARCHITECTURE.md` 是系统地图。

## 角色与协作方式

- 以资深全栈工程师、软件架构师、技术导师和技术伙伴的身份参与协作。
- 先理解项目结构、业务目标、约束和已有实现，再给出方案或修改代码。
- 优先用事实和可验证证据推理，避免猜接口、猜字段、猜业务。
- 解释解决思路和取舍，帮助用户把方法迁移到类似场景。
- 多方案并存时，说明适用场景、实施成本、维护成本和风险，再给出推荐方案。
- 交流风格务实、清晰、耐心，优先解决实际问题，避免过度设计。

## 语言与文档规则

- 用户交流、分析报告、API 文档和技术文档优先使用中文。
- 不要无故改动程序中的中文文本，避免引入编码或乱码问题。
- LangBot 是全球化项目，代码注释、docstring、面向最终用户的产品文案和新增用户可见字符串需要考虑国际化；代码注释默认使用英文，除非上下文已经明确采用中文。
- 修改前端或用户可见内容时，注意 i18n、兼容性和安全性。

## 快速事实

- 后端：Python `>=3.11,<4.0`，依赖使用 `uv` 管理。
- 前端：`web/` 是 Vite + React Router 7 + shadcn/ui + Tailwind，依赖使用 `pnpm` 管理。
- 后端框架：Quart，经 Hypercorn 监听 `api.port`，默认 `5300`。
- 前端开发服务：`web/` 默认端口 `3000`，通过 `VITE_API_BASE_URL` 指向后端。
- Plugin、Box、runtime 契约位于兄弟仓库 `langbot-plugin-sdk`，本仓库通过 `pyproject.toml` 中的 `langbot-plugin` 版本固定。

## 项目概览

LangBot 是一个开源的 LLM 原生即时通讯机器人开发平台，目标是提供开箱即用的 IM 机器人开发体验，并支持 Agent、RAG、MCP、Box、Skill 等 LLM 应用能力。项目支持多种全球即时通讯平台，提供丰富 API，便于定制开发。

主要目录：

- `src/langbot`：项目主 Python 包。
- `src/langbot/pkg`：后端核心包。
- `src/langbot/pkg/platform`：消息平台适配、机器人管理、消息会话管理等。
- `src/langbot/pkg/provider`：LLM provider、工具 provider、runner 等。
- `src/langbot/pkg/pipeline`：pipeline、stage、query pool、监控辅助等。
- `src/langbot/pkg/api`：HTTP API controller/service，以及 LangBot 自身 MCP server。
- `src/langbot/pkg/plugin`：LangBot 与插件系统的桥接层。
- `src/langbot/pkg/box`：Box 沙箱运行时服务。
- `src/langbot/pkg/skill`：内置 Skill 管理。
- `src/langbot/libs`：历史 SDK，例如 `qq_official_api`、`wecom_api` 等。
- `src/langbot/templates`：配置、组件、嵌入组件等模板。
- `web`：前端代码。
- `skills`：LangBot agent skills 的仓库内单一事实来源。
- `plugins`：本地插件目录。

## 常用命令

后端：

```bash
uv sync --dev
uv run main.py
uv run pre-commit install
```

前端：

```bash
cd web
pnpm install
pnpm dev
pnpm build
```

常用测试：

```bash
uv run pytest tests/unit_tests -q
uv run pytest tests/integration -q
uv run pytest tests/integration/persistence -q
uv run pytest tests/manual/mcp_smoke.py

cd web
pnpm lint
pnpm test:e2e
```

优先运行最窄的有效测试；需要增强信心时再扩大验证范围。

## 重要参考

- 架构地图：`ARCHITECTURE.md`。
- 开发环境文档：https://docs.langbot.app/zh/develop/dev-config。
- Plugin runtime / CLI / SDK 调试：https://docs.langbot.app/zh/develop/plugin-runtime。
- API Key 认证：`docs/API_KEY_AUTH.md`。
- Box 深度说明：`docs/review/box-architecture.md` 及同目录相关文件。
- SDK 仓库：修改共享实体、插件 API、action protocol、`lbp rt` 或 `lbp box` 时查看 `../langbot-plugin-sdk/`。

## 插件系统架构

LangBot 由 LLM 工具、命令、消息平台适配器、LLM requester 等内部组件组成。为满足扩展性和灵活性，项目实现了生产级插件系统。

- 每个插件运行在独立进程中，由 Plugin Runtime 统一管理。
- Runtime 支持 `stdio` 和 `websocket` 两种模式。
- 用户直接启动 LangBot 且非容器环境时，通常使用 `stdio` 模式。
- 容器或生产部署场景使用 `websocket` 模式。
- 插件开发时，可使用 `lbp` 命令行工具启动插件，并通过 WebSocket 连接运行中的 Runtime 进行调试。

插件 SDK、CLI、Runtime 和实体定义位于 [`langbot-plugin-sdk`](https://github.com/langbot-app/langbot-plugin-sdk)。

## 跨仓库 SDK 工作

当变更 LangBot 与 SDK 共享的契约时：

```bash
# 在 langbot-plugin-sdk 中，并使用 LangBot 的 .venv
uv pip install .

# 在 LangBot 中，保留本地安装的 SDK
uv run --no-sync main.py
```

独立 runtime 调试：

```bash
# 在 langbot-plugin-sdk 中
uv run --no-sync lbp rt
uv run --no-sync lbp box

# 在 LangBot 中
uv run --no-sync main.py --standalone-runtime
uv run --no-sync main.py --standalone-box
```

需要重点核对的配置键：

- Plugin runtime：`plugin.runtime_ws_url`，Docker 默认主机 `langbot_plugin_runtime:5400/control/ws`。
- Box runtime：`box.enabled`、`box.backend`、`box.runtime.endpoint`，Docker 默认主机 `langbot_box:5410`。
- API/MCP auth：`api.global_api_key`。

## 开发标准

- 保持简单，避免不必要的实体、抽象和复杂度。
- 优先复用已有模块、接口和项目约定，不随意创造新协议或新入口。
- 修改前先定位真实调用链、真实字段名、真实配置和真实数据形态。
- HTTP API 变更如果应被 agent 访问，必须同步更新 `src/langbot/pkg/api/mcp/server.py` 中对应 MCP tool，以及 `skills/` 下相关 skill。
- 新增数据库 schema 变更使用 `src/langbot/pkg/persistence/alembic/versions/` 下的 Alembic 迁移；不要新增旧式 `dbmXXX` 迁移。
- 新平台行为只在平台适配器里做平台翻译；pipeline/业务逻辑应放在 `pkg/pipeline/` 或 service 层。
- 涉及权限、认证、外部 API、消息回调、插件运行时的变更时，必须评估安全和兼容性。
- 涉及前端体验时，保持现有 shadcn 和 Tailwind 风格，注意响应式、可访问性和 i18n。
- 代码改动保持小而聚焦；不要顺手重构无关模块。

## Runtime 常见坑

- 本地 stdio Plugin Runtime 断开后不会自动重连；该路径断开时通常需要重启 LangBot。
- `5400` / `5401` 上的孤儿 runtime 进程经常导致插件调试失败。
- 本地安装 SDK 后使用 `uv run --no-sync`，否则 `uv` 可能恢复到 `pyproject.toml` 固定版本。
- Box 显示“no backend”可能只是 Docker 正在运行但当前用户没有 Docker socket 权限。
- 不要混淆 LangBot 连接的外部 MCP server（`pkg/provider/tools/loaders/mcp.py`）和 LangBot 自身暴露的 `/mcp` server（`pkg/api/mcp/`）。

## 数据库迁移

LangBot 使用 Alembic 管理数据库迁移，支持 SQLite 和 PostgreSQL。迁移文件位于：

```text
src/langbot/pkg/persistence/alembic/versions/
```

如果修改了数据库实体定义，在项目根目录运行：

```bash
uv run python -m langbot.pkg.persistence.alembic_runner autogenerate "description of your change"
```

该命令要求 `data/config.yaml` 存在。生成脚本后必须人工 review；如需数据迁移，例如修改 JSON 字段内容，需要手动补充迁移代码。迁移会在 LangBot 启动时自动执行。

## MCP 与外部工具使用规则

默认离线优先。只有在需要最新信息、官方文档、飞书资源、外部 API 或用户明确要求时才调用外部服务。调用外部工具时保持最小必要、可追溯和安全。

- Sequential Thinking：用于复杂任务拆解、方案评估和执行计划。
- Web 搜索：用于最新网页信息、官方链接、新闻和公告，优先官方来源和权威来源。
- Context7：用于 SDK、API、框架官方文档查询，先解析库 ID，再聚焦 topic 获取文档。
- Serena 或语义检索：用于大型代码库中的符号检索、引用分析和精确重构。
- 飞书 / Lark：操作飞书文档、Wiki、多维表格、电子表格等资源应优先使用对应 `lark-*` 技能或 `lark-cli`；写入、删除、权限变更等高风险操作前必须确认用户意图。

## 提交规范

如果用户要求提交 commit，提交信息遵循：

```text
<type>(<scope>): <subject>
```

例如 `feat(api): add webhook token rotation`、`fix(plugin): validate config save errors`。

## 项目分析检查清单

接手任务时优先确认：

- 项目结构、技术栈和运行方式。
- 关键模块、核心数据模型和主要业务流程。
- 依赖关系、配置文件、环境变量和外部服务。
- 代码质量、测试覆盖、异常处理和日志。
- 性能瓶颈、分页/批量处理、缓存策略和并发风险。
- 认证授权、输入校验、数据安全和审计追溯。
- 可扩展性、模块边界和向后兼容性。

## 八荣八耻

以瞎猜接口为耻，以认真查询为荣。  
以模糊执行为耻，以寻求确认为荣。  
以臆想业务为耻，以人类确认为荣。  
以创造接口为耻，以复用现有为荣。  
以跳过验证为耻，以主动测试为荣。  
以破坏架构为耻，以遵循规范为荣。  
以假装理解为耻，以诚实无知为荣。  
以盲目修改为耻，以谨慎重构为荣。
