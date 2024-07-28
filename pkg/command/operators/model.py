from __future__ import annotations

import typing

from .. import operator, entities, cmdmgr, errors

@operator.operator_class(
    name="model",
    help='显示和切换模型列表',
    usage='!model\n!model show <模型名>\n!model set <模型名>',
    privilege=2
)
class ModelOperator(operator.CommandOperator):
    """Model命令"""
    
    async def execute(self, context: entities.ExecuteContext) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        content = '模型列表:\n'

        model_list = self.ap.model_mgr.model_list

        for model in model_list:
            content += f"\n名称: {model.name}\n"
            content += f"请求器: {model.requester.name}\n"

        content += f"\n当前对话使用模型: {context.query.use_model.name}\n"
        content += f"新对话默认使用模型: {self.ap.provider_cfg.data.get('model')}\n"

        yield entities.CommandReturn(text=content.strip())


@operator.operator_class(
    name="show",
    help='显示模型详情',
    privilege=2,
    parent_class=ModelOperator
)
class ModelShowOperator(operator.CommandOperator):
    """Model Show命令"""
    
    async def execute(self, context: entities.ExecuteContext) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        model_name = context.crt_params[0]

        model = None
        for _model in self.ap.model_mgr.model_list:
            if model_name == _model.name:
                model = _model
                break

        if model is None:
            yield entities.CommandReturn(error=errors.CommandError(f"未找到模型 {model_name}"))
        else:
            content = f"模型详情\n"
            content += f"名称: {model.name}\n"
            if model.model_name is not None:
                content += f"请求模型名称: {model.model_name}\n"
            content += f"请求器: {model.requester.name}\n"
            content += f"密钥组: {model.token_mgr.provider}\n"
            content += f"支持视觉: {model.vision_supported}\n"
            content += f"支持工具: {model.tool_call_supported}\n"

            yield entities.CommandReturn(text=content.strip())

@operator.operator_class(
    name="set",
    help='设置默认使用模型',
    privilege=2,
    parent_class=ModelOperator
)
class ModelSetOperator(operator.CommandOperator):
    """Model Set命令"""
    
    async def execute(self, context: entities.ExecuteContext) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        model_name = context.crt_params[0]

        model = None
        for _model in self.ap.model_mgr.model_list:
            if model_name == _model.name:
                model = _model
                break

        if model is None:
            yield entities.CommandReturn(error=errors.CommandError(f"未找到模型 {model_name}"))
        else:
            self.ap.provider_cfg.data['model'] = model_name
            await self.ap.provider_cfg.dump_config()
            yield entities.CommandReturn(text=f"已设置当前使用模型为 {model_name}，重置会话以生效")
