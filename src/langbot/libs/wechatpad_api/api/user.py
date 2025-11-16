from langbot.libs.wechatpad_api.util.http_util import post_json, async_request, get_json


class UserApi:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token

    def get_profile(self):
        """获取个人资料"""
        url = f'{self.base_url}/user/GetProfile'

        return get_json(base_url=url, token=self.token)

    def get_qr_code(self, recover: bool = True, style: int = 8):
        """获取自己的二维码"""
        param = {'Recover': recover, 'Style': style}
        url = f'{self.base_url}/user/GetMyQRCode'
        return post_json(base_url=url, token=self.token, data=param)

    def get_safety_info(self):
        """获取设备记录"""
        url = f'{self.base_url}/equipment/GetSafetyInfo'
        return post_json(base_url=url, token=self.token)

    async def update_head_img(self, head_img_base64):
        """修改头像"""
        param = {'Base64': head_img_base64}
        url = f'{self.base_url}/user/UploadHeadImage'
        return await async_request(base_url=url, token_key=self.token, json=param)
