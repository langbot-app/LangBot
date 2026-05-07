# 事件路由与编排

## 1. 概述

事件路由是 EBA 架构的核心机制：事件从适配器产生后，经由 EventBus 进入 EventRouter，由 EventRouter 根据 Bot 的配置将事件分发到对应的处理器（Handler）。

**配置方式**：用户在 WebUI 的 Bot 管理页面通过可视化编排面板管理事件处理器配置，配置数据存储在数据库的 Bot 表 `event_handlers` JSON 字段中。

## 2. 数据模型

### 2.1 Bot 实体扩展

在 `bots` 表新增 `event_handlers` 字段：

```python
class Bot(Base):
    __tablename__ = "bots"

    uuid: str               # 主键
    name: str
    description: str
    adapter: str
    adapter_config: dict    # JSON
    enable: bool

    # 新增
    event_handlers: list    # JSON — 事件处理器配置列表

    # 保留（过渡期后弃用）
    use_pipeline_name: str  # deprecated
    use_pipeline_uuid: str  # deprecated

    created_at: datetime
    updated_at: datetime
```

### 2.2 EventHandler 配置结构

`event_handlers` 字段存储一个 JSON 数组，每个元素定义一条事件路由规则：

```python
class EventHandlerConfig(pydantic.BaseModel):
    """单条事件处理器配置"""

    event_type: str
    """匹配的事件类型

    支持精确匹配和通配符：
    - "message.received"       — 精确匹配
    - "message.*"              — 匹配 message 命名空间下所有事件
    - "group.*"                — 匹配 group 命名空间下所有事件
    - "*"                      — 匹配所有事件（兜底）
    """

    handler_type: str
    """处理器类型: "pipeline" | "agent" | "webhook" | "plugin" """

    handler_config: dict = {}
    """处理器的具体配置，结构取决于 handler_type"""

    enabled: bool = True
    """是否启用此规则"""

    priority: int = 0
    """优先级，数字越大越先匹配（同一事件类型有多条规则时）"""

    description: str = ""
    """规则描述（供 WebUI 显示）"""
```

### 2.3 各 Handler 类型的 handler_config 结构

#### pipeline

```json
{
    "handler_type": "pipeline",
    "handler_config": {
        "pipeline_uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    }
}
```

将事件作为消息事件传入现有 Pipeline 流水线。仅适用于 `message.received` 事件。

#### agent

```json
{
    "handler_type": "agent",
    "handler_config": {
        "runner": "local-agent",
        "runner_config": {
            "model_uuid": "...",
            "prompt": "你是一个群组助理，请处理以下事件：{event_summary}",
            "tools_enabled": true
        }
    }
}
```

```json
{
    "handler_type": "agent",
    "handler_config": {
        "runner": "dify-service-api",
        "runner_config": {
            "base_url": "https://api.dify.ai/v1",
            "api_key": "...",
            "app_type": "agent"
        }
    }
}
```

直接调用 RequestRunner 处理事件。可用的 runner 包括：
- `local-agent` — 内置 LLM Agent
- `dify-service-api` — Dify 平台
- `n8n-service-api` — n8n 工作流
- `coze-api` — Coze (扣子)
- `dashscope-app-api` — 阿里百炼
- `langflow-api` — Langflow
- `tbox-app-api` — 蚂蚁 Tbox

Agent 处理器不经过 Pipeline 的多 Stage 流程，而是直接构建上下文并调用 Runner。适用于所有事件类型。

**Agent Handler 与 Pipeline 的关系**：
- Pipeline 是完整的多 Stage 处理链（PreProcessor → MessageProcessor(内含Runner) → PostProcessor → ...），适合复杂消息处理
- Agent Handler 是轻量级的，直接调用 Runner，跳过 PreProcessor/PostProcessor 等阶段
- Pipeline 内部的 AI Stage 仍然使用 Runner，所以 Runner 本身被两种 Handler 共享
- 用户可以根据场景选择：消息处理用 Pipeline（更多控制），其他事件用 Agent（更直接）

#### webhook

```json
{
    "handler_type": "webhook",
    "handler_config": {
        "url": "https://example.com/webhook/langbot-events",
        "method": "POST",
        "headers": {
            "Authorization": "Bearer xxx"
        },
        "timeout": 30,
        "retry_count": 3,
        "retry_interval": 5,
        "response_actions": true
    }
}
```

