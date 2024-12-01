from __future__ import annotations

import json
import typing
import aiohttp

from .. import runner
from ...core import app, entities as core_entities
from .. import entities as llm_entities

api_url = "请求地址/v1"
api_key = "请求key"
user_name = "dify-plugin"
# 需要在dify的自定义字段中另外设置context和system_prompt
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}


def get_content_text(content):
    if isinstance(content, list):
        return " ".join(str(element) if element.image_url is None else " " for element in content)
    elif isinstance(content, str):
        return content
    else:
        return ""


@runner.runner_class("difyapi")
class DifyAgentRunner(runner.RequestRunner):
    """Dify API 对话请求器
    """

    async def run(self, query: core_entities.Query) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """运行请求"""
        await query.use_model.requester.preprocess(query)

        # 构建系统提示词
        prompt_messages = query.prompt.messages.copy()
        system_prompt = "\n".join(
            f"{msg.role}: {get_content_text(msg.content)}" for msg in prompt_messages if msg.content
        )

        # 构建上下文
        previous_messages = query.messages.copy()
        user_message = [query.user_message]

        # 检查 user_message 中的 image_url
        image_urls = [element.image_url.url for element in query.user_message.content if element.type == 'image_url' and element.image_url is not None]

        if len(image_urls) > 10:
            raise ValueError("仅可包含最多10张图片")

        data = {}
        if image_urls:
            data["files"] = [
                {
                    "type": "image",
                    "transfer_method": "remote_url",
                    "url": url
                } for url in image_urls
            ]
        else:
            data["files"] = []

        # 继续处理其他逻辑
        all_messages = previous_messages + user_message

        context = "\n".join(
            f"{msg.role}: {get_content_text(msg.content)}" for msg in all_messages if msg.content
        )

        # 构建请求数据
        data.update({
            "inputs": {
                "context": context,
                "system_prompt": system_prompt,
                "files": data["files"]
            },
            "query": get_content_text(query.user_message.content),
            "response_mode": "blocking",
            "conversation_id": "",
            "user": user_name
            
        })

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(api_url + "/chat-messages", headers=headers, json=data) as response:
                    response_data = await response.json()
                    response.raise_for_status()

                    # 处理响应数据
                    content_elements = [llm_entities.ContentElement.from_text(response_data.get("answer", ""))]

                    msg = llm_entities.Message(
                        role="assistant",
                        content=content_elements
                    )
                    yield msg
            except aiohttp.ClientResponseError as http_err:
                if response.status == 404:
                    error_message = "对话不存在"
                elif response.status == 400:
                    error_code = response_data.get("code")
                    if error_code == "invalid_param":
                        error_message = "传入参数异常"
                    elif error_code == "app_unavailable":
                        error_message = "App 配置不可用"
                    elif error_code == "provider_not_initialize":
                        error_message = "无可用模型凭据配置"
                    elif error_code == "provider_quota_exceeded":
                        error_message = "模型调用额度不足"
                    elif error_code == "model_currently_not_support":
                        error_message = "当前模型不可用"
                    elif error_code == "completion_request_error":
                        error_message = "文本生成失败"
                elif response.status == 500:
                    error_message = "服务内部异常"
                else:
                    error_message = f"HTTP error occurred: {http_err}"
                raise ValueError(error_message)
            except Exception as err:
                raise ValueError(f"An error occurred: {err}")


@runner.runner_class("local-agent")
class LocalAgentRunner(runner.RequestRunner):
    """本地Agent请求运行器
    """

    async def run(self, query: core_entities.Query) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """运行请求
        """
        await query.use_model.requester.preprocess(query)

        pending_tool_calls = []

        req_messages = query.prompt.messages.copy() + query.messages.copy() + [query.user_message]

        # 首次请求
        try:
            msg = await query.use_model.requester.call(query.use_model, req_messages, query.use_funcs)
            if "answer" not in msg.content:
                raise ValueError("请求失败：返回内容不含answer")
        except Exception as e:
            err_msg = llm_entities.Message(
                role="system", content=f"请求失败：{e}"
            )
            yield err_msg
            return

        yield msg

        pending_tool_calls = msg.tool_calls

        req_messages.append(msg)

        # 持续请求，只要还有待处理的工具调用就继续处理调用
        while pending_tool_calls:
            for tool_call in pending_tool_calls:
                try:
                    func = tool_call.function
                    
                    parameters = json.loads(func.arguments)

                    func_ret = await self.ap.tool_mgr.execute_func_call(
                        query, func.name, parameters
                    )

                    msg = llm_entities.Message(
                        role="tool", content=json.dumps(func_ret, ensure_ascii=False), tool_call_id=tool_call.id
                    )

                    yield msg

                    req_messages.append(msg)
                except Exception as e:
                    # 工具调用出错，添加一个报错信息到 req_messages
                    err_msg = llm_entities.Message(
                        role="tool", content=f"err: {e}", tool_call_id=tool_call.id
                    )

                    yield err_msg

                    req_messages.append(err_msg)

            # 处理完所有调用，再次请求
            try:
                msg = await query.use_model.requester.call(query.use_model, req_messages, query.use_funcs)
                if "answer" not in msg.content:
                    raise ValueError("请求失败：返回内容不含answer")
            except Exception as e:
                err_msg = llm_entities.Message(
                    role="system", content=f"请求失败：{e}"
                )
                yield err_msg
                return

            yield msg

            pending_tool_calls = msg.tool_calls

            req_messages.append(msg)