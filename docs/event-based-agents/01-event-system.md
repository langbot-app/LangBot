# 统一事件体系

## 1. 设计原则

- **命名空间分类**：事件类型采用 `{namespace}.{action}` 格式，如 `message.received`
- **通用优先**：大部分平台都支持的事件抽象为通用事件，定义统一的字段格式
- **平台特有事件标准化**：各适配器的独有事件通过 `PlatformSpecificEvent` 承载，保留原始数据
- **向后兼容**：现有 `FriendMessage` / `GroupMessage` 通过兼容层映射到新的 `message.received` 事件

## 2. 事件基类层次

```
Event (事件基类)
├── MessageEvent (消息相关事件)
│   ├── MessageReceivedEvent       # message.received
│   ├── MessageEditedEvent         # message.edited
│   ├── MessageDeletedEvent        # message.deleted
│   └── MessageReactionEvent       # message.reaction
├── GroupEvent (群组相关事件)
│   ├── MemberJoinedEvent          # group.member_joined
│   ├── MemberLeftEvent            # group.member_left
│   ├── MemberBannedEvent          # group.member_banned
│   ├── MemberUnbannedEvent        # group.member_unbanned
│   └── GroupInfoUpdatedEvent      # group.info_updated
├── FriendEvent (好友相关事件)
│   ├── FriendRequestReceivedEvent # friend.request_received
│   ├── FriendAddedEvent           # friend.added
│   └── FriendRemovedEvent         # friend.removed
├── BotEvent (Bot 状态事件)
│   ├── BotInvitedToGroupEvent     # bot.invited_to_group
│   ├── BotRemovedFromGroupEvent   # bot.removed_from_group
│   ├── BotMutedEvent              # bot.muted
│   └── BotUnmutedEvent            # bot.unmuted
└── PlatformSpecificEvent          # platform.{adapter}.{action}
```

## 3. 通用事件定义

### 3.1 事件基类

```python
class Event(pydantic.BaseModel):
    """事件基类"""

    type: str
    """事件类型标识，如 'message.received'"""

    timestamp: float
    """事件发生的时间戳"""

    bot_uuid: str
    """接收到此事件的 Bot UUID"""

    adapter_name: str
    """产生此事件的适配器名称"""

    source_platform_object: typing.Optional[typing.Any] = None
    """原始平台事件对象，供适配器内部使用"""
```

### 3.2 消息事件

#### MessageReceivedEvent (`message.received`)

收到新消息。这是最核心的事件，替代现有的 `FriendMessage` / `GroupMessage`。

```python
class MessageReceivedEvent(Event):
    """收到新消息"""

    type: str = "message.received"

    message_id: typing.Union[int, str]
    """消息 ID"""

    message_chain: MessageChain
    """消息内容"""

    sender: User
    """发送者"""

    chat_type: ChatType  # "private" | "group"
    """会话类型"""

    chat_id: typing.Union[int, str]
    """会话 ID（私聊为对方用户 ID，群聊为群 ID）"""

    group: typing.Optional[Group] = None
    """群信息（仅群聊时存在）"""
```

与现有类型的映射关系：
- `chat_type == "private"` → 等价于现有 `FriendMessage`
- `chat_type == "group"` → 等价于现有 `GroupMessage`

`ChatType` 枚举：

```python
class ChatType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
```

#### MessageEditedEvent (`message.edited`)

消息被编辑。

```python
class MessageEditedEvent(Event):
    """消息被编辑"""

    type: str = "message.edited"

    message_id: typing.Union[int, str]
    """被编辑的消息 ID"""

    new_content: MessageChain
    """编辑后的新内容"""

    editor: User
    """编辑者"""

    chat_type: ChatType
    chat_id: typing.Union[int, str]
    group: typing.Optional[Group] = None
```

#### MessageDeletedEvent (`message.deleted`)

消息被删除/撤回。

```python
class MessageDeletedEvent(Event):
    """消息被删除/撤回"""

    type: str = "message.deleted"

    message_id: typing.Union[int, str]
    """被删除的消息 ID"""

    operator: typing.Optional[User] = None
    """操作者（可能是发送者自己撤回，也可能是管理员删除）"""

    chat_type: ChatType
    chat_id: typing.Union[int, str]
    group: typing.Optional[Group] = None
```

#### MessageReactionEvent (`message.reaction`)

消息收到表情回应。

```python
class MessageReactionEvent(Event):
    """消息收到表情回应"""

    type: str = "message.reaction"

    message_id: typing.Union[int, str]
    """被回应的消息 ID"""

    user: User
    """回应者"""

    reaction: str
    """回应的表情标识（emoji 或平台特定表情 ID）"""

    is_add: bool
    """True 为添加回应，False 为移除回应"""

    chat_type: ChatType
    chat_id: typing.Union[int, str]
    group: typing.Optional[Group] = None
```

