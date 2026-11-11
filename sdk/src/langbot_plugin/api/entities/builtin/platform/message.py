from __future__ import annotations

import asyncio
import base64
import httpx
import typing
import aiofiles
from datetime import datetime
from pathlib import Path

import pydantic


MAX_IMAGE_BYTES = 10 * 1024 * 1024


async def _read_httpx_body_limited(
    response: httpx.Response,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> bytes:
    declared_size = response.headers.get("Content-Length")
    if declared_size is not None:
        try:
            if int(declared_size) > max_bytes:
                raise ValueError(f"Image exceeds the {max_bytes}-byte limit")
        except ValueError as exc:
            if "exceeds" in str(exc):
                raise

    body = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
        body.extend(chunk)
        if len(body) > max_bytes:
            raise ValueError(f"Image exceeds the {max_bytes}-byte limit")
    return bytes(body)


class MessageComponent(pydantic.BaseModel):
    """Message component."""

    type: str
    """Type of the message component."""


class MessageChain(pydantic.RootModel[list[pydantic.SerializeAsAny[MessageComponent]]]):
    """Message chain, a list of message components."""

    def __init__(self, root: list[MessageComponent] = []):
        """Initialize the message chain."""
        if not isinstance(root, list):
            raise ValueError("root must be a list")
        for item in root:
            if not isinstance(item, MessageComponent):
                raise ValueError(
                    f"root must be a list of MessageComponent, but got {type(item)}"
                )
        super().__init__(root=root)

    @classmethod
    def _get_component_types(cls) -> dict[str, type[MessageComponent]]:
        """Get the component type mapping dictionary."""
        return {
            "Source": Source,
            "Plain": Plain,
            "Quote": Quote,
            "At": At,
            "AtAll": AtAll,
            "Image": Image,
            "Unknown": Unknown,
            "Voice": Voice,
            "Forward": Forward,
            "File": File,
            "Face": Face,
            "WeChatMiniPrograms": WeChatMiniPrograms,
            "WeChatForwardMiniPrograms": WeChatForwardMiniPrograms,
            "WeChatEmoji": WeChatEmoji,
            "WeChatLink": WeChatLink,
            "WeChatForwardLink": WeChatForwardLink,
            "WeChatForwardImage": WeChatForwardImage,
            "WeChatForwardFile": WeChatForwardFile,
            "WeChatAppMsg": WeChatAppMsg,
            "WeChatForwardQuote": WeChatForwardQuote,
            "WeChatFile": WeChatFile,
        }

    def get_first(self, t: type[MessageComponent]) -> MessageComponent | None:
        """Get the first message component of the specified type."""
        for component in self.root:
            if isinstance(component, t):
                return component
        return None

    def __len__(self):
        return len(self.root)

    def __getitem__(self, index: int) -> MessageComponent:
        return self.root[index]

    def __setitem__(self, index: int, value: MessageComponent):
        self.root[index] = value

    def __delitem__(self, index: int):
        del self.root[index]

    def __iter__(self):
        return iter(self.root)

    def __contains__(
        self, item: typing.Union[MessageComponent, type[MessageComponent]]
    ):
        if isinstance(item, type):
            return any(isinstance(component, item) for component in self.root)
        else:
            return item in self.root

    def __str__(self):
        return "".join(
            str(component)
            for component in self.root
            if not isinstance(component, Source)
        )

    def __repr__(self):
        return f"MessageChain({self.root})"

    def __eq__(self, other):
        return isinstance(other, MessageChain) and self.root == other.root

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(tuple(self.root))

    def __add__(self, other):
        return MessageChain(self.root + other.root)

    def __radd__(self, other):
        return MessageChain(other.root + self.root)

    def append(self, item: MessageComponent):
        self.root.append(item)

    def extend(self, items: list[MessageComponent]):
        self.root.extend(items)

    def insert(self, index: int, item: MessageComponent):
        self.root.insert(index, item)

    def pop(self, index: int = -1):
        return self.root.pop(index)

    def remove(self, item: MessageComponent):
        self.root.remove(item)

    def clear(self):
        self.root.clear()

    @property
    def source(self):
        """Get the Source component in the message chain."""
        return self.get_first(Source)

    @property
    def message_id(self):
        """Get the message_id of the message chain, return -1 if there is no source."""
        src = self.source
        return src.id if src else -1

    def model_dump(self, **kwargs):
        result = []
        for component in self.root:
            data = component.model_dump()
            # Recursively process the MessageChain type field
            for field_name, field_info in component.__class__.model_fields.items():
                if field_info.annotation is MessageChain and field_name in data:
                    field_value = getattr(component, field_name)
                    if isinstance(field_value, MessageChain):
                        data[field_name] = field_value.model_dump()
            result.append(data)
        return result

    @classmethod
    def model_validate(cls, obj):
        """Custom deserialization logic, create the correct MessageComponent subclass instance according to the type field, and recursively process the MessageChain field"""

        if isinstance(obj, list):
            components = []
            component_types = cls._get_component_types()
            for item in obj:
                if isinstance(item, dict) and "type" in item:
                    component_type = item["type"]
                    if component_type in component_types:
                        component_class = component_types[component_type]
                        # Recursively process the MessageChain type field
                        for (
                            field_name,
                            field_info,
                        ) in component_class.model_fields.items():
                            if (
                                field_info.annotation is MessageChain
                                and field_name in item
                            ):
                                field_value = item[field_name]
                                if isinstance(field_value, MessageChain):
                                    # It is already a MessageChain, no need to process
                                    pass
                                elif isinstance(field_value, list):
                                    item[field_name] = MessageChain.model_validate(
                                        field_value
                                    )
                        # Special handling for Forward: recursively deserialize
                        # message_chain inside each ForwardMessageNode
                        if component_type == "Forward" and "node_list" in item:
                            for node_data in item["node_list"]:
                                if (
                                    isinstance(node_data, dict)
                                    and "message_chain" in node_data
                                ):
                                    mc = node_data["message_chain"]
                                    if isinstance(mc, list):
                                        node_data["message_chain"] = (
                                            MessageChain.model_validate(mc)
                                        )

                        # Special processing of the time field of the Source class
                        if component_type == "Source" and "time" in item:
                            item["time"] = datetime.fromtimestamp(item["time"])
                        components.append(component_class.model_validate(item))
                    else:
                        # Unknown type, create Unknown component
                        components.append(
                            Unknown(text=f"Unknown component type: {component_type}")
                        )
                else:
                    # Not a dictionary or no type field, create Unknown component
                    components.append(Unknown(text=f"Invalid component data: {item}"))
            return cls(root=components)
        else:
            return super().model_validate(obj)


class Source(MessageComponent):
    """Source. Contains basic information about the message."""

    type: str = "Source"
    """Message component type."""
    id: typing.Union[int, str]
    """The identification number of the message, used for reference reply (the Source type is always the first element of MessageChain)."""
    time: datetime = pydantic.Field(serialization_alias="timestamp")
    """Message time."""

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # 将datetime转换为时间戳
        if "time" in data:
            data["timestamp"] = int(self.time.timestamp())
            del data["time"]
        return data

    @classmethod
    def model_validate(cls, obj):
        if isinstance(obj, dict) and "timestamp" in obj:
            # 将时间戳转换为datetime
            timestamp = obj["timestamp"]
            obj["time"] = datetime.fromtimestamp(timestamp)
            del obj["timestamp"]
        return super().model_validate(obj)


class Plain(MessageComponent):
    """Plain text."""

    type: str = "Plain"
    """Message component type."""
    text: str
    """Text message."""

    def __str__(self):
        return self.text

    def __repr__(self):
        return f"Plain({self.text!r})"


class Quote(MessageComponent):
    """Quote."""

    type: str = "Quote"
    """Message component type."""
    id: typing.Optional[typing.Union[int, str]] = None
    """The message_id of the original message to be quoted."""
    group_id: typing.Optional[typing.Union[int, str]] = None
    """The group number of the original message to be quoted, 0 when it is a friend message."""
    sender_id: typing.Optional[typing.Union[int, str]] = None
    """The ID of the sender of the original message to be quoted."""
    target_id: typing.Optional[typing.Union[int, str]] = None
    """The ID or group ID of the receiver of the original message to be quoted."""
    origin: MessageChain
    """The message chain object of the original message to be quoted."""

    def __str__(self):
        return ""


class At(MessageComponent):
    """At someone."""

    type: str = "At"
    """Message component type."""
    target: typing.Union[int, str]
    """Group member ID."""
    display: typing.Optional[str] = pydantic.Field(default="")
    """The text displayed when At, invalid when sending messages, automatically using the group nickname."""

    def __eq__(self, other):
        return isinstance(other, At) and self.target == other.target

    def __str__(self):
        return f"@{self.display or self.target}"


class AtAll(MessageComponent):
    """At all."""

    type: str = "AtAll"
    """Message component type."""

    def __str__(self):
        return "@All"


class Image(MessageComponent):
    """Image."""

    type: str = "Image"
    """Message component type."""
    image_id: typing.Optional[str] = pydantic.Field(default="")
    """The image_id of the image, if not empty, the url attribute will be ignored."""
    url: typing.Optional[str] = pydantic.Field(default="")
    """The URL of the image, can be used as a network image link when sending; when receiving, it is the link of the image, which can be used for image download."""
    path: typing.Union[str, Path, None] = pydantic.Field(default="")
    """The path of the image, send local image."""
    base64: typing.Optional[str] = pydantic.Field(default="")
    """The Base64 encoding of the image."""

    def __eq__(self, other):
        return (
            isinstance(other, Image)
            and self.type == other.type
            and self.uuid == other.uuid
        )

    def __str__(self):
        return "[Image]"

    async def get_bytes(self) -> typing.Tuple[bytes, str]:
        """Get image bytes and mimetype"""
        if self.url:
            async with httpx.AsyncClient(timeout=30) as client:
                async with client.stream("GET", self.url) as response:
                    response.raise_for_status()
                    return (
                        await _read_httpx_body_limited(response),
                        response.headers.get(
                            "Content-Type", "application/octet-stream"
                        ),
                    )
        elif self.base64:
            mime_type = "image/jpeg"

            split_index = self.base64.find(";base64,")
            if split_index == -1:
                raise ValueError("Invalid base64 string")

            mime_type = self.base64[5:split_index]
            base64_data = self.base64[split_index + 8 :]
            max_encoded_bytes = 4 * ((MAX_IMAGE_BYTES + 2) // 3)
            if len(base64_data) > max_encoded_bytes:
                raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES}-byte limit")

            decoded = await asyncio.to_thread(base64.b64decode, base64_data)
            if len(decoded) > MAX_IMAGE_BYTES:
                raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES}-byte limit")
            return decoded, mime_type
        elif self.path:
            size = await asyncio.to_thread(Path(self.path).stat)
            if size.st_size > MAX_IMAGE_BYTES:
                raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES}-byte limit")
            async with aiofiles.open(self.path, "rb") as f:
                data = await f.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError(f"Image exceeds the {MAX_IMAGE_BYTES}-byte limit")
            return data, "image/jpeg"
        else:
            raise ValueError("Can not get bytes from image")


