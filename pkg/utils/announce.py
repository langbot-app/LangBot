from __future__ import annotations

import json
import typing
import os
import base64
import logging

import pydantic.v1 as pydantic
import requests

from ..core import app


class Announcement(pydantic.BaseModel):
    """公告"""

    id: int

    time: str

    timestamp: int

    content: str

    enabled: typing.Optional[bool] = True

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'time': self.time,
            'timestamp': self.timestamp,
            'content': self.content,
            'enabled': self.enabled,
        }


class AnnouncementManager:
    """公告管理器"""

    ap: app.Application = None

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def fetch_all(self) -> list[Announcement]:
        """获取所有公告"""
        resp = requests.get(
            url='https://api.github.com/repos/RockChinQ/LangBot/contents/res/announcement.json',
            proxies=self.ap.proxy_mgr.get_forward_proxies(),
            timeout=5,
        )
        obj_json = resp.json()
        b64_content = obj_json['content']
        # 解码
        content = base64.b64decode(b64_content).decode('utf-8')

        return [Announcement(**item) for item in json.loads(content)]

    async def fetch_saved(self) -> list[Announcement]:
        if not os.path.exists('data/labels/announcement_saved.json'):
            with open('data/labels/announcement_saved.json', 'w', encoding='utf-8') as f:
                f.write('[]')

        with open('data/labels/announcement_saved.json', 'r', encoding='utf-8') as f:
            content = f.read()

        if not content:
            content = '[]'

        return [Announcement(**item) for item in json.loads(content)]

    async def write_saved(self, content: list[Announcement]):
        with open('data/labels/announcement_saved.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps([item.to_dict() for item in content], indent=4, ensure_ascii=False))

    async def fetch_new(self) -> list[Announcement]:
        """获取新公告"""
        all = await self.fetch_all()
        saved = await self.fetch_saved()

        to_show: list[Announcement] = []

        for item in all:
            # 遍历saved检查是否有相同id的公告
            for saved_item in saved:
                if saved_item.id == item.id:
                    break
            else:
                if item.enabled:
                    # 没有相同id的公告
                    to_show.append(item)

        await self.write_saved(all)
        return to_show

    async def show_announcements(self) -> typing.Tuple[str, int]:
        """显示公告"""
        try:
            announcements = await self.fetch_new()
            ann_text = ''
            for ann in announcements:
                ann_text += f'[公告] {ann.time}: {ann.content}\n'

            # TODO statistics

            return ann_text, logging.INFO
        except Exception as e:
            return f'获取公告时出错: {e}', logging.WARNING
