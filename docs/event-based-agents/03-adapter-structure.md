# 适配器新目录结构

## 1. 设计目标

- **模块化**：每个适配器从单文件拆分到独立目录，各模块职责清晰
- **可维护**：随着事件和 API 的增加，代码量会显著增长，目录结构有助于管理复杂度
- **一致性**：所有适配器遵循相同的目录布局和文件命名约定
- **兼容现有发现机制**：保持 YAML manifest + ComponentDiscoveryEngine 的注册体系

## 2. 新目录布局

### 2.1 整体结构

```
pkg/platform/
├── __init__.py
├── botmgr.py                  # PlatformManager + RuntimeBot（重构）
├── event_bus.py               # EventBus（新增）
├── event_router.py            # EventRouter（新增）
├── logger.py                  # EventLogger（保留）
├── webhook_pusher.py          # WebhookPusher（重构为 WebhookHandler）
│
├── adapters/                  # 适配器（新目录）
│   ├── __init__.py
│   │
│   ├── telegram/
│   │   ├── __init__.py
│   │   ├── adapter.py         # TelegramAdapter 主类
│   │   ├── event_converter.py # 平台事件 → 统一事件
│   │   ├── message_converter.py # MessageChain 互转
│   │   ├── api_impl.py        # 通用 API 实现
│   │   ├── platform_api.py    # call_platform_api 的动作映射
│   │   ├── types.py           # 平台特有类型定义
│   │   └── manifest.yaml      # 适配器清单
│   │
│   ├── discord/
│   │   ├── __init__.py
│   │   ├── adapter.py
│   │   ├── event_converter.py
│   │   ├── message_converter.py
│   │   ├── api_impl.py
│   │   ├── platform_api.py
│   │   ├── types.py
│   │   ├── voice.py           # Discord 语音连接管理（特有）
│   │   └── manifest.yaml
│   │
│   ├── aiocqhttp/             # OneBot v11 (QQ)
│   │   └── ...
│   ├── qqofficial/
│   │   └── ...
│   ├── lark/                  # 飞书
│   │   └── ...
│   ├── dingtalk/
│   │   └── ...
│   ├── slack/
│   │   └── ...
│   ├── wechatpad/
│   │   └── ...
│   ├── officialaccount/       # 微信公众号
│   │   └── ...
│   ├── wecom/                 # 企业微信
│   │   └── ...
│   ├── wecombot/
│   │   └── ...
│   ├── wecomcs/
│   │   └── ...
│   ├── kook/
│   │   └── ...
│   ├── line/
│   │   └── ...
│   ├── satori/
│   │   └── ...
│   ├── websocket/             # 内置 WebSocket 适配器
│   │   ├── __init__.py
│   │   ├── adapter.py
│   │   ├── manager.py         # WebSocket 连接管理
│   │   └── manifest.yaml
│   │
│   └── legacy/                # 旧版适配器（保留一段时间后移除）
│       ├── gewechat/
│       ├── nakuru/
│       └── qqbotpy/
│
└── handlers/                  # 事件处理器实现（新增）
    ├── __init__.py
    ├── base.py                # AbstractEventHandler 基类
    ├── pipeline_handler.py    # PipelineHandler
    ├── agent_handler.py       # AgentHandler
    ├── webhook_handler.py     # WebhookHandler
    └── plugin_handler.py      # PluginHandler
```

### 2.2 适配器目录内各文件职责

以 Telegram 为例：

| 文件 | 职责 | 关键类/函数 |
|------|------|------------|
| `adapter.py` | 主入口，继承 `AbstractPlatformAdapter`，组装其他模块 | `TelegramAdapter` |
| `event_converter.py` | 将 Telegram 原生事件转换为统一事件类型 | `TelegramEventConverter` — 支持 Message/Edit/Delete/Reaction/MemberJoin 等所有事件 |
| `message_converter.py` | `MessageChain` 与 Telegram 消息格式互转 | `TelegramMessageConverter.yiri2target()` / `target2yiri()` |
| `api_impl.py` | 实现通用 API 方法（edit_message, delete_message, get_group_info 等） | 各 API 方法的 Telegram 实现 |
| `platform_api.py` | 实现 `call_platform_api` 的动作分发表 | `PLATFORM_API_MAP = {"pin_message": ..., "unpin_message": ...}` |
| `types.py` | 平台特有的类型定义 | Telegram 特有的枚举、配置结构等 |
| `manifest.yaml` | 适配器清单：名称、配置 schema、支持的事件和 API 列表 | — |