class Unknown(MessageComponent):
    """Unknown."""

    type: str = "Unknown"
    """Message component type."""
    text: str = pydantic.Field(default="")
    """Text."""

    def __str__(self):
        return f"Unknown Message: {self.text}"


class Voice(MessageComponent):
    """Voice."""

    type: str = "Voice"
    """Message component type."""
    voice_id: typing.Optional[str] = pydantic.Field(default="")
    """The voice_id of the voice, if not empty, the url attribute will be ignored."""
    url: typing.Optional[str] = pydantic.Field(default="")
    """The URL of the voice, can be used as a network voice link when sending; when receiving, it is the link of the voice file, which can be used for voice download."""
    path: typing.Optional[str] = pydantic.Field(default="")
    """The path of the voice, send local voice."""
    base64: typing.Optional[str] = pydantic.Field(default="")
    """The Base64 encoding of the voice."""
    length: typing.Optional[int] = pydantic.Field(default=0)
    """The length of the voice, in seconds."""

    def __str__(self):
        return "[Voice]"


class ForwardMessageNode(pydantic.BaseModel):
    """A message in a merged forward."""

    sender_id: typing.Optional[typing.Union[int, str]] = pydantic.Field(default="")
    """Sender ID."""
    sender_name: typing.Optional[str] = pydantic.Field(default="")
    """Display name."""
    message_chain: typing.Optional[MessageChain] = pydantic.Field(
        default=MessageChain([])
    )
    """Message content."""
    message_id: typing.Optional[int] = pydantic.Field(default=0)
    """The message_id of the message."""


