from __future__ import annotations

import aiohttp
import typing
from urllib.parse import urlparse, parse_qs
import ssl

from . import service as osssv
from ..core import app
from .services import aliyun


class OSSServiceManager:

    ap: app.Application

    service: osssv.OSSService = None

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        """初始化
        """

        mapping = {}

        for svcls in osssv.preregistered_services:
            mapping[svcls.name] = svcls

        for sv in self.ap.system_cfg.data['oss']:
            if sv['enable']:
                
                if sv['type'] not in mapping:
                    raise Exception(f"未知的OSS服务类型: {sv['type']}")

                self.service = mapping[sv['type']](self.ap, sv)
                await self.service.initialize()
                break
    
    def available(self) -> bool:
        """是否可用

        Returns:
            bool: 是否可用
        """
        return self.service is not None

    async def fetch_image(self, image_url: str) -> bytes:
        parsed = urlparse(image_url)
        query = parse_qs(parsed.query)

        # Flatten the query dictionary
        query = {k: v[0] for k, v in query.items()}

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with aiohttp.ClientSession(trust_env=False) as session:
            async with session.get(
                f"http://{parsed.netloc}{parsed.path}",
                params=query,
                ssl=ssl_context
            ) as resp:
                resp.raise_for_status()  # 检查HTTP错误
                file_bytes = await resp.read()
                return file_bytes

    async def upload_url_image(
        self,
        image_url: str,
    ) -> str:
        """上传URL图片

        Args:
            image_url (str): 图片URL

        Returns:
            str: 文件URL
        """

        file_bytes = await self.fetch_image(image_url)

        return await self.service.upload(file_bytes=file_bytes, ext=".jpg")