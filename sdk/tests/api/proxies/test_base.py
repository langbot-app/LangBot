from langbot_plugin.api.proxies.base import APIProxy


def test_api_proxy_stores_runtime_handler_and_container():
    runtime_handler = object()
    plugin_container = object()

    proxy = APIProxy(runtime_handler, plugin_container)

    assert proxy.plugin_runtime_handler is runtime_handler
    assert proxy.plugin_container is plugin_container
