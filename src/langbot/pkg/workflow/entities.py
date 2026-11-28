from pydantic import BaseModel


class MessageContext(BaseModel):
    message_id: str
    message_content: str
    sender_id: str
    sender_name: str = ''
    platform: str = ''
    conversation_id: str = ''
    is_group: bool = False
    group_id: str | None = None
