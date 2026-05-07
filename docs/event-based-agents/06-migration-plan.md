# 分阶段迁移计划

## 1. 概述

EBA 架构涉及 langbot-plugin-sdk、LangBot 后端、LangBot 前端、文档和示例插件等多个仓库的改动。为降低风险、保证系统稳定性，采用分阶段渐进式迁移策略。

### 1.1 阶段总览

| 阶段 | 名称 | 范围 | 依赖 |
|------|------|------|------|
| Phase 1 | SDK 实体层 | langbot-plugin-sdk | 无 |
| Phase 2 | 适配器重构 | LangBot 后端 | Phase 1 |
| Phase 3 | 核心系统 | LangBot 后端 | Phase 2 |
| Phase 4 | 插件 SDK 集成 | langbot-plugin-sdk + LangBot | Phase 3 |
| Phase 5 | WebUI 编排面板 | LangBot 前端 | Phase 3 |
| Phase 6 | 文档与示例 | langbot-wiki + langbot-plugin-demo | Phase 4, 5 |

### 1.2 核心原则

- **每个阶段结束后系统可运行**：任何阶段完成后，现有功能不受影响
- **向后兼容贯穿全程**：旧接口在整个迁移期间保持可用
- **先 SDK 后实现**：先定义好接口和模型，再做具体实现
- **先核心适配器后边缘**：优先迁移用户量大的适配器

---

## 2. Phase 1：SDK 实体层

**目标**：在 langbot-plugin-sdk 中定义新的事件体系、通用实体、API 接口和适配器基类。

**仓库**：`langbot-plugin-sdk`

### 2.1 任务清单

| # | 任务 | 文件/模块 | 说明 |
|---|------|----------|------|
| 1.1 | 定义通用事件基类层次 | `api/entities/builtin/platform/events.py` | 新增 `MessageReceivedEvent`, `MessageEditedEvent`, `GroupMemberJoinedEvent` 等，保留现有 `FriendMessage`/`GroupMessage` |
| 1.2 | 定义平台特有事件基类 | `api/entities/builtin/platform/events.py` | 新增 `PlatformSpecificEvent` |
| 1.3 | 扩展通用实体 | `api/entities/builtin/platform/entities.py` | 新增 `User`（统一 Friend/GroupMember 的基础）、`Channel` 等，保留现有实体 |
| 1.4 | 清理消息组件 | `api/entities/builtin/platform/message.py` | 将 `WeChatMiniPrograms` 等 WeChat 特有组件标记为 platform-specific，不再作为通用组件 |
| 1.5 | 定义新适配器基类 | `api/definition/abstract/platform/adapter.py` | 新增 `AbstractPlatformAdapter`（继承现有 `AbstractMessagePlatformAdapter` 并扩展通用 API 方法），保留旧基类 |
| 1.6 | 定义 API 能力声明 | `api/definition/abstract/platform/capabilities.py`（新文件） | `AdapterCapabilities` 数据类，声明适配器支持的事件和 API |
| 1.7 | 定义 `NotSupportedError` | `api/entities/builtin/platform/errors.py`（新文件） | 可选 API 未实现时抛出的异常 |

### 2.2 关键设计约束

- 所有新增定义以**新增文件或新增类**的方式引入，**不修改**现有类的字段和方法签名
- 现有 `AbstractMessagePlatformAdapter` 保留不动，新基类 `AbstractPlatformAdapter` 继承它
- 新事件类与旧事件类并存，通过 `event_type` 字段（命名空间字符串）区分

### 2.3 验收标准

- [ ] 所有新增类可正常 import 且通过类型检查
- [ ] 现有 `FriendMessage`, `GroupMessage`, `AbstractMessagePlatformAdapter` 等类行为不变
- [ ] 新增单元测试覆盖事件序列化/反序列化、实体构造
- [ ] SDK 版本号 minor bump（如 `0.x.0` → `0.x+1.0`）

---

## 3. Phase 2：适配器重构

**目标**：将现有单文件适配器迁移到独立目录结构，实现新事件监听和通用 API。

**仓库**：`LangBot`（后端）

### 3.1 适配器迁移优先级

根据用户量和代表性，建议按以下顺序迁移：

