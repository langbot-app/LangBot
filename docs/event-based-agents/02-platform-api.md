# 统一平台 API 与实体定义

## 1. 设计原则

- **通用 API 抽象**：大部分平台都支持的操作（发消息、获取群信息等）定义为通用 API 方法
- **required / optional 标记**：每个 API 标记为必需或可选，适配器未实现可选 API 时抛出 `NotSupportedError`
- **透传机制**：适配器特有的操作通过 `call_platform_api(action, params)` 统一入口透传调用
- **能力声明**：适配器在 manifest 中声明自己支持的 API 列表，供 WebUI 和插件查询
- **实体统一**：通用实体（User、Group 等）在 SDK 层面统一定义，适配器负责转换

## 2. 通用实体定义

### 2.1 现有实体回顾

当前 SDK 已有以下实体（`langbot_plugin/api/entities/builtin/platform/entities.py`）：

```python
Entity(id)
├── Friend(id, nickname, remark)
├── Group(id, name, permission)
└── GroupMember(id, member_name, permission, group, special_title)
```

### 2.2 新实体设计

扩展实体体系，保持向后兼容：

```python
class User(pydantic.BaseModel):
    """用户实体（统一表示）"""

    id: typing.Union[int, str]
    """用户 ID"""

    nickname: str = ""
    """昵称"""

    avatar_url: typing.Optional[str] = None
    """头像 URL"""

    is_bot: bool = False
    """是否为 Bot"""

    # 以下为可选的扩展信息，不同平台可能部分为空
    username: typing.Optional[str] = None
    """用户名（如 Telegram 的 @username）"""

    remark: typing.Optional[str] = None
    """备注名"""


class Group(pydantic.BaseModel):
    """群组实体"""

    id: typing.Union[int, str]
    """群组 ID"""

    name: str = ""
    """群组名称"""

    description: typing.Optional[str] = None
    """群组描述"""

    member_count: typing.Optional[int] = None
    """成员数量"""

    avatar_url: typing.Optional[str] = None
    """群组头像 URL"""

    owner_id: typing.Optional[typing.Union[int, str]] = None
    """群主 ID"""


class GroupMember(pydantic.BaseModel):
    """群成员实体"""

    user: User
    """用户信息"""

    group_id: typing.Union[int, str]
    """所属群组 ID"""

    role: MemberRole
    """群内角色"""

    display_name: typing.Optional[str] = None
    """群内显示名"""

    joined_at: typing.Optional[float] = None
    """加入群组的时间戳"""

    title: typing.Optional[str] = None
    """群头衔/特殊称号"""


class MemberRole(str, Enum):
    """群成员角色"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
```

### 2.3 与现有实体的兼容映射

| 新实体 | 旧实体 | 映射方式 |
|--------|--------|----------|
| `User` | `Friend` | `User(id=friend.id, nickname=friend.nickname, remark=friend.remark)` |
| `Group` | `Group`（旧） | `Group(id=old.id, name=old.name)` + `permission` 字段弃用 |
| `GroupMember` | `GroupMember`（旧） | `GroupMember(user=User(...), role=..., display_name=old.member_name)` |
| `MemberRole` | `Permission` | `OWNER↔Owner`, `ADMIN↔Administrator`, `MEMBER↔Member` |

旧实体类保留，标记为 `@deprecated`，内部通过转换方法桥接到新实体。

## 3. 通用 API 定义

### 3.1 API 方法一览

#### 消息 API

| 方法 | 必需/可选 | 说明 |
|------|----------|------|
| `send_message(target_type, target_id, message)` | **必需** | 主动发送消息 |
| `reply_message(event, message, quote_origin)` | **必需** | 回复一个消息事件 |
| `edit_message(chat_type, chat_id, message_id, new_content)` | 可选 | 编辑已发送的消息 |
| `delete_message(chat_type, chat_id, message_id)` | 可选 | 删除/撤回消息 |
| `forward_message(from_chat, message_id, to_chat_type, to_chat_id)` | 可选 | 转发消息到另一个会话 |
| `get_message(chat_type, chat_id, message_id)` | 可选 | 获取指定消息的内容 |

#### 群组 API

| 方法 | 必需/可选 | 说明 |
|------|----------|------|
| `get_group_info(group_id)` | 可选 | 获取群组信息 |
| `get_group_list()` | 可选 | 获取 Bot 加入的群组列表 |
| `get_group_member_list(group_id)` | 可选 | 获取群成员列表 |
| `get_group_member_info(group_id, user_id)` | 可选 | 获取指定群成员信息 |
| `set_group_name(group_id, name)` | 可选 | 修改群名称 |
| `mute_member(group_id, user_id, duration)` | 可选 | 禁言群成员 |
| `unmute_member(group_id, user_id)` | 可选 | 解除禁言 |
| `kick_member(group_id, user_id)` | 可选 | 踢出群成员 |
| `leave_group(group_id)` | 可选 | Bot 退出群组 |

#### 用户 API

