import pydantic
import mirai


class RuleJudgeResult(pydantic.BaseModel):

    matching: bool = False

    replacement: mirai.MessageChain = None