### 3.3 群组事件

#### MemberJoinedEvent (`group.member_joined`)

新成员加入群组。

```python
class MemberJoinedEvent(Event):
    """新成员加入群组"""

    type: str = "group.member_joined"

    group: Group
    """群组"""

    member: User
    """加入的成员"""

    inviter: typing.Optional[User] = None
    """邀请者（如有）"""

    join_type: typing.Optional[str] = None
    """加入方式：'invite' / 'request' / 'direct' / None"""
```

#### MemberLeftEvent (`group.member_left`)

成员离开群组。

```python
class MemberLeftEvent(Event):
    """成员离开群组"""

    type: str = "group.member_left"

    group: Group
    member: User

    is_kicked: bool = False
    """是否被踢出"""

    operator: typing.Optional[User] = None
    """操作者（踢出时为管理员）"""
```

#### MemberBannedEvent (`group.member_banned`)

成员被禁言。

```python
class MemberBannedEvent(Event):
    """成员被禁言"""

    type: str = "group.member_banned"

    group: Group
    member: User
    operator: typing.Optional[User] = None
    duration: typing.Optional[int] = None
    """禁言时长（秒），None 表示永久"""
```

#### MemberUnbannedEvent (`group.member_unbanned`)

成员被解除禁言。

```python
class MemberUnbannedEvent(Event):
    """成员被解除禁言"""

    type: str = "group.member_unbanned"

    group: Group
    member: User
    operator: typing.Optional[User] = None
```

#### GroupInfoUpdatedEvent (`group.info_updated`)

群组信息被修改。

```python
class GroupInfoUpdatedEvent(Event):
    """群组信息被修改"""

    type: str = "group.info_updated"

    group: Group
    """更新后的群组信息"""

    operator: typing.Optional[User] = None
    """操作者"""

    changed_fields: list[str] = []
    """发生变更的字段名列表，如 ['name', 'description']"""
```

### 3.4 好友事件

#### FriendRequestReceivedEvent (`friend.request_received`)

收到好友请求。

```python
class FriendRequestReceivedEvent(Event):
    """收到好友请求"""

    type: str = "friend.request_received"

    request_id: typing.Union[int, str]
    """请求 ID，用于后续 approve/reject 操作"""

    user: User
    """请求者"""

    message: typing.Optional[str] = None
    """验证消息"""
```

#### FriendAddedEvent (`friend.added`)

成功添加好友。

```python
class FriendAddedEvent(Event):
    """成功添加好友"""

    type: str = "friend.added"

    user: User
    """新好友"""
```

#### FriendRemovedEvent (`friend.removed`)

好友被移除。

```python
class FriendRemovedEvent(Event):
    """好友被移除"""

    type: str = "friend.removed"

    user: User
    """被移除的好友"""
```

### 3.5 Bot 状态事件

#### BotInvitedToGroupEvent (`bot.invited_to_group`)

Bot 被邀请加入群组。

```python
class BotInvitedToGroupEvent(Event):
    """Bot 被邀请加入群组"""

    type: str = "bot.invited_to_group"

    group: Group
    inviter: typing.Optional[User] = None

    request_id: typing.Optional[typing.Union[int, str]] = None
    """邀请请求 ID，某些平台需要 Bot 确认才加入"""
```

#### BotRemovedFromGroupEvent (`bot.removed_from_group`)

Bot 被移出群组。

```python
class BotRemovedFromGroupEvent(Event):
    """Bot 被移出群组"""

    type: str = "bot.removed_from_group"

    group: Group
    operator: typing.Optional[User] = None
```

#### BotMutedEvent / BotUnmutedEvent (`bot.muted` / `bot.unmuted`)

Bot 被禁言/解除禁言。

```python
class BotMutedEvent(Event):
    """Bot 被禁言"""

    type: str = "bot.muted"

    group: Group
    operator: typing.Optional[User] = None
    duration: typing.Optional[int] = None


class BotUnmutedEvent(Event):
    """Bot 被解除禁言"""

    type: str = "bot.unmuted"

    group: Group
    operator: typing.Optional[User] = None
```

### 3.6 平台特有事件

对于无法抽象为通用事件的平台特有事件，使用统一的 `PlatformSpecificEvent` 承载：

