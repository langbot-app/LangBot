import pydantic

import langbot_plugin.api.entities.builtin.platform.message as platform_message


class RuleJudgeResult(pydantic.BaseModel):
    matching: bool = False

    replacement: platform_message.MessageChain = None