class ForwardMessageDiaplay(pydantic.BaseModel):
    title: str = pydantic.Field(default="Chat history of the group")
    brief: str = pydantic.Field(default="[Chat history]")
    source: str = pydantic.Field(default="Chat history")
    preview: typing.List[str] = pydantic.Field(default_factory=list)
    summary: str = pydantic.Field(default="View x forwarded messages")


class Forward(MessageComponent):
    """Merged forward."""

    type: str = "Forward"
    """Message component type."""
    display: ForwardMessageDiaplay = pydantic.Field(default=ForwardMessageDiaplay())
    """Display information"""
    node_list: typing.List[ForwardMessageNode] = pydantic.Field(default_factory=list)
    """List of forwarded message nodes."""

    def __str__(self):
        return "[Chat history]"


class File(MessageComponent):
    """File."""

    type: str = "File"
    """Message component type."""
    id: str = pydantic.Field(default="")
    """File recognition ID."""
    name: str = pydantic.Field(default="")
    """File name."""
    size: int = pydantic.Field(default=0)
    """File size."""
    url: str = pydantic.Field(default="")
    """File url."""
    path: typing.Optional[str] = pydantic.Field(default="")
    """The path of the file, send local file."""
    base64: typing.Optional[str] = pydantic.Field(default="")
    """The Base64 encoding of the file."""

    def __str__(self):
        return f"[File]{self.name}"


