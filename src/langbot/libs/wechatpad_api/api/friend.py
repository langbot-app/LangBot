from langbot.libs.wechatpad_api.util.http_util import post_json


class FriendApi:
    """联系人API类，处理所有与联系人相关的操作"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token

    def accept_friend_request(self, scene: int, v3: str, v4: str, chatroom_username: str = ''):
        """Accept an incoming friend request."""
        url = f'{self.base_url}/friend/AgreeAdd'
        data = {
            'ChatRoomUserName': chatroom_username,
            'OpCode': 3,
            'Scene': scene,
            'V3': v3,
            'V4': v4,
            'VerifyContent': '',
        }
        return post_json(base_url=url, token=self.token, data=data)
