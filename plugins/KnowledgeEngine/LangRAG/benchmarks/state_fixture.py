"""Explicit in-memory Host storage for offline tests/benchmarks only."""
from components.observability.installation import InstallationTelemetry
from components.offload import BoundedOffload


async def attach_installation_state(plugin):
    data = {}
    async def keys():
        return list(data)
    async def get(key):
        return data[key]
    async def set_value(key, value):
        data[key] = value
    plugin.get_plugin_storage_keys = keys
    plugin.get_plugin_storage = get
    plugin.set_plugin_storage = set_value
    plugin.offload = BoundedOffload()
    plugin.telemetry = InstallationTelemetry(plugin)
    await plugin.telemetry.initialize()
    return plugin
