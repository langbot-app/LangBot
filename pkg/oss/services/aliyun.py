from __future__ import annotations

import uuid

import oss2

from .. import service as osssv


@osssv.service_class('aliyun')
class AliyunOSSService(osssv.OSSService):
    """阿里云OSS服务"""

    auth: oss2.Auth

    bucket: oss2.Bucket

    async def initialize(self):
        self.auth = oss2.Auth(
            self.cfg['access-key-id'],
            self.cfg['access-key-secret']
        )

        self.bucket = oss2.Bucket(
            self.auth,
            self.cfg['endpoint'],
            self.cfg['bucket']
        )

    async def upload(
        self,
        local_file: str=None,
        file_bytes: bytes=None,
        ext: str=None,
    ) -> str:
        if local_file is not None:
            with open(local_file, 'rb') as f:
                file_bytes = f.read()

        if file_bytes is None:
            raise Exception("缺少文件内容")

        name = str(uuid.uuid1())

        key = f"{self.cfg['prefix']}/{name}{ext}"
        self.bucket.put_object(key, file_bytes)

        return f"{self.cfg['public-read-base-url']}/{key}"