| 方法 | 必需/可选 | 说明 |
|------|----------|------|
| `get_user_info(user_id)` | 可选 | 获取用户信息 |
| `get_friend_list()` | 可选 | 获取好友列表 |
| `approve_friend_request(request_id, approve, remark)` | 可选 | 处理好友请求 |
| `approve_group_invite(request_id, approve)` | 可选 | 处理入群邀请 |

#### 媒体 API

| 方法 | 必需/可选 | 说明 |
|------|----------|------|
| `upload_file(file_data, filename)` | 可选 | 上传文件，返回可引用的文件 ID 或 URL |
| `get_file_url(file_id)` | 可选 | 获取文件下载 URL |

#### 透传 API

| 方法 | 必需/可选 | 说明 |
|------|----------|------|
| `call_platform_api(action, params)` | 可选 | 调用适配器特有 API |

### 3.2 API 方法签名详解

```python
class AbstractPlatformAdapter(pydantic.BaseModel, metaclass=abc.ABCMeta):
    """平台适配器基类（新版）"""

    # ======== 必需方法 ========

    @abc.abstractmethod
    async def send_message(
        self,
        target_type: str,          # "private" | "group"
        target_id: typing.Union[int, str],
        message: MessageChain,
    ) -> MessageResult:
        """主动发送消息

        Returns:
            MessageResult: 包含 message_id 等发送结果
        """
        ...

    @abc.abstractmethod
    async def reply_message(
        self,
        event: MessageReceivedEvent,
        message: MessageChain,
        quote_origin: bool = False,
    ) -> MessageResult:
        """回复一个消息事件"""
        ...

    # ======== 可选消息方法 ========

    async def edit_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        new_content: MessageChain,
    ) -> None:
        """编辑已发送的消息"""
        raise NotSupportedError("edit_message")

    async def delete_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> None:
        """删除/撤回消息"""
        raise NotSupportedError("delete_message")

    async def forward_message(
        self,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> MessageResult:
        """转发消息"""
        raise NotSupportedError("forward_message")

    async def get_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> MessageReceivedEvent:
        """获取指定消息"""
        raise NotSupportedError("get_message")

    # ======== 可选群组方法 ========

    async def get_group_info(
        self,
        group_id: typing.Union[int, str],
    ) -> Group:
        """获取群组信息"""
        raise NotSupportedError("get_group_info")

    async def get_group_list(self) -> list[Group]:
        """获取 Bot 加入的群组列表"""
        raise NotSupportedError("get_group_list")

    async def get_group_member_list(
        self,
        group_id: typing.Union[int, str],
    ) -> list[GroupMember]:
        """获取群成员列表"""
        raise NotSupportedError("get_group_member_list")

    async def get_group_member_info(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> GroupMember:
        """获取指定群成员信息"""
        raise NotSupportedError("get_group_member_info")

    async def set_group_name(
        self,
        group_id: typing.Union[int, str],
        name: str,
    ) -> None:
        """修改群名称"""
        raise NotSupportedError("set_group_name")

    async def mute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
        duration: int = 0,
    ) -> None:
        """禁言群成员，duration 为秒数，0 表示永久"""
        raise NotSupportedError("mute_member")

    async def unmute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        """解除禁言"""
        raise NotSupportedError("unmute_member")

    async def kick_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        """踢出群成员"""
        raise NotSupportedError("kick_member")

    async def leave_group(
        self,
        group_id: typing.Union[int, str],
    ) -> None:
        """Bot 退出群组"""
        raise NotSupportedError("leave_group")

    # ======== 可选用户方法 ========

    async def get_user_info(
        self,
        user_id: typing.Union[int, str],
    ) -> User:
        """获取用户信息"""
        raise NotSupportedError("get_user_info")

    async def get_friend_list(self) -> list[User]:
        """获取好友列表"""
        raise NotSupportedError("get_friend_list")

    async def approve_friend_request(
        self,
        request_id: typing.Union[int, str],
        approve: bool = True,
        remark: typing.Optional[str] = None,
    ) -> None:
        """处理好友请求"""
        raise NotSupportedError("approve_friend_request")

    async def approve_group_invite(
        self,
        request_id: typing.Union[int, str],
        approve: bool = True,
    ) -> None:
        """处理入群邀请"""
        raise NotSupportedError("approve_group_invite")

    # ======== 可选媒体方法 ========

    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
    ) -> str:
        """上传文件，返回文件 ID 或 URL"""
        raise NotSupportedError("upload_file")

    async def get_file_url(
        self,
        file_id: str,
    ) -> str:
        """获取文件下载 URL"""
        raise NotSupportedError("get_file_url")

    # ======== 透传 API ========

    async def call_platform_api(
        self,
        action: str,
        params: dict = {},
    ) -> dict:
        """调用适配器特有 API

        Args:
            action: 平台特有的 API 动作标识
            params: 参数字典

        Returns:
            dict: 返回结果

        Examples:
            # Telegram: pin 消息
            await adapter.call_platform_api("pin_message", {
                "chat_id": 123456,
                "message_id": 789
            })

            # Discord: 创建频道
            await adapter.call_platform_api("create_channel", {
                "guild_id": "...",
                "name": "new-channel",
                "type": "text"
            })
        """
        raise NotSupportedError("call_platform_api")

    # ======== 流式输出（保留现有机制） ========

    async def reply_message_chunk(
        self,
        event: MessageReceivedEvent,
        bot_message: dict,
        message: MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        """流式回复消息"""
        raise NotSupportedError("reply_message_chunk")

    async def is_stream_output_supported(self) -> bool:
        """是否支持流式输出"""
        return False

    # ======== 生命周期方法（保留现有） ========

    @abc.abstractmethod
    async def run_async(self):
        """启动适配器"""
        ...

    @abc.abstractmethod
    async def kill(self) -> bool:
        """停止适配器"""
        ...

    @abc.abstractmethod
    def register_listener(self, event_type, callback):
        """注册事件监听器"""
        ...

    @abc.abstractmethod
    def unregister_listener(self, event_type, callback):
        """注销事件监听器"""
        ...
```

