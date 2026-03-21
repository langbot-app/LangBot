# 插件 SDK 改造

## 1. 概述

插件 SDK 需要配合 EBA 架构进行以下改造：

1. **新事件类型**：将所有通用事件暴露给插件
2. **新 API**：将新增的平台 API 通过 `LangBotAPIProxy` 暴露给插件
3. **兼容层**：保证现有插件零修改运行
4. **通信协议扩展**：新增 action 枚举支持新 API

## 2. 新事件类型暴露

### 2.1 插件事件模型扩展

当前插件 SDK 的事件模型（`api/entities/events.py`）只有消息相关事件。需要新增所有通用事件的插件级包装：

```python
# api/entities/events.py — 新增事件

# ---- 消息事件（扩展） ----

class MessageEditedReceived(BaseEventModel):
    """消息被编辑事件"""
    launcher_type: str
    launcher_id: typing.Union[int, str]
    message_id: typing.Union[int, str]
    editor_id: typing.Union[int, str]
    new_content: MessageChain
    chat_type: str  # "private" | "group"

class MessageDeletedReceived(BaseEventModel):
    """消息被删除/撤回事件"""
    launcher_type: str
    launcher_id: typing.Union[int, str]
    message_id: typing.Union[int, str]
    operator_id: typing.Optional[typing.Union[int, str]] = None
    chat_type: str

class MessageReactionReceived(BaseEventModel):
    """消息表情回应事件"""
    launcher_type: str
    launcher_id: typing.Union[int, str]
    message_id: typing.Union[int, str]
    user_id: typing.Union[int, str]
    reaction: str
    is_add: bool

# ---- 群组事件 ----

class GroupMemberJoined(BaseEventModel):
    """新成员加入群组"""
    group_id: typing.Union[int, str]
    group_name: str
    member_id: typing.Union[int, str]
    member_name: str
    inviter_id: typing.Optional[typing.Union[int, str]] = None
    join_type: typing.Optional[str] = None

class GroupMemberLeft(BaseEventModel):
    """成员离开群组"""
    group_id: typing.Union[int, str]
    group_name: str
    member_id: typing.Union[int, str]
    member_name: str
    is_kicked: bool = False
    operator_id: typing.Optional[typing.Union[int, str]] = None

class GroupMemberBanned(BaseEventModel):
    """成员被禁言"""
    group_id: typing.Union[int, str]
    member_id: typing.Union[int, str]
    operator_id: typing.Optional[typing.Union[int, str]] = None
    duration: typing.Optional[int] = None

class GroupMemberUnbanned(BaseEventModel):
    """成员被解除禁言"""
    group_id: typing.Union[int, str]
    member_id: typing.Union[int, str]
    operator_id: typing.Optional[typing.Union[int, str]] = None

class GroupInfoUpdated(BaseEventModel):
    """群组信息被修改"""
    group_id: typing.Union[int, str]
    group_name: str
    operator_id: typing.Optional[typing.Union[int, str]] = None
    changed_fields: list[str] = []

# ---- 好友事件 ----

class FriendRequestReceived(BaseEventModel):
    """收到好友请求"""
    request_id: typing.Union[int, str]
    user_id: typing.Union[int, str]
    user_name: str
    message: typing.Optional[str] = None

class FriendAdded(BaseEventModel):
    """成功添加好友"""
    user_id: typing.Union[int, str]
    user_name: str

class FriendRemoved(BaseEventModel):
    """好友被移除"""
    user_id: typing.Union[int, str]
    user_name: str

# ---- Bot 状态事件 ----

class BotInvitedToGroup(BaseEventModel):
    """Bot 被邀请加入群组"""
    group_id: typing.Union[int, str]
    group_name: str
    inviter_id: typing.Optional[typing.Union[int, str]] = None
    request_id: typing.Optional[typing.Union[int, str]] = None

class BotRemovedFromGroup(BaseEventModel):
    """Bot 被移出群组"""
    group_id: typing.Union[int, str]
    group_name: str
    operator_id: typing.Optional[typing.Union[int, str]] = None

class BotMuted(BaseEventModel):
    """Bot 被禁言"""
    group_id: typing.Union[int, str]
    operator_id: typing.Optional[typing.Union[int, str]] = None
    duration: typing.Optional[int] = None

class BotUnmuted(BaseEventModel):
    """Bot 被解除禁言"""
    group_id: typing.Union[int, str]
    operator_id: typing.Optional[typing.Union[int, str]] = None

# ---- 平台特有事件 ----

class PlatformSpecificEventReceived(BaseEventModel):
    """平台特有事件"""
    adapter_name: str
    action: str
    data: dict = {}
```