class Face(MessageComponent):
    """系统表情
    此处将超级表情骰子/划拳，一同归类于face
    当face_type为rps(划拳)时 face_id 对应的是手势
    当face_type为dice(骰子)时 face_id 对应的是点数
    """

    type: str = "Face"
    """表情类型"""
    face_type: str = "face"
    """表情id"""
    face_id: int = 0
    """表情名"""
    face_name: str = ""

    def __str__(self):
        if self.face_type == "face":
            return f"[表情]{self.face_name}"
        elif self.face_type == "dice":
            return f"[表情]{self.face_id}点的{self.face_name}"
        elif self.face_type == "rps":
            return f"[表情]{self.face_name}({self.rps_data(self.face_id)})"

    def rps_data(self, face_id):
        rps_dict = {
            1: "布",
            2: "剪刀",
            3: "石头",
        }
        return rps_dict[face_id]


# ================ 个人微信专用组件 ================


class WeChatMiniPrograms(MessageComponent):
    """Mini program. Personal WeChat only."""

    type: str = "WeChatMiniPrograms"
    """Mini program ID"""
    mini_app_id: str
    """Mini program owner ID"""
    user_name: str
    """Mini program name"""
    display_name: typing.Optional[str] = ""
    """Open address"""
    page_path: typing.Optional[str] = ""
    """Mini program title"""
    title: typing.Optional[str] = ""
    """Home page image"""
    image_url: typing.Optional[str] = ""


class WeChatForwardMiniPrograms(MessageComponent):
    """Forward mini program. Personal WeChat only."""

    type: str = "WeChatForwardMiniPrograms"
    """xml data"""
    xml_data: str
    """Home page image"""
    image_url: typing.Optional[str] = None

    def __str__(self):
        return self.xml_data


class WeChatEmoji(MessageComponent):
    """Emoji. Personal WeChat only."""

    type: str = "WeChatEmoji"
    """emojimd5"""
    emoji_md5: str
    """Emoji size"""
    emoji_size: int


class WeChatLink(MessageComponent):
    """Send link. Personal WeChat only."""

    type: str = "WeChatLink"
    """Title"""
    link_title: str = ""
    """Link description"""
    link_desc: str = ""
    """Link address"""
    link_url: str = ""
    """Link thumbnail"""
    link_thumb_url: str = ""


class WeChatForwardLink(MessageComponent):
    """Forward link. Personal WeChat only."""

    type: str = "WeChatForwardLink"
    """xml data"""
    xml_data: str

    def __str__(self):
        return self.xml_data


class WeChatForwardImage(MessageComponent):
    """Forward image. Personal WeChat only."""

    type: str = "WeChatForwardImage"
    """xml data"""
    xml_data: str

    def __str__(self):
        return self.xml_data


class WeChatForwardFile(MessageComponent):
    """Forward file. Personal WeChat only."""

    type: str = "WeChatForwardFile"
    """xml data"""
    xml_data: str

    def __str__(self):
        return self.xml_data


class WeChatAppMsg(MessageComponent):
    """Send appmsg. Personal WeChat only."""

    type: str = "WeChatAppMsg"
    """xml data"""
    app_msg: str

    def __str__(self):
        return self.app_msg


class WeChatForwardQuote(MessageComponent):
    """Forward quoted message. Personal WeChat only."""

    type: str = "WeChatForwardQuote"
    """xml data"""
    app_msg: str

    def __str__(self):
        return self.app_msg


class WeChatFile(MessageComponent):
    """文件。"""

    type: str = "File"
    """消息组件类型。"""
    file_id: str = ""
    """文件识别 ID。"""
    file_name: str = ""
    """文件名称。"""
    file_size: int = 0
    """文件大小。"""
    file_path: str = ""
    """文件地址"""
    file_base64: str = ""
    """base64"""

    def __str__(self):
        return f"[文件]{self.file_name}"
