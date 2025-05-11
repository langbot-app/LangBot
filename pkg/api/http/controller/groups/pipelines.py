from __future__ import annotations

import quart

from .. import group


@group.group_class('pipelines', '/api/v1/pipelines')
class PipelinesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'])
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data={'pipelines': await self.ap.pipeline_service.get_pipelines()})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json

                pipeline_uuid = await self.ap.pipeline_service.create_pipeline(json_data)

                return self.success(data={'uuid': pipeline_uuid})

        @self.route('/_/metadata', methods=['GET'])
        async def _() -> str:
            return self.success(data={'configs': await self.ap.pipeline_service.get_pipeline_metadata()})

        @self.route('/<pipeline_uuid>', methods=['GET', 'PUT', 'DELETE'])
        async def _(pipeline_uuid: str) -> str:
            if quart.request.method == 'GET':
                pipeline = await self.ap.pipeline_service.get_pipeline(pipeline_uuid)

                if pipeline is None:
                    return self.http_status(404, -1, 'pipeline not found')

                return self.success(data={'pipeline': pipeline})
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json

                await self.ap.pipeline_service.update_pipeline(pipeline_uuid, json_data)

                return self.success()
            elif quart.request.method == 'DELETE':
                await self.ap.pipeline_service.delete_pipeline(pipeline_uuid)

                return self.success()