### 2.2 EventListener 注册方式

插件的 EventListener 继续使用 `@self.handler(EventType)` 装饰器注册，只是可以注册的事件类型大幅增加：

```python
class MyEventListener(EventListener):
    def __init__(self, host):
        super().__init__(host)

        # 现有方式（继续工作）
        @self.handler(PersonNormalMessageReceived)
        async def on_person_message(ctx: EventContext):
            ...

        # 新事件类型
        @self.handler(GroupMemberJoined)
        async def on_member_joined(ctx: EventContext):
            group_name = ctx.event.group_name
            member_name = ctx.event.member_name
            await ctx.reply(MessageChain([
                Plain(f"欢迎 {member_name} 加入 {group_name}！")
            ]))

        @self.handler(FriendRequestReceived)
        async def on_friend_request(ctx: EventContext):
            # 自动通过好友请求
            await ctx.approve_friend_request(
                ctx.event.request_id, approve=True
            )

        @self.handler(PlatformSpecificEventReceived)
        async def on_platform_event(ctx: EventContext):
            if ctx.event.adapter_name == "telegram" and ctx.event.action == "chat_join_request":
                ...
```

## 3. 新 API 暴露

### 3.1 LangBotAPIProxy 扩展

在 `LangBotAPIProxy` 中新增以下方法，插件通过 `self.xxx()` 调用（在 BasePlugin 中继承）：

```python
class LangBotAPIProxy:
    # ---- 现有方法（保留） ----
    # get_langbot_version, get_bots, get_bot_info,
    # send_message, invoke_llm, get/set/delete_plugin_storage, ...

    # ---- 新增消息 API ----

    async def edit_message(
        self,
        bot_uuid: str,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        new_content: MessageChain,
    ) -> None:
        """编辑已发送的消息"""
        ...

    async def delete_message(
        self,
        bot_uuid: str,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> None:
        """删除/撤回消息"""
        ...

    async def forward_message(
        self,
        bot_uuid: str,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> dict:
        """转发消息"""
        ...

    async def get_message(
        self,
        bot_uuid: str,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> dict:
        """获取指定消息"""
        ...

    # ---- 新增群组 API ----

    async def get_group_info(
        self,
        bot_uuid: str,
        group_id: typing.Union[int, str],
    ) -> dict:
        """获取群组信息"""
        ...

    async def get_group_list(
        self,
        bot_uuid: str,
    ) -> list[dict]:
        """获取 Bot 加入的群组列表"""
        ...

    async def get_group_member_list(
        self,
        bot_uuid: str,
        group_id: typing.Union[int, str],
    ) -> list[dict]:
        """获取群成员列表"""
        ...

    async def get_group_member_info(
        self,
        bot_uuid: str,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> dict:
        """获取指定群成员信息"""
        ...

    async def mute_member(
        self,
        bot_uuid: str,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
        duration: int = 0,
    ) -> None:
        """禁言群成员"""
        ...

    async def unmute_member(
        self,
        bot_uuid: str,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        """解除禁言"""
        ...

    async def kick_member(
        self,
        bot_uuid: str,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        """踢出群成员"""
        ...

    # ---- 新增用户 API ----

    async def get_user_info(
        self,
        bot_uuid: str,
        user_id: typing.Union[int, str],
    ) -> dict:
        """获取用户信息"""
        ...

    async def get_friend_list(
        self,
        bot_uuid: str,
    ) -> list[dict]:
        """获取好友列表"""
        ...

    async def approve_friend_request(
        self,
        bot_uuid: str,
        request_id: typing.Union[int, str],
        approve: bool = True,
        remark: typing.Optional[str] = None,
    ) -> None:
        """处理好友请求"""
        ...

    async def approve_group_invite(
        self,
        bot_uuid: str,
        request_id: typing.Union[int, str],
        approve: bool = True,
    ) -> None:
        """处理入群邀请"""
        ...

    # ---- 新增透传 API ----

    async def call_platform_api(
        self,
        bot_uuid: str,
        action: str,
        params: dict = {},
    ) -> dict:
        """调用适配器特有 API

        Examples:
            # Telegram: pin 消息
            result = await self.call_platform_api(
                bot_uuid, "pin_message",
                {"chat_id": 123456, "message_id": 789}
            )

            # Discord: 创建频道
            result = await self.call_platform_api(
                bot_uuid, "create_channel",
                {"guild_id": "...", "name": "new-channel"}
            )
        """
        ...

    # ---- 新增能力查询 API ----

    async def get_supported_events(
        self,
        bot_uuid: str,
    ) -> list[str]:
        """获取指定 Bot 的适配器支持的事件类型"""
        ...

    async def get_supported_apis(
        self,
        bot_uuid: str,
    ) -> list[str]:
        """获取指定 Bot 的适配器支持的 API"""
        ...
```

