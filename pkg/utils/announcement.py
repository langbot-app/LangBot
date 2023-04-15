import base64
import os
import json

import requests


def read_latest() -> list:
    import pkg.utils.network as network
    resp = requests.get(
        url="https://api.github.com/repos/RockChinQ/QChatGPT/contents/res/announcement.json",
        proxies=network.wrapper_proxies()
    )
    obj_json = resp.json()
    b64_content = obj_json["content"]
    # 解码
    content = base64.b64decode(b64_content).decode("utf-8")
    return json.loads(content)


def read_saved() -> list:
    # 已保存的在res/announcement_saved
    # 检查是否存在
    if not os.path.exists("res/announcement_saved.json"):
        with open("res/announcement_saved.json", "w", encoding="utf-8") as f:
            f.write("[]")

    with open("res/announcement_saved.json", "r", encoding="utf-8") as f:
        content = f.read()

    return json.loads(content)


def write_saved(content: list):
    # 已保存的在res/announcement_saved
    with open("res/announcement_saved.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(content, indent=4, ensure_ascii=False))


def fetch_new() -> list:
    latest = read_latest()
    saved = read_saved()

    to_show: list = []

    for item in latest:
        # 遍历saved检查是否有相同id的公告
        for saved_item in saved:
            if saved_item["id"] == item["id"]:
                break
        else:
            # 没有相同id的公告
            to_show.append(item)

    write_saved(latest)
    return to_show


if __name__ == '__main__':
    
    resp = requests.get(
        url="https://api.github.com/repos/RockChinQ/QChatGPT/contents/res/announcement.json",
    )
    obj_json = resp.json()
    b64_content = obj_json["content"]
    # 解码
    content = base64.b64decode(b64_content).decode("utf-8")
    print(json.dumps(json.loads(content), indent=4, ensure_ascii=False))
