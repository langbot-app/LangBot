from langbot.libs.wechatpad_api.api.login import LoginApi
from langbot.libs.wechatpad_api.api.friend import FriendApi
from langbot.libs.wechatpad_api.api.message import MessageApi
from langbot.libs.wechatpad_api.api.user import UserApi
from langbot.libs.wechatpad_api.api.downloadpai import DownloadApi
from langbot.libs.wechatpad_api.api.chatroom import ChatRoomApi


class WeChatPadClient:
    def __init__(self, base_url, token, logger=None):
        self._login_api = LoginApi(base_url, token)
        self._friend_api = FriendApi(base_url, token)
        self._message_api = MessageApi(base_url, token)
        self._user_api = UserApi(base_url, token)
        self._download_api = DownloadApi(base_url, token)
        self._chatroom_api = ChatRoomApi(base_url, token)
        self.logger = logger

    def get_token(self, admin_key, day: int):
        """获取token"""
        return self._login_api.get_token(admin_key, day)

    def get_login_qr(self, Proxy: str = ''):
        """登录二维码"""
        return self._login_api.get_login_qr(Proxy=Proxy)

    def awaken_login(self, Proxy: str = ''):
        """唤醒登录"""
        return self._login_api.wake_up_login(Proxy=Proxy)

    def log_out(self):
        """退出登录"""
        return self._login_api.logout()

    def get_login_status(self):
        """获取登录状态"""
        return self._login_api.get_login_status()

    def send_text_message(self, to_wxid, message, ats: list = []):
        """发送文本消息"""
        return self._message_api.post_text(to_wxid, message, ats)

    def send_image_message(self, to_wxid, img_url, ats: list = []):
        """发送图片消息"""
        return self._message_api.post_image(to_wxid, img_url, ats)

    def send_voice_message(self, to_wxid, voice_data, voice_forma, voice_duration):
        """发送音频消息"""
        return self._message_api.post_voice(to_wxid, voice_data, voice_forma, voice_duration)

    def send_app_message(self, to_wxid, app_message, type):
        """发送app消息"""
        return self._message_api.post_app_msg(to_wxid, app_message, type)

    def send_emoji_message(self, to_wxid, emoji_md5, emoji_size):
        """发送emoji消息"""
        return self._message_api.post_emoji(to_wxid, emoji_md5, emoji_size)

    def revoke_msg(self, to_wxid, msg_id, new_msg_id, create_time):
        """撤回消息"""
        return self._message_api.revoke_msg(to_wxid, msg_id, new_msg_id, create_time)

    def get_profile(self):
        """获取用户信息"""
        return self._user_api.get_profile()

    def get_qr_code(self, recover: bool = True, style: int = 8):
        """获取用户二维码"""
        return self._user_api.get_qr_code(recover=recover, style=style)

    def get_safety_info(self):
        """获取设备信息"""
        return self._user_api.get_safety_info()

    def update_head_img(self, head_img_base64):
        """上传用户头像"""
        return self._user_api.update_head_img(head_img_base64)

    def cdn_download(self, aeskey, file_type, file_url):
        """cdn下载"""
        return self._download_api.send_download(aeskey, file_type, file_url)

    def get_msg_voice(self, buf_id, length, msgid):
        """下载语音"""
        return self._download_api.get_msg_voice(buf_id, length, msgid)

    async def download_base64(self, url):
        return await self._download_api.download_url_to_base64(download_url=url)

    def get_chatroom_member_detail(self, chatroom_name):
        """查看群成员详情"""
        return self._chatroom_api.get_chatroom_member_detail(chatroom_name)