### 3.2 QueryBasedAPIProxy 扩展

在事件处理上下文中（EventContext），通过 `QueryBasedAPIProxy` 新增便捷方法：

```python
class QueryBasedAPIProxy:
    # ---- 现有方法（保留） ----
    # reply, get_bot_uuid, set_query_var, get_query_var,
    # create_new_conversation, ...

    # ---- 新增便捷方法 ----

    async def edit_message(
        self,
        message_id: typing.Union[int, str],
        new_content: MessageChain,
    ) -> None:
        """在当前会话中编辑消息（自动使用当前 bot_uuid 和 chat 信息）"""
        ...

    async def delete_message(
        self,
        message_id: typing.Union[int, str],
    ) -> None:
        """在当前会话中删除消息"""
        ...

    async def approve_friend_request(
        self,
        request_id: typing.Union[int, str],
        approve: bool = True,
        remark: typing.Optional[str] = None,
    ) -> None:
        """处理好友请求（上下文中自动获取 bot_uuid）"""
        ...

    async def approve_group_invite(
        self,
        request_id: typing.Union[int, str],
        approve: bool = True,
    ) -> None:
        """处理入群邀请"""
        ...

    async def get_group_info(self) -> dict:
        """获取当前群组信息（仅群聊事件中可用）"""
        ...

    async def get_group_member_list(self) -> list[dict]:
        """获取当前群组成员列表（仅群聊事件中可用）"""
        ...

    async def call_platform_api(
        self,
        action: str,
        params: dict = {},
    ) -> dict:
        """调用平台特有 API（自动使用当前 bot_uuid）"""
        ...
```

## 4. 兼容层设计

### 4.1 事件兼容层

当 PluginHandler 将新的 `MessageReceivedEvent` 分发给插件时，需要同时生成旧格式事件：

