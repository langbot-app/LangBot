import httpx

from langbot.pkg.api.application.client import ApplicationAPIClient


def test_application_client_uses_http_service_api_for_pipeline_operations():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.read()))
        if request.url.path == '/api/v1/pipelines':
            return httpx.Response(200, json={'code': 0, 'data': {'pipelines': [{'uuid': 'p1'}]}})
        if request.url.path == '/api/v1/pipelines/p1':
            return httpx.Response(200, json={'code': 0, 'data': {'pipeline': {'uuid': 'p1'}}})
        if request.url.path.endswith('/extensions') and request.method == 'GET':
            return httpx.Response(200, json={'code': 0, 'data': {'bound_plugins': []}})
        return httpx.Response(200, json={'code': 0, 'data': {}})

    client = ApplicationAPIClient(
        'http://langbot.test',
        api_key='test-key',
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.list_pipelines() == [{'uuid': 'p1'}]
        assert client.get_pipeline('p1') == {'uuid': 'p1'}
        assert client.get_pipeline_extensions('p1') == {'bound_plugins': []}
        client.update_pipeline_extensions(
            'p1',
            bound_plugins=[],
            bound_mcp_servers=[],
            bound_skills=[],
            bound_mcp_resources=[],
            enable_all_plugins=False,
            enable_all_mcp_servers=False,
            enable_all_skills=False,
            mcp_resource_agent_read_enabled=False,
        )
    finally:
        client.close()

    assert [method for method, _path, _body in calls] == ['GET', 'GET', 'GET', 'PUT']
    assert all(body == b'' for _method, _path, body in calls[:3])
