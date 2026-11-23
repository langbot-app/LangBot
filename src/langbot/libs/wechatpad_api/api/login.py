from langbot.libs.wechatpad_api.util.http_util import post_json, get_json


class LoginApi:
    def __init__(self, base_url: str, token: str = None, admin_key: str = None):
        """

        Args:
            base_url: 原始路径
            token: token
            admin_key: 管理员key
        """
        self.base_url = base_url
        self.token = token
        # self.admin_key = admin_key

    def get_token(self, admin_key, day: int = 365):
        # 获取普通token
        url = f'{self.base_url}/admin/GenAuthKey1'
        json_data = {'Count': 1, 'Days': day}
        return post_json(base_url=url, token=admin_key, data=json_data)

    def get_login_qr(self, Proxy: str = ''):
        """

        Args:
            Proxy:异地使用时代理

        Returns:json数据

        """
        """
        
        {
  "Code": 200,
  "Data": {
    "Key": "3141312",
    "QrCodeUrl": "https://1231x/g6bMlv2dX8zwNbqE6-Zs",
    "Txt": "建议返回data=之后内容自定义生成二维码",
    "baseResp": {
      "ret": 0,
      "errMsg": {}
    }
  },
  "Text": ""
}
        
        """
        # 获取登录二维码
        url = f'{self.base_url}/login/GetLoginQrCodeNew'
        check = False
        if Proxy != '':
            check = True
        json_data = {'Check': check, 'Proxy': Proxy}
        return post_json(base_url=url, token=self.token, data=json_data)

    def get_login_status(self):
        # 获取登录状态
        url = f'{self.base_url}/login/GetLoginStatus'
        return get_json(base_url=url, token=self.token)

    def logout(self):
        # 退出登录
        url = f'{self.base_url}/login/LogOut'
        return post_json(base_url=url, token=self.token)

    def wake_up_login(self, Proxy: str = ''):
        # 唤醒登录
        url = f'{self.base_url}/login/WakeUpLogin'
        check = False
        if Proxy != '':
            check = True
        json_data = {'Check': check, 'Proxy': ''}

        return post_json(base_url=url, token=self.token, data=json_data)

    def login(self, admin_key):
        login_status = self.get_login_status()
        if login_status['Code'] == 300 and login_status['Text'] == '你已退出微信':
            print('token已经失效，重新获取')
            token_data = self.get_token(admin_key)
            self.token = token_data['Data'][0]
