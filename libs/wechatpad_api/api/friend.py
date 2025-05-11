from libs.wechatpad_api.util.http_util import post_json,async_request
from typing import List, Dict, Any, Optional


class FriendApi:
    """联系人API类，处理所有与联系人相关的操作"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token

