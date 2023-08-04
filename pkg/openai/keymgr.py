# 此模块提供了维护api-key的各种功能
import hashlib
import logging

import pkg.plugin.host as plugin_host
import pkg.plugin.models as plugin_models


class KeysManager:
    api_key = {}
    """所有api-key"""

    using_key = ""
    """当前使用的api-key"""

    alerted = []
    """已提示过超额的key
    
    记录在此以避免重复提示
    """

    exceeded = []
    """已超额的key
    
    供自动切换功能识别
    """

    def get_using_key(self):
        return self.using_key

    def get_using_key_md5(self):
        return hashlib.md5(self.using_key.encode('utf-8')).hexdigest()

    def __init__(self, api_key):

        if type(api_key) is dict:
            self.api_key = api_key
        elif type(api_key) is str:
            self.api_key = {
                "default": api_key
            }
        elif type(api_key) is list:
            for i in range(len(api_key)):
                self.api_key[str(i)] = api_key[i]
        # 从usage中删除未加载的api-key的记录
        # 不删了，也许会运行时添加曾经有记录的api-key

        self.auto_switch()

    def auto_switch(self) -> tuple[bool, str]:
        """尝试切换api-key

        Returns:
            是否切换成功, 切换后的api-key的别名
        """

        index = 0

        for key_name in self.api_key:
            if self.api_key[key_name] == self.using_key:
                break
            
            index += 1

        # 从当前key开始向后轮询
        start_index = index
        index += 1
        if index >= len(self.api_key):
            index = 0

        while index != start_index:
            
            key_name = list(self.api_key.keys())[index]

            if self.api_key[key_name] not in self.exceeded:
                self.using_key = self.api_key[key_name]

                logging.info("使用api-key:" + key_name)

                # 触发插件事件
                args = {
                    "key_name": key_name,
                    "key_list": self.api_key.keys()
                }
                _ = plugin_host.emit(plugin_models.KeySwitched, **args)

                return True, key_name

            index += 1
            if index >= len(self.api_key):
                index = 0

        self.using_key = list(self.api_key.values())[start_index]
        logging.debug("使用api-key:" + list(self.api_key.keys())[start_index])

        return False, list(self.api_key.keys())[start_index]

    def add(self, key_name, key):
        self.api_key[key_name] = key

    def set_current_exceeded(self):
        """设置当前使用的api-key使用量超限"""
        self.exceeded.append(self.using_key)

    def get_key_name(self, api_key):
        """根据api-key获取其别名"""
        for key_name in self.api_key:
            if self.api_key[key_name] == api_key:
                return key_name
        return ""
