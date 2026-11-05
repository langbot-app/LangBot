"""Marketplace search and agent-driven installation through the Workspace API."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from langbot.pkg.api.application import plugin_operations as ops
from langbot.pkg.api.application.api import ApplicationAPI
from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.application.plugin_permissions import expand_declaration
from langbot.pkg.api.application.tool_grants import get_workspace_operations_catalog
from langbot.pkg.api.authz import permissions_for_role
from langbot.pkg.api.context import ExecutionContext, PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.core import taskmgr


def context(principal=PrincipalType.ACCOUNT, role='owner'):
    return RequestContext(
        'instance-a',
        3,
        'request',
        'test',
        PrincipalContext(principal, account_uuid='member' if principal == PrincipalType.ACCOUNT else None),
        WorkspaceContext('workspace-a', None, role, permissions_for_role(role)),
    )


def app(*, marketplace=True, installed=False, space_url='https://space.example/'):
    execution = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=3)
    rows = SimpleNamespace(first=lambda: ('installation',) if installed else None)
    return SimpleNamespace(
        plugin_connector=SimpleNamespace(
            require_workspace_context=AsyncMock(return_value=execution),
            list_plugins=AsyncMock(return_value=[]),
        ),
        mcp_service=SimpleNamespace(get_mcp_servers=AsyncMock(return_value=[])),
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock(return_value=rows)),
        task_mgr=SimpleNamespace(
            create_user_task=Mock(side_effect=lambda coro, **_: coro.close() or SimpleNamespace(id=7))
        ),
        instance_config=SimpleNamespace(
            data={'plugin': {'enable_marketplace': marketplace}, 'space': {'url': space_url}, 'system': {}}
        ),
    )


@pytest.fixture
def space(monkeypatch):
    requests = []
    reply = {
        'code': 0,
        'data': {
            'plugins': [
                {
                    'ID': 29,
                    'plugin_id': 'langbot-team/QWeather',
                    'author': 'langbot-team',
                    'name': 'QWeather',
                    'latest_version': '0.1.6',
                    'components': {'Command': 1},
                    'certificate_id': 'cert:internal',
                    'deleted_at': None,
                }
            ],
            'total': 1,
        },
    }
    state = {'reply': reply}

    def handler(request):
        requests.append(request)
        reply = state['reply']
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, json=reply)

    original = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(ops.httpx, 'AsyncClient', client)
    return SimpleNamespace(requests=requests, state=state)


@pytest.mark.asyncio
async def test_marketplace_search_proxies_configured_space_and_projects_results(space):
    result = await ops.marketplace_search(
        app(), context(), ops.MarketplaceSearchInput(query='weather', component_filter='Tool')
    )
    request = space.requests[0]
    assert str(request.url) == 'https://space.example/api/v1/marketplace/plugins/search'
    assert json.loads(request.content) == {
        'query': 'weather',
        'page': 1,
        'page_size': 10,
        'sort_by': 'install_count',
        'sort_order': 'DESC',
        'component_filter': 'Tool',
    }
    assert result == {
        'plugins': [
            {
                'plugin_id': 'langbot-team/QWeather',
                'author': 'langbot-team',
                'name': 'QWeather',
                'latest_version': '0.1.6',
                'components': {'Command': 1},
            }
        ],
        'total': 1,
        'page': 1,
        'page_size': 10,
    }


@pytest.mark.asyncio
async def test_marketplace_search_respects_disabled_marketplace_and_bad_responses(space):
    with pytest.raises(ApplicationAPIException) as error:
        await ops.marketplace_search(app(marketplace=False), context(), ops.MarketplaceSearchInput())
    assert (error.value.error.code, error.value.error.status_code) == ('marketplace_disabled', 503)
    assert space.requests == []

    for reply in ({'code': 1, 'msg': 'boom'}, httpx.ConnectError('offline'), httpx.Response(500)):
        space.state['reply'] = reply
        with pytest.raises(ApplicationAPIException) as error:
            await ops.marketplace_search(app(), context(), ops.MarketplaceSearchInput())
        assert (error.value.error.code, error.value.error.status_code) == ('marketplace_unavailable', 502)


def test_marketplace_search_input_is_bounded():
    for invalid in ({'page_size': 51}, {'sort_by': 'hot_score'}, {'component_filter': '../x'}, {'query': 'x' * 201}):
        with pytest.raises(Exception):
            ops.MarketplaceSearchInput(**invalid)


@pytest.mark.asyncio
@pytest.mark.parametrize('principal', [PrincipalType.PLUGIN, PrincipalType.PROCESSOR])
async def test_agents_cannot_auto_confirm_or_replace_installations(principal):
    ap = app()
    payload = ops.MarketplaceInput(plugin_author='a', plugin_name='b', auto_confirm_permissions=True)
    with pytest.raises(ApplicationAPIException) as error:
        await ops.install_marketplace(ap, context(principal), payload)
    assert error.value.error.code == 'permission_denied'

    ap = app(installed=True)
    with pytest.raises(ApplicationAPIException) as error:
        await ops.install_marketplace(ap, context(principal), ops.MarketplaceInput(plugin_author='a', plugin_name='b'))
    assert (error.value.error.code, error.value.error.status_code) == ('plugin_already_installed', 409)
    ap.task_mgr.create_user_task.assert_not_called()

    ap = app(marketplace=False)
    with pytest.raises(ApplicationAPIException) as error:
        await ops.install_marketplace(ap, context(principal), ops.MarketplaceInput(plugin_author='a', plugin_name='b'))
    assert error.value.error.code == 'marketplace_disabled'

    ap = app()
    result = await ops.install_marketplace(
        ap, context(principal), ops.MarketplaceInput(plugin_author='a', plugin_name='b')
    )
    assert result == {'task_id': 7}


@pytest.mark.asyncio
async def test_members_keep_reinstalling_through_marketplace():
    ap = app(installed=True, marketplace=False)
    result = await ops.install_marketplace(ap, context(), ops.MarketplaceInput(plugin_author='a', plugin_name='b'))
    assert result == {'task_id': 7}


def test_plugins_and_processors_may_be_granted_search_install_and_task_status():
    api = ApplicationAPI(None)
    ap = SimpleNamespace(application_api=api)
    granted = ['plugin.install.marketplace', 'plugin.marketplace.search', 'task.get']
    assert expand_declaration(ap, {'workspace_operations': granted})['workspace_operations'] == granted
    for rejected in (['plugin.install.*'], ['plugin.install.github'], ['plugin.*'], ['task.list']):
        with pytest.raises(ApplicationAPIException):
            expand_declaration(ap, {'workspace_operations': rejected})

    catalog = {item['id']: item for item in get_workspace_operations_catalog(ap, context())['workspace_operations']}
    assert catalog['plugin.install.marketplace']['risk'] == 'dangerous'
    assert catalog['plugin.install.marketplace']['grantable']
    assert catalog['plugin.marketplace.search']['risk'] == 'read'
    assert catalog['task.get']['risk'] == 'read'
    assert 'plugin.install.github' not in catalog


@pytest.mark.asyncio
async def test_task_status_hides_internal_logs_from_agents():
    async def work():
        return None

    manager = taskmgr.AsyncTaskManager(
        SimpleNamespace(instance_config=SimpleNamespace(data={}), event_loop=asyncio.get_running_loop())
    )
    task_context = taskmgr.TaskContext.new()
    task_context.trace('secret internal diagnostic')
    task_context.metadata['pending_permission_confirmation'] = True
    wrapper = manager.create_user_task(
        work(), context=task_context, instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=3
    )
    await asyncio.gather(wrapper.task)
    ap = SimpleNamespace(task_mgr=manager)
    from langbot.pkg.api.application.auxiliary import TaskGet, task_get

    for principal in (PrincipalType.PLUGIN, PrincipalType.PROCESSOR):
        public = await task_get(ap, context(principal), TaskGet(task_id=wrapper.id))
        assert public['status'] == 'succeeded'
        assert public['pending_permission_confirmation'] is True
        assert 'secret internal diagnostic' not in str(public)
    member = await task_get(ap, context(), TaskGet(task_id=wrapper.id))
    assert 'secret internal diagnostic' in str(member)
