# Event Based Agents 架构设计总览

## 1. 背景与动机

### 当前架构的局限性

LangBot 当前的平台适配器架构围绕**消息事件**单一场景设计：

- **事件层面**：只监听 `FriendMessage`（私聊消息）和 `GroupMessage`（群消息）两种事件
- **API 层面**：只暴露 `send_message` 和 `reply_message` 两个平台 API
- **处理层面**：所有消息统一进入 Pipeline 流水线处理，无法为不同事件类型配置不同处理逻辑
- **适配器结构**：每个适配器是单个 Python 文件（200-800 行），随着功能增加难以维护

这导致以下问题：

1. **无法处理非消息事件**：新成员入群、好友请求、消息撤回、消息编辑等大部分平台都支持的事件被完全忽略
2. **平台能力未充分利用**：编辑消息、撤回消息、获取群成员列表、管理群组等 API 无法使用
3. **插件能力受限**：插件只能监听消息事件、只能发送/回复消息，无法实现更丰富的交互
4. **处理逻辑不灵活**：所有消息走同一条 Pipeline，无法为入群欢迎、好友自动通过等场景配置独立的处理流程

### 设计目标

Event Based Agents（EBA）架构旨在将 LangBot 从"消息处理平台"升级为"事件驱动的智能代理平台"：

- **丰富事件**：支持消息、群组、好友、Bot 状态等多种事件类型
- **丰富 API**：支持消息编辑/撤回、群组管理、用户信息查询等通用 API，以及适配器特有 API 的透传调用
- **灵活编排**：用户可在 WebUI 上为每个 Bot 的每种事件类型配置不同的处理器
- **可扩展**：适配器可声明自己支持的事件和 API，平台特有能力通过标准机制暴露
- **向后兼容**：现有插件无需修改即可在新架构下运行

## 2. 架构对比

### 现有架构

```
消息平台 (Telegram/Discord/...)
    │
    ▼
平台适配器 (单文件, 只处理消息)
    │ FriendMessage / GroupMessage
    ▼
RuntimeBot (注册 on_friend_message / on_group_message 回调)
    │
    ▼
MessageAggregator (消息聚合)
    │
    ▼
QueryPool → Controller → Pipeline (固定阶段链)
    │                         │
    │                         ▼
    │                    RequestRunner (local-agent / dify / n8n / ...)
    │
    ▼
adapter.reply_message() / adapter.send_message()
```

关键代码路径：
- 适配器基类：`langbot-plugin-sdk/.../abstract/platform/adapter.py` — `AbstractMessagePlatformAdapter`
- 事件定义：`langbot-plugin-sdk/.../builtin/platform/events.py` — 仅 `FriendMessage` / `GroupMessage`
- Bot 管理：`LangBot/src/langbot/pkg/platform/botmgr.py` — `RuntimeBot` 只注册两个消息回调
- 流水线控制：`LangBot/src/langbot/pkg/pipeline/controller.py` — 从 QueryPool 消费并执行 Pipeline

### 新架构（Event Based Agents）

```
消息平台 (Telegram/Discord/...)
    │
    ▼
平台适配器 (独立目录, 监听所有事件, 实现丰富 API)
    │ MessageReceived / MemberJoined / FriendRequest / ...
    ▼
EventBus (统一事件总线)
    │
    ▼
EventRouter (事件路由引擎, 读取 Bot 的 event_handlers 配置)
    │
    ├─→ PipelineHandler   — 现有流水线（完整 Stage 链）
    ├─→ AgentHandler      — 直接调用 RequestRunner（轻量 AI 处理）
    ├─→ WebhookHandler    — POST 到外部服务（Dify/n8n webhook 等）
    └─→ PluginHandler     — 分发给插件 EventListener
    │
    ▼
统一平台 API
  send / reply / edit / delete / getGroupInfo / getUserInfo / callPlatformApi / ...
```

## 3. 核心概念

### 3.1 统一事件体系

所有平台事件统一为命名空间式的事件类型：

| 命名空间 | 事件 | 说明 |
|----------|------|------|
| `message.*` | `message.received`, `message.edited`, `message.deleted`, `message.reaction` | 消息相关 |
| `feedback.*` | `feedback.received` | 用户对 Bot 回复的点赞、点踩、取消反馈等评价事件 |
| `group.*` | `group.member_joined`, `group.member_left`, `group.member_banned`, `group.info_updated` | 群组相关 |
| `friend.*` | `friend.request_received`, `friend.added`, `friend.removed` | 好友相关 |
| `bot.*` | `bot.invited_to_group`, `bot.removed_from_group`, `bot.muted`, `bot.unmuted` | Bot 状态 |
| `platform.*` | `platform.{adapter}.{action}` | 适配器特有事件 |

详见 [01-event-system.md](./01-event-system.md)。

### 3.2 统一平台 API

扩展适配器基类，提供通用 API + 透传机制：

