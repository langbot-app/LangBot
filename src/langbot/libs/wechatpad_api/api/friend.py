class FriendApi:
    """联系人API类，处理所有与联系人相关的操作"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
