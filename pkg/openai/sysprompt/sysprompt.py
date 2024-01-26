from __future__ import annotations

from ...core import app
from . import loader
from .loaders import single, scenario


class PromptManager:

    ap: app.Application

    loader_inst: loader.PromptLoader

    default_prompt: str = 'default'

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):

        loader_map = {
            "normal": single.SingleSystemPromptLoader,
            "full_scenario": scenario.ScenarioPromptLoader
        }

        loader_cls = loader_map[self.ap.cfg_mgr.data['preset_mode']]

        self.loader_inst: loader.PromptLoader = loader_cls(self.ap)

        await self.loader_inst.initialize()
        await self.loader_inst.load()

    def get_all_prompts(self) -> list[loader.entities.Prompt]:
        """获取所有Prompt
        """
        return self.loader_inst.get_prompts()
    
    async def  get_prompt(self, name: str) -> loader.entities.Prompt:
        """获取Prompt
        """
        for prompt in self.get_all_prompts():
            if prompt.name == name:
                return prompt