## 3. 新基类设计

### 3.1 AbstractPlatformAdapter

新基类继承自现有 `AbstractMessagePlatformAdapter` 并扩展，位于 `langbot-plugin-sdk` 中：

```python
# langbot_plugin/api/definition/abstract/platform/adapter.py

class AbstractPlatformAdapter(pydantic.BaseModel, metaclass=abc.ABCMeta):
    """平台适配器基类（EBA 版本）

    相比旧版 AbstractMessagePlatformAdapter：
    - 新增通用 API 方法（edit_message, delete_message, get_group_info 等）
    - 新增透传 API（call_platform_api）
    - 新增能力声明（get_supported_events, get_supported_apis）
    - 事件监听器支持所有事件类型，不仅限于消息事件
    """

    bot_account_id: str = ""
    config: dict
    logger: AbstractEventLogger = pydantic.Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    # ---- 能力声明 ----

    def get_supported_events(self) -> list[str]:
        """返回此适配器支持的事件类型列表

        默认实现从 manifest.yaml 读取。
        适配器也可以 override 此方法动态声明。
        """
        return ["message.received"]

    def get_supported_apis(self) -> list[str]:
        """返回此适配器支持的 API 列表

        默认实现从 manifest.yaml 读取。
        """
        return ["send_message", "reply_message"]

    # ---- 必需方法（抽象） ----

    @abc.abstractmethod
    async def send_message(self, target_type, target_id, message) -> MessageResult:
        ...

    @abc.abstractmethod
    async def reply_message(self, event, message, quote_origin=False) -> MessageResult:
        ...

    @abc.abstractmethod
    async def run_async(self):
        ...

    @abc.abstractmethod
    async def kill(self) -> bool:
        ...

    @abc.abstractmethod
    def register_listener(self, event_type, callback):
        ...

    @abc.abstractmethod
    def unregister_listener(self, event_type, callback):
        ...

    # ---- 可选方法（默认抛 NotSupportedError） ----
    # edit_message, delete_message, forward_message,
    # get_group_info, get_group_member_list, ...
    # call_platform_api, ...
    # （完整签名见 02-platform-api.md）

    # ---- 流式输出（保留） ----

    async def reply_message_chunk(self, event, bot_message, message,
                                   quote_origin=False, is_final=False):
        raise NotSupportedError("reply_message_chunk")

    async def is_stream_output_supported(self) -> bool:
        return False

    # ---- 消息卡片（保留） ----

    async def create_message_card(self, message_id, event) -> bool:
        return False

    async def is_muted(self, group_id) -> bool:
        return False
```

### 3.2 AbstractMessagePlatformAdapter 兼容

旧的 `AbstractMessagePlatformAdapter` 保留为 `AbstractPlatformAdapter` 的类型别名：

```python
# 向后兼容
AbstractMessagePlatformAdapter = AbstractPlatformAdapter
```

现有适配器代码中的 `AbstractMessagePlatformAdapter` 引用不需要立即修改。

### 3.3 EventConverter 新设计

现有 `AbstractEventConverter` 只有 `target2yiri` 和 `yiri2target` 两个静态方法，且只处理消息事件。

新设计支持多种事件类型：