将事件序列化为 JSON POST 到外部 URL。支持的特性：
- **认证**：通过 headers 配置（Bearer Token、API Key 等）
- **重试**：配置重试次数和间隔
- **响应动作**：如果 `response_actions` 为 true，解析响应 JSON 中的 `actions` 字段并执行（如发送消息、同意好友请求等）

Webhook 请求体格式：

```json
{
    "event": {
        "type": "group.member_joined",
        "timestamp": 1700000000.0,
        "bot_uuid": "...",
        "adapter_name": "telegram",
        "group": { "id": "...", "name": "..." },
        "member": { "id": "...", "nickname": "..." }
    },
    "bot": {
        "uuid": "...",
        "name": "...",
        "adapter": "telegram"
    }
}
```

响应体格式（当 `response_actions` 为 true 时）：

```json
{
    "actions": [
        {
            "type": "send_message",
            "params": {
                "target_type": "group",
                "target_id": "123456",
                "message": [{ "type": "Plain", "text": "欢迎新成员！" }]
            }
        },
        {
            "type": "call_platform_api",
            "params": {
                "action": "pin_message",
                "params": { "chat_id": "123456", "message_id": "789" }
            }
        }
    ]
}
```

#### plugin

```json
{
    "handler_type": "plugin",
    "handler_config": {
        "plugin_filter": []
    }
}
```

将事件分发给插件的 EventListener 处理。

- `plugin_filter`：可选的插件名过滤列表，为空表示分发给所有插件
- 沿用现有的插件事件分发机制（按优先级遍历插件，支持 `prevent_postorder`）

### 2.4 完整配置示例

一个 Bot 的 `event_handlers` 配置示例：

```json
[
    {
        "event_type": "message.received",
        "handler_type": "pipeline",
        "handler_config": {
            "pipeline_uuid": "default-pipeline-uuid"
        },
        "enabled": true,
        "priority": 10,
        "description": "消息事件使用默认流水线处理"
    },
    {
        "event_type": "group.member_joined",
        "handler_type": "agent",
        "handler_config": {
            "runner": "local-agent",
            "runner_config": {
                "model_uuid": "gpt-4o-mini",
                "prompt": "有新成员 {member_name} 加入了群组 {group_name}，请生成一条欢迎消息。"
            }
        },
        "enabled": true,
        "priority": 0,
        "description": "新成员入群时用 AI 生成欢迎消息"
    },
    {
        "event_type": "friend.request_received",
        "handler_type": "webhook",
        "handler_config": {
            "url": "https://my-server.com/api/friend-request",
            "response_actions": true
        },
        "enabled": true,
        "priority": 0,
        "description": "好友请求转发到自建服务处理"
    },
    {
        "event_type": "*",
        "handler_type": "plugin",
        "handler_config": {},
        "enabled": true,
        "priority": -100,
        "description": "所有事件兜底发给插件处理"
    }
]
```

## 3. EventBus 设计

EventBus 是事件的中转站，接收来自各个 RuntimeBot 的事件，交由 EventRouter 处理。

```python
class EventBus:
    """事件总线"""

    def __init__(self, ap: Application):
        self.ap = ap
        self.event_router = EventRouter(ap)

    async def emit(
        self,
        event: Event,
        adapter: AbstractPlatformAdapter,
    ):
        """接收并分发事件

        Args:
            event: 统一事件对象
            adapter: 产生此事件的适配器实例
        """
        # 1. 全局事件日志
        self.ap.logger.debug(
            f"EventBus: {event.type} from bot {event.bot_uuid}"
        )

        # 2. 交由 EventRouter 路由处理
        await self.event_router.route(event, adapter)
```

## 4. EventRouter 设计

EventRouter 是事件路由引擎，根据 Bot 的 `event_handlers` 配置决定事件的处理方式。

