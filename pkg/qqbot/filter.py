# 敏感词过滤模块
import re


class ReplyFilter:

    sensitive_words = []

    def __init__(self, sensitive_words: list):
        self.sensitive_words = sensitive_words

    def process(self, message: str) -> str:
        for word in self.sensitive_words:
            match = re.findall(word, message)
            if len(match) > 0:
                for i in range(len(match)):
                    message = message.replace(match[i], "*" * len(match[i]))

        return message
