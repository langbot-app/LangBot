import openai
from openai.types import completion, completion_choice

from .model import RequestBase


class CompletionRequest(RequestBase):
    """调用Completion接口的请求类。
    
    调用方可以一直next completion直到finish_reason为stop。
    """

    model: str
    prompt: str
    kwargs: dict

    stopped: bool = False

    def __init__(
        self,
        client: openai.Client,
        model: str,
        messages: list[dict[str, str]],
        **kwargs
    ):
        self.client = client
        self.model = model
        self.prompt = ""
        
        for message in messages:
            self.prompt += message["role"] + ": " + message["content"] + "\n"
        
        self.prompt += "assistant: "

        self.kwargs = kwargs

        self.req_func = self.client.completions.create

    def __iter__(self):
        return self

    def __next__(self) -> dict:
        """调用Completion接口，返回生成的文本
        
        {
            "id": "id",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "type": "text",
                        "content": "message"
                    },
                    "finish_reason": "reason"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        """

        if self.stopped:
            raise StopIteration()

        resp: completion.Completion = self._req(
            model=self.model,
            prompt=self.prompt,
            **self.kwargs
        )

        if resp.choices[0].finish_reason == "stop":
            self.stopped = True

        choice0: completion_choice.CompletionChoice = resp.choices[0]

        self.prompt += choice0.text

        return {
            "id": resp.id,
            "choices": [
                {
                    "index": choice0.index,
                    "message": {
                        "role": "assistant",
                        "type": "text",
                        "content": choice0.text
                    },
                    "finish_reason": choice0.finish_reason
                }
            ],
            "usage": {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens
            }
        }
