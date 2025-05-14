from __future__ import annotations
import os
import traceback


from . import strategy
from .. import stage, entities
from ...core import entities as core_entities
from ...platform.types import message as platform_message
from ...utils import importutil

from . import strategies

importutil.import_modules_in_pkg(strategies)


@stage.stage_class('LongTextProcessStage')
class LongTextProcessStage(stage.PipelineStage):
    """长消息处理阶段

    改写：
        - resp_message_chain
    """

    strategy_impl: strategy.LongTextStrategy

    async def initialize(self, pipeline_config: dict):
        config = pipeline_config['output']['long-text-processing']
        if config['strategy'] == 'image':
            use_font = config['font-path']
            try:
                # 检查是否存在
                if not os.path.exists(use_font):
                    # 若是windows系统，使用微软雅黑
                    if os.name == 'nt':
                        use_font = 'C:/Windows/Fonts/msyh.ttc'
                        if not os.path.exists(use_font):
                            self.ap.logger.warn(
                                '未找到字体文件，且无法使用Windows自带字体，更换为转发消息组件以发送长消息，您可以在配置文件中调整相关设置。'
                            )
                            config['blob_message_strategy'] = 'forward'
                        else:
                            self.ap.logger.info('使用Windows自带字体：' + use_font)
                            config['font-path'] = use_font
                    else:
                        self.ap.logger.warn(
                            '未找到字体文件，且无法使用系统自带字体，更换为转发消息组件以发送长消息，您可以在配置文件中调整相关设置。'
                        )

                        pipeline_config['output']['long-text-processing']['strategy'] = 'forward'
            except Exception:
                traceback.print_exc()
                self.ap.logger.error(
                    '加载字体文件失败({})，更换为转发消息组件以发送长消息，您可以在配置文件中调整相关设置。'.format(
                        use_font
                    )
                )

                pipeline_config['output']['long-text-processing']['strategy'] = 'forward'

        for strategy_cls in strategy.preregistered_strategies:
            if strategy_cls.name == config['strategy']:
                self.strategy_impl = strategy_cls(self.ap)
                break
        else:
            raise ValueError(f'未找到名为 {config["strategy"]} 的长消息处理策略')

        await self.strategy_impl.initialize()

    async def process(self, query: core_entities.Query, stage_inst_name: str) -> entities.StageProcessResult:
        # 检查是否包含非 Plain 组件
        contains_non_plain = False

        for msg in query.resp_message_chain[-1]:
            if not isinstance(msg, platform_message.Plain):
                contains_non_plain = True
                break

        if contains_non_plain:
            self.ap.logger.debug('消息中包含非 Plain 组件，跳过长消息处理。')
        elif (
            len(str(query.resp_message_chain[-1]))
            > query.pipeline_config['output']['long-text-processing']['threshold']
        ):
            query.resp_message_chain[-1] = platform_message.MessageChain(
                await self.strategy_impl.process(str(query.resp_message_chain[-1]), query)
            )

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
