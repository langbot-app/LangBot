from __future__ import annotations

from ...core import app
from . import entities
from . import filter
from .filters import cntignore, banwords, baiduexamine


class ContentFilterManager:

    ao: app.Application

    filter_chain: list[filter.ContentFilter]

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self.filter_chain = []

    async def initialize(self):
        self.filter_chain.append(cntignore.ContentIgnore(self.ap))

        if self.ap.cfg_mgr.data['sensitive_word_filter']:
            self.filter_chain.append(banwords.BanWordFilter(self.ap))
        
        if self.ap.cfg_mgr.data['baidu_check']:
            self.filter_chain.append(baiduexamine.BaiduCloudExamine(self.ap))

        for filter in self.filter_chain:
            await filter.initialize()

    async def pre_process(self, message: str) -> entities.FilterManagerResult:
        """请求llm前处理消息
        只要有一个不通过就不放行，只放行 PASS 的消息
        """
        if not self.ap.cfg_mgr.data['income_msg_check']:  # 不检查收到的消息，直接放行
            return entities.FilterManagerResult(
                level=entities.ManagerResultLevel.CONTINUE,
                replacement=message,
                user_notice='',
                console_notice=''
            )
        else:
            for filter in self.filter_chain:
                if entities.EnableStage.PRE in filter.enable_stages:
                    result = await filter.process(message)

                    if result.level in [
                        entities.ResultLevel.BLOCK,
                        entities.ResultLevel.MASKED
                    ]:
                        return entities.FilterManagerResult(
                            level=entities.ManagerResultLevel.INTERRUPT,
                            replacement=result.replacement,
                            user_notice=result.user_notice,
                            console_notice=result.console_notice
                        )
                    elif result.level == entities.ResultLevel.PASS:
                        message = result.replacement

            return entities.FilterManagerResult(
                level=entities.ManagerResultLevel.CONTINUE,
                replacement=message,
                user_notice='',
                console_notice=''
            )

    async def post_process(self, message: str) -> entities.FilterManagerResult:
        """请求llm后处理响应
        只要是 PASS 或者 MASKED 的就通过此 filter，将其 replacement 设置为message，进入下一个 filter
        """
        for filter in self.filter_chain:
            if entities.EnableStage.POST in filter.enable_stages:
                result = await filter.process(message)

                if result.level == entities.ResultLevel.BLOCK:
                    return entities.FilterManagerResult(
                        level=entities.ManagerResultLevel.INTERRUPT,
                        replacement=result.replacement,
                        user_notice=result.user_notice,
                        console_notice=result.console_notice
                    )
                elif result.level in [
                    entities.ResultLevel.PASS,
                    entities.ResultLevel.MASKED
                ]:
                    message = result.replacement

        return entities.FilterManagerResult(
            level=entities.ManagerResultLevel.CONTINUE,
            replacement=message,
            user_notice='',
            console_notice=''
        )
