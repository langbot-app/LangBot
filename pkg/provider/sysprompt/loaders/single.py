from __future__ import annotations
import os

from .. import loader
from .. import entities
from ....provider import entities as llm_entities


@loader.loader_class("normal")
class SingleSystemPromptLoader(loader.PromptLoader):
    """配置文件中的单条system prompt的prompt加载器
    """

    async def load(self):
        """加载Prompt
        """
        
        for name, cnt in self.ap.provider_cfg.data['prompt'].items():
            prompt = entities.Prompt(
                name=name,
                messages=[
                    llm_entities.Message(
                        role='system',
                        content=cnt
                    )
                ]
            )
            self.prompts.append(prompt)

        for file in os.listdir("data/prompts"):
            with open("data/prompts/{}".format(file), "r", encoding="utf-8") as f:
                file_str = f.read()
                file_name = file.split(".")[0]
                prompt = entities.Prompt(
                    name=file_name,
                    messages=[
                        llm_entities.Message(
                            role='system',
                            content=file_str
                        )
                    ]
                )
                self.prompts.append(prompt)
