import quart
from ... import group


@group.group_class('knowledge_base', '/api/v1/knowledge/bases')
class KnowledgeBaseRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['POST', 'GET'])
        async def handle_knowledge_bases() -> quart.Response:
            if quart.request.method == 'GET':
                knowledge_bases = await self.ap.knowledge_service.get_knowledge_bases()
                return self.success(data={'bases': knowledge_bases})

            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                knowledge_base_uuid = await self.ap.knowledge_service.create_knowledge_base(json_data)
                return self.success(data={'uuid': knowledge_base_uuid})

            return self.http_status(405, -1, 'Method not allowed')

        @self.route(
            '/<knowledge_base_uuid>',
            methods=['GET', 'DELETE', 'PUT'],
        )
        async def handle_specific_knowledge_base(knowledge_base_uuid: str) -> quart.Response:
            if quart.request.method == 'GET':
                knowledge_base = await self.ap.knowledge_service.get_knowledge_base(knowledge_base_uuid)

                if knowledge_base is None:
                    return self.http_status(404, -1, 'knowledge base not found')

                return self.success(
                    data={
                        'base': knowledge_base,
                    }
                )

            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.knowledge_service.update_knowledge_base(knowledge_base_uuid, json_data)
                return self.success({})

            elif quart.request.method == 'DELETE':
                await self.ap.knowledge_service.delete_knowledge_base(knowledge_base_uuid)
                return self.success({})

        @self.route(
            '/<knowledge_base_uuid>/files',
            methods=['GET', 'POST'],
        )
        async def get_knowledge_base_files(knowledge_base_uuid: str) -> str:
            if quart.request.method == 'GET':
                files = await self.ap.knowledge_service.get_files_by_knowledge_base(knowledge_base_uuid)
                return self.success(
                    data={
                        'files': files,
                    }
                )

            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                file_id = json_data.get('file_id')
                if not file_id:
                    return self.http_status(400, -1, 'File ID is required')

                # 调用服务层方法将文件与知识库关联
                task_id = await self.ap.knowledge_service.store_file(knowledge_base_uuid, file_id)
                return self.success(
                    {
                        'task_id': task_id,
                    }
                )

        @self.route(
            '/<knowledge_base_uuid>/files/<file_id>',
            methods=['DELETE'],
        )
        async def delete_specific_file_in_kb(file_id: str, knowledge_base_uuid: str) -> str:
            await self.ap.knowledge_service.delete_file(knowledge_base_uuid, file_id)
            return self.success({})

        @self.route(
            '/<knowledge_base_uuid>/retrieve',
            methods=['POST'],
        )
        async def retrieve_knowledge_base(knowledge_base_uuid: str) -> str:
            json_data = await quart.request.json
            query = json_data.get('query')
            results = await self.ap.knowledge_service.retrieve_knowledge_base(knowledge_base_uuid, query)
            return self.success(data={'results': results})
