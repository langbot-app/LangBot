from __future__ import annotations

import quart
import datetime

from .. import group


@group.group_class('market', '/api/v1/market')
class MarketRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/plugins', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """获取插件市场列表"""
            # data = await quart.request.json
            # page = data.get('page', 1)
            # page_size = data.get('page_size', 10)
            # query = data.get('query', '')
            # sort_by = data.get('sort_by', 'stars')
            # sort_order = data.get('sort_order', 'DESC')

            # # 这里是获取插件列表的实现
            # # 实际项目中这部分会连接到真实的插件市场API或数据库
            # # 这里我们只是返回一些假数据作为示例

            # # 模拟延迟
            # import asyncio

            # await asyncio.sleep(0.5)

            # 返回结果
            return self.success(data={'plugins': [], 'total': 0})

        @self.route('/mcp', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            """获取MCP服务器市场列表"""
            data = await quart.request.json
            page = data.get('page', 1)
            page_size = data.get('page_size', 10)
            query = data.get('query', '')
            sort_by = data.get('sort_by', 'stars')
            sort_order = data.get('sort_order', 'DESC')

            # 这里是获取MCP服务器列表的实现
            # 实际项目中这部分会连接到真实的MCP市场API或数据库
            # 这里我们只是返回一些假数据作为示例

            # 模拟延迟
            import asyncio

            await asyncio.sleep(0.5)

            # 生成假数据
            servers = []

            # 只在有搜索关键词或排序时才返回数据
            if query or sort_by:
                now = datetime.datetime.now().isoformat()
                yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()

                test_servers = [
                    {
                        'ID': 1,
                        'CreatedAt': yesterday,
                        'UpdatedAt': now,
                        'DeletedAt': None,
                        'name': 'Google Maps MCP',
                        'author': 'langbot-community',
                        'description': 'Google Maps integration for LangBot, providing geocoding and directions capabilities.',
                        'repository': 'langbot-community/google-maps-mcp',
                        'artifacts_path': '',
                        'stars': 124,
                        'downloads': 342,
                        'status': 'initialized',
                        'synced_at': now,
                        'pushed_at': now,
                        'version': '1.0.0',
                    },
                    {
                        'ID': 2,
                        'CreatedAt': yesterday,
                        'UpdatedAt': now,
                        'DeletedAt': None,
                        'name': 'Weather MCP',
                        'author': 'langbot-community',
                        'description': 'Weather integration for LangBot, providing current weather and forecasts.',
                        'repository': 'langbot-community/weather-mcp',
                        'artifacts_path': '',
                        'stars': 85,
                        'downloads': 215,
                        'status': 'initialized',
                        'synced_at': now,
                        'pushed_at': yesterday,
                        'version': '1.1.0',
                    },
                    {
                        'ID': 3,
                        'CreatedAt': yesterday,
                        'UpdatedAt': now,
                        'DeletedAt': None,
                        'name': 'Serper Search MCP',
                        'author': 'langbot-developers',
                        'description': 'Serper Search integration for LangBot, providing advanced web search capabilities.',
                        'repository': 'langbot-developers/serper-search-mcp',
                        'artifacts_path': '',
                        'stars': 67,
                        'downloads': 178,
                        'status': 'initialized',
                        'synced_at': now,
                        'pushed_at': yesterday,
                        'version': '0.9.0',
                    },
                ]

                # 应用搜索过滤
                if query:
                    query = query.lower()
                    servers = [
                        s
                        for s in test_servers
                        if query in s['name'].lower()
                        or query in s['description'].lower()
                        or query in s['author'].lower()
                    ]
                else:
                    servers = test_servers

                # 应用排序
                reverse = sort_order.upper() == 'DESC'
                if sort_by == 'stars':
                    servers = sorted(servers, key=lambda s: s['stars'], reverse=reverse)
                elif sort_by == 'created_at':
                    servers = sorted(servers, key=lambda s: s['CreatedAt'], reverse=reverse)
                elif sort_by == 'pushed_at':
                    servers = sorted(servers, key=lambda s: s['pushed_at'], reverse=reverse)

                # 应用分页
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                servers = servers[start_idx:end_idx]

            # 返回结果
            return self.success(data={'servers': servers, 'total': len(servers)})
