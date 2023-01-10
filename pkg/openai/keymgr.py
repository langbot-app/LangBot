# 此模块提供了维护api-key的各种功能
import hashlib
import logging

import pkg.database.manager
import pkg.qqbot.manager
import pkg.utils.context


class KeysManager:
    api_key = {}

    # api-key的使用量
    # 其中键为api-key的md5值，值为使用量
    using_key = ""

    alerted = []

    # 在此list中的都是经超额报错标记过的api-key
    # 记录的是key值，仅在运行时有效
    exceeded = []

    def get_using_key(self):
        return self.using_key

    def get_using_key_md5(self):
        return hashlib.md5(self.using_key.encode('utf-8')).hexdigest()

    def __init__(self, api_key):
        # if hasattr(config, 'api_key_usage_threshold'):
        #     self.api_key_usage_threshold = config.api_key_usage_threshold

        if type(api_key) is dict:
            self.api_key = api_key
        elif type(api_key) is str:
            self.api_key = {
                "default": api_key
            }
        elif type(api_key) is list:
            for i in range(len(api_key)):
                self.api_key[str(i)] = api_key[i]

        self.auto_switch()
        # 从usage中删除未加载的api-key的记录
        # 不删了，也许会运行时添加曾经有记录的api-key

        if 'exceeded_keys' in pkg.utils.context.context and pkg.utils.context.context['exceeded_keys'] is not None:
            self.exceeded = pkg.utils.context.context['exceeded_keys']

    # 根据tested自动切换到可用的api-key
    # 返回是否切换成功, 切换后的api-key的别名
    def auto_switch(self) -> (bool, str):
        for key_name in self.api_key:
            if self.api_key[key_name] not in self.exceeded:
                self.using_key = self.api_key[key_name]
                logging.info("使用api-key:" + key_name)
                return True, key_name

        self.using_key = list(self.api_key.values())[0]
        logging.info("使用api-key:" + list(self.api_key.keys())[0])

        return False, ""

    def add(self, key_name, key):
        self.api_key[key_name] = key

    # 设置当前使用的api-key使用量超限
    # 这是在尝试调用api时发生超限异常时调用的
    def set_current_exceeded(self):
        # md5 = hashlib.md5(self.using_key.encode('utf-8')).hexdigest()
        # self.usage[md5] = self.api_key_usage_threshold
        # self.fee[md5] = self.api_key_fee_threshold
        self.exceeded.append(self.using_key)

    def get_key_name(self, api_key):
        """根据api-key获取其别名"""
        for key_name in self.api_key:
            if self.api_key[key_name] == api_key:
                return key_name
        return ""