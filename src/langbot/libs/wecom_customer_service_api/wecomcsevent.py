from typing import Dict, Any, Optional


class WecomCSEvent(dict):
    """
    封装从企业微信收到的事件数据对象（字典），提供属性以获取其中的字段。

    除 `type` 和 `detail_type` 属性对于任何事件都有效外，其它属性是否存在（若不存在则返回 `None`）依事件类型不同而不同。
    """

    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> Optional['WecomCSEvent']:
        """
        从企业微信(客服会话)事件数据构造 `WecomEvent` 对象。

        Args:
            payload (Dict[str, Any]): 解密后的企业微信事件数据。

        Returns:
            Optional[WecomEvent]: 如果事件数据合法，则返回 WecomEvent 对象；否则返回 None。
        """
        try:
            event = WecomCSEvent(payload)
            _ = (event.type,)
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
        return self.get('msgtype', '')

    @property
    def user_id(self) -> Optional[str]:
        """
        用户 ID，例如消息的发送者或事件的触发者。

        Returns:
            Optional[str]: 用户 ID。
        """
        return self.get('external_userid')

    @property
    def receiver_id(self) -> Optional[str]:
        """
        接收者 ID，例如机器人自身的企业微信 ID。

        Returns:
            Optional[str]: 接收者 ID。
        """
        return self.get('open_kfid', '')

    @property
    def picurl(self) -> Optional[str]:
        """
        图片 URL，仅在图片消息中存在。
        base64格式
        Returns:
            Optional[str]: 图片 URL。
        """

        return self.get('picurl', '')

    @property
    def message_id(self) -> Optional[str]:
        """
        消息 ID，仅在消息类型事件中存在。

        Returns:
            Optional[str]: 消息 ID。
        """
        return self.get('msgid')

    @property
    def message(self) -> Optional[str]:
        """
        消息内容，仅在消息类型事件中存在。

        Returns:
            Optional[str]: 消息内容。
        """
        if self.get('msgtype') == 'text':
            return self.get('text').get('content', '')
        else:
            return None

    @property
    def timestamp(self) -> Optional[int]:
        """
        事件发生的时间戳。

        Returns:
            Optional[int]: 时间戳。
        """
        return self.get('send_time')

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
