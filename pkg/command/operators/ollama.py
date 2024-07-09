from __future__ import annotations

import json
import typing

import ollama
from .. import operator, entities


@operator.operator_class(
    name="ollama",
    help="ollama平台操作",
    usage="!ollama\n!ollama show <模型名>\n!ollama pull <模型名>\n!ollama del <模型名>"
)
class OllamaOperator(operator.CommandOperator):
    async def execute(
            self, context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        content: str = '模型列表:\n'
        model_list: list = ollama.list().get('models', [])
        for model in model_list:
            content += f"name: {model['name']}\n"
            content += f"modified_at: {model['modified_at']}\n"
            content += f"size: {bytes_to_mb(model['size'])}MB\n\n"
        yield entities.CommandReturn(text=f"{content.strip()}")


def bytes_to_mb(num_bytes):
    mb: float = num_bytes / 1024 / 1024
    return format(mb, '.2f')


@operator.operator_class(
    name="show",
    help="ollama模型详情",
    privilege=2,
    parent_class=OllamaOperator
)
class OllamaShowOperator(operator.CommandOperator):
    async def execute(
            self, context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        content: str = '模型详情:\n'
        try:
            show: dict = ollama.show(model=context.crt_params[0])
            model_info: dict = show.get('model_info', {})
            ignore_show: str = 'too long to show...'

            for key in ['license', 'modelfile']:
                show[key] = ignore_show

            for key in ['tokenizer.chat_template.rag', 'tokenizer.chat_template.tool_use']:
                model_info[key] = ignore_show

            content += json.dumps(show, indent=4)
        except ollama.ResponseError as e:
            content = f"{e.error}"

        yield entities.CommandReturn(text=content.strip())


@operator.operator_class(
    name="pull",
    help="ollama模型拉取",
    privilege=2,
    parent_class=OllamaOperator
)
class OllamaPullOperator(operator.CommandOperator):
    async def execute(
            self, context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        model_list: list = ollama.list().get('models', [])
        if context.crt_params[0] in [model['name'] for model in model_list]:
            yield entities.CommandReturn(text="模型已存在")
            return

        on_progress: bool = False
        progress_count: int = 0
        try:
            for resp in ollama.pull(model=context.crt_params[0], stream=True):
                total: typing.Any = resp.get('total')
                if not on_progress:
                    if total is not None:
                        on_progress = True
                    yield entities.CommandReturn(text=resp.get('status'))
                else:
                    if total is None:
                        on_progress = False

                    completed: typing.Any = resp.get('completed')
                    if isinstance(completed, int) and isinstance(total, int):
                        percentage_completed = (completed / total) * 100
                        if percentage_completed > progress_count:
                            progress_count += 10
                            yield entities.CommandReturn(
                                text=f"下载进度: {completed}/{total} ({percentage_completed:.2f}%)")
        except ollama.ResponseError as e:
            yield entities.CommandReturn(text=f"拉取失败: {e.error}")


@operator.operator_class(
    name="del",
    help="ollama模型删除",
    privilege=2,
    parent_class=OllamaOperator
)
class OllamaDelOperator(operator.CommandOperator):
    async def execute(
            self, context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        try:
            ret: str = ollama.delete(model=context.crt_params[0])['status']
        except ollama.ResponseError as e:
            ret = f"{e.error}"
        yield entities.CommandReturn(text=ret)