```python
class EventRouter:
    """事件路由引擎"""

    def __init__(self, ap: Application):
        self.ap = ap
        self.handlers: dict[str, AbstractEventHandler] = {
            "pipeline": PipelineHandler(ap),
            "agent": AgentHandler(ap),
            "webhook": WebhookHandler(ap),
            "plugin": PluginHandler(ap),
        }

    async def route(
        self,
        event: Event,
        adapter: AbstractPlatformAdapter,
    ):
        """路由事件到对应处理器"""

        # 1. 获取 Bot 配置
        bot = await self.ap.platform_mgr.get_bot_by_uuid(event.bot_uuid)
        if not bot:
            return

        # 2. 获取事件处理器配置
        event_handlers = bot.bot_entity.event_handlers or []

        # 3. 匹配规则（按 priority 降序排列）
        matched_handlers = self._match_handlers(event.type, event_handlers)

        if not matched_handlers:
            # 未匹配到任何规则 → 默认交给插件处理（向后兼容）
            await self.handlers["plugin"].handle(event, adapter, {})
            return

        # 4. 执行第一个匹配的 Handler
        #    （未来可扩展为多个 Handler 串行/并行执行）
        handler_config = matched_handlers[0]
        handler = self.handlers.get(handler_config.handler_type)

        if handler:
            await handler.handle(event, adapter, handler_config.handler_config)
        else:
            self.ap.logger.warning(
                f"Unknown handler type: {handler_config.handler_type}"
            )

    def _match_handlers(
        self,
        event_type: str,
        handlers: list[EventHandlerConfig],
    ) -> list[EventHandlerConfig]:
        """匹配事件类型到处理器配置

        匹配规则：
        1. 精确匹配：event_type == handler.event_type
        2. 命名空间通配：handler.event_type 为 "message.*" 时匹配所有 "message.xxx"
        3. 全局通配：handler.event_type 为 "*" 时匹配所有事件
        4. 按 priority 降序排列
        5. 只返回 enabled=True 的规则
        """
        matched = []
        for handler in handlers:
            if not handler.enabled:
                continue
            if self._event_type_matches(event_type, handler.event_type):
                matched.append(handler)

        matched.sort(key=lambda h: h.priority, reverse=True)
        return matched

    @staticmethod
    def _event_type_matches(event_type: str, pattern: str) -> bool:
        """判断事件类型是否匹配模式"""
        if pattern == "*":
            return True
        if pattern == event_type:
            return True
        if pattern.endswith(".*"):
            namespace = pattern[:-2]
            return event_type.startswith(namespace + ".")
        return False
```

## 5. 事件处理器（Handler）实现

### 5.1 Handler 基类

```python
class AbstractEventHandler(abc.ABC):
    """事件处理器基类"""

    def __init__(self, ap: Application):
        self.ap = ap

    @abc.abstractmethod
    async def handle(
        self,
        event: Event,
        adapter: AbstractPlatformAdapter,
        config: dict,
    ) -> None:
        """处理事件

        Args:
            event: 统一事件对象
            adapter: 适配器实例（用于调用平台 API 发送响应）
            config: handler_config 配置
        """
        ...
```

### 5.2 PipelineHandler

将消息事件注入现有 Pipeline 流水线处理。

```python
class PipelineHandler(AbstractEventHandler):
    """Pipeline 处理器 — 将事件送入现有 Pipeline 流水线"""

    async def handle(self, event, adapter, config):
        pipeline_uuid = config.get("pipeline_uuid")

        if not isinstance(event, MessageReceivedEvent):
            self.ap.logger.warning(
                f"PipelineHandler only supports MessageReceivedEvent, "
                f"got {event.type}"
            )
            return

        # 将 MessageReceivedEvent 转换为现有的 Query 并投入 QueryPool
        # 复用现有的 MessageAggregator + QueryPool + Pipeline 机制
        launcher_type = (
            LauncherTypes.PERSON
            if event.chat_type == ChatType.PRIVATE
            else LauncherTypes.GROUP
        )

        await self.ap.msg_aggregator.add_message(
            bot_uuid=event.bot_uuid,
            launcher_type=launcher_type,
            launcher_id=event.chat_id,
            sender_id=event.sender.id,
            message_event=event.to_legacy_event(),  # 转换为 FriendMessage/GroupMessage
            message_chain=event.message_chain,
            adapter=adapter,
            pipeline_uuid=pipeline_uuid,
        )
```

### 5.3 AgentHandler

直接调用 RequestRunner 处理事件，不经过 Pipeline Stage 链。

