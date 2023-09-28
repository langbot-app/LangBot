"""
使用量统计以及数据上报功能实现
"""

import hashlib
import json
import logging
import threading

import requests

import pkg.utils.context
import pkg.utils.updater


class DataGatherer:
    """数据收集器"""

    usage = {}
    """各api-key的使用量
    
    以key值md5为key,{
        "text": {
            "text-davinci-003": 文字量:int,
        },
        "image": {
            "256x256": 图片数量:int,
        }
    }为值的字典"""

    version_str = "undetermined"

    def __init__(self):
        self.load_from_db()
        try:
            self.version_str = pkg.utils.updater.get_current_tag()  # 从updater模块获取版本号
        except:
            pass

    def report_to_server(self, subservice_name: str, count: int):
        """向中央服务器报告使用量

        只会报告此次请求的使用量，不会报告总量。
        不包含除版本号、使用类型、使用量以外的任何信息，仅供开发者分析使用情况。
        """
        
        def thread_func():
        
            try:
                config = pkg.utils.context.get_config()
                if not config.report_usage:
                    return
                res = requests.get("http://reports.rockchin.top:18989/usage?service_name=qchatgpt.{}&version={}&count={}&msg_source={}".format(subservice_name, self.version_str, count, config.msg_source_adapter))
                if res.status_code != 200 or res.text != "ok":
                    logging.warning("report to server failed, status_code: {}, text: {}".format(res.status_code, res.text))
            except:
                return
            
        threading.Thread(target=thread_func).start()

    def get_usage(self, key_md5):
        return self.usage[key_md5] if key_md5 in self.usage else {}

    def report_text_model_usage(self, model, total_tokens):
        """调用方报告文字模型请求文字使用量"""

        key_md5 = pkg.utils.context.get_openai_manager().key_mgr.get_using_key_md5()  # 以key的md5进行储存

        if key_md5 not in self.usage:
            self.usage[key_md5] = {}

        if "text" not in self.usage[key_md5]:
            self.usage[key_md5]["text"] = {}

        if model not in self.usage[key_md5]["text"]:
            self.usage[key_md5]["text"][model] = 0

        length = total_tokens
        self.usage[key_md5]["text"][model] += length
        self.dump_to_db()

        self.report_to_server("text", length)

    def report_image_model_usage(self, size):
        """调用方报告图片模型请求图片使用量"""

        key_md5 = pkg.utils.context.get_openai_manager().key_mgr.get_using_key_md5()

        if key_md5 not in self.usage:
            self.usage[key_md5] = {}

        if "image" not in self.usage[key_md5]:
            self.usage[key_md5]["image"] = {}

        if size not in self.usage[key_md5]["image"]:
            self.usage[key_md5]["image"][size] = 0

        self.usage[key_md5]["image"][size] += 1
        self.dump_to_db()

        self.report_to_server("image", 1)

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
        pkg.utils.context.get_database_manager().dump_usage_json(self.usage)

    def load_from_db(self):
        json_str = pkg.utils.context.get_database_manager().load_usage_json()
        if json_str is not None:
            self.usage = json.loads(json_str)
