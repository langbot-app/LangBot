from __future__ import annotations

import typing
import json
import uuid
import aiohttp

from .. import runner
from ...core import app
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class N8nAPIError(Exception):
    """N8n API 请求失败"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


@runner.runner_class('n8n-service-api')
class N8nServiceAPIRunner(runner.RequestRunner):
    """N8n Service API 工作流请求器"""

    def __init__(self, ap: app.Application, pipeline_config: dict):
        self.ap = ap
        self.pipeline_config = pipeline_config

        # 获取webhook URL
        self.webhook_url = self.pipeline_config['ai']['n8n-service-api']['webhook-url']

        # 获取超时设置，默认为120秒
        self.timeout = self.pipeline_config['ai']['n8n-service-api'].get('timeout', 120)

        # 获取输出键名，默认为response
        self.output_key = self.pipeline_config['ai']['n8n-service-api'].get('output-key', 'response')

        # 获取认证类型，默认为none
        self.auth_type = self.pipeline_config['ai']['n8n-service-api'].get('auth-type', 'none')

        # 根据认证类型获取相应的认证信息
        if self.auth_type == 'basic':
            self.basic_username = self.pipeline_config['ai']['n8n-service-api'].get('basic-username', '')
            self.basic_password = self.pipeline_config['ai']['n8n-service-api'].get('basic-password', '')
        elif self.auth_type == 'jwt':
            self.jwt_secret = self.pipeline_config['ai']['n8n-service-api'].get('jwt-secret', '')
            self.jwt_algorithm = self.pipeline_config['ai']['n8n-service-api'].get('jwt-algorithm', 'HS256')
        elif self.auth_type == 'header':
            self.header_name = self.pipeline_config['ai']['n8n-service-api'].get('header-name', '')
            self.header_value = self.pipeline_config['ai']['n8n-service-api'].get('header-value', '')

    async def _preprocess_user_message(self, query: pipeline_query.Query) -> str:
        """预处理用户消息，提取纯文本

        Returns:
            str: 纯文本消息
        """
        plain_text = ''

        if isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == 'text':
                    plain_text += ce.text
                # 注意：n8n webhook目前不支持直接处理图片，如需支持可在此扩展
        elif isinstance(query.user_message.content, str):
            plain_text = query.user_message.content

        return plain_text

    async def _call_webhook(self, query: pipeline_query.Query) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用n8n webhook"""
        # 生成会话ID（如果不存在）
        if not query.session.using_conversation.uuid:
            query.session.using_conversation.uuid = str(uuid.uuid4())

        # 预处理用户消息
        plain_text = await self._preprocess_user_message(query)

        # 准备请求数据
        payload = {
            # 基本消息内容
            'message': plain_text,
            'user_message_text': plain_text,
            'conversation_id': query.session.using_conversation.uuid,
            'session_id': query.variables.get('session_id', ''),
            'user_id': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            'msg_create_time': query.variables.get('msg_create_time', ''),
        }

        # 添加所有变量到payload
        payload.update(query.variables)

        try:
            # 准备请求头和认证信息
            headers = {}
            auth = None

            # 根据认证类型设置相应的认证信息
            if self.auth_type == 'basic':
                # 使用Basic认证
                auth = aiohttp.BasicAuth(self.basic_username, self.basic_password)
                self.ap.logger.debug(f'using basic auth: {self.basic_username}')
            elif self.auth_type == 'jwt':
                # 使用JWT认证
                import jwt
                import time

                # 创建JWT令牌
                payload_jwt = {
                    'exp': int(time.time()) + 3600,  # 1小时过期
                    'iat': int(time.time()),
                    'sub': 'n8n-webhook',
                }
                token = jwt.encode(payload_jwt, self.jwt_secret, algorithm=self.jwt_algorithm)

                # 添加到Authorization头
                headers['Authorization'] = f'Bearer {token}'
                self.ap.logger.debug('using jwt auth')
            elif self.auth_type == 'header':
                # 使用自定义请求头认证
                headers[self.header_name] = self.header_value
                self.ap.logger.debug(f'using header auth: {self.header_name}')
            else:
                self.ap.logger.debug('no auth')

            # 调用webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=payload, headers=headers, auth=auth, timeout=self.timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self.ap.logger.error(f'n8n webhook call failed: {response.status}, {error_text}')
                        raise Exception(f'n8n webhook call failed: {response.status}, {error_text}')

                    # 解析响应
                    response_data = await response.json()
                    self.ap.logger.debug(f'n8n webhook response: {response_data}')

                    # 从响应中提取输出
                    if self.output_key in response_data:
                        output_content = response_data[self.output_key]
                    else:
                        # 如果没有指定的输出键，则使用整个响应
                        output_content = json.dumps(response_data, ensure_ascii=False)

                    # 返回消息
                    yield provider_message.Message(
                        role='assistant',
                        content=output_content,
                    )
        except Exception as e:
            self.ap.logger.error(f'n8n webhook call exception: {str(e)}')
            raise N8nAPIError(f'n8n webhook call exception: {str(e)}')

    async def run(self, query: pipeline_query.Query) -> typing.AsyncGenerator[provider_message.Message, None]:
        """运行请求"""
        async for msg in self._call_webhook(query):
            yield msg
