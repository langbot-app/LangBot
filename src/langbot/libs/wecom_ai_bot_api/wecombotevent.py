from typing import Dict, Any, Optional


class WecomBotEvent(dict):
    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> Optional['WecomBotEvent']:
        try:
            event = WecomBotEvent(payload)
            return event
        except KeyError:
            return None

    @property
    def type(self) -> str:
        """
        事件类型
        """
        return self.get('type', '')

    @property
    def msgtype(self) -> str:
        """
        消息 msgtype
        """
        return self.get('msgtype', '')

    @property
    def userid(self) -> str:
        """
        用户id
        """
        return self.get('from', {}).get('userid', '') or self.get('userid', '')

    @property
    def username(self) -> str:
        """
        用户名称
        """
        return (
            self.get('username', '')
            or self.get('from', {}).get('alias', '')
            or self.get('from', {}).get('name', '')
            or self.userid
        )

    @property
    def chatname(self) -> str:
        """
        群组名称
        """
        return self.get('chatname', '') or str(self.chatid)

    @property
    def content(self) -> str:
        """
        内容
        """
        return self.get('content', '')

    @property
    def picurl(self) -> str:
        """
        图片url
        """
        return self.get('picurl', '')

    @property
    def images(self):
        """
        图片列表（兼容 mixed）
        """
        return self.get('images', [])

    @property
    def file(self):
        """
        文件信息
        """
        return self.get('file', {})

    @property
    def voice(self):
        """
        语音信息
        """
        return self.get('voice', {})

    @property
    def video(self):
        """
        视频信息
        """
        return self.get('video', {})

    @property
    def link(self):
        """
        链接消息信息
        """
        return self.get('link', {})

    @property
    def location(self):
        """
        位置信息
        """
        return self.get('location', {})

    @property
    def attachments(self):
        """
        原始 mixed 中的附件项
        """
        return self.get('attachments', [])

    @property
    def chatid(self) -> str:
        """
        群组id
        """
        return self.get('chatid', {})

    @property
    def message_id(self) -> str:
        """
        消息id
        """
        return self.get('msgid', '')

    @property
    def ai_bot_id(self) -> str:
        """
        AI Bot ID
        """
        return self.get('aibotid', '')
