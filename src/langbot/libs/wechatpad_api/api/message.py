from langbot.libs.wechatpad_api.util.http_util import post_json


class MessageApi:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token

    def post_text(self, to_wxid, content, ats: list = []):
        """

        Args:
            app_id: 微信id
            to_wxid: 发送方的微信id
            content: 内容
            ats: at

        Returns:

        """
        url = self.base_url + '/message/SendTextMessage'
        """发送文字消息"""
        json_data = {
            'MsgItem': [
                {'AtWxIDList': ats, 'ImageContent': '', 'MsgType': 0, 'TextContent': content, 'ToUserName': to_wxid}
            ]
        }
        return post_json(base_url=url, token=self.token, data=json_data)

    def post_image(self, to_wxid, img_url, ats: list = []):
        """发送图片消息"""
        # 这里好像可以尝试发送多个暂时未测试
        json_data = {
            'MsgItem': [
                {'AtWxIDList': ats, 'ImageContent': img_url, 'MsgType': 0, 'TextContent': '', 'ToUserName': to_wxid}
            ]
        }
        url = self.base_url + '/message/SendImageMessage'
        return post_json(base_url=url, token=self.token, data=json_data)

    def post_voice(self, to_wxid, voice_data, voice_forma, voice_duration):
        """发送语音消息"""
        json_data = {
            'ToUserName': to_wxid,
            'VoiceData': voice_data,
            'VoiceFormat': voice_forma,
            'VoiceSecond': voice_duration,
        }
        url = self.base_url + '/message/SendVoice'
        return post_json(base_url=url, token=self.token, data=json_data)

    def post_name_card(self, alias, to_wxid, nick_name, name_card_wxid, flag):
        """发送名片消息"""
        param = {
            'CardAlias': alias,
            'CardFlag': flag,
            'CardNickName': nick_name,
            'CardWxId': name_card_wxid,
            'ToUserName': to_wxid,
        }
        url = f'{self.base_url}/message/ShareCardMessage'
        return post_json(base_url=url, token=self.token, data=param)

    def post_emoji(self, to_wxid, emoji_md5, emoji_size: int = 0):
        """发送emoji消息"""
        json_data = {'EmojiList': [{'EmojiMd5': emoji_md5, 'EmojiSize': emoji_size, 'ToUserName': to_wxid}]}
        url = f'{self.base_url}/message/SendEmojiMessage'
        return post_json(base_url=url, token=self.token, data=json_data)

    def post_app_msg(self, to_wxid, xml_data, contenttype: int = 0):
        """发送appmsg消息"""
        json_data = {'AppList': [{'ContentType': contenttype, 'ContentXML': xml_data, 'ToUserName': to_wxid}]}
        url = f'{self.base_url}/message/SendAppMessage'
        return post_json(base_url=url, token=self.token, data=json_data)

    def revoke_msg(self, to_wxid, msg_id, new_msg_id, create_time):
        """撤回消息"""
        param = {'ClientMsgId': msg_id, 'CreateTime': create_time, 'NewMsgId': new_msg_id, 'ToUserName': to_wxid}
        url = f'{self.base_url}/message/RevokeMsg'
        return post_json(base_url=url, token=self.token, data=param)