```python
class AbstractEventConverter:
    """事件转换器基类（EBA 版本）

    适配器需要实现此转换器，将平台原生事件转换为统一事件。
    """

    @staticmethod
    def target2yiri(raw_event: typing.Any) -> typing.Optional[Event]:
        """将平台原生事件转换为统一事件

        Args:
            raw_event: 平台 SDK 回调传入的原始事件对象

        Returns:
            统一 Event 对象，如果无法转换或不需要处理则返回 None
        """
        raise NotImplementedError

    @staticmethod
    def yiri2target(event: Event) -> typing.Any:
        """将统一事件转换为平台原生事件（一般不需要）"""
        raise NotImplementedError
```

具体适配器的 EventConverter 实现会是一个分发式的结构：

```python
class TelegramEventConverter(AbstractEventConverter):
    """Telegram 事件转换器"""

    @staticmethod
    def target2yiri(update: telegram.Update) -> typing.Optional[Event]:
        # 消息事件
        if update.message:
            return TelegramEventConverter._convert_message(update)
        # 消息编辑
        if update.edited_message:
            return TelegramEventConverter._convert_edited_message(update)
        # 成员变动
        if update.chat_member:
            return TelegramEventConverter._convert_chat_member(update)
        # 回调查询（按钮点击等）
        if update.callback_query:
            return TelegramEventConverter._convert_callback_query(update)
        # 其他 → PlatformSpecificEvent
        return TelegramEventConverter._convert_platform_specific(update)

    @staticmethod
    def _convert_message(update) -> MessageReceivedEvent:
        ...

    @staticmethod
    def _convert_edited_message(update) -> MessageEditedEvent:
        ...

    @staticmethod
    def _convert_chat_member(update) -> typing.Union[
        MemberJoinedEvent, MemberLeftEvent, ...
    ]:
        ...

    @staticmethod
    def _convert_platform_specific(update) -> PlatformSpecificEvent:
        ...
```

## 4. Manifest 文件格式扩展

现有 manifest.yaml 只声明 `kind`, `metadata`, `spec.config`, `execution`。

新增 `spec.supported_events` 和 `spec.supported_apis`：

```yaml
apiVersion: v1
kind: MessagePlatformAdapter

metadata:
  name: telegram
  label:
    en_US: Telegram
    zh_Hans: Telegram
  icon: telegram.svg
  description:
    en_US: Telegram Bot adapter
    zh_Hans: Telegram Bot 适配器

spec:
  config:
    # 现有配置 schema（保持不变）
    - key: token
      label: { en_US: "Bot Token", zh_Hans: "Bot Token" }
      type: string
      required: true
      sensitive: true
    # ...

  supported_events:
    - message.received
    - message.edited
    - message.deleted
    - message.reaction
    - group.member_joined
    - group.member_left
    - group.member_banned
    - group.info_updated
    - bot.invited_to_group
    - bot.removed_from_group

  supported_apis:
    required:
      - send_message
      - reply_message
    optional:
      - edit_message
      - delete_message
      - get_group_info
      - get_group_member_list
      - get_group_member_info
      - get_user_info
      - upload_file
      - get_file_url
      - call_platform_api

  platform_specific_apis:
    - action: pin_message
      description: { en_US: "Pin a message", zh_Hans: "置顶消息" }
    - action: unpin_message
      description: { en_US: "Unpin a message", zh_Hans: "取消置顶" }
    - action: get_chat_administrators
      description: { en_US: "Get chat admins", zh_Hans: "获取群管理员列表" }

execution:
  python:
    path: pkg/platform/adapters/telegram/adapter.py
    attr: TelegramAdapter
```

## 5. 适配器注册与发现

### 5.1 Blueprint 更新

`templates/components.yaml` 中更新扫描路径：

```yaml
kind: Blueprint
spec:
  components:
    MessagePlatformAdapter:
      fromDirs:
        - path: pkg/platform/adapters/     # 新路径
```

`ComponentDiscoveryEngine` 的递归扫描逻辑不变——它会扫描所有子目录中的 `.yaml` 文件。因此每个适配器目录下的 `manifest.yaml` 会被自动发现。

### 5.2 PlatformManager 适配

`PlatformManager.initialize()` 的核心逻辑基本不变：

