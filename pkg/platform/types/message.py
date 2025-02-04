import itertools
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
import typing

import pydantic.v1 as pydantic

from . import entities as platform_entities
from .base import PlatformBaseModel, PlatformIndexedMetaclass, PlatformIndexedModel


logger = logging.getLogger(__name__)


class MessageComponentMetaclass(PlatformIndexedMetaclass):
    """消息组件元类。"""
    __message_component__ = None

    def __new__(cls, name, bases, attrs, **kwargs):
        new_cls = super().__new__(cls, name, bases, attrs, **kwargs)
        if name == 'MessageComponent':
            cls.__message_component__ = new_cls

        if not cls.__message_component__:
            return new_cls

        for base in bases:
            if issubclass(base, cls.__message_component__):
                # 获取字段名
                if hasattr(new_cls, '__fields__'):
                    # 忽略 type 字段
                    new_cls.__parameter_names__ = list(new_cls.__fields__)[1:]
                else:
                    new_cls.__parameter_names__ = []
                break

        return new_cls


class MessageComponent(PlatformIndexedModel, metaclass=MessageComponentMetaclass):
    """消息组件。"""
    type: str
    """消息组件类型。"""
    def __str__(self):
        return ''

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join(
            (
                f'{k}={repr(v)}'
                for k, v in self.__dict__.items() if k != 'type' and v
            )
        ) + ')'

    def __init__(self, *args, **kwargs):
        # 解析参数列表，将位置参数转化为具名参数
        parameter_names = self.__parameter_names__
        if len(args) > len(parameter_names):
            raise TypeError(
                f'`{self.type}`需要{len(parameter_names)}个参数，但传入了{len(args)}个。'
            )
        for name, value in zip(parameter_names, args):
            if name in kwargs:
                raise TypeError(f'在 `{self.type}` 中，具名参数 `{name}` 与位置参数重复。')
            kwargs[name] = value

        super().__init__(**kwargs)


TMessageComponent = typing.TypeVar('TMessageComponent', bound=MessageComponent)


