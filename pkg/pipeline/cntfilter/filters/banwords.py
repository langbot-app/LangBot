from __future__ import annotations
import re

from .. import filter as filter_model
from .. import entities
from ....config import manager as cfg_mgr


@filter_model.filter_class("ban-word-filter")
class BanWordFilter(filter_model.ContentFilter):
    """根据内容禁言"""

    sensitive: cfg_mgr.ConfigManager

    async def initialize(self):
        self.sensitive = await cfg_mgr.load_json_config(
            "data/config/sensitive-words.json",
            "templates/sensitive-words.json"
        )

    async def process(self, message: str) -> entities.FilterResult:
        found = False

        for word in self.sensitive.data['words']:
            match = re.findall(word, message)

            if len(match) > 0:
                found = True

                for i in range(len(match)):
                    if self.sensitive.data['mask_word'] == "":
                        message = message.replace(
                            match[i], self.sensitive.data['mask'] * len(match[i])
                        )
                    else:
                        message = message.replace(
                            match[i], self.sensitive.data['mask_word']
                        )

        return entities.FilterResult(
            level=entities.ResultLevel.MASKED if found else entities.ResultLevel.PASS,
            replacement=message,
            user_notice='消息中存在不合适的内容, 请修改' if found else '',
            console_notice=''
        )