```python
class AgentHandler(AbstractEventHandler):
    """Agent 处理器 — 直接调用 RequestRunner 处理事件"""

    async def handle(self, event, adapter, config):
        runner_name = config.get("runner", "local-agent")
        runner_config = config.get("runner_config", {})

        # 1. 查找 Runner 类
        runner_cls = None
        for r in preregistered_runners:
            if r.name == runner_name:
                runner_cls = r
                break

        if not runner_cls:
            self.ap.logger.error(f"Runner not found: {runner_name}")
            return

        # 2. 构建事件上下文（将事件信息整理为 Runner 可处理的格式）
        event_context = self._build_event_context(event, runner_config)

        # 3. 实例化并调用 Runner
        runner = runner_cls(self.ap, self._build_runner_pipeline_config(config))

        response_messages = []
        async for result in runner.run(event_context):
            response_messages.append(result)

        # 4. 发送响应（如果 Runner 产生了回复）
        if response_messages and isinstance(event, MessageReceivedEvent):
            # 将 Runner 输出转换为 MessageChain 并回复
            reply_chain = self._build_reply_chain(response_messages)
            await adapter.reply_message(event, reply_chain)

    def _build_event_context(self, event, runner_config):
        """将事件构建为 Runner 可处理的上下文

        对于消息事件，直接使用消息内容。
        对于其他事件，根据 runner_config 中的 prompt 模板生成描述文本。
        """
        ...

    def _build_runner_pipeline_config(self, config):
        """将 handler_config 转换为 Runner 需要的 pipeline_config 格式"""
        ...
```

### 5.4 WebhookHandler

将事件 POST 到外部 URL。

```python
class WebhookHandler(AbstractEventHandler):
    """Webhook 处理器 — 将事件 POST 到外部 URL"""

    async def handle(self, event, adapter, config):
        url = config.get("url")
        method = config.get("method", "POST")
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30)
        retry_count = config.get("retry_count", 3)
        response_actions = config.get("response_actions", False)

        # 1. 构建请求体
        bot = await self.ap.platform_mgr.get_bot_by_uuid(event.bot_uuid)
        payload = {
            "event": event.model_dump(),
            "bot": {
                "uuid": bot.bot_entity.uuid,
                "name": bot.bot_entity.name,
                "adapter": bot.bot_entity.adapter,
            }
        }

        # 2. 发送请求（带重试）
        response = await self._send_with_retry(
            url, method, headers, payload, timeout, retry_count
        )

        # 3. 处理响应动作
        if response_actions and response:
            await self._execute_response_actions(
                response, adapter, event
            )

    async def _execute_response_actions(self, response, adapter, event):
        """执行响应中的动作列表"""
        actions = response.get("actions", [])
        for action in actions:
            action_type = action.get("type")
            params = action.get("params", {})

            if action_type == "send_message":
                chain = MessageChain.model_validate(params.get("message", []))
                await adapter.send_message(
                    params["target_type"],
                    params["target_id"],
                    chain,
                )
            elif action_type == "reply":
                chain = MessageChain.model_validate(params.get("message", []))
                await adapter.reply_message(event, chain)
            elif action_type == "call_platform_api":
                await adapter.call_platform_api(
                    params["action"],
                    params.get("params", {}),
                )
            elif action_type == "approve_friend_request":
                await adapter.approve_friend_request(
                    params["request_id"],
                    params.get("approve", True),
                )
            # ... 更多动作类型
```

### 5.5 PluginHandler

将事件分发给插件的 EventListener。

```python
class PluginHandler(AbstractEventHandler):
    """Plugin 处理器 — 分发给插件 EventListener"""

    async def handle(self, event, adapter, config):
        plugin_filter = config.get("plugin_filter", [])

        # 复用现有的插件事件分发机制
        # 通过 plugin_connector 将事件发送给 Plugin Runtime
        await self.ap.plugin_connector.emit_event(
            event=event,
            adapter=adapter,
            plugin_filter=plugin_filter,
        )
```

## 6. use_pipeline_uuid 迁移

### 6.1 自动迁移

数据库迁移脚本将现有的 `use_pipeline_uuid` 自动转换为 `event_handlers`：

