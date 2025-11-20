from __future__ import annotations

import aiohttp

from .. import entities
from .. import filter as filter_model
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

BAIDU_EXAMINE_URL = 'https://aip.baidubce.com/rest/2.0/solution/v1/text_censor/v2/user_defined?access_token={}'
BAIDU_EXAMINE_TOKEN_URL = 'https://aip.baidubce.com/oauth/2.0/token'


@filter_model.filter_class('baidu-cloud-examine')
class BaiduCloudExamine(filter_model.ContentFilter):
    """百度云内容审核"""

    async def _get_token(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                BAIDU_EXAMINE_TOKEN_URL,
                params={
                    'grant_type': 'client_credentials',
                    'client_id': self.ap.pipeline_cfg.data['baidu-cloud-examine']['api-key'],
                    'client_secret': self.ap.pipeline_cfg.data['baidu-cloud-examine']['api-secret'],
                },
            ) as resp:
                return (await resp.json())['access_token']

    async def process(self, query: pipeline_query.Query, message: str) -> entities.FilterResult:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                BAIDU_EXAMINE_URL.format(await self._get_token()),
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                },
                data=f'text={message}'.encode('utf-8'),
            ) as resp:
                result = await resp.json()

                if 'error_code' in result:
                    return entities.FilterResult(
                        level=entities.ResultLevel.BLOCK,
                        replacement=message,
                        user_notice='',
                        console_notice=f'百度云判定出错，错误信息：{result["error_msg"]}',
                    )
                else:
                    conclusion = result['conclusion']

                    if conclusion in ('合规'):
                        return entities.FilterResult(
                            level=entities.ResultLevel.PASS,
                            replacement=message,
                            user_notice='',
                            console_notice=f'百度云判定结果：{conclusion}',
                        )
                    else:
                        return entities.FilterResult(
                            level=entities.ResultLevel.BLOCK,
                            replacement=message,
                            user_notice='消息中存在不合适的内容, 请修改',
                            console_notice=f'百度云判定结果：{conclusion}',
                        )