```python
class PlatformSpecificEvent(Event):
    """平台特有事件

    适配器无法映射到通用事件类型时，使用此类型承载。
    插件可以通过 adapter_name + action 来识别和处理。
    """

    type: str = "platform.specific"

    action: str
    """平台特有的事件动作标识，如 'channel_created', 'pin_message'"""

    data: dict = {}
    """事件数据，结构由具体适配器定义"""
```

事件类型字符串格式为 `platform.{adapter_name}.{action}`，例如：
- `platform.telegram.chat_member_updated` — Telegram 的群成员信息更新
- `platform.discord.channel_created` — Discord 的频道创建
- `platform.discord.voice_state_update` — Discord 的语音状态变更
- `platform.slack.app_home_opened` — Slack 的 App Home 打开

## 4. 各平台事件支持矩阵

下表标注各通用事件在主要平台上的支持情况：

| 事件 | Telegram | Discord | OneBot(QQ) | 飞书 | 钉钉 | Slack | 微信 | LINE | KOOK |
|------|----------|---------|-----------|------|------|-------|------|------|------|
| `message.received` | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| `message.edited` | Y | Y | N | Y | N | Y | N | N | Y |
| `message.deleted` | Y | Y | Y | Y | N | Y | Y | N | Y |
| `message.reaction` | Y | Y | Y | Y | Y | Y | N | N | Y |
| `group.member_joined` | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| `group.member_left` | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| `group.member_banned` | Y | Y | Y | N | N | N | N | N | N |
| `group.info_updated` | Y | Y | Y | Y | Y | Y | N | N | Y |
| `friend.request_received` | N | Y | Y | N | N | N | Y | Y | Y |
| `friend.added` | N | Y | Y | N | N | N | Y | Y | N |
| `bot.invited_to_group` | Y | Y | Y | Y | Y | Y | Y | N | Y |
| `bot.removed_from_group` | Y | Y | Y | Y | N | N | Y | N | Y |
| `bot.muted` | N | N | Y | N | N | N | N | N | N |

> 注：此表为初步评估，具体以各平台 SDK/API 文档为准，实施时逐个确认。

## 5. 事件生命周期

```
1. 平台 SDK 回调触发
      │
2. 适配器 EventConverter.target2yiri(raw_event)
      │  将平台原生事件转换为统一 Event 对象
      │  无法映射的事件 → PlatformSpecificEvent
      │
3. 适配器回调注册的 listener(event, adapter)
      │
4. RuntimeBot 接收事件
      │
5. EventBus 分发
      │
6. EventRouter 查询 Bot 的 event_handlers 配置
      │  匹配事件类型 → 找到对应的 Handler
      │  支持通配符：'message.*' 匹配所有消息事件
      │  未匹配到 → 走默认 Handler（plugin，保持向后兼容）
      │
7. Handler 处理事件
      │  PipelineHandler → 进入 Pipeline 流水线
      │  AgentHandler    → 调用 RequestRunner
      │  WebhookHandler  → POST 到外部 URL
      │  PluginHandler   → 分发给插件 EventListener
      │
8. Handler 执行完毕，可能通过 API 执行响应动作
      （发消息、编辑消息、踢人、同意好友请求等）
```

## 6. 与现有事件类型的兼容映射

为保证现有插件不受影响，建立以下映射关系：

| 新事件 | 条件 | 旧事件 |
|--------|------|--------|
| `MessageReceivedEvent` (chat_type=private) | — | `FriendMessage` |
| `MessageReceivedEvent` (chat_type=group) | — | `GroupMessage` |

在插件 SDK 层面：

| 新事件 | 旧插件事件 |
|--------|-----------|
| `MessageReceivedEvent` (chat_type=private, 非命令) | `PersonNormalMessageReceived` |
| `MessageReceivedEvent` (chat_type=group, 非命令) | `GroupNormalMessageReceived` |
| `MessageReceivedEvent` (chat_type=private, 命令) | `PersonCommandSent` |
| `MessageReceivedEvent` (chat_type=group, 命令) | `GroupCommandSent` |
| `MessageReceivedEvent` (处理完毕后) | `NormalMessageResponded` |

兼容层在事件分发给插件 EventListener 时自动生成旧格式事件，确保监听旧事件类型的插件仍能正常工作。

## 7. 事件类型注册表

适配器在 manifest.yaml 中声明自己支持的事件类型：

```yaml
kind: MessagePlatformAdapter
metadata:
  name: telegram
spec:
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
  platform_specific_events:
    - chat_member_updated
    - chat_join_request
```

这份声明用于：
1. WebUI 在配置事件处理器时，只显示当前 Bot 的适配器支持的事件类型
2. EventRouter 在路由时校验事件类型有效性
3. 文档自动生成
