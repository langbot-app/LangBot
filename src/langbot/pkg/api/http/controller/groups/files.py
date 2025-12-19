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
            if '/' in image_key or '\\' in image_key:
                return quart.Response(status=404)

            if not await self.ap.storage_mgr.storage_provider.exists(image_key):
                return quart.Response(status=404)

            image_bytes = await self.ap.storage_mgr.storage_provider.load(image_key)
            mime_type = mimetypes.guess_type(image_key)[0]
            if mime_type is None:
                mime_type = 'image/jpeg'

            return quart.Response(image_bytes, mimetype=mime_type)

        @self.route('/images', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def upload_image() -> quart.Response:
            request = quart.request

            # Check file size limit before reading the file
            content_length = request.content_length
            if content_length and content_length > group.MAX_FILE_SIZE:
                return self.fail(400, 'Image size exceeds 10MB limit.')

            # get file bytes from 'file'
            files = await request.files
            if 'file' not in files:
                return self.fail(400, 'No image file provided')

            file = files['file']
            assert isinstance(file, quart.datastructures.FileStorage)

            file_bytes = await asyncio.to_thread(file.stream.read)

            # Double-check actual file size after reading
            if len(file_bytes) > group.MAX_FILE_SIZE:
                return self.fail(400, 'Image size exceeds 10MB limit.')

            # Validate image file extension
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
            if '.' in file.filename:
                file_name, extension = file.filename.rsplit('.', 1)
                extension = extension.lower()
            else:
                return self.fail(400, 'Invalid image file: no file extension')

            if extension not in allowed_extensions:
                return self.fail(400, f'Invalid image format. Allowed formats: {", ".join(allowed_extensions)}')

            # check if file name contains '/' or '\'
            if '/' in file_name or '\\' in file_name:
                return self.fail(400, 'File name contains invalid characters')

            file_key = file_name + '_' + str(uuid.uuid4())[:8] + '.' + extension

            # save file to storage
            await self.ap.storage_mgr.storage_provider.save(file_key, file_bytes)
            return self.success(
                data={
                    'file_key': file_key,
                }
            )

        @self.route('/documents', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def upload_document() -> quart.Response:
            request = quart.request

            # Check file size limit before reading the file
            content_length = request.content_length
            if content_length and content_length > group.MAX_FILE_SIZE:
                return self.fail(400, 'File size exceeds 10MB limit. Please split large files into smaller parts.')

            # get file bytes from 'file'
            files = await request.files
            if 'file' not in files:
                return self.fail(400, 'No file provided in request')

            file = files['file']
            assert isinstance(file, quart.datastructures.FileStorage)

            file_bytes = await asyncio.to_thread(file.stream.read)

            # Double-check actual file size after reading
            if len(file_bytes) > group.MAX_FILE_SIZE:
                return self.fail(400, 'File size exceeds 10MB limit. Please split large files into smaller parts.')

            # Split filename and extension properly
            if '.' in file.filename:
                file_name, extension = file.filename.rsplit('.', 1)
            else:
                file_name = file.filename
                extension = ''

            # check if file name contains '/' or '\'
            if '/' in file_name or '\\' in file_name:
                return self.fail(400, 'File name contains invalid characters')

            file_key = file_name + '_' + str(uuid.uuid4())[:8]
            if extension:
                file_key += '.' + extension

            # save file to storage
            await self.ap.storage_mgr.storage_provider.save(file_key, file_bytes)
            return self.success(
                data={
                    'file_id': file_key,
                }
            )
