from libs.wechatpad_api.util.http_util import async_request, post_json

class DownloadApi:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token

    def send_download(self, aeskey, file_type, file_url):
        json_data = {
                  "AesKey": aeskey,
                  "FileType": file_type,
                  "FileURL": file_url
                }
        url = self.base_url + "/message/SendCdnDownload"
        return post_json(url, token=self.token, data=json_data)

    def get_msg_voice(self,buf_id, length, new_msgid):
        json_data = {
            "Bufid": buf_id,
            "Length": length,
            "NewMsgId": new_msgid,
            "ToUserName": ""
        }
        url = self.base_url + "/message/GetMsgVoice"
        return post_json(url, token=self.token, data=json_data)