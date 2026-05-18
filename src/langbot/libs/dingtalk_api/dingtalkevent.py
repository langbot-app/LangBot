from typing import Dict, Any, Optional
import dingtalk_stream  # type: ignore


class DingTalkEvent(dict):
    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> Optional['DingTalkEvent']:
        try:
            event = DingTalkEvent(payload)
            return event
        except KeyError:
            return None

    @property
    def content(self):
        return self.get('Content', '')

    @property
    def rich_content(self):
        return self.get('Rich_Content', '')

    @property
    def incoming_message(self) -> Optional['dingtalk_stream.chatbot.ChatbotMessage']:
        return self.get('IncomingMessage')

    @property
    def type(self):
        return self.get('Type', '')

    @property
    def picture(self):
        return self.get('Picture', '')

    @property
    def audio(self):
        return self.get('Audio', '')

    @property
    def file(self):
        return self.get('File', '')

    @property
    def name(self):
        return self.get('Name', '')

    @property
    def conversation(self):
        return self.get('conversation_type', '')

    @property
    def quoted_message(self) -> Optional[Dict[str, Any]]:
        """Get the quoted/replied message info if this is a reply message.

        Returns:
            A dict containing:
            - message_id: The original message ID
            - msg_type: The message type (text, file, picture, audio, etc.)
            - content: The text content (if any)
            - file_url: The file download URL (if file type)
            - file_name: The file name (if file type)
            - picture: The picture base64 (if picture type)
            - audio: The audio base64 (if audio type)
        """
        return self.get('QuotedMessage')

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
        return f'<DingTalkEvent {super().__repr__()}>'
