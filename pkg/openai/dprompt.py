# 多情景预设值管理
import json
import logging
import config
import os

# __current__ = "default"
# """当前默认使用的情景预设的名称

# 由管理员使用`!default <名称>`指令切换
# """

# __prompts_from_files__ = {}
# """从文件中读取的情景预设值"""

# __scenario_from_files__ = {}


__universal_first_reply__ = "ok, I'll follow your commands."
"""通用首次回复"""


class ScenarioMode:
    """情景预设模式抽象类"""

    using_prompt_name = "default"
    """新session创建时使用的prompt名称"""

    prompts: dict[str, list] = {}

    def __init__(self):
        logging.debug("prompts: {}".format(self.prompts))

    def list(self) -> dict[str, list]:
        """获取所有情景预设的名称及内容"""
        return self.prompts

    def get_prompt(self, name: str) -> tuple[list, str]:
        """获取指定情景预设的名称及内容"""
        for key in self.prompts:
            if key.startswith(name):
                return self.prompts[key], key
        raise Exception("没有找到情景预设: {}".format(name))

    def set_using_name(self, name: str) -> str:
        """设置默认情景预设"""
        for key in self.prompts:
            if key.startswith(name):
                self.using_prompt_name = key
                return key
        raise Exception("没有找到情景预设: {}".format(name))
    
    def get_full_name(self, name: str) -> str:
        """获取完整的情景预设名称"""
        for key in self.prompts:
            if key.startswith(name):
                return key
        raise Exception("没有找到情景预设: {}".format(name))

    def get_using_name(self) -> str:
        """获取默认情景预设"""
        return self.using_prompt_name


class NormalScenarioMode(ScenarioMode):
    """普通情景预设模式"""

    def __init__(self):
        global __universal_first_reply__
        # 加载config中的default_prompt值
        if type(config.default_prompt) == str:
            self.using_prompt_name = "default"
            self.prompts = {"default": [
                {
                    "role": "user",
                    "content": config.default_prompt
                },{
                    "role": "assistant",
                    "content": __universal_first_reply__
                }
            ]}
        
        elif type(config.default_prompt) == dict:
            for key in config.default_prompt:
                self.prompts[key] = [
                    {
                        "role": "user",
                        "content": config.default_prompt[key]
                    },{
                        "role": "assistant",
                        "content": __universal_first_reply__
                    }
                ]

        # 从prompts/目录下的文件中载入
        # 遍历文件
        for file in os.listdir("prompts"):
            with open(os.path.join("prompts", file), encoding="utf-8") as f:
                self.prompts[file] = [
                    {
                        "role": "user",
                        "content": f.read()
                    },{
                        "role": "assistant",
                        "content": __universal_first_reply__
                    }
                ]


class FullScenarioMode(ScenarioMode):
    """完整情景预设模式"""

    def __init__(self):
        """从json读取所有"""
        # 遍历scenario/目录下的所有文件，以文件名为键，文件内容中的prompt为值
        for file in os.listdir("scenario"):
            if file == "default-template.json":
                continue
            with open(os.path.join("scenario", file), encoding="utf-8") as f:
                self.prompts[file] = json.load(f)["prompt"]

        super().__init__()


scenario_mode_mapping = {}
"""情景预设模式名称与对象的映射"""


def register_all():
    """注册所有情景预设模式，不使用装饰器，因为装饰器的方式不支持热重载"""
    global scenario_mode_mapping
    scenario_mode_mapping = {
        "normal": NormalScenarioMode(),
        "full_scenario": FullScenarioMode()
    }


def mode_inst() -> ScenarioMode:
    """获取指定名称的情景预设模式对象"""
    import config

    if config.preset_mode == "default":
        config.preset_mode = "normal"

    return scenario_mode_mapping[config.preset_mode]
