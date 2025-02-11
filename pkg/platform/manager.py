from __future__ import annotations

import json
import os
import sys
import logging
import asyncio
import traceback

from .sources import qqofficial

#     FriendMessage, Image, MessageChain, Plain
from ..platform import adapter as msadapter

from ..core import app, entities as core_entities
from ..plugin import events
from .types import message as platform_message
from .types import events as platform_events
from .types import entities as platform_entities

# 处理 3.4 移除了 YiriMirai 之后，插件的兼容性问题
from . import types as mirai
sys.modules['mirai'] = mirai


# 控制QQ消息输入输出的类
class PlatformManager:
    
    # adapter: msadapter.MessageSourceAdapter = None
    adapters: list[msadapter.MessageSourceAdapter] = []

    # modern
    ap: app.Application = None

    def __init__(self, ap: app.Application = None):

        self.ap = ap
        self.adapters = []
    
    async def initialize(self):

        from .sources import nakuru, aiocqhttp, qqbotpy, qqofficial, wecom, lark, discord, gewechat, officialaccount

        async def on_friend_message(event: platform_events.FriendMessage, adapter: msadapter.MessageSourceAdapter):

            await self.ap.query_pool.add_query(
                launcher_type=core_entities.LauncherTypes.PERSON,
                launcher_id=event.sender.id,
                sender_id=event.sender.id,
                message_event=event,
                message_chain=event.message_chain,
                adapter=adapter
            )

        async def on_group_message(event: platform_events.GroupMessage, adapter: msadapter.MessageSourceAdapter):

            await self.ap.query_pool.add_query(
                launcher_type=core_entities.LauncherTypes.GROUP,
                launcher_id=event.group.id,
                sender_id=event.sender.id,
                message_event=event,
                message_chain=event.message_chain,
                adapter=adapter
            )
        
        index = 0

        for adap_cfg in self.ap.platform_cfg.data['platform-adapters']:
            if adap_cfg['enable']:
                self.ap.logger.info(f'初始化平台适配器 {index}: {adap_cfg["adapter"]}')
                index += 1
                cfg_copy = adap_cfg.copy()
                del cfg_copy['enable']
                adapter_name = cfg_copy['adapter']
                del cfg_copy['adapter']

                found = False

                for adapter in msadapter.preregistered_adapters:
                    if adapter.name == adapter_name:
                        found = True
                        adapter_cls = adapter
                        
                        adapter_inst = adapter_cls(
                            cfg_copy,
                            self.ap
                        )
                        self.adapters.append(adapter_inst)

                        adapter_inst.register_listener(
                            platform_events.FriendMessage,
                            on_friend_message
                        )
                        adapter_inst.register_listener(
                            platform_events.GroupMessage,
                            on_group_message
                        )
                
                if not found:
                    raise Exception('platform.json 中启用了未知的平台适配器: ' + adapter_name)
                
        if len(self.adapters) == 0:
            self.ap.logger.warning('未运行平台适配器，请根据文档配置并启用平台适配器。')

    async def write_back_config(self, adapter_inst: msadapter.MessageSourceAdapter, config: dict):
        index = -2

        for i, adapter in enumerate(self.adapters):
            if adapter == adapter_inst:
                index = i
                break

        if index == -2:
            raise Exception('平台适配器未找到')

        # 只修改启用的适配器
        real_index = -1

        for i, adapter in enumerate(self.ap.platform_cfg.data['platform-adapters']):
            if adapter['enable']:
                index -= 1
                if index == -1:
                    real_index = i
                    break

        new_cfg = {
            'adapter': adapter_inst.name,
            'enable': True,
            **config
        }
        self.ap.platform_cfg.data['platform-adapters'][real_index] = new_cfg
        await self.ap.platform_cfg.dump_config()

    async def send(self, event: platform_events.MessageEvent, msg: platform_message.MessageChain, adapter: msadapter.MessageSourceAdapter):
        
        if self.ap.platform_cfg.data['at-sender'] and isinstance(event, platform_events.GroupMessage):

            msg.insert(
                0,
                platform_message.At(
                    event.sender.id
                )
            )

        await adapter.reply_message(
            event,
            msg,
            quote_origin=True if self.ap.platform_cfg.data['quote-origin'] else False
        )

    async def run(self):
        try:
            tasks = []
            for adapter in self.adapters:
                async def exception_wrapper(adapter: msadapter.MessageSourceAdapter):
                    try:
                        await adapter.run_async()
                    except Exception as e:
                        if isinstance(e, asyncio.CancelledError):
                            return
                        self.ap.logger.error('平台适配器运行出错: ' + str(e))
                        self.ap.logger.debug(f"Traceback: {traceback.format_exc()}")

                tasks.append(exception_wrapper(adapter))
            
            for task in tasks:
                self.ap.task_mgr.create_task(
                    task,
                    kind="platform-adapter",
                    name=f"platform-adapter-{adapter.name}",
                    scopes=[core_entities.LifecycleControlScope.APPLICATION, core_entities.LifecycleControlScope.PLATFORM],
                )

        except Exception as e:
            self.ap.logger.error('平台适配器运行出错: ' + str(e))
            self.ap.logger.debug(f"Traceback: {traceback.format_exc()}")
    
    async def shutdown(self):
        for adapter in self.adapters:
            await adapter.kill()
        self.ap.task_mgr.cancel_by_scope(core_entities.LifecycleControlScope.PLATFORM)