```python
async def initialize(self):
    # 1. 发现适配器组件（自动扫描新目录结构）
    self.adapter_components = self.ap.discover.get_components_by_kind('MessagePlatformAdapter')

    # 2. 动态导入适配器类
    for component in self.adapter_components:
        self.adapter_dict[component.metadata.name] = component.get_python_component_class()

    # 3. 从数据库加载 Bot 并实例化适配器（不变）
    await self.load_bots_from_db()
```

变更点：
- `execution.python.path` 从 `pkg/platform/sources/telegram.py` 变为 `pkg/platform/adapters/telegram/adapter.py`
- `get_python_component_class()` 正常工作，因为它按路径动态导入

## 6. RuntimeBot 重构

### 6.1 现有问题

当前 `RuntimeBot.initialize()` 硬编码注册了两个回调：

```python
# 现有代码
self.adapter.register_listener(platform_events.FriendMessage, on_friend_message)
self.adapter.register_listener(platform_events.GroupMessage, on_group_message)
```

### 6.2 新设计

`RuntimeBot` 改为注册一个通用的事件回调：

```python
class RuntimeBot:
    async def initialize(self):
        # 注册通用事件回调，接收所有事件类型
        self.adapter.register_listener(Event, self._on_event)

    async def _on_event(
        self,
        event: Event,
        adapter: AbstractPlatformAdapter,
    ):
        """统一事件入口"""

        # 1. 设置事件的 bot_uuid 和 adapter_name
        event.bot_uuid = self.bot_entity.uuid
        event.adapter_name = self.bot_entity.adapter

        # 2. 日志记录
        await self._log_event(event)

        # 3. 提交给 EventBus
        await self.ap.event_bus.emit(event, adapter)
```

适配器侧的 `register_listener` 实现也需调整：
- 当 `event_type` 为 `Event`（基类）时，注册为"接收所有事件"的通配回调
- 适配器在收到平台原生事件时，通过 `EventConverter.target2yiri()` 转换后，调用所有匹配的回调

## 7. 从现有单文件适配器迁移

### 7.1 迁移模式

以 Telegram 为例，从 `sources/telegram.py`（445 行）拆分：

| 原代码位置 | → 新文件 |
|-----------|----------|
| `TelegramMessageConverter` 类 | `telegram/message_converter.py` |
| `TelegramEventConverter` 类 | `telegram/event_converter.py`（扩展，支持更多事件） |
| `TelegramAdapter.__init__` / `run_async` / `kill` / `register_listener` | `telegram/adapter.py` |
| `TelegramAdapter.send_message` / `reply_message` / `reply_message_chunk` | `telegram/adapter.py`（消息方法保留在主类）+ `telegram/api_impl.py`（新增 API） |
| 新增代码 | `telegram/api_impl.py`（edit_message, delete_message, get_group_info 等） |
| 新增代码 | `telegram/platform_api.py`（pin_message, unpin_message 等的映射） |
| `telegram.yaml` | `telegram/manifest.yaml`（扩展 supported_events/apis） |

### 7.2 迁移顺序建议

1. **Telegram** — 功能最完整的适配器之一，适合作为模板
2. **Discord** — 第二个迁移，验证模式的通用性
3. **AioCQHTTP (OneBot)** — 国内最常用，确保兼容
4. **其他适配器** — 按使用频率排序

### 7.3 渐进式迁移

不需要一次性迁移所有适配器。可以采用渐进策略：

1. 先在 `adapters/` 下建立新适配器
2. `Blueprint` 同时扫描 `sources/` 和 `adapters/` 两个目录
3. 旧适配器在 `sources/` 中继续工作
4. 逐个迁移到新结构
5. 全部迁移完成后移除 `sources/` 目录

```yaml
# 过渡期的 Blueprint
kind: Blueprint
spec:
  components:
    MessagePlatformAdapter:
      fromDirs:
        - path: pkg/platform/sources/      # 旧路径（尚未迁移的适配器）
        - path: pkg/platform/adapters/      # 新路径（已迁移的适配器）
```
