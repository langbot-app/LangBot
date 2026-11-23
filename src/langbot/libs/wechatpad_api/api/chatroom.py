from langbot.libs.wechatpad_api.util.http_util import post_json


class ChatRoomApi:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token

    def get_chatroom_member_detail(self, chatroom_name):
        params = {'ChatRoomName': chatroom_name}
        url = self.base_url + '/group/GetChatroomMemberDetail'
        return post_json(url, token=self.token, data=params)
