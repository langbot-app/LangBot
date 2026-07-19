from __future__ import annotations

import quart
import mimetypes
import uuid
import asyncio

import quart.datastructures

from ...authz import Permission
from ...context import RequestContext
from .. import group


def _storage_owner(context: RequestContext) -> str:
    if context.principal.account_uuid:
        return f'account:{context.principal.account_uuid}'
    if context.principal.api_key_uuid:
        return f'api-key:{context.principal.api_key_uuid}'
    return f'principal:{context.principal.principal_type.value}'


@group.group_class('files', '/api/v1/files')
class FilesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/image/<path:image_key>', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _(image_key: str) -> quart.Response:
            image_bytes = await self.ap.storage_mgr.resolve_public_object(
                image_key,
                expected_owner_type='upload_image',
            )
            if image_bytes is None:
                image_bytes = await self.ap.storage_mgr.resolve_public_object(
                    image_key,
                    expected_owner_type='bot_log',
                )
            if image_bytes is None:
                return quart.Response(status=404)
            mime_type = mimetypes.guess_type(image_key)[0]
            if mime_type is None:
                mime_type = 'image/jpeg'

            return quart.Response(image_bytes, mimetype=mime_type)

        @self.route(
            '/images',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def upload_image(request_context: RequestContext) -> quart.Response:
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

            logical_key = f'{uuid.uuid4()}.{extension}'

            # save file to storage
            file_key = await self.ap.storage_mgr.save_scoped(
                request_context,
                owner_type='upload_image',
                owner=_storage_owner(request_context),
                key=logical_key,
                value=file_bytes,
            )
            return self.success(
                data={
                    'file_key': file_key,
                }
            )

        @self.route(
            '/documents',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def upload_document(request_context: RequestContext) -> quart.Response:
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

            logical_key = str(uuid.uuid4())
            if extension:
                logical_key += '.' + extension

            # save file to storage
            file_key = await self.ap.storage_mgr.save_scoped(
                request_context,
                owner_type='upload_document',
                owner=_storage_owner(request_context),
                key=logical_key,
                value=file_bytes,
            )
            return self.success(
                data={
                    'file_id': file_key,
                }
            )