```python
# 迁移逻辑
for bot in all_bots:
    if bot.use_pipeline_uuid and not bot.event_handlers:
        bot.event_handlers = [
            {
                "event_type": "message.received",
                "handler_type": "pipeline",
                "handler_config": {
                    "pipeline_uuid": bot.use_pipeline_uuid
                },
                "enabled": True,
                "priority": 10,
                "description": "Auto-migrated from use_pipeline_uuid"
            },
            {
                "event_type": "*",
                "handler_type": "plugin",
                "handler_config": {},
                "enabled": True,
                "priority": -100,
                "description": "Default plugin handler"
            }
        ]
```

### 6.2 过渡期兼容

在过渡期内，如果 `event_handlers` 为空且 `use_pipeline_uuid` 非空，EventRouter 自动回退到旧行为：

```python
# EventRouter.route() 中的兼容逻辑
if not event_handlers and bot.bot_entity.use_pipeline_uuid:
    # 回退：消息事件走 Pipeline，其他事件走 Plugin
    if isinstance(event, MessageReceivedEvent):
        await self.handlers["pipeline"].handle(
            event, adapter,
            {"pipeline_uuid": bot.bot_entity.use_pipeline_uuid}
        )
    else:
        await self.handlers["plugin"].handle(event, adapter, {})
    return
```

## 7. WebUI 编排面板数据模型

### 7.1 交互设计概要

在 WebUI 的 Bot 管理页面，新增"事件处理器"标签页（或区域），呈现为一个**规则列表**：

```
┌─────────────────────────────────────────────────────────────┐
│  事件处理器                                       [+ 添加规则]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ 规则 1 ─────────────────────────────────── [启用] [删除] ─┐ │
│  │  事件类型: [message.received    ▾]                         │ │
│  │  处理器:   [Pipeline           ▾]                         │ │
│  │  Pipeline: [默认流水线          ▾]                         │ │
│  │  优先级:   [10]                                           │ │
│  │  描述:     消息事件使用默认流水线处理                         │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ 规则 2 ─────────────────────────────────── [启用] [删除] ─┐ │
│  │  事件类型: [group.member_joined ▾]                         │ │
│  │  处理器:   [Agent              ▾]                         │ │
│  │  Runner:   [local-agent        ▾]                         │ │
│  │  模型:     [gpt-4o-mini        ▾]                         │ │
│  │  Prompt:   [有新成员加入...]                                │ │
│  │  优先级:   [0]                                            │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ 规则 3 (兜底) ──────────────────────────── [启用] [删除] ─┐ │
│  │  事件类型: [*                   ▾]                         │ │
│  │  处理器:   [Plugin             ▾]                         │ │
│  │  优先级:   [-100]                                         │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 前端数据结构

```typescript
interface EventHandlerRule {
  event_type: string;       // 下拉选择，选项从适配器 manifest 的 supported_events 获取
  handler_type: string;     // "pipeline" | "agent" | "webhook" | "plugin"
  handler_config: Record<string, any>;  // 根据 handler_type 动态渲染不同的配置表单
  enabled: boolean;
  priority: number;
  description: string;
}

// Bot 编辑接口扩展
interface BotConfig {
  uuid: string;
  name: string;
  adapter: string;
  adapter_config: Record<string, any>;
  enable: boolean;
  event_handlers: EventHandlerRule[];  // 新增
}
```

### 7.3 事件类型下拉选项

从 Bot 关联的适配器 manifest 中获取 `supported_events`，加上通配符选项：

```
- message.received
- message.edited
- message.deleted
- message.reaction
- feedback.received
- group.member_joined
- group.member_left
- group.member_banned
- group.info_updated
- friend.request_received
- friend.added
- bot.invited_to_group
- bot.removed_from_group
- bot.muted
- bot.unmuted
- platform.specific
─────────────────
- message.*          (所有消息事件)
- feedback.*         (所有反馈事件)
- group.*            (所有群组事件)
- friend.*           (所有好友事件)
- bot.*              (所有 Bot 事件)
- *                  (所有事件)
```

### 7.4 HTTP API

```
GET    /api/v1/bots/{uuid}/event-handlers         获取 Bot 的事件处理器配置
PUT    /api/v1/bots/{uuid}/event-handlers         更新 Bot 的事件处理器配置
GET    /api/v1/adapters/{name}/supported-events    获取适配器支持的事件类型
GET    /api/v1/adapters/{name}/supported-apis      获取适配器支持的 API
```
