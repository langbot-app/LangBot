from __future__ import annotations

import tiktoken

from .. import tokenizer
from ... import entities as llm_entities
from .. import entities


class Tiktoken(tokenizer.LLMTokenizer):

    async def count_token(
        self,
        messages: list[llm_entities.Message],
        model: entities.LLMModelInfo
    ) -> int:
        try:
            encoding = tiktoken.encoding_for_model(model.name)
        except KeyError:
            print("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")

        num_tokens = 0
        for message in messages:
                num_tokens += len(encoding.encode(message.role))
                num_tokens += len(encoding.encode(message.content if message.content is not None else ''))
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return num_tokens
