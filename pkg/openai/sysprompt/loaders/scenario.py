from __future__ import annotations

import json
import os

from .. import loader
from .. import entities
from ....openai import entities as llm_entities


class ScenarioPromptLoader(loader.PromptLoader):
    """加载scenario目录下的json"""

    async def load(self):
        """加载Prompt
        """
        for file in os.listdir("scenarios"):
            with open("scenarios/{}".format(file), "r", encoding="utf-8") as f:
                file_str = f.read()
                file_name = file.split(".")[0]
                file_json = json.loads(file_str)
                messages = []
                for msg in file_json["prompt"]:
                    role = 'system'
                    if "role" in msg:
                        role = msg['role']
                    messages.append(
                        llm_entities.Message(
                            role=role,
                            content=msg['content'],
                        )
                    )
                prompt = entities.Prompt(
                    name=file_name,
                    messages=messages
                )
                self.prompts.append(prompt)
        