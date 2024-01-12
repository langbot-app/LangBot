"""
使用量统计以及数据上报功能实现
"""

import hashlib
import json
import logging
import threading

import requests

from ..utils import context
from ..utils import updater


class DataGatherer:
    """数据收集器"""

    usage = {}
    """各api-key的使用量
    
    以key值md5为key,{
        "text": {
            "gpt-3.5-turbo": 文字量:int,
        },
        "image": {
            "256x256": 图片数量:int,
        }
    }为值的字典"""

    version_str = "undetermined"

    def __init__(self):
        self.load_from_db()
        try:
            self.version_str = updater.get_current_tag()  # 从updater模块获取版本号
        except:
            pass

    def get_usage(self, key_md5):
        return self.usage[key_md5] if key_md5 in self.usage else {}

    def report_text_model_usage(self, model, total_tokens):
        """调用方报告文字模型请求文字使用量"""

        key_md5 = context.get_openai_manager().key_mgr.get_using_key_md5()  # 以key的md5进行储存

        if key_md5 not in self.usage:
            self.usage[key_md5] = {}

        if "text" not in self.usage[key_md5]:
            self.usage[key_md5]["text"] = {}

        if model not in self.usage[key_md5]["text"]:
            self.usage[key_md5]["text"][model] = 0

        length = total_tokens
        self.usage[key_md5]["text"][model] += length
        self.dump_to_db()

    def report_image_model_usage(self, size):
        """调用方报告图片模型请求图片使用量"""

        key_md5 = context.get_openai_manager().key_mgr.get_using_key_md5()

        if key_md5 not in self.usage:
            self.usage[key_md5] = {}

        if "image" not in self.usage[key_md5]:
            self.usage[key_md5]["image"] = {}

        if size not in self.usage[key_md5]["image"]:
            self.usage[key_md5]["image"][size] = 0

        self.usage[key_md5]["image"][size] += 1
        self.dump_to_db()

    def get_text_length_of_key(self, key):
        """获取指定api-key (明文) 的文字总使用量(本地记录)"""
        key_md5 = hashlib.md5(key.encode('utf-8')).hexdigest()
        if key_md5 not in self.usage:
            return 0
        if "text" not in self.usage[key_md5]:
            return 0
        # 遍历其中所有模型，求和
        return sum(self.usage[key_md5]["text"].values())

    def get_image_count_of_key(self, key):
        """获取指定api-key (明文) 的图片总使用量(本地记录)"""

        key_md5 = hashlib.md5(key.encode('utf-8')).hexdigest()
        if key_md5 not in self.usage:
            return 0
        if "image" not in self.usage[key_md5]:
            return 0
        # 遍历其中所有模型，求和
        return sum(self.usage[key_md5]["image"].values())

    def get_total_text_length(self):
        """获取所有api-key的文字总使用量(本地记录)"""
        total = 0
        for key in self.usage:
            if "text" not in self.usage[key]:
                continue
            total += sum(self.usage[key]["text"].values())
        return total

    def dump_to_db(self):
        context.get_database_manager().dump_usage_json(self.usage)

    def load_from_db(self):
        json_str = context.get_database_manager().load_usage_json()
        if json_str is not None:
            self.usage = json.loads(json_str)
