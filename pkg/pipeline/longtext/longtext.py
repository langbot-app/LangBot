from __future__ import annotations
import os
import traceback

from PIL import Image, ImageDraw, ImageFont
from mirai.models.message import MessageComponent, Plain, MessageChain

from ...core import app
from . import strategy
from .strategies import image, forward
from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...config import manager as cfg_mgr


@stage.stage_class("LongTextProcessStage")
class LongTextProcessStage(stage.PipelineStage):

    strategy_impl: strategy.LongTextStrategy

    async def initialize(self):
        config = self.ap.platform_cfg.data['long-text-process']
        if config['strategy'] == 'image':
            use_font = config['font-path']
            try:
                # 检查是否存在
                if not os.path.exists(use_font):
                    # 若是windows系统，使用微软雅黑
                    if os.name == "nt":
                        use_font = "C:/Windows/Fonts/msyh.ttc"
                        if not os.path.exists(use_font):
                            self.ap.logger.warn("未找到字体文件，且无法使用Windows自带字体，更换为转发消息组件以发送长消息，您可以在config.py中调整相关设置。")
                            config['blob_message_strategy'] = "forward"
                        else:
                            self.ap.logger.info("使用Windows自带字体：" + use_font)
                            config['font-path'] = use_font
                    else:
                        self.ap.logger.warn("未找到字体文件，且无法使用系统自带字体，更换为转发消息组件以发送长消息，您可以在config.py中调整相关设置。")

                        self.ap.platform_cfg.data['long-text-process']['strategy'] = "forward"
            except:
                traceback.print_exc()
                self.ap.logger.error("加载字体文件失败({})，更换为转发消息组件以发送长消息，您可以在config.py中调整相关设置。".format(use_font))

                self.ap.platform_cfg.data['long-text-process']['strategy'] = "forward"
        
        if config['strategy'] == 'image':
            self.strategy_impl = image.Text2ImageStrategy(self.ap)
        elif config['strategy'] == 'forward':
            self.strategy_impl = forward.ForwardComponentStrategy(self.ap)
        await self.strategy_impl.initialize()
    
    async def process(self, query: core_entities.Query, stage_inst_name: str) -> entities.StageProcessResult:
        if len(str(query.resp_message_chain)) > self.ap.platform_cfg.data['long-text-process']['threshold']:
            query.resp_message_chain = MessageChain(await self.strategy_impl.process(str(query.resp_message_chain)))
        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE,
            new_query=query
        )
