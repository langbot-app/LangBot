import hashlib
import json
import logging

import requests

import pkg.utils.context

version = "0.1.0"


class DataGatherer:
    """数据收集器"""
    usage = {}
    """以key值md5为key,{
        "text": {
            "text-davinci-003": 文字量:int,
        },
        "image": {
            "256x256": 图片数量:int,
        }
    }为值的字典"""

    def __init__(self):
        self.load_from_db()

    def report_to_server(self, subservice_name: str, count: int):
        config = pkg.utils.context.get_config()
        if hasattr(config, "report_usage") and not config.report_usage:
            return
        res = requests.get("http://rockchin.top:18989/usage?service_name=qchatgpt.{}&version={}&count={}".format(subservice_name, version, count))
        if res.status_code != 200 or res.text != "ok":
            logging.warning("report to server failed, status_code: {}, text: {}".format(res.status_code, res.text))

    def report_text_model_usage(self, model, text):
        key_md5 = pkg.utils.context.get_openai_manager().key_mgr.get_using_key_md5()

        if key_md5 not in self.usage:
            self.usage[key_md5] = {}

        if "text" not in self.usage[key_md5]:
            self.usage[key_md5]["text"] = {}

        if model not in self.usage[key_md5]["text"]:
            self.usage[key_md5]["text"][model] = 0

        length = int((len(text.encode('utf-8')) - len(text)) / 2 + len(text))
        self.usage[key_md5]["text"][model] += length
        self.dump_to_db()

        self.report_to_server("text", length)

    def report_image_model_usage(self, size):
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
        key_md5 = hashlib.md5(key.encode('utf-8')).hexdigest()
        if key_md5 not in self.usage:
            return 0
        if "text" not in self.usage[key_md5]:
            return 0
        # 遍历其中所有模型，求和
        return sum(self.usage[key_md5]["text"].values())

    def get_image_count_of_key(self, key):
        key_md5 = hashlib.md5(key.encode('utf-8')).hexdigest()
        if key_md5 not in self.usage:
            return 0
        if "image" not in self.usage[key_md5]:
            return 0
        # 遍历其中所有模型，求和
        return sum(self.usage[key_md5]["image"].values())

    def dump_to_db(self):
        pkg.utils.context.get_database_manager().dump_usage_json(self.usage)

    def load_from_db(self):
        json_str = pkg.utils.context.get_database_manager().load_usage_json()
        if json_str is not None:
            self.usage = json.loads(json_str)
