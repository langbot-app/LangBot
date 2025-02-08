from __future__ import annotations

import re
import asyncio
import typing
import dashscope

from .. import entities, errors, requester
from ....core import entities as core_entities, app
from ... import entities as llm_entities
from ...tools import entities as tools_entities

#阿里云百炼平台的自定义应用支持资料引用，此函数可以将引用标签替换为参考资料
def replace_references(text, references_dict):
    # 修正正则表达式，匹配 <ref>[index_id]</ref> 形式的字符串
    pattern = re.compile(r'<ref>\[(.*?)\]</ref>')

    def replacement(match):
        ref_key = match.group(1)  # 获取引用编号
        if ref_key in references_dict:
            return f"（参考资料来自：{references_dict[ref_key]}）"
        else:
            return match.group(0)  # 如果没有对应的参考资料，保留原样

    # 使用 re.sub() 进行替换
    return pattern.sub(replacement, text)


@requester.requester_class("dashscope-chat-applications")
class DashscopeChatApplication(requester.LLMAPIRequester):
    """Dashscope ChatApplications API 请求器"""
    
    requester_cfg: dict

    def __init__(self, ap: app.Application):
        self.requester_cfg = ap.provider_cfg.data['requester']['dashscope-chat-applications']
        self.ap = ap

    async def initialize(self):
        dashscope.api_key = self.ap.provider_cfg.data['keys']['dashscope'][0]

    async def _req(self, args: dict):
        
        #print("args:", args)
        
        #局部变量
        chunk = None
        pending_content = ""
        output = {
            "role": "assistant",
            "content": "",
            "tool_calls": [], 
            "tool_call_id": None  # Dashscope暂时不支持工具调用
        }   #由于Dashscope的content的键值是text，所以需要定义一个新格式的字典适配llm_entities.Message
        
        references_dict = {}  # 用于存储引用编号和对应的参考资料
        
        #调用API
        response = dashscope.Application.call(
            api_key=dashscope.api_key,
            app_id=args["model"],
            prompt=args["messages"],
            stream=True,  # 设置流式输出
            tools=args.get("tools", None),
            incremental_output = True,
        )

        #处理API返回的流式输出
        for chunk in response:
            #print(chunk)
            if not chunk:
                continue
            
            #获取流式传输的output
            stream_output = chunk.get("output", {})
            if stream_output.get("text") is not None:
                pending_content += stream_output.get("text")
        

        #获取模型传出的参考资料列表
        references_dict_list = stream_output.get("doc_references", [])
        
        #从模型传出的参考资料信息中提取用于替换的字典
        if references_dict_list is not None:
            for doc in references_dict_list:
                if doc.get("index_id") is not None:
                    references_dict[doc.get("index_id")] = doc.get("doc_name")

            #将参考资料替换到文本中
            pending_content = replace_references(pending_content, references_dict)
        
        #将流式传输的内容整合到output中
        output["content"] = pending_content
        
        return output if chunk else None

    async def _make_msg(
        self,
        chat_completion: dict,
    ) -> llm_entities.Message:
        chatcmpl_message = chat_completion

        # 确保 role 字段存在且不为 None
        if 'role' not in chatcmpl_message or chatcmpl_message['role'] is None:
            chatcmpl_message['role'] = 'assistant'

        message = llm_entities.Message(**chatcmpl_message)
        #print("message:", message)
        return message

    async def _closure(
        self,
        query: core_entities.Query,
        req_messages: list[dict],
        use_model: entities.LLMModelInfo,
        use_funcs: list[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:

        args = self.requester_cfg['args'].copy()
        args["model"] = use_model.name if use_model.model_name is None else use_model.model_name

        # 设置此次请求中的messages
        messages = req_messages.copy()
        
        # 检查vision
        for msg in messages:
            if 'content' in msg and isinstance(msg["content"], list):
                for me in msg["content"]:
                    if me["type"] == "image_base64":
                        me["image_url"] = {
                            "url": me["image_base64"]
                        }
                        me["type"] = "image_url"
                        del me["image_base64"]

        args["messages"] = messages

        # 发送请求
        resp = await self._req(args)

        # 处理请求结果
        message = await self._make_msg(resp)

        return message
    
    async def call(
        self,
        query: core_entities.Query,
        model: entities.LLMModelInfo,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        req_messages = []  # req_messages 仅用于类内，外部同步由 query.messages 进行
        for m in messages:
            msg_dict = m.dict(exclude_none=True)
            content = msg_dict.get("content")
            if isinstance(content, list):
                # 检查 content 列表中是否每个部分都是文本
                if all(isinstance(part, dict) and part.get("type") == "text" for part in content):
                    # 将所有文本部分合并为一个字符串
                    msg_dict["content"] = "\n".join(part["text"] for part in content)
            req_messages.append(msg_dict)

        try:
            return await self._closure(query=query, req_messages=req_messages, use_model=model, use_funcs=funcs)
        except asyncio.TimeoutError:
            raise errors.RequesterError('请求超时')