class MessageChain(PlatformBaseModel):
    """消息链。

    一个构造消息链的例子：
    ```py
    message_chain = MessageChain([
        AtAll(),
        Plain("Hello World!"),
    ])
    ```

    `Plain` 可以省略。
    ```py
    message_chain = MessageChain([
        AtAll(),
        "Hello World!",
    ])
    ```

    在调用 API 时，参数中需要 MessageChain 的，也可以使用 `List[MessageComponent]` 代替。
    例如，以下两种写法是等价的：
    ```py
    await bot.send_friend_message(12345678, [
        Plain("Hello World!")
    ])
    ```
    ```py
    await bot.send_friend_message(12345678, MessageChain([
        Plain("Hello World!")
    ]))
    ```

    可以使用 `in` 运算检查消息链中：
    1. 是否有某个消息组件。
    2. 是否有某个类型的消息组件。

    ```py
    if AtAll in message_chain:
        print('AtAll')

    if At(bot.qq) in message_chain:
        print('At Me')
    ```

    消息链对索引操作进行了增强。以消息组件类型为索引，获取消息链中的全部该类型的消息组件。
    ```py
    plain_list = message_chain[Plain]
    '[Plain("Hello World!")]'
    ```

    可以用加号连接两个消息链。
    ```py
    MessageChain(['Hello World!']) + MessageChain(['Goodbye World!'])
    # 返回 MessageChain([Plain("Hello World!"), Plain("Goodbye World!")])
    ```

    """
    __root__: typing.List[MessageComponent]

    @staticmethod
    def _parse_message_chain(msg_chain: typing.Iterable):
        result = []
        for msg in msg_chain:
            if isinstance(msg, dict):
                result.append(MessageComponent.parse_subtype(msg))
            elif isinstance(msg, MessageComponent):
                result.append(msg)
            elif isinstance(msg, str):
                result.append(Plain(msg))
            else:
                raise TypeError(
                    f"消息链中元素需为 dict 或 str 或 MessageComponent，当前类型：{type(msg)}"
                )
        return result
    
    @pydantic.validator('__root__', always=True, pre=True)
    def _parse_component(cls, msg_chain):
        if isinstance(msg_chain, (str, MessageComponent)):
            msg_chain = [msg_chain]
        if not msg_chain:
            msg_chain = []
        return cls._parse_message_chain(msg_chain)

    @classmethod
    def parse_obj(cls, msg_chain: typing.Iterable):
        """通过列表形式的消息链，构造对应的 `MessageChain` 对象。

        Args:
            msg_chain: 列表形式的消息链。
        """
        result = cls._parse_message_chain(msg_chain)
        return cls(__root__=result)

    def __init__(self, __root__: typing.Iterable[MessageComponent] = None):
        super().__init__(__root__=__root__)

    def __str__(self):
        return "".join(str(component) for component in self.__root__)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.__root__!r})'

    def __iter__(self):
        yield from self.__root__

    def get_first(self,
                  t: typing.Type[TMessageComponent]) -> typing.Optional[TMessageComponent]:
        """获取消息链中第一个符合类型的消息组件。"""
        for component in self:
            if isinstance(component, t):
                return component
        return None

    @typing.overload
    def __getitem__(self, index: int) -> MessageComponent:
        ...

    @typing.overload
    def __getitem__(self, index: slice) -> typing.List[MessageComponent]:
        ...

    @typing.overload
    def __getitem__(self,
                    index: typing.Type[TMessageComponent]) -> typing.List[TMessageComponent]:
        ...

    @typing.overload
    def __getitem__(
        self, index: typing.Tuple[typing.Type[TMessageComponent], int]
    ) -> typing.List[TMessageComponent]:
        ...

    def __getitem__(
        self, index: typing.Union[int, slice, typing.Type[TMessageComponent],
                           typing.Tuple[typing.Type[TMessageComponent], int]]
    ) -> typing.Union[MessageComponent, typing.List[MessageComponent],
               typing.List[TMessageComponent]]:
        return self.get(index)

    def __setitem__(
        self, key: typing.Union[int, slice],
        value: typing.Union[MessageComponent, str, typing.Iterable[typing.Union[MessageComponent,
                                                           str]]]
    ):
        if isinstance(value, str):
            value = Plain(value)
        if isinstance(value, typing.Iterable):
            value = (Plain(c) if isinstance(c, str) else c for c in value)
        self.__root__[key] = value  # type: ignore

    def __delitem__(self, key: typing.Union[int, slice]):
        del self.__root__[key]

    def __reversed__(self) -> typing.Iterable[MessageComponent]:
        return reversed(self.__root__)

    def has(
        self, sub: typing.Union[MessageComponent, typing.Type[MessageComponent],
                         'MessageChain', str]
    ) -> bool:
        """判断消息链中：
        1. 是否有某个消息组件。
        2. 是否有某个类型的消息组件。

        Args:
            sub (`Union[MessageComponent, Type[MessageComponent], 'MessageChain', str]`):
                若为 `MessageComponent`，则判断该组件是否在消息链中。
                若为 `Type[MessageComponent]`，则判断该组件类型是否在消息链中。

        Returns:
            bool: 是否找到。
        """
        if isinstance(sub, type):  # 检测消息链中是否有某种类型的对象
            for i in self:
                if type(i) is sub:
                    return True
            return False
        if isinstance(sub, MessageComponent):  # 检查消息链中是否有某个组件
            for i in self:
                if i == sub:
                    return True
            return False
        raise TypeError(f"类型不匹配，当前类型：{type(sub)}")

    def __contains__(self, sub) -> bool:
        return self.has(sub)

    def __ge__(self, other):
        return other in self

    def __len__(self) -> int:
        return len(self.__root__)

    def __add__(
        self, other: typing.Union['MessageChain', MessageComponent, str]
    ) -> 'MessageChain':
        if isinstance(other, MessageChain):
            return self.__class__(self.__root__ + other.__root__)
        if isinstance(other, str):
            return self.__class__(self.__root__ + [Plain(other)])
        if isinstance(other, MessageComponent):
            return self.__class__(self.__root__ + [other])
        return NotImplemented

    def __radd__(self, other: typing.Union[MessageComponent, str]) -> 'MessageChain':
        if isinstance(other, MessageComponent):
            return self.__class__([other] + self.__root__)
        if isinstance(other, str):
            return self.__class__(
                [typing.cast(MessageComponent, Plain(other))] + self.__root__
            )
        return NotImplemented

    def __mul__(self, other: int):
        if isinstance(other, int):
            return self.__class__(self.__root__ * other)
        return NotImplemented

    def __rmul__(self, other: int):
        return self.__mul__(other)

    def __iadd__(self, other: typing.Iterable[typing.Union[MessageComponent, str]]):
        self.extend(other)

    def __imul__(self, other: int):
        if isinstance(other, int):
            self.__root__ *= other
        return NotImplemented

    def index(
        self,
        x: typing.Union[MessageComponent, typing.Type[MessageComponent]],
        i: int = 0,
        j: int = -1
    ) -> int:
        """返回 x 在消息链中首次出现项的索引号（索引号在 i 或其后且在 j 之前）。

        Args:
            x (`Union[MessageComponent, Type[MessageComponent]]`):
                要查找的消息元素或消息元素类型。
            i: 从哪个位置开始查找。
            j: 查找到哪个位置结束。

        Returns:
            int: 如果找到，则返回索引号。

        Raises:
            ValueError: 没有找到。
            TypeError: 类型不匹配。
        """
        if isinstance(x, type):
            l = len(self)
            if i < 0:
                i += l
            if i < 0:
                i = 0
            if j < 0:
                j += l
            if j > l:
                j = l
            for index in range(i, j):
                if type(self[index]) is x:
                    return index
            raise ValueError("消息链中不存在该类型的组件。")
        if isinstance(x, MessageComponent):
            return self.__root__.index(x, i, j)
        raise TypeError(f"类型不匹配，当前类型：{type(x)}")

    def count(self, x: typing.Union[MessageComponent, typing.Type[MessageComponent]]) -> int:
        """返回消息链中 x 出现的次数。

        Args:
            x (`Union[MessageComponent, Type[MessageComponent]]`):
                要查找的消息元素或消息元素类型。

        Returns:
            int: 次数。
        """
        if isinstance(x, type):
            return sum(1 for i in self if type(i) is x)
        if isinstance(x, MessageComponent):
            return self.__root__.count(x)
        raise TypeError(f"类型不匹配，当前类型：{type(x)}")

    def extend(self, x: typing.Iterable[typing.Union[MessageComponent, str]]):
        """将另一个消息链中的元素添加到消息链末尾。

        Args:
            x: 另一个消息链，也可为消息元素或字符串元素的序列。
        """
        self.__root__.extend(Plain(c) if isinstance(c, str) else c for c in x)

    def append(self, x: typing.Union[MessageComponent, str]):
        """将一个消息元素或字符串元素添加到消息链末尾。

        Args:
            x: 消息元素或字符串元素。
        """
        self.__root__.append(Plain(x) if isinstance(x, str) else x)

    def insert(self, i: int, x: typing.Union[MessageComponent, str]):
        """将一个消息元素或字符串添加到消息链中指定位置。

        Args:
            i: 插入位置。
            x: 消息元素或字符串元素。
        """
        self.__root__.insert(i, Plain(x) if isinstance(x, str) else x)

    def pop(self, i: int = -1) -> MessageComponent:
        """从消息链中移除并返回指定位置的元素。

        Args:
            i: 移除位置。默认为末尾。

        Returns:
            MessageComponent: 移除的元素。
        """
        return self.__root__.pop(i)

    def remove(self, x: typing.Union[MessageComponent, typing.Type[MessageComponent]]):
        """从消息链中移除指定元素或指定类型的一个元素。

        Args:
            x: 指定的元素或元素类型。
        """
        if isinstance(x, type):
            self.pop(self.index(x))
        if isinstance(x, MessageComponent):
            self.__root__.remove(x)

    def exclude(
        self,
        x: typing.Union[MessageComponent, typing.Type[MessageComponent]],
        count: int = -1
    ) -> 'MessageChain':
        """返回移除指定元素或指定类型的元素后剩余的消息链。

        Args:
            x: 指定的元素或元素类型。
            count: 至多移除的数量。默认为全部移除。

        Returns:
            MessageChain: 剩余的消息链。
        """
        def _exclude():
            nonlocal count
            x_is_type = isinstance(x, type)
            for c in self:
                if count > 0 and ((x_is_type and type(c) is x) or c == x):
                    count -= 1
                    continue
                yield c

        return self.__class__(_exclude())

    def reverse(self):
        """将消息链原地翻转。"""
        self.__root__.reverse()

    @classmethod
    def join(cls, *args: typing.Iterable[typing.Union[str, MessageComponent]]):
        return cls(
            Plain(c) if isinstance(c, str) else c
            for c in itertools.chain(*args)
        )

    @property
    def source(self) -> typing.Optional['Source']:
        """获取消息链中的 `Source` 对象。"""
        return self.get_first(Source)

    @property
    def message_id(self) -> int:
        """获取消息链的 message_id，若无法获取，返回 -1。"""
        source = self.source
        return source.id if source else -1


