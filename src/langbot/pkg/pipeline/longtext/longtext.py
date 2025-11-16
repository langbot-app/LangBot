from __future__ import annotations
import os
import traceback


from . import strategy
from .. import stage, entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from ...utils import importutil
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from . import strategies

importutil.import_modules_in_pkg(strategies)


@stage.stage_class('LongTextProcessStage')
class LongTextProcessStage(stage.PipelineStage):
    """Long message processing stage

    Rewrite:
        - resp_message_chain
    """

    strategy_impl: strategy.LongTextStrategy | None

    async def initialize(self, pipeline_config: dict):
        config = pipeline_config['output']['long-text-processing']

        if config['strategy'] == 'none':
            self.strategy_impl = None
            return

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
                                'Font file not found, and Windows system font cannot be used, switch to forward message component to send long messages, you can adjust the related settings in the configuration file.'
                            )
                            config['blob_message_strategy'] = 'forward'
                        else:
                            self.ap.logger.info('Using Windows system font: ' + use_font)
                            config['font-path'] = use_font
                    else:
                        self.ap.logger.warn(
                            'Font file not found, and system font cannot be used, switch to forward message component to send long messages, you can adjust the related settings in the configuration file.'
                        )

                        pipeline_config['output']['long-text-processing']['strategy'] = 'forward'
            except Exception:
                traceback.print_exc()
                self.ap.logger.error(
                    'Failed to load font file ({}), switch to forward message component to send long messages, you can adjust the related settings in the configuration file.'.format(
                        use_font
                    )
                )

                pipeline_config['output']['long-text-processing']['strategy'] = 'forward'

        for strategy_cls in strategy.preregistered_strategies:
            if strategy_cls.name == config['strategy']:
                self.strategy_impl = strategy_cls(self.ap)
                break
        else:
            raise ValueError(f'Long message processing strategy not found: {config["strategy"]}')

        await self.strategy_impl.initialize()

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        if self.strategy_impl is None:
            self.ap.logger.debug('Long message processing strategy is not set, skip long message processing.')
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        # 检查是否包含非 Plain 组件
        contains_non_plain = False

        for msg in query.resp_message_chain[-1]:
            if not isinstance(msg, platform_message.Plain):
                contains_non_plain = True
                break

        if contains_non_plain:
            self.ap.logger.debug('Message contains non-Plain components, skip long message processing.')
        elif (
            len(str(query.resp_message_chain[-1]))
            > query.pipeline_config['output']['long-text-processing']['threshold']
        ):
            query.resp_message_chain[-1] = platform_message.MessageChain(
                await self.strategy_impl.process(str(query.resp_message_chain[-1]), query)
            )

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