| 类别 | API | 必需/可选 |
|------|-----|----------|
| 消息 | `send_message`, `reply_message`, `edit_message`, `delete_message`, `forward_message` | send/reply 必需，其余可选 |
| 群组 | `get_group_info`, `get_group_member_list`, `get_group_member_info`, `mute_member`, `kick_member` | 全部可选 |
| 用户 | `get_user_info`, `get_friend_list` | 全部可选 |
| 媒体 | `upload_file`, `get_file_url` | 全部可选 |
| 透传 | `call_platform_api(action, params)` | 可选 |

详见 [02-platform-api.md](./02-platform-api.md)。

### 3.3 适配器新结构

每个适配器从单文件迁移到独立目录：

```
pkg/platform/adapters/
├── _base/                    # 基类和通用定义
│   ├── adapter.py
│   ├── events.py
│   ├── entities.py
│   └── api.py
├── telegram/
│   ├── __init__.py
│   ├── adapter.py            # 主适配器类
│   ├── event_converter.py    # 事件转换（多种事件类型）
│   ├── message_converter.py  # 消息链转换
│   ├── api_impl.py           # 通用 API 实现
│   ├── platform_api.py       # 平台特有 API
│   ├── types.py              # 平台特有类型
│   └── manifest.yaml
├── discord/
│   └── ...
```

详见 [03-adapter-structure.md](./03-adapter-structure.md)。

### 3.4 事件处理器（Event Handler）

四种处理器类型，用户在 WebUI 的 Bot 管理页面配置：

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| **pipeline** | 现有流水线机制，完整的多 Stage 处理链（PreProcessor → MessageProcessor → PostProcessor 等） | 复杂消息处理，需要完整的预处理/后处理流程 |
| **agent** | 直接调用 RequestRunner（local-agent / dify / n8n / coze / dashscope / langflow / tbox），从 Pipeline 中解耦 | 轻量级 AI 处理、直接对接外部 LLMOps 平台处理各类事件 |
| **webhook** | 将事件 POST 到外部 URL，根据响应执行动作 | 对接自建服务、Dify/n8n 的 Webhook 触发器、自定义后端 |
| **plugin** | 分发给插件 EventListener 处理 | 插件自定义逻辑 |

配置存储在 Bot 表的 `event_handlers` JSON 字段中，通过 WebUI 编排面板管理。

详见 [04-event-routing.md](./04-event-routing.md)。

### 3.5 插件 SDK 改造

- 新事件类型全部暴露给插件
- 新 API 全部通过 `LangBotAPIProxy` 暴露
- 兼容层保证现有插件零修改运行

详见 [05-plugin-sdk.md](./05-plugin-sdk.md)。

## 4. 关键设计决策

| # | 决策点 | 选择 | 理由 |
|---|--------|------|------|
| 1 | 事件处理器配置粒度 | 每个 Bot 独立配置 | Bot 是用户操作的核心单元，不同 Bot 可能对接不同业务场景 |
| 2 | 适配器特有 API | 统一抽象 + `call_platform_api` 透传 | 通用 API 覆盖大部分场景，透传机制保证灵活性，避免每个适配器导出独立的类型化 API 包 |
| 3 | 向后兼容策略 | 兼容层适配 | 保留旧事件类型和 API 作为新系统的 alias/wrapper，现有插件无需修改 |
| 4 | 处理器配置存储 | Bot 表新增 `event_handlers` JSON 字段 | 简单直接，避免新增关联表；替代现有 `use_pipeline_uuid` |
| 5 | Agent 处理器定位 | 从 Pipeline 中解耦 RequestRunner | 不是所有事件都需要完整 Pipeline Stage 链；Agent 处理器提供轻量级 AI 处理路径，支持所有现有 Runner |
| 6 | 事件命名方式 | 命名空间式（`message.received`） | 清晰的分类层级，便于通配匹配（`message.*`），与 WebUI 配置天然对应 |

## 5. 文档索引

| 文档 | 内容 |
|------|------|
| [01-event-system.md](./01-event-system.md) | 统一事件体系：事件分类、定义、生命周期 |
| [02-platform-api.md](./02-platform-api.md) | 统一平台 API：通用 API、透传 API、实体定义 |
| [03-adapter-structure.md](./03-adapter-structure.md) | 适配器新结构：目录布局、基类、注册机制 |
| [04-event-routing.md](./04-event-routing.md) | 事件路由与编排：路由引擎、处理器类型、WebUI 数据模型 |
| [05-plugin-sdk.md](./05-plugin-sdk.md) | 插件 SDK 改造：新事件/API、兼容层 |
| [06-migration-plan.md](./06-migration-plan.md) | 分阶段迁移计划 |

## 6. 涉及的代码仓库

| 仓库 | 改动范围 |
|------|----------|
| **langbot-plugin-sdk** | 事件定义、实体模型、API 接口、适配器基类、通信协议扩展 |
| **LangBot**（后端） | 适配器实现、事件路由引擎、Bot 实体扩展、数据库迁移、RequestRunner 解耦 |
| **LangBot**（前端） | Bot 事件处理器编排面板 |
| **langbot-wiki** | 新架构文档、插件开发指南更新、适配器开发指南 |
| **langbot-plugin-demo** | 示例更新（使用新事件和 API） |
