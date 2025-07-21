from __future__ import annotations

import quart
import mimetypes
import uuid
import asyncio

import quart.datastructures

from .. import group


@group.group_class('files', '/api/v1/files')
class FilesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/image/<image_key>', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _(image_key: str) -> quart.Response:
            if not await self.ap.storage_mgr.storage_provider.exists(image_key):
                return quart.Response(status=404)

            image_bytes = await self.ap.storage_mgr.storage_provider.load(image_key)
            mime_type = mimetypes.guess_type(image_key)[0]
            if mime_type is None:
                mime_type = 'image/jpeg'

            return quart.Response(image_bytes, mimetype=mime_type)

        @self.route('/documents', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> quart.Response:
            request = quart.request
            # get file bytes from 'file'
            file = (await request.files)['file']
            assert isinstance(file, quart.datastructures.FileStorage)

            file_bytes = await asyncio.to_thread(file.stream.read)
            extension = file.filename.split('.')[-1]
            file_name = file.filename.split('.')[0]

            file_key = file_name + '_' + str(uuid.uuid4())[:8] + '.' + extension
            # save file to storage
            await self.ap.storage_mgr.storage_provider.save(file_key, file_bytes)
            return self.success(
                data={
                    'file_id': file_key,
                }
            )
