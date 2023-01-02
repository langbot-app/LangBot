# 此模块提供了维护api-key的各种功能
import hashlib
import logging

import pkg.database.manager
import pkg.qqbot.manager
import pkg.utils.context
import config


class KeysManager:
    api_key = {}

    # api-key的使用量
    # 其中键为api-key的md5值，值为使用量
    fee = {}

    api_key_fee_threshold = 18.0

    using_key = ""

    alerted = []

    def get_using_key(self):
        return self.using_key

    def __init__(self, api_key):
        # if hasattr(config, 'api_key_usage_threshold'):
        #     self.api_key_usage_threshold = config.api_key_usage_threshold
        if hasattr(config, 'api_key_fee_threshold'):
            self.api_key_fee_threshold = config.api_key_fee_threshold
        self.load_fee()

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
        self.dump_fee()
        for key_name in self.api_key:
            if self.get_fee(self.api_key[key_name]) < self.api_key_fee_threshold:
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
        md5 = hashlib.md5(self.using_key.encode('utf-8')).hexdigest()
        # self.usage[md5] = self.api_key_usage_threshold
        self.fee[md5] = self.api_key_fee_threshold
        self.dump_fee()

    def get_fee(self, api_key):
        md5 = hashlib.md5(api_key.encode('utf-8')).hexdigest()
        if md5 not in self.fee:
            self.fee[md5] = 0
        return self.fee[md5]

    def report_fee(self, fee: float) -> bool:
        logging.debug("report fee:" + str(fee))

        md5 = hashlib.md5(self.using_key.encode('utf-8')).hexdigest()
        if md5 not in self.fee:
            self.fee[md5] = 0

        self.fee[md5] += fee

        if self.fee[md5] >= self.api_key_fee_threshold:
            switch_result, key_name = self.auto_switch()

            # 检查是否切换到新的
            if switch_result:
                if key_name not in self.alerted:
                    # 通知管理员
                    pkg.utils.context.get_qqbot_manager().notify_admin("api-key已切换到:" + key_name)
                    self.alerted.append(key_name)
                    return True
            else:
                if key_name not in self.alerted:
                    # 通知管理员
                    pkg.utils.context.get_qqbot_manager().notify_admin("api-key已用完，无未使用的api-key可供切换")
                    self.alerted.append(key_name)
                    return False

    def dump_fee(self):
        pkg.utils.context.get_database_manager().dump_api_key_fee(api_keys=self.api_key, fee=self.fee)

    def load_fee(self):
        self.fee = pkg.utils.context.get_database_manager().load_api_key_fee()
        logging.info("load fee:" + str(self.fee))