### 3.3 返回值类型

```python
class MessageResult(pydantic.BaseModel):
    """消息发送结果"""

    message_id: typing.Optional[typing.Union[int, str]] = None
    """发送成功后的消息 ID"""

    raw: typing.Optional[dict] = None
    """平台原始返回数据"""


class NotSupportedError(Exception):
    """适配器未实现此 API"""

    def __init__(self, api_name: str):
        self.api_name = api_name
        super().__init__(f"API not supported by this adapter: {api_name}")
```

## 4. API 能力声明

适配器在 manifest.yaml 中声明支持的 API：

```yaml
kind: MessagePlatformAdapter
metadata:
  name: telegram
spec:
  supported_apis:
    required:
      - send_message
      - reply_message
    optional:
      - edit_message
      - delete_message
      - get_group_info
      - get_group_member_list
      - get_user_info
      - upload_file
      - get_file_url
      - call_platform_api
  platform_specific_apis:
    - action: pin_message
      description: "Pin a message in a chat"
      params_schema:
        chat_id: { type: "string", required: true }
        message_id: { type: "string", required: true }
    - action: unpin_message
      description: "Unpin a message"
      params_schema:
        chat_id: { type: "string", required: true }
        message_id: { type: "string", required: true }
```

用途：
1. **WebUI**：在配置界面展示当前 Bot 可用的 API 能力
2. **插件**：插件可查询某个 Bot 是否支持特定 API，据此决定行为
3. **文档**：自动生成各适配器的 API 支持矩阵

## 5. 各平台 API 支持矩阵

| API | Telegram | Discord | OneBot(QQ) | 飞书 | 钉钉 | Slack | 微信 | LINE | KOOK |
|-----|----------|---------|-----------|------|------|-------|------|------|------|
| `send_message` | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| `reply_message` | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| `edit_message` | Y | Y | N | Y | N | Y | N | N | Y |
| `delete_message` | Y | Y | Y | Y | N | Y | Y | N | Y |
| `forward_message` | Y | N | Y | Y | N | N | Y | N | N |
| `get_group_info` | Y | Y | Y | Y | Y | Y | N | Y | Y |
| `get_group_member_list` | Y | Y | Y | Y | Y | Y | N | Y | Y |
| `get_user_info` | Y | Y | Y | Y | Y | Y | N | Y | Y |
| `get_friend_list` | N | Y | Y | N | N | N | Y | N | N |
| `mute_member` | Y | Y | Y | N | N | N | N | N | N |
| `kick_member` | Y | Y | Y | N | N | N | N | N | Y |
| `upload_file` | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| `call_platform_api` | Y | Y | Y | Y | Y | Y | Y | Y | Y |

> 注：此表为初步评估，具体以各平台 SDK/API 文档为准。

## 6. MessageChain 扩展

### 6.1 保留的通用组件

以下 MessageComponent 类型保持不变，继续作为通用消息元素：

- `Source` — 消息元信息
- `Plain` — 纯文本
- `Quote` — 引用回复
- `At` / `AtAll` — @提及
- `Image` — 图片
- `Voice` — 语音
- `File` — 文件
- `Forward` — 合并转发
- `Face` — 表情
- `Unknown` — 未知类型

### 6.2 平台特有组件处理

当前 MessageChain 中存在大量微信特有的组件类型（`WeChatMiniPrograms`, `WeChatEmoji`, `WeChatLink` 等）。在新架构下：

- 这些类型**继续保留**在 SDK 中以保持兼容
- 新增的平台特有消息组件统一使用 `PlatformComponent` 基类：

```python
class PlatformComponent(MessageComponent):
    """平台特有的消息组件"""

    type: str = "Platform"

    platform: str
    """平台标识"""

    component_type: str
    """组件类型"""

    data: dict = {}
    """组件数据"""
```

适配器在转换消息链时，对于无法映射到通用组件的平台特有内容，使用 `PlatformComponent` 承载。
