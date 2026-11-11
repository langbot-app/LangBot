from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel

# {
#     "code": 0,
#     "data": {
#         "plugin": {
#             "created_at": "2025-08-10T21:29:28.54938+08:00",
#             "updated_at": "2025-08-11T14:17:19.223492+08:00",
#             "deleted_at": null,
#             "plugin_id": "langbot-team/GoogleSearch",
#             "author": "langbot-team",
#             "name": "GoogleSearch",
#             "label": {
#                 "en_US": "GoogleSearch",
#                 "zh_Hans": "谷歌搜索",
#                 "zh_Hant": "",
#                 "ja_JP": ""
#             },
#             "description": {
#                 "en_US": "Search A tool for performing a Google SERP search and extracting snippets and webpages.Input should be a search query.",
#                 "zh_Hans": "一个用于执行 Google SERP 搜索并提取片段和网页的工具。输入应该是一个搜索查询。",
#                 "zh_Hant": "",
#                 "ja_JP": ""
#             },
#             "icon": "plugins/langbot-team/GoogleSearch/resources/icon.svg",
#             "repository": "https://github.com/langbot-app/langbot-plugin-demo",
#             "tags": null,
#             "install_count": 4,
#             "latest_version": "0.1.0",
#             "status": "live"
#         }
#     },
#     "msg": "ok"
# }


class PluginInfo(BaseModel):
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    plugin_id: str
    author: str
    name: str
    label: dict[str, str]
    description: dict[str, str]
    icon: str
    repository: str
    tags: list[str] | None
    install_count: int
    latest_version: str
    status: str