TMessage = typing.Union[MessageChain, typing.Iterable[typing.Union[MessageComponent, str]],
                 MessageComponent, str]
"""可以转化为 MessageChain 的类型。"""


class Source(MessageComponent):
    """源。包含消息的基本信息。"""
    type: str = "Source"
    """消息组件类型。"""
    id: typing.Union[int, str]
    """消息的识别号，用于引用回复（Source 类型永远为 MessageChain 的第一个元素）。"""
    time: datetime
    """消息时间。"""


class Plain(MessageComponent):
    """纯文本。"""
    type: str = "Plain"
    """消息组件类型。"""
    text: str
    """文字消息。"""
    def __str__(self):
        return self.text

    def __repr__(self):
        return f'Plain({self.text!r})'


class Quote(MessageComponent):
    """引用。"""
    type: str = "Quote"
    """消息组件类型。"""
    id: typing.Optional[int] = None
    """被引用回复的原消息的 message_id。"""
    group_id: typing.Optional[typing.Union[int, str]] = None
    """被引用回复的原消息所接收的群号，当为好友消息时为0。"""
    sender_id: typing.Optional[typing.Union[int, str]] = None
    """被引用回复的原消息的发送者的QQ号。"""
    target_id: typing.Optional[typing.Union[int, str]] = None
    """被引用回复的原消息的接收者者的QQ号（或群号）。"""
    origin: MessageChain
    """被引用回复的原消息的消息链对象。"""

    @pydantic.validator("origin", always=True, pre=True)
    def origin_formater(cls, v):
        return MessageChain.parse_obj(v)


