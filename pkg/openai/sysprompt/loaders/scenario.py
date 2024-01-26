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
                    role = llm_entities.MessageRole.SYSTEM
                    if "role" in msg:
                        if msg["role"] == "user":
                            role = llm_entities.MessageRole.USER
                        elif msg["role"] == "system":
                            role = llm_entities.MessageRole.SYSTEM
                        elif msg["role"] == "function":
                            role = llm_entities.MessageRole.FUNCTION
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
        