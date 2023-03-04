# 敏感词过滤模块
import re
import requests
import json
from config import baidu_check, baidu_api_key, baidu_secret_key, illgalmessage
import logging


# 然后可以通过config.check, config.baidu_api_key等方式来使用这些变量。

def get_access_token():
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {"grant_type": "client_credentials", "client_id": baidu_api_key,
              "client_secret": baidu_secret_key}
    return str(requests.post(url, params=params).json().get("access_token"))


# 百度云审核URL
baidu_url = "https://aip.baidubce.com/rest/2.0/solution/v1/text_censor/v2/user_defined?access_token=" \
            + get_access_token()


class ReplyFilter:
    sensitive_words = []

    def __init__(self, sensitive_words: list):
        self.sensitive_words = sensitive_words

    def process(self, message: str) -> str:
        # 百度云审核
        if baidu_check:
            # 百度云审核
            payload = "text=" + message
            logging.info("向百度云发送:" + payload)
            headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
            response = requests.request("POST", baidu_url, headers=headers, data=payload.encode('utf-8'))
            response_dict = json.loads(response.text)
            # 处理百度云审核结果
            if "error_code" in response_dict:
                error_msg = response_dict.get("error_msg")
                logging.info(f"百度云判定出错，错误信息：{error_msg}")
                conclusion = f"百度云判定出错，错误信息：{error_msg}\n以下是原消息：{message}"
            else:
                conclusion = response_dict["conclusion"]
                if conclusion in ("合规"):
                    logging.info(f"百度云判定结果：{conclusion}")
                    return message
                else:
                    logging.info(f"百度云判定结果：{conclusion}")
                    conclusion = illgalmessage
            # 返回百度云审核结果
            return conclusion

        # 本地关键词屏蔽
        for word in self.sensitive_words:
            match = re.findall(word, message)
            if len(match) > 0:
                for i in range(len(match)):
                    message = message.replace(match[i], "*" * len(match[i]))
        return message