class At(MessageComponent):
    """At某人。"""
    type: str = "At"
    """消息组件类型。"""
    target: typing.Union[int, str]
    """群员 QQ 号。"""
    display: typing.Optional[str] = None
    """At时显示的文字，发送消息时无效，自动使用群名片。"""
    def __eq__(self, other):
        return isinstance(other, At) and self.target == other.target

    def __str__(self):
        return f"@{self.display or self.target}"


class AtAll(MessageComponent):
    """At全体。"""
    type: str = "AtAll"
    """消息组件类型。"""
    def __str__(self):
        return "@全体成员"


class Image(MessageComponent):
    """图片。"""
    type: str = "Image"
    """消息组件类型。"""
    image_id: typing.Optional[str] = None
    """图片的 image_id，群图片与好友图片格式不同。不为空时将忽略 url 属性。"""
    url: typing.Optional[pydantic.HttpUrl] = None
    """图片的 URL，发送时可作网络图片的链接；接收时为腾讯图片服务器的链接，可用于图片下载。"""
    path: typing.Union[str, Path, None] = None
    """图片的路径，发送本地图片。"""
    base64: typing.Optional[str] = None
    """图片的 Base64 编码。"""
    def __eq__(self, other):
        return isinstance(
            other, Image
        ) and self.type == other.type and self.uuid == other.uuid

    def __str__(self):
        return '[图片]'

    @pydantic.validator('path')
    def validate_path(cls, path: typing.Union[str, Path, None]):
        """修复 path 参数的行为，使之相对于 LangBot 的启动路径。"""
        if path:
            try:
                return str(Path(path).resolve(strict=True))
            except FileNotFoundError:
                raise ValueError(f"无效路径：{path}")
        else:
            return path

    @property
    def uuid(self):
        image_id = self.image_id
        if image_id[0] == '{':  # 群图片
            image_id = image_id[1:37]
        elif image_id[0] == '/':  # 好友图片
            image_id = image_id[1:]
        return image_id

    async def download(
        self,
        filename: typing.Union[str, Path, None] = None,
        directory: typing.Union[str, Path, None] = None,
        determine_type: bool = True
    ):
        """下载图片到本地。

        Args:
            filename: 下载到本地的文件路径。与 `directory` 二选一。
            directory: 下载到本地的文件夹路径。与 `filename` 二选一。
            determine_type: 是否自动根据图片类型确定拓展名，默认为 True。
        """
        if not self.url:
            logger.warning(f'图片 `{self.uuid}` 无 url 参数，下载失败。')
            return

        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(self.url)
            response.raise_for_status()
            content = response.content

            if filename:
                path = Path(filename)
                if determine_type:
                    import imghdr
                    path = path.with_suffix(
                        '.' + str(imghdr.what(None, content))
                    )
                path.parent.mkdir(parents=True, exist_ok=True)
            elif directory:
                import imghdr
                path = Path(directory)
                path.mkdir(parents=True, exist_ok=True)
                path = path / f'{self.uuid}.{imghdr.what(None, content)}'
            else:
                raise ValueError("请指定文件路径或文件夹路径！")

            import aiofiles
            async with aiofiles.open(path, 'wb') as f:
                await f.write(content)

            return path

    @classmethod
    async def from_local(
        cls,
        filename: typing.Union[str, Path, None] = None,
        content: typing.Optional[bytes] = None,
    ) -> "Image":
        """从本地文件路径加载图片，以 base64 的形式传递。

        Args:
            filename: 从本地文件路径加载图片，与 `content` 二选一。
            content: 从本地文件内容加载图片，与 `filename` 二选一。

        Returns:
            Image: 图片对象。
        """
        if content:
            pass
        elif filename:
            path = Path(filename)
            import aiofiles
            async with aiofiles.open(path, 'rb') as f:
                content = await f.read()
        else:
            raise ValueError("请指定图片路径或图片内容！")
        import base64
        img = cls(base64=base64.b64encode(content).decode())
        return img

    @classmethod
    def from_unsafe_path(cls, path: typing.Union[str, Path]) -> "Image":
        """从不安全的路径加载图片。

        Args:
            path: 从不安全的路径加载图片。

        Returns:
            Image: 图片对象。
        """
        return cls.construct(path=str(path))