```python
class PluginEventCompatLayer:
    """插件事件兼容层

    将新的统一事件转换为旧的插件事件格式，
    确保监听旧事件类型的插件仍能正常工作。
    """

    @staticmethod
    def convert_to_legacy_events(
        event: Event,
    ) -> list[BaseEventModel]:
        """将统一事件转换为旧插件事件列表

        一个统一事件可能生成多个旧插件事件。
        例如 MessageReceivedEvent 会同时生成：
        - PersonMessageReceived / GroupMessageReceived（总是生成）
        - PersonNormalMessageReceived / GroupNormalMessageReceived（非命令时）
        - PersonCommandSent / GroupCommandSent（命令时）
        """
        legacy_events = []

        if isinstance(event, MessageReceivedEvent):
            if event.chat_type == ChatType.PRIVATE:
                legacy_events.append(
                    PersonMessageReceived(
                        launcher_type="person",
                        launcher_id=event.chat_id,
                        sender_id=event.sender.id,
                        message_event=event.to_legacy_friend_message(),
                        message_chain=event.message_chain,
                    )
                )
                # 命令检测后还会生成 PersonNormalMessageReceived
                # 或 PersonCommandSent，在 Pipeline 阶段处理
            elif event.chat_type == ChatType.GROUP:
                legacy_events.append(
                    GroupMessageReceived(
                        launcher_type="group",
                        launcher_id=event.chat_id,
                        sender_id=event.sender.id,
                        message_event=event.to_legacy_group_message(),
                        message_chain=event.message_chain,
                    )
                )

        # 新事件类型没有旧的对应物，不生成兼容事件
        # 只有监听了新事件类型的插件才会收到

        return legacy_events
```

### 4.2 分发流程

```
统一事件 (MessageReceivedEvent)
    │
    ├─→ 转换为旧格式 (PersonMessageReceived / GroupMessageReceived)
    │   └─→ 分发给监听旧事件类型的插件 EventListener
    │
    └─→ 直接分发为新格式 (MessageReceivedEvent → 对应的插件事件)
        └─→ 分发给监听新事件类型的插件 EventListener
```

插件 Runtime 在分发事件时检查每个 EventListener 注册的事件类型：
- 如果注册的是旧类型（`PersonMessageReceived` 等），发送兼容层生成的旧格式事件
- 如果注册的是新类型（`GroupMemberJoined` 等），发送新格式事件
- 两者可以共存，同一个插件可以同时监听新旧类型

### 4.3 API 兼容层

现有插件使用的 API 不受影响：

| 现有 API | 新架构行为 |
|---------|----------|
| `self.send_message(bot_uuid, target_type, target_id, message_chain)` | 不变，直接调用适配器的 `send_message` |
| `ctx.reply(message_chain, quote_origin)` | 不变，在 MessageReceivedEvent 上下文中调用适配器的 `reply_message` |
| `self.get_bots()` | 不变 |
| `self.get_bot_info(bot_uuid)` | 不变 |

新 API 只是额外新增的方法，不影响现有方法。

## 5. 通信协议扩展

### 5.1 新增 Action 枚举

在 `entities/io/actions/enums.py` 中新增 action：

```python
class PluginToRuntimeAction(str, Enum):
    # ---- 现有 actions（保留） ----
    REGISTER_PLUGIN = "register_plugin"
    REPLY = "reply"
    SEND_MESSAGE = "send_message"
    # ...

    # ---- 新增消息 API ----
    EDIT_MESSAGE = "edit_message"
    DELETE_MESSAGE = "delete_message"
    FORWARD_MESSAGE = "forward_message"
    GET_MESSAGE = "get_message"

    # ---- 新增群组 API ----
    GET_GROUP_INFO = "get_group_info"
    GET_GROUP_LIST = "get_group_list"
    GET_GROUP_MEMBER_LIST = "get_group_member_list"
    GET_GROUP_MEMBER_INFO = "get_group_member_info"
    MUTE_MEMBER = "mute_member"
    UNMUTE_MEMBER = "unmute_member"
    KICK_MEMBER = "kick_member"

    # ---- 新增用户 API ----
    GET_USER_INFO = "get_user_info"
    GET_FRIEND_LIST = "get_friend_list"
    APPROVE_FRIEND_REQUEST = "approve_friend_request"
    APPROVE_GROUP_INVITE = "approve_group_invite"

    # ---- 新增透传 API ----
    CALL_PLATFORM_API = "call_platform_api"

    # ---- 新增能力查询 ----
    GET_SUPPORTED_EVENTS = "get_supported_events"
    GET_SUPPORTED_APIS = "get_supported_apis"


class RuntimeToPluginAction(str, Enum):
    # ---- 现有 actions（保留） ----
    EMIT_EVENT = "emit_event"
    # ...
    # EMIT_EVENT 的 data 结构扩展以支持新事件类型
```

