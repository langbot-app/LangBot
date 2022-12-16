# 此模块提供了维护api-key的各种功能
import hashlib
import logging

import pkg.database.manager
import pkg.qqbot.manager
import config


class KeysManager:
    api_key = {}

    # api-key的使用量
    # 其中键为api-key的md5值，值为使用量
    usage = {}

    api_key_usage_threshold = 900000

    using_key = ""

    alerted = []

    def get_using_key(self):
        return self.using_key

    def __init__(self, api_key):
        if hasattr(config, 'api_key_usage_threshold'):
            self.api_key_usage_threshold = config.api_key_usage_threshold
        self.load_usage()

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

    # 根据使用量自动切换到可用的api-key
    # 返回是否切换成功, 切换后的api-key的别名
    def auto_switch(self) -> (bool, str):
        self.dump_usage()
        for key_name in self.api_key:
            if self.get_usage(self.api_key[key_name]) < self.api_key_usage_threshold:
                self.using_key = self.api_key[key_name]
                logging.info("使用api-key:" + key_name)
                return True, key_name

        self.using_key = list(self.api_key.values())[0]
        logging.info("使用api-key:" + self.using_key)

        return False, ""

    def get_usage(self, api_key):
        md5 = hashlib.md5(api_key.encode('utf-8')).hexdigest()
        if md5 not in self.usage:
            self.usage[md5] = 0
        return self.usage[md5]

    def add(self, key_name, key):
        self.api_key[key_name] = key

    # 报告使用
    # 返回是否需要将openai的api-key切换
    def report_usage(self, new_content: str) -> bool:
        md5 = hashlib.md5(self.using_key.encode('utf-8')).hexdigest()
        if md5 not in self.usage:
            self.usage[md5] = 0
        self.usage[md5] += int((len(new_content.encode('utf-8')) - len(new_content)) / 2 + len(new_content))

        if self.usage[md5] >= self.api_key_usage_threshold:
            switch_result, key_name = self.auto_switch()

            # 检查是否切换到新的
            if switch_result:
                if key_name not in self.alerted:
                    # 通知管理员
                    pkg.qqbot.manager.get_inst().notify_admin("api-key已切换到:" + key_name)
                    self.alerted.append(key_name)
                    return True
            else:
                if key_name not in self.alerted:
                    # 通知管理员
                    pkg.qqbot.manager.get_inst().notify_admin("api-key已用完，无未使用的api-key可供切换")
                    self.alerted.append(key_name)
                    return False

    # 设置当前使用的api-key使用量超限
    # 这是在尝试调用api时发生超限异常时调用的
    def set_current_exceeded(self):
        md5 = hashlib.md5(self.using_key.encode('utf-8')).hexdigest()
        self.usage[md5] = self.api_key_usage_threshold
        self.dump_usage()

    def dump_usage(self):
        pkg.database.manager.get_inst().dump_api_key_usage(api_keys=self.api_key, usage=self.usage)

    def load_usage(self):
        self.usage = pkg.database.manager.get_inst().load_api_key_usage()
        logging.debug("load usage:" + str(self.usage))
        print("load usage:" + str(self.usage))
