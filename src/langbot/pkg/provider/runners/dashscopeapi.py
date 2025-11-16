from __future__ import annotations

import typing
import re

import dashscope

from .. import runner
from ...core import app
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class DashscopeAPIError(Exception):
    """Dashscope API 请求失败"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


@runner.runner_class('dashscope-app-api')
class DashScopeAPIRunner(runner.RequestRunner):
    "阿里云百炼DashsscopeAPI对话请求器"

    # 运行器内部使用的配置
    app_type: str  # 应用类型
    app_id: str  # 应用ID
    api_key: str  # API Key
    references_quote: (
        str  # 引用资料提示（当展示回答来源功能开启时，这个变量会作为引用资料名前的提示，可在provider.json中配置）
    )

    def __init__(self, ap: app.Application, pipeline_config: dict):
        """初始化"""
        self.ap = ap
        self.pipeline_config = pipeline_config

        valid_app_types = ['agent', 'workflow']
        self.app_type = self.pipeline_config['ai']['dashscope-app-api']['app-type']
        # 检查配置文件中使用的应用类型是否支持
        if self.app_type not in valid_app_types:
            raise DashscopeAPIError(f'不支持的 Dashscope 应用类型: {self.app_type}')

        # 初始化Dashscope 参数配置
        self.app_id = self.pipeline_config['ai']['dashscope-app-api']['app-id']
        self.api_key = self.pipeline_config['ai']['dashscope-app-api']['api-key']
        self.references_quote = self.pipeline_config['ai']['dashscope-app-api']['references_quote']

    def _replace_references(self, text, references_dict):
        """阿里云百炼平台的自定义应用支持资料引用，此函数可以将引用标签替换为参考资料"""

        # 匹配 <ref>[index_id]</ref> 形式的字符串
        pattern = re.compile(r'<ref>\[(.*?)\]</ref>')

        def replacement(match):
            # 获取引用编号
            ref_key = match.group(1)
            if ref_key in references_dict:
                # 如果有对应的参考资料按照provider.json中的reference_quote返回提示，来自哪个参考资料文件
                return f'({self.references_quote} {references_dict[ref_key]})'
            else:
                # 如果没有对应的参考资料，保留原样
                return match.group(0)

        # 使用 re.sub() 进行替换
        return pattern.sub(replacement, text)

    async def _preprocess_user_message(self, query: pipeline_query.Query) -> tuple[str, list[str]]:
        """预处理用户消息，提取纯文本，阿里云提供的上传文件方法过于复杂，暂不支持上传文件（包括图片）"""
        plain_text = ''
        image_ids = []
        if isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == 'text':
                    plain_text += ce.text
                # 暂时不支持上传图片，保留代码以便后续扩展
                # elif ce.type == "image_base64":
                #     image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)
                #     file_bytes = base64.b64decode(image_b64)
                #     file = ("img.png", file_bytes, f"image/{image_format}")
                #     file_upload_resp = await self.dify_client.upload_file(
                #         file,
                #         f"{query.session.launcher_type.value}_{query.session.launcher_id}",
                #     )
                #     image_id = file_upload_resp["id"]
                #     image_ids.append(image_id)
        elif isinstance(query.user_message.content, str):
            plain_text = query.user_message.content

        return plain_text, image_ids

    async def _agent_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """Dashscope 智能体对话请求"""

        # 局部变量
        chunk = None  # 流式传输的块
        pending_content = ''  # 待处理的Agent输出内容
        references_dict = {}  # 用于存储引用编号和对应的参考资料
        plain_text = ''  # 用户输入的纯文本信息
        image_ids = []  # 用户输入的图片ID列表 （暂不支持）

        think_start = False
        think_end = False

        plain_text, image_ids = await self._preprocess_user_message(query)
        has_thoughts = True  # 获取思考过程
        remove_think = self.pipeline_config['output'].get('misc', '').get('remove-think')
        if remove_think:
            has_thoughts = False
        # 发送对话请求
        response = dashscope.Application.call(
            api_key=self.api_key,  # 智能体应用的API Key
            app_id=self.app_id,  # 智能体应用的ID
            prompt=plain_text,  # 用户输入的文本信息
            stream=True,  # 流式输出
            incremental_output=True,  # 增量输出，使用流式输出需要开启增量输出
            session_id=query.session.using_conversation.uuid,  # 会话ID用于，多轮对话
            has_thoughts=has_thoughts,
            # rag_options={                                     # 主要用于文件交互，暂不支持
            #     "session_file_ids": ["FILE_ID1"],             # FILE_ID1 替换为实际的临时文件ID,逗号隔开多个
            # }
        )
        idx_chunk = 0
        try:
            is_stream = await query.adapter.is_stream_output_supported()

        except AttributeError:
            is_stream = False
        if is_stream:
            for chunk in response:
                if chunk.get('status_code') != 200:
                    raise DashscopeAPIError(
                        f'Dashscope API 请求失败: status_code={chunk.get("status_code")} message={chunk.get("message")} request_id={chunk.get("request_id")} '
                    )
                if not chunk:
                    continue
                idx_chunk += 1
                # 获取流式传输的output
                stream_output = chunk.get('output', {})
                stream_think = stream_output.get('thoughts', [])
                if stream_think[0].get('thought'):
                    if not think_start:
                        think_start = True
                        pending_content += f'<think>\n{stream_think[0].get("thought")}'
                    else:
                        # 继续输出 reasoning_content
                        pending_content += stream_think[0].get('thought')
                elif stream_think[0].get('thought') == '' and not think_end:
                    think_end = True
                    pending_content += '\n</think>\n'
                if stream_output.get('text') is not None:
                    pending_content += stream_output.get('text')
                # 是否是流式最后一个chunk
                is_final = False if stream_output.get('finish_reason', False) == 'null' else True

                # 获取模型传出的参考资料列表
                references_dict_list = stream_output.get('doc_references', [])

                # 从模型传出的参考资料信息中提取用于替换的字典
                if references_dict_list is not None:
                    for doc in references_dict_list:
                        if doc.get('index_id') is not None:
                            references_dict[doc.get('index_id')] = doc.get('doc_name')

                    # 将参考资料替换到文本中
                    pending_content = self._replace_references(pending_content, references_dict)

                if idx_chunk % 8 == 0 or is_final:
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=pending_content,
                        is_final=is_final,
                    )
            # 保存当前会话的session_id用于下次对话的语境
            query.session.using_conversation.uuid = stream_output.get('session_id')
        else:
            for chunk in response:
                if chunk.get('status_code') != 200:
                    raise DashscopeAPIError(
                        f'Dashscope API 请求失败: status_code={chunk.get("status_code")} message={chunk.get("message")} request_id={chunk.get("request_id")} '
                    )
                if not chunk:
                    continue
                idx_chunk += 1
                # 获取流式传输的output
                stream_output = chunk.get('output', {})
                stream_think = stream_output.get('thoughts', [])
                if stream_think[0].get('thought'):
                    if not think_start:
                        think_start = True
                        pending_content += f'<think>\n{stream_think[0].get("thought")}'
                    else:
                        # 继续输出 reasoning_content
                        pending_content += stream_think[0].get('thought')
                elif stream_think[0].get('thought') == '' and not think_end:
                    think_end = True
                    pending_content += '\n</think>\n'
                if stream_output.get('text') is not None:
                    pending_content += stream_output.get('text')

            # 保存当前会话的session_id用于下次对话的语境
            query.session.using_conversation.uuid = stream_output.get('session_id')

            # 获取模型传出的参考资料列表
            references_dict_list = stream_output.get('doc_references', [])

            # 从模型传出的参考资料信息中提取用于替换的字典
            if references_dict_list is not None:
                for doc in references_dict_list:
                    if doc.get('index_id') is not None:
                        references_dict[doc.get('index_id')] = doc.get('doc_name')

                # 将参考资料替换到文本中
                pending_content = self._replace_references(pending_content, references_dict)

            yield provider_message.Message(
                role='assistant',
                content=pending_content,
            )

    async def _workflow_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """Dashscope 工作流对话请求"""

        # 局部变量
        chunk = None  # 流式传输的块
        pending_content = ''  # 待处理的Agent输出内容
        references_dict = {}  # 用于存储引用编号和对应的参考资料
        plain_text = ''  # 用户输入的纯文本信息
        image_ids = []  # 用户输入的图片ID列表 （暂不支持）

        plain_text, image_ids = await self._preprocess_user_message(query)

        biz_params = {}
        biz_params.update(query.variables)

        # 发送对话请求
        response = dashscope.Application.call(
            api_key=self.api_key,  # 智能体应用的API Key
            app_id=self.app_id,  # 智能体应用的ID
            prompt=plain_text,  # 用户输入的文本信息
            stream=True,  # 流式输出
            incremental_output=True,  # 增量输出，使用流式输出需要开启增量输出
            session_id=query.session.using_conversation.uuid,  # 会话ID用于，多轮对话
            biz_params=biz_params,  # 工作流应用的自定义输入参数传递
            flow_stream_mode='message_format',  # 消息模式，输出/结束节点的流式结果
            # rag_options={                                     # 主要用于文件交互，暂不支持
            #     "session_file_ids": ["FILE_ID1"],             # FILE_ID1 替换为实际的临时文件ID,逗号隔开多个
            # }
        )

        # 处理API返回的流式输出
        try:
            is_stream = await query.adapter.is_stream_output_supported()

        except AttributeError:
            is_stream = False
        idx_chunk = 0
        if is_stream:
            for chunk in response:
                if chunk.get('status_code') != 200:
                    raise DashscopeAPIError(
                        f'Dashscope API 请求失败: status_code={chunk.get("status_code")} message={chunk.get("message")} request_id={chunk.get("request_id")} '
                    )
                if not chunk:
                    continue
                idx_chunk += 1
                # 获取流式传输的output
                stream_output = chunk.get('output', {})
                if stream_output.get('workflow_message') is not None:
                    pending_content += stream_output.get('workflow_message').get('message').get('content')
                # if stream_output.get('text') is not None:
                #     pending_content += stream_output.get('text')

                is_final = False if stream_output.get('finish_reason', False) == 'null' else True

                # 获取模型传出的参考资料列表
                references_dict_list = stream_output.get('doc_references', [])

                # 从模型传出的参考资料信息中提取用于替换的字典
                if references_dict_list is not None:
                    for doc in references_dict_list:
                        if doc.get('index_id') is not None:
                            references_dict[doc.get('index_id')] = doc.get('doc_name')

                    # 将参考资料替换到文本中
                    pending_content = self._replace_references(pending_content, references_dict)
                if idx_chunk % 8 == 0 or is_final:
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=pending_content,
                        is_final=is_final,
                    )

            # 保存当前会话的session_id用于下次对话的语境
            query.session.using_conversation.uuid = stream_output.get('session_id')

        else:
            for chunk in response:
                if chunk.get('status_code') != 200:
                    raise DashscopeAPIError(
                        f'Dashscope API 请求失败: status_code={chunk.get("status_code")} message={chunk.get("message")} request_id={chunk.get("request_id")} '
                    )
                if not chunk:
                    continue

                # 获取流式传输的output
                stream_output = chunk.get('output', {})
                if stream_output.get('text') is not None:
                    pending_content += stream_output.get('text')

                is_final = False if stream_output.get('finish_reason', False) == 'null' else True

            # 保存当前会话的session_id用于下次对话的语境
            query.session.using_conversation.uuid = stream_output.get('session_id')

            # 获取模型传出的参考资料列表
            references_dict_list = stream_output.get('doc_references', [])

            # 从模型传出的参考资料信息中提取用于替换的字典
            if references_dict_list is not None:
                for doc in references_dict_list:
                    if doc.get('index_id') is not None:
                        references_dict[doc.get('index_id')] = doc.get('doc_name')

                # 将参考资料替换到文本中
                pending_content = self._replace_references(pending_content, references_dict)

            yield provider_message.Message(
                role='assistant',
                content=pending_content,
            )

    async def run(self, query: pipeline_query.Query) -> typing.AsyncGenerator[provider_message.Message, None]:
        """运行"""
        msg_seq = 0
        if self.app_type == 'agent':
            async for msg in self._agent_messages(query):
                if isinstance(msg, provider_message.MessageChunk):
                    msg_seq += 1
                    msg.msg_sequence = msg_seq
                yield msg
        elif self.app_type == 'workflow':
            async for msg in self._workflow_messages(query):
                if isinstance(msg, provider_message.MessageChunk):
                    msg_seq += 1
                    msg.msg_sequence = msg_seq
                yield msg
        else:
            raise DashscopeAPIError(f'不支持的 Dashscope 应用类型: {self.app_type}')
