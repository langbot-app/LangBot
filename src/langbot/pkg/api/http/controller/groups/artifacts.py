"""Authenticated Artifact transport; authorization and lifetime live in the service."""

from __future__ import annotations

import asyncio
from urllib.parse import quote

import quart

from ....application import ApplicationAPIException
from ....application.artifact_operations import MAX_ARTIFACT_BYTES
from ...authz import Permission
from ...context import RequestContext
from .. import group


@group.group_class('artifacts', '/api/v1/artifacts')
class ArtifactsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        async def invoke(operation, context, payload, *, download=False):
            try:
                result = await self.ap.application_api.execute(operation, context, payload)
            except ApplicationAPIException as exc:
                return self.http_status(exc.error.status_code, exc.error.code, exc.error.message)
            if not download:
                response = self.success(data=result)
                response.headers['Cache-Control'] = 'private, no-store'
                return response
            metadata = result['metadata']
            return quart.Response(
                result['content'],
                mimetype=metadata['mime_type'],
                headers={
                    'Content-Disposition': "attachment; filename*=UTF-8''" + quote(metadata['name'], safe=''),
                    'ETag': f'"{metadata["digest"]}"',
                    'Cache-Control': 'private, no-store',
                    'X-Content-Type-Options': 'nosniff',
                },
            )

        @self.route(
            '/producers/<producer_type>/<producer_id>/publication',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_publication(producer_type: str, producer_id: str, request_context: RequestContext):
            return await invoke(
                'artifact.publication.get',
                request_context,
                {
                    'producer_type': producer_type,
                    'producer_id': producer_id,
                },
            )

        @self.route(
            '/producers/<producer_type>/<producer_id>/publication',
            methods=['PUT', 'DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def update_publication(producer_type: str, producer_id: str, request_context: RequestContext):
            payload = {'producer_type': producer_type, 'producer_id': producer_id}
            if quart.request.method == 'DELETE':
                return await invoke('artifact.publication.disable', request_context, payload)
            data = await quart.request.json
            if not isinstance(data, dict):
                return self.http_status(400, 'invalid_input', 'Expected an object')
            return await invoke('artifact.publication.set', request_context, {**data, **payload})

        @self.route(
            '', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY, permission=Permission.RESOURCE_MANAGE
        )
        async def upload(request_context: RequestContext):
            files = await quart.request.files
            if 'file' not in files:
                return self.http_status(400, 'invalid_input', 'No file provided in request')
            file = files['file']
            content = await asyncio.to_thread(file.stream.read, MAX_ARTIFACT_BYTES + 1)
            if len(content) > MAX_ARTIFACT_BYTES:
                return self.http_status(413, 'artifact_too_large', 'Artifact exceeds the size limit.')
            form = await quart.request.form
            try:
                ttl_seconds = int(form.get('ttl_seconds', '86400'))
            except ValueError:
                return self.http_status(400, 'invalid_input', 'Invalid ttl_seconds')
            return await invoke(
                'artifact.create',
                request_context,
                {
                    'filename': file.filename or '',
                    'content': content,
                    'mime_type': file.mimetype or 'application/octet-stream',
                    'ttl_seconds': ttl_seconds,
                },
            )

        @self.route(
            '/skill-resources',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def create_skill_resource(request_context: RequestContext):
            payload = await quart.request.json
            if not isinstance(payload, dict):
                return self.http_status(400, 'invalid_input', 'Expected an object')
            return await invoke('artifact.skill_resource.create', request_context, payload)

        @self.route(
            '/<artifact_id>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def metadata(artifact_id: str, request_context: RequestContext):
            return await invoke('artifact.get', request_context, {'artifact_id': artifact_id})

        @self.route(
            '/<artifact_id>/content',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def download(artifact_id: str, request_context: RequestContext):
            try:
                max_bytes = int(quart.request.args.get('max_bytes', str(MAX_ARTIFACT_BYTES)))
            except ValueError:
                return self.http_status(400, 'invalid_input', 'Invalid max_bytes')
            return await invoke(
                'artifact.read',
                request_context,
                {
                    'artifact_id': artifact_id,
                    'max_bytes': max_bytes,
                },
                download=True,
            )

        @self.route(
            '/<artifact_id>/read',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def read_content(artifact_id: str, request_context: RequestContext):
            payload = {'artifact_id': artifact_id, 'mode': quart.request.args.get('mode', 'auto')}
            for key in ('offset', 'max_chars', 'page_start', 'page_end'):
                if key in quart.request.args:
                    try:
                        payload[key] = int(quart.request.args[key])
                    except ValueError:
                        return self.http_status(400, 'invalid_input', f'Invalid {key}')
            return await invoke('artifact.read_content', request_context, payload)

        @self.route(
            '/<artifact_id>/retain',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def retain(artifact_id: str, request_context: RequestContext):
            return await invoke('artifact.retain', request_context, {'artifact_id': artifact_id})

        @self.route(
            '/<artifact_id>/release',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def release(artifact_id: str, request_context: RequestContext):
            return await invoke('artifact.release', request_context, {'artifact_id': artifact_id})

        @self.route(
            '/<artifact_id>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def delete(artifact_id: str, request_context: RequestContext):
            return await invoke('artifact.delete', request_context, {'artifact_id': artifact_id})
