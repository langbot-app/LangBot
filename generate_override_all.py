# 使用config-template生成override.json的字段全集模板文件override-all.json
# 关于override.json机制，请参考：https://github.com/RockChinQ/QChatGPT/pull/271
import json
import importlib


template = importlib.import_module("config-template")
output_json = {
    "comment": "这是override.json支持的字段全集, 关于override.json机制, 请查看https://github.com/RockChinQ/QChatGPT/pull/271"
}


for k, v in template.__dict__.items():
    if k.startswith("__"):
        continue
    # 如果是module
    if type(v) == type(template):
        continue
    print(k, v, type(v))
    output_json[k] = v

with open("override-all.json", "w", encoding="utf-8") as f:
    json.dump(output_json, f, indent=4, ensure_ascii=False)
