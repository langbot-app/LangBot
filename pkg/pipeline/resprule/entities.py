import pydantic.v1 as pydantic

from ...platform.types import message as platform_message


class RuleJudgeResult(pydantic.BaseModel):
    matching: bool = False

    replacement: platform_message.MessageChain = None
