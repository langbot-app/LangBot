from __future__ import annotations

import typing
import traceback

from .. import operator, entities, cmdmgr, errors


@operator.operator_class(
    name="default",
    help="操作情景预设",
    usage='!default\n!default set <指定情景预设为默认>'
)
class DefaultOperator(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        
        reply_str = "当前所有情景预设: \n\n"

        for prompt in self.ap.prompt_mgr.get_all_prompts():

            content = ""
            for msg in prompt.messages:
                content += f"  {msg.role}: {msg.content}"

            reply_str += f"名称: {prompt.name}\n内容: \n{content}\n\n"

        reply_str += f"当前会话使用的是: {context.session.use_prompt_name}"

        yield entities.CommandReturn(text=reply_str.strip())


@operator.operator_class(
    name="set",
    help="设置当前会话默认情景预设",
    parent_class=DefaultOperator
)
class DefaultSetOperator(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
            
            if len(context.crt_params) == 0:
                yield entities.CommandReturn(error=errors.ParamNotEnoughError('请提供情景预设名称'))
            else:
                prompt_name = context.crt_params[0]
        
                try:
                    prompt = await self.ap.prompt_mgr.get_prompt_by_prefix(prompt_name)
                    if prompt is None:
                        yield entities.CommandReturn(error=errors.CommandError("设置当前会话默认情景预设失败: 未找到情景预设 {}".format(prompt_name)))
                    else:
                        context.session.use_prompt_name = prompt.name
                        yield entities.CommandReturn(text=f"已设置当前会话默认情景预设为 {prompt_name}, !reset 后生效")
                except Exception as e:
                    traceback.print_exc()
                    yield entities.CommandReturn(error=errors.CommandError("设置当前会话默认情景预设失败: "+str(e)))
