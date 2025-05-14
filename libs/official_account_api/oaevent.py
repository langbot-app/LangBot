from typing import Dict, Any, Optional


class OAEvent(dict):
    """
    封装从微信公众号收到的事件数据对象（字典），提供属性以获取其中的字段。

    除 `type` 和 `detail_type` 属性对于任何事件都有效外，其它属性是否存在（若不存在则返回 `None`）依事件类型不同而不同。
    """

    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> Optional['OAEvent']:
        """
        从微信公众号事件数据构造 `WecomEvent` 对象。

        Args:
            payload (Dict[str, Any]): 解密后的微信事件数据。

        Returns:
            Optional[OAEvent]: 如果事件数据合法，则返回 OAEvent 对象；否则返回 None。
        """
        try:
            event = OAEvent(payload)
            _ = event.type, event.detail_type  # 确保必须字段存在
            return event
        except KeyError:
            return None

    @property
    def type(self) -> str:
        """
        事件类型，例如 "message"、"event"、"text" 等。

        Returns:
            str: 事件类型。
        """
        return self.get('MsgType', '')

    @property
    def picurl(self) -> str:
        """
        图片链接
        """
        return self.get('PicUrl', '')

    @property
    def detail_type(self) -> str:
        """
        事件详细类型，依 `type` 的不同而不同。例如：
        - 消息事件: "text", "image", "voice", 等
        - 事件通知: "subscribe", "unsubscribe", "click", 等

        Returns:
            str: 事件详细类型。
        """
        if self.type == 'event':
            return self.get('Event', '')
        return self.type

    @property
    def name(self) -> str:
        """
        事件名，对于消息事件是 `type.detail_type`，对于其他事件是 `event_type`。

        Returns:
            str: 事件名。
        """
        return f'{self.type}.{self.detail_type}'

    @property
    def user_id(self) -> Optional[str]:
        """
        发送方账号
        """
        return self.get('FromUserName')

    @property
    def receiver_id(self) -> Optional[str]:
        """
        接收者 ID，例如机器人自身的公众号微信 ID。

        Returns:
            Optional[str]: 接收者 ID。
        """
        return self.get('ToUserName')

    @property
    def message_id(self) -> Optional[str]:
        """
        消息 ID，仅在消息类型事件中存在。

        Returns:
            Optional[str]: 消息 ID。
        """
        return self.get('MsgId')

    @property
    def message(self) -> Optional[str]:
        """
        消息内容，仅在消息类型事件中存在。

        Returns:
            Optional[str]: 消息内容。
        """
        return self.get('Content')

    @property
    def media_id(self) -> Optional[str]:
        """
        媒体文件 ID，仅在图片、语音等消息类型中存在。

        Returns:
            Optional[str]: 媒体文件 ID。
        """
        return self.get('MediaId')

    @property
    def timestamp(self) -> Optional[int]:
        """
        事件发生的时间戳。

        Returns:
            Optional[int]: 时间戳。
        """
        return self.get('CreateTime')

    @property
    def event_key(self) -> Optional[str]:
        """
        事件的 Key 值，例如点击菜单时的 `EventKey`。

        Returns:
            Optional[str]: 事件 Key。
        """
        return self.get('EventKey')

    def __getattr__(self, key: str) -> Optional[Any]:
        """
        允许通过属性访问数据中的任意字段。

        Args:
            key (str): 字段名。

        Returns:
            Optional[Any]: 字段值。
        """
        return self.get(key)

    def __setattr__(self, key: str, value: Any) -> None:
        """
        允许通过属性设置数据中的任意字段。

        Args:
            key (str): 字段名。
            value (Any): 字段值。
        """
        self[key] = value

    def __repr__(self) -> str:
        """
        生成事件对象的字符串表示。

        Returns:
            str: 字符串表示。
        """
        return f'<WecomEvent {super().__repr__()}>'
