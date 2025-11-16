from langbot.libs.wechatpad_api.util.http_util import post_json
import httpx
import base64


class DownloadApi:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token

    def send_download(self, aeskey, file_type, file_url):
        json_data = {'AesKey': aeskey, 'FileType': file_type, 'FileURL': file_url}
        url = self.base_url + '/message/SendCdnDownload'
        return post_json(url, token=self.token, data=json_data)

    def get_msg_voice(self, buf_id, length, new_msgid):
        json_data = {'Bufid': buf_id, 'Length': length, 'NewMsgId': new_msgid, 'ToUserName': ''}
        url = self.base_url + '/message/GetMsgVoice'
        return post_json(url, token=self.token, data=json_data)

    async def download_url_to_base64(self, download_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)

            if response.status_code == 200:
                file_bytes = response.content
                base64_str = base64.b64encode(file_bytes).decode('utf-8')  # 返回字符串格式
                return base64_str
            else:
                raise Exception('获取文件失败')