class Unknown(MessageComponent):
    """未知。"""
    type: str = "Unknown"
    """消息组件类型。"""
    text: str
    """文本。"""


class Voice(MessageComponent):
    """语音。"""
    type: str = "Voice"
    """消息组件类型。"""
    voice_id: typing.Optional[str] = None
    """语音的 voice_id，不为空时将忽略 url 属性。"""
    url: typing.Optional[str] = None
    """语音的 URL，发送时可作网络语音的链接；接收时为腾讯语音服务器的链接，可用于语音下载。"""
    path: typing.Optional[str] = None
    """语音的路径，发送本地语音。"""
    base64: typing.Optional[str] = None
    """语音的 Base64 编码。"""
    length: typing.Optional[int] = None
    """语音的长度，单位为秒。"""
    @pydantic.validator('path')
    def validate_path(cls, path: typing.Optional[str]):
        """修复 path 参数的行为，使之相对于 LangBot 的启动路径。"""
        if path:
            try:
                return str(Path(path).resolve(strict=True))
            except FileNotFoundError:
                raise ValueError(f"无效路径：{path}")
        else:
            return path

    def __str__(self):
        return '[语音]'

    async def download(
        self,
        filename: typing.Union[str, Path, None] = None,
        directory: typing.Union[str, Path, None] = None
    ):
        """下载语音到本地。

        语音采用 silk v3 格式，silk 格式的编码解码请使用 [graiax-silkcoder](https://pypi.org/project/graiax-silkcoder/)。

        Args:
            filename: 下载到本地的文件路径。与 `directory` 二选一。
            directory: 下载到本地的文件夹路径。与 `filename` 二选一。
        """
        if not self.url:
            logger.warning(f'语音 `{self.voice_id}` 无 url 参数，下载失败。')
            return

        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(self.url)
            response.raise_for_status()
            content = response.content

            if filename:
                path = Path(filename)
                path.parent.mkdir(parents=True, exist_ok=True)
            elif directory:
                path = Path(directory)
                path.mkdir(parents=True, exist_ok=True)
                path = path / f'{self.voice_id}.silk'
            else:
                raise ValueError("请指定文件路径或文件夹路径！")

            import aiofiles
            async with aiofiles.open(path, 'wb') as f:
                await f.write(content)

    @classmethod
    async def from_local(
        cls,
        filename: typing.Union[str, Path, None] = None,
        content: typing.Optional[bytes] = None,
    ) -> "Voice":
        """从本地文件路径加载语音，以 base64 的形式传递。

        Args:
            filename: 从本地文件路径加载语音，与 `content` 二选一。
            content: 从本地文件内容加载语音，与 `filename` 二选一。
        """
        if content:
            pass
        if filename:
            path = Path(filename)
            import aiofiles
            async with aiofiles.open(path, 'rb') as f:
                content = await f.read()
        else:
            raise ValueError("请指定语音路径或语音内容！")
        import base64
        img = cls(base64=base64.b64encode(content).decode())
        return img


