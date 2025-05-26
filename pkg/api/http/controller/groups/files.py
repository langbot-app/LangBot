from __future__ import annotations

import quart
import mimetypes

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