### 5.2 新增 Action 的请求/响应格式

以 `EDIT_MESSAGE` 为例：

```json
// 请求 (Plugin → Runtime)
{
    "action": "edit_message",
    "seq_id": 12345,
    "data": {
        "bot_uuid": "...",
        "chat_type": "group",
        "chat_id": "123456",
        "message_id": "789",
        "new_content": [
            { "type": "Plain", "text": "edited message" }
        ]
    }
}

// 响应 (Runtime → Plugin)
{
    "seq_id": 12345,
    "code": 0,
    "message": "ok",
    "data": {}
}
```

以 `GET_GROUP_MEMBER_LIST` 为例：

```json
// 请求
{
    "action": "get_group_member_list",
    "seq_id": 12346,
    "data": {
        "bot_uuid": "...",
        "group_id": "123456"
    }
}

// 响应
{
    "seq_id": 12346,
    "code": 0,
    "message": "ok",
    "data": {
        "members": [
            {
                "user": { "id": "111", "nickname": "Alice" },
                "group_id": "123456",
                "role": "admin",
                "display_name": "管理员Alice"
            },
            ...
        ]
    }
}
```

以 `CALL_PLATFORM_API` 为例：

```json
// 请求
{
    "action": "call_platform_api",
    "seq_id": 12347,
    "data": {
        "bot_uuid": "...",
        "action": "pin_message",
        "params": {
            "chat_id": "123456",
            "message_id": "789"
        }
    }
}

// 响应
{
    "seq_id": 12347,
    "code": 0,
    "message": "ok",
    "data": {
        "result": { ... }
    }
}
```

### 5.3 LangBot 侧 Handler 实现

在 `ControlConnectionHandler`（LangBot → Runtime 侧）和 `PluginConnectionHandler`（Runtime → Plugin 侧）中新增对应的 action 处理逻辑：

```python
# PluginConnectionHandler 中新增
async def _handle_edit_message(self, data):
    bot_uuid = data["bot_uuid"]
    bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
    await bot.adapter.edit_message(
        chat_type=data["chat_type"],
        chat_id=data["chat_id"],
        message_id=data["message_id"],
        new_content=MessageChain.model_validate(data["new_content"]),
    )
    return {}

async def _handle_call_platform_api(self, data):
    bot_uuid = data["bot_uuid"]
    bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
    result = await bot.adapter.call_platform_api(
        action=data["action"],
        params=data.get("params", {}),
    )
    return {"result": result}
```

## 6. 插件开发者迁移指南

### 6.1 无需迁移（零修改运行）

以下场景的现有插件**不需要任何修改**：

- 使用 `PersonNormalMessageReceived` / `GroupNormalMessageReceived` 监听消息
- 使用 `PersonCommandSent` / `GroupCommandSent` 处理命令
- 使用 `ctx.reply()` 回复消息
- 使用 `self.send_message()` 主动发消息
- 使用 LLM / 存储 / RAG 等现有 API

### 6.2 推荐迁移（获得新能力）

如果插件希望利用新功能，可以：

1. **监听新事件类型**：在 EventListener 中注册新事件类型的 handler
2. **使用新 API**：调用 `self.edit_message()`, `self.get_group_info()` 等
3. **使用透传 API**：调用 `self.call_platform_api()` 使用平台特有功能

### 6.3 SDK 版本号

新功能通过提升 SDK minor 版本发布：

- 现有版本：`langbot-plugin-sdk >= x.y.z`
- 新版本：`langbot-plugin-sdk >= x.(y+1).0`

插件的 `manifest.yaml` 中的 `min_sdk_version` 决定是否能使用新 API。使用旧 SDK 版本的插件在新 LangBot 上正常运行（兼容层保证），只是无法调用新 API。