class ForwardMessageNode(pydantic.BaseModel):
    """合并转发中的一条消息。"""
    sender_id: typing.Optional[typing.Union[int, str]] = None
    """发送人QQ号。"""
    sender_name: typing.Optional[str] = None
    """显示名称。"""
    message_chain: typing.Optional[MessageChain] = None
    """消息内容。"""
    message_id: typing.Optional[int] = None
    """消息的 message_id，可以只使用此属性，从缓存中读取消息内容。"""
    time: typing.Optional[datetime] = None
    """发送时间。"""
    @pydantic.validator('message_chain', check_fields=False)
    def _validate_message_chain(cls, value: typing.Union[MessageChain, list]):
        if isinstance(value, list):
            return MessageChain.parse_obj(value)
        return value

    @classmethod
    def create(
        cls, sender: typing.Union[platform_entities.Friend, platform_entities.GroupMember], message: MessageChain
    ) -> 'ForwardMessageNode':
        """从消息链生成转发消息。

        Args:
            sender: 发送人。
            message: 消息内容。

        Returns:
            ForwardMessageNode: 生成的一条消息。
        """
        return ForwardMessageNode(
            sender_id=sender.id,
            sender_name=sender.get_name(),
            message_chain=message
        )


class ForwardMessageDiaplay(pydantic.BaseModel):
    title: str = "群聊的聊天记录"
    brief: str = "[聊天记录]"
    source: str = "聊天记录"
    preview: typing.List[str] = []
    summary: str = "查看x条转发消息"


class Forward(MessageComponent):
    """合并转发。"""
    type: str = "Forward"
    """消息组件类型。"""
    display: ForwardMessageDiaplay
    """显示信息"""
    node_list: typing.List[ForwardMessageNode]
    """转发消息节点列表。"""
    def __init__(self, *args, **kwargs):
        if len(args) == 1:
            self.node_list = args[0]
            super().__init__(**kwargs)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return '[聊天记录]'


class File(MessageComponent):
    """文件。"""
    type: str = "File"
    """消息组件类型。"""
    id: str
    """文件识别 ID。"""
    name: str
    """文件名称。"""
    size: int
    """文件大小。"""
    def __str__(self):
        return f'[文件]{self.name}'

