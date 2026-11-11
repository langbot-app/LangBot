import pydantic

from langbot_plugin.api.entities.builtin.provider import message as provider_message


class Prompt(pydantic.BaseModel):
    """Prompt for AI"""

    name: str
    """Name of the prompt"""

    messages: list[provider_message.Message]
    """Messages of the prompt"""
