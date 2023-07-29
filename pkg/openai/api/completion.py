import openai

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
        model: str,
        messages: list[dict[str, str]],
        **kwargs
    ):
        self.model = model
        self.prompt = ""
        
        for message in messages:
            self.prompt += message["role"] + ": " + message["content"] + "\n"
        
        self.prompt += "assistant: "

        self.kwargs = kwargs

        self.req_func = openai.Completion.acreate

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

        resp = self._req(
            model=self.model,
            prompt=self.prompt,
            **self.kwargs
        )

        if resp["choices"][0]["finish_reason"] == "stop":
            self.stopped = True

        choice0 = resp["choices"][0]

        self.prompt += choice0["text"]

        return {
            "id": resp["id"],
            "choices": [
                {
                    "index": choice0["index"],
                    "message": {
                        "role": "assistant",
                        "type": "text",
                        "content": choice0["text"]
                    },
                    "finish_reason": choice0["finish_reason"]
                }
            ],
            "usage": resp["usage"]
        }
        
if __name__ == "__main__":
    import os

    openai.api_key = os.environ["OPENAI_API_KEY"]

    for resp in CompletionRequest(
        model="text-davinci-003",
        messages=[
            {
                "role": "user",
                "content": "Hello, who are you?"
            }
        ]
    ):
        print(resp)
        if resp["choices"][0]["finish_reason"] == "stop":
            break