| 优先级 | 适配器 | 理由 |
|--------|--------|------|
| P0 | **Telegram** | 用户量大，API 最完善，适合作为参考实现 |
| P0 | **Discord** | 国际用户主要平台，事件类型丰富 |
| P1 | **aiocqhttp**（OneBot v11） | 国内 QQ 用户主要适配器 |
| P1 | **Satori** | 通用协议适配器，覆盖多个平台 |
| P2 | **Lark** / **DingTalk** / **Slack** | 企业平台，用户量中等 |
| P2 | **qqofficial** / **WeChat 系列** | 国内用户 |
| P3 | **Kook** / **LINE** / **WeCom 系列** | 用户量较小 |
| P3 | **WebSocket** | 内置适配器，相对简单 |
| P4 | **legacy/*** | 遗留适配器，按需决定是否迁移或废弃 |

### 3.2 单个适配器迁移步骤（以 Telegram 为例）

| # | 任务 | 说明 |
|---|------|------|
| 2.1 | 创建目录结构 | `pkg/platform/adapters/telegram/` 下创建 `__init__.py`, `adapter.py`, `event_converter.py`, `message_converter.py`, `api_impl.py`, `types.py`, `manifest.yaml` |
| 2.2 | 迁移消息转换器 | 将 `TelegramMessageConverter` 从 `sources/telegram.py` 搬到 `adapters/telegram/message_converter.py`，逻辑不变 |
| 2.3 | 重写事件转换器 | 新的 `TelegramEventConverter` 支持将 Telegram Update 转换为所有通用事件类型（不只是消息），不支持的事件转为 `PlatformSpecificEvent` |
| 2.4 | 实现通用 API | 在 `api_impl.py` 中实现 `edit_message`, `delete_message`, `get_group_info` 等 Telegram 支持的通用 API |
| 2.5 | 实现透传 API | 在 `adapter.py` 中实现 `call_platform_api`，将 action 映射到 Telegram Bot API 调用 |
| 2.6 | 声明能力 | 在 `manifest.yaml` 或适配器类中声明支持的事件和 API 列表 |
| 2.7 | 新建 Adapter 主类 | `TelegramAdapter` 继承 `AbstractPlatformAdapter`（新基类），委托各模块实现 |
| 2.8 | 更新 manifest.yaml | 更新 `execution.python.path` 指向新位置 |
| 2.9 | 验证 | 确保新适配器通过现有消息收发流程的测试 |

### 3.3 基础设施任务

| # | 任务 | 说明 |
|---|------|------|
| 2.A | 创建 `adapters/_base/` | 将 SDK 中新基类的运行时辅助代码放在此处（如事件分发辅助函数） |
| 2.B | 更新 ComponentDiscovery | 使 `discover_blueprint` 支持扫描 `adapters/` 子目录中的 YAML |
| 2.C | 更新 `templates/components.yaml` | 将 `fromDirs` 从 `pkg/platform/sources/` 改为 `pkg/platform/adapters/`（过渡期两个都扫描） |
| 2.D | 保留旧 sources/ | 过渡期不删除旧文件，通过 manifest 的 `deprecated: true` 标记 |

### 3.4 验收标准

- [ ] 已迁移的适配器在新目录结构下正常启动和收发消息
- [ ] 新事件（如 `message.edited`）在支持的平台上正确触发
- [ ] 通用 API（如 `edit_message`）在支持的平台上正确执行
- [ ] 未迁移的适配器（仍在 `sources/`）继续正常工作
- [ ] ComponentDiscovery 同时扫描新旧目录

---

## 4. Phase 3：核心系统

**目标**：实现 EventBus、EventRouter 和事件处理器框架，将事件从适配器分发到不同的处理器。

**仓库**：`LangBot`（后端）

### 4.1 任务清单

| # | 任务 | 文件/模块 | 说明 |
|---|------|----------|------|
| 3.1 | 实现 EventBus | `pkg/platform/event_bus.py`（新文件） | 事件总线：接收适配器事件，进行日志记录，分发给 EventRouter |
| 3.2 | 实现 EventRouter | `pkg/platform/event_router.py`（新文件） | 事件路由引擎：读取 Bot 的 `event_handlers` 配置，匹配事件类型，分发到对应 Handler |
| 3.3 | 实现 PipelineHandler | `pkg/platform/handlers/pipeline_handler.py` | 将 `message.received` 事件转为现有 Query，进入 Pipeline 流水线 |
| 3.4 | 实现 AgentHandler | `pkg/platform/handlers/agent_handler.py` | 直接调用 RequestRunner 处理事件，不经过 Pipeline 多 Stage 流程 |
| 3.5 | 实现 WebhookHandler | `pkg/platform/handlers/webhook_handler.py` | 将事件 POST 到外部 URL，解析响应执行动作（重构现有 WebhookPusher） |
| 3.6 | 实现 PluginHandler | `pkg/platform/handlers/plugin_handler.py` | 将事件分发给插件 EventListener（复用现有 plugin_connector 机制） |
| 3.7 | Bot 实体扩展 | `pkg/entity/persistence/bot.py` | 新增 `event_handlers` JSON 字段 |
| 3.8 | 数据库迁移 | `pkg/persistence/migrations/` | 新增迁移脚本：添加 `event_handlers` 列，将现有 `use_pipeline_uuid` 数据迁移为 `event_handlers` 格式 |
| 3.9 | 重构 RuntimeBot | `pkg/platform/botmgr.py` | 将 `initialize()` 中硬编码的 `on_friend_message`/`on_group_message` 回调替换为通过 EventBus 分发所有事件 |
| 3.10 | 重构 MessageAggregator | `pkg/pipeline/aggregator.py` | 从 RuntimeBot 解耦，作为 PipelineHandler 的内部机制（只对 `message.received` 事件生效） |
| 3.11 | Agent Handler 中 RequestRunner 解耦 | `pkg/provider/runner.py` + handlers | RequestRunner 需要能独立于 Pipeline Stage 运行，为 Agent Handler 提供轻量调用路径 |
| 3.12 | HTTP API 扩展 | `pkg/api/http/controller/` | 新增/更新 Bot API 端点以支持 `event_handlers` 的 CRUD |

### 4.2 数据迁移策略

现有 Bot 表有 `use_pipeline_uuid` 字段，需要自动迁移为 `event_handlers`：

```python
# 迁移逻辑伪代码
for bot in all_bots:
    if bot.use_pipeline_uuid:
        bot.event_handlers = [
            {
                "event_type": "message.received",
                "handler_type": "pipeline",
                "handler_config": {
                    "pipeline_uuid": bot.use_pipeline_uuid
                }
            }
        ]
    else:
        bot.event_handlers = []
```

### 4.3 RuntimeBot 重构要点

当前 `RuntimeBot.initialize()` 硬编码注册两个回调：

```python
# 现有代码 (botmgr.py)
self.adapter.register_listener(FriendMessage, on_friend_message)
self.adapter.register_listener(GroupMessage, on_group_message)
```

重构后改为注册通用事件回调：

```python
# 新代码
async def on_event(event: Event, adapter: AbstractPlatformAdapter):
    await self.event_bus.emit(
        bot_uuid=self.bot_entity.uuid,
        event=event,
        adapter=adapter,
    )

# 注册所有事件类型的统一回调
self.adapter.register_listener(Event, on_event)
```

EventBus 接收事件后，调用 EventRouter 按配置分发。

### 4.4 事件处理器执行流程

```
EventBus.emit(bot_uuid, event, adapter)
    │
    ▼
EventRouter.route(bot_uuid, event)
    │ 查询 bot.event_handlers 配置
    │ 匹配 event_type（精确匹配 > 通配符 *）
    ▼
匹配到的 Handler(s)
    │
    ├── PipelineHandler.handle(event, adapter)
    │   │ 仅支持 message.received
    │   │ 构造 Query → MessageAggregator → QueryPool → Pipeline
    │   └── 沿用现有完整流水线机制
    │
    ├── AgentHandler.handle(event, adapter)
    │   │ 根据 handler_config 选择 RequestRunner
    │   │ 直接调用 runner.run() 处理事件
    │   └── 将结果通过 adapter API 回复
    │
    ├── WebhookHandler.handle(event, adapter)
    │   │ 序列化事件为 JSON
    │   │ POST 到 handler_config.url
    │   └── 解析响应，执行动作（回复消息、调用 API 等）
    │
    └── PluginHandler.handle(event, adapter)
        │ 通过 plugin_connector 分发给插件
        └── 插件 EventListener 处理
```

### 4.5 验收标准

- [ ] `message.received` 事件通过 PipelineHandler 正确进入现有 Pipeline（与旧行为一致）
- [ ] 新增事件（如 `group.member_joined`）能通过 PluginHandler 分发给插件
- [ ] AgentHandler 能直接调用 RequestRunner（至少 `local-agent`）处理事件并回复
- [ ] WebhookHandler 能将事件 POST 到外部 URL
- [ ] 数据库迁移正确执行，`use_pipeline_uuid` 数据迁移到 `event_handlers`
- [ ] 现有 Bot 在不修改配置的情况下行为不变（自动迁移保证）

---

## 5. Phase 4：插件 SDK 集成

**目标**：将新事件和 API 通过插件 SDK 暴露给插件开发者，同时实现兼容层。

**仓库**：`langbot-plugin-sdk` + `LangBot`

### 5.1 任务清单

| # | 任务 | 说明 |
|---|------|------|
| 4.1 | 新增插件事件包装 | 在 `api/entities/events.py` 中为每个通用事件新增插件级事件类（如 `MessageEditedReceived`, `MemberJoinedReceived`） |
| 4.2 | 兼容层实现 | `PersonMessageReceived` / `GroupMessageReceived` 由新的 `MessageReceivedEvent` 自动生成，旧事件作为新事件的 alias |
| 4.3 | 新 API 暴露 | 在 `LangBotAPIProxy` 中新增方法：`edit_message`, `delete_message`, `get_group_info`, `get_user_info`, `call_platform_api` 等 |
| 4.4 | 通信协议扩展 | 在 `entities/io/actions/enums.py` 中新增 action 枚举（如 `EDIT_MESSAGE`, `DELETE_MESSAGE`, `GET_GROUP_INFO`, `CALL_PLATFORM_API`） |
| 4.5 | Runtime Handler 扩展 | 在 PluginConnectionHandler / ControlConnectionHandler 中添加新 action 的处理逻辑 |
| 4.6 | EventListener 扩展 | 确保 `@handler()` 装饰器支持注册新事件类型 |
| 4.7 | QueryBasedAPI 扩展 | 在 `QueryBasedAPIProxy` 中新增事件上下文相关的 API（如 `get_event_source_adapter`） |

### 5.2 兼容层详细设计

```
新事件系统                         旧事件系统（兼容层）
─────────────                    ─────────────────
MessageReceivedEvent             ┌→ PersonMessageReceived (chat_type == "private")
  (chat_type: "private"|"group") ┤
                                 └→ GroupMessageReceived  (chat_type == "group")
```

**实现方式**：在 RuntimeEventDispatcher 中，当分发 `MessageReceivedEvent` 给插件时，同时生成对应的旧事件类实例。插件可以用新事件类或旧事件类注册 handler，都能收到。

### 5.3 验收标准

- [ ] 现有插件（使用旧事件和 API）无需修改即可运行
- [ ] 新插件可以使用新事件类型（如 `MemberJoinedReceived`）注册 handler
- [ ] 新 API（如 `edit_message`）可通过 `self.edit_message()` 或 `event_context.edit_message()` 调用
- [ ] 透传 API `call_platform_api` 可正常调用适配器特有功能
- [ ] 所有新 action 的通信协议正确工作（stdio / WebSocket）

---

## 6. Phase 5：WebUI 编排面板

**目标**：在 WebUI 的 Bot 管理页面实现事件处理器的可视化编排。

**仓库**：`LangBot`（前端 `web/`）

### 6.1 任务清单

| # | 任务 | 说明 |
|---|------|------|
| 5.1 | Bot 编辑页面扩展 | 在 Bot 编辑页面新增「事件处理」面板 |
| 5.2 | 事件处理器列表组件 | 可视化展示当前 Bot 的 `event_handlers` 列表，支持增删改排序 |
| 5.3 | 事件类型选择器 | 下拉选择事件类型（命名空间分组展示），支持通配符 `*` |
| 5.4 | Handler 类型选择与配置 | 选择 handler 类型后展示对应的配置表单（Pipeline 选择器、Runner 选择器、Webhook URL 等） |
| 5.5 | Pipeline Handler 配置 | 复用现有的 Pipeline 选择 UI（从现有 `use_pipeline_uuid` 选择器迁移） |
| 5.6 | Agent Handler 配置 | Runner 选择器（local-agent / dify / n8n / coze 等）+ Runner 参数配置表单 |
| 5.7 | Webhook Handler 配置 | URL 输入、认证方式选择、Header 配置 |
| 5.8 | Plugin Handler 配置 | 通常无需额外配置，分发给所有匹配的插件 EventListener |
| 5.9 | HTTP API 对接 | 前端调用后端 API 保存/读取 `event_handlers` 配置 |
| 5.10 | 迁移提示 | 对于从旧版本升级的用户，如果检测到 `use_pipeline_uuid` 已自动迁移，展示提示说明 |

### 6.2 UI 交互设计概要

```
┌─ Bot 编辑页面 ─────────────────────────────────────┐
│                                                     │
│  基本信息  │  适配器配置  │  ★ 事件处理  │           │
│                                                     │
│  ┌─ 事件处理器列表 ────────────────────────────┐    │
│  │                                              │    │
│  │  ① message.received → Pipeline: "主流水线"   │    │
│  │     [编辑] [删除]                            │    │
│  │                                              │    │
│  │  ② group.member_joined → Agent: local-agent  │    │
│  │     [编辑] [删除]                            │    │
│  │                                              │    │
│  │  ③ * (默认) → Plugin                         │    │
│  │     [编辑] [删除]                            │    │
│  │                                              │    │
│  │  [+ 添加事件处理器]                           │    │
│  │                                              │    │
│  └──────────────────────────────────────────────┘    │
│                                                     │
│                              [保存]  [取消]          │
└─────────────────────────────────────────────────────┘
```

### 6.3 验收标准

- [ ] 用户可以在 WebUI 上为 Bot 添加/编辑/删除事件处理器
- [ ] 四种 Handler 类型均有对应的配置表单
- [ ] 配置保存后正确写入数据库 `event_handlers` 字段
- [ ] 旧版本升级后，自动迁移的配置在 UI 上正确展示
- [ ] Pipeline Handler 的行为与旧的 `use_pipeline_uuid` 完全一致

---

## 7. Phase 6：文档与示例

**目标**：更新所有面向开发者的文档和示例。

**仓库**：`langbot-wiki`, `langbot-plugin-demo`

### 7.1 任务清单

| # | 任务 | 仓库 | 说明 |
|---|------|------|------|
| 6.1 | EBA 架构概览文档 | langbot-wiki | 面向用户的新架构说明 |
| 6.2 | 适配器开发指南更新 | langbot-wiki | 如何开发一个新的适配器（新目录结构、新基类、事件转换等） |
| 6.3 | 插件开发指南更新 | langbot-wiki | 新事件类型、新 API 的使用说明 |
| 6.4 | 插件迁移指南 | langbot-wiki | 现有插件如何迁移到新事件/API（如果需要使用新能力） |
| 6.5 | 事件处理器配置指南 | langbot-wiki | WebUI 上如何配置事件处理器 |
| 6.6 | 示例插件更新 | langbot-plugin-demo | HelloPlugin 增加新事件监听示例、新 API 调用示例 |
| 6.7 | 新示例插件 | langbot-plugin-demo | 新建一个示例展示非消息事件处理（如入群欢迎） |

---

## 8. 风险评估与缓解

### 8.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 适配器迁移中断现有功能 | 高 | 中 | 新旧目录并存，ComponentDiscovery 同时扫描两个目录，逐个适配器迁移验证 |
| 事件模型不兼容导致插件崩溃 | 高 | 低 | 兼容层保证旧事件类型继续工作，新增类不修改旧类 |
| 数据库迁移失败 | 高 | 低 | 迁移脚本做前置校验，`use_pipeline_uuid` 在过渡期保留不删除 |
| RequestRunner 解耦破坏 Pipeline | 高 | 中 | Agent Handler 调用 Runner 的路径独立于 Pipeline，不修改现有 Pipeline Stage 中的 Runner 调用逻辑 |
| 性能回退（EventBus 额外开销） | 中 | 低 | EventBus 在进程内同步分发，无额外序列化/网络开销 |
| 各平台事件差异大难以统一 | 中 | 中 | 通用事件只抽象最大公约数字段，差异部分保留在 `source_platform_object`；不支持的事件走 `PlatformSpecificEvent` |

### 8.2 兼容性风险

| 风险 | 缓解措施 |
|------|----------|
| 现有插件使用旧事件类 | 兼容层自动将新事件转为旧事件分发，两种事件类都能注册 handler |
| 现有插件调用 `reply()` / `send_message()` | 这两个 API 保持不变，只是底层实现可能微调 |
| 第三方基于 `AbstractMessagePlatformAdapter` 开发的适配器 | 旧基类保留，新基类继承旧基类，第三方适配器无需立即迁移 |
| 用户自定义 Pipeline 配置 | Pipeline 机制完整保留，PipelineHandler 只是入口变了（从 RuntimeBot 硬编码变为 EventRouter 配置） |

### 8.3 回滚策略

每个 Phase 独立可回滚：

- **Phase 1**（SDK 新增类）：删除新增文件，回退 SDK 版本号
- **Phase 2**（适配器目录）：恢复 `components.yaml` 的 `fromDirs` 指向旧目录，旧 sources/ 未删除
- **Phase 3**（核心系统）：回退数据库迁移，恢复 RuntimeBot 旧的硬编码回调
- **Phase 4**（插件集成）：回退 SDK 版本，插件使用旧版 SDK
- **Phase 5**（WebUI）：前端回退，Bot 编辑页面隐藏事件处理面板

---

## 9. 里程碑与时间线建议

| 里程碑 | 阶段 | 预期产出 |
|--------|------|----------|
| M1 | Phase 1 完成 | SDK 新版本发布，包含新事件/实体/基类定义 |
| M2 | Phase 2 首批适配器（Telegram + Discord） | 两个参考实现，验证目录结构和事件/API 体系 |
| M3 | Phase 3 核心系统 | EventBus + EventRouter + 四种 Handler 可用 |
| M4 | Phase 2 剩余适配器 | 所有活跃适配器迁移完成 |
| M5 | Phase 4 插件集成 | 新 SDK 发布，插件可使用新事件和 API |
| M6 | Phase 5 WebUI | 事件处理器编排面板上线 |
| M7 | Phase 6 文档 | 开发者文档和示例更新完毕 |

建议 M1-M3 作为第一个大版本发布（如 v5.0），M4-M7 在后续小版本迭代中完成。

---

## 10. 开发指引

### 10.1 分支策略

建议在主仓库创建 `feature/eba` 长期特性分支，各 Phase 在子分支上开发后合入特性分支：

```
main
  └── feature/eba
        ├── feature/eba-sdk-entities      (Phase 1)
        ├── feature/eba-adapter-telegram   (Phase 2)
        ├── feature/eba-adapter-discord    (Phase 2)
        ├── feature/eba-core-system        (Phase 3)
        ├── feature/eba-plugin-sdk         (Phase 4)
        └── feature/eba-webui              (Phase 5)
```

### 10.2 测试策略

| 层次 | 测试内容 | 工具 |
|------|----------|------|
| 单元测试 | 事件序列化/反序列化、实体构造、API 调用 mock | pytest |
| 集成测试 | EventBus → EventRouter → Handler 全链路 | pytest + asyncio |
| 适配器测试 | 各适配器的事件转换、消息转换、API 调用 | pytest + mock SDK |
| 端到端测试 | 从模拟平台事件到完整处理流程 | staging 环境 |
| 插件兼容性测试 | 旧插件在新系统下的行为 | langbot-plugin-demo |

### 10.3 代码审查关注点

- 新增代码是否影响现有行为
- 兼容层是否正确映射所有旧事件/API 场景
- 数据库迁移是否可逆
- 新 API 的错误处理（`NotSupportedError`）是否一致
- 事件模型的序列化在 stdio/WebSocket 通信中是否正确
