import quart
import mimetypes
from ... import group
from langbot.pkg.utils import importutil


@group.group_class('adapters', '/api/v1/platform/adapters')
class AdaptersRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'])
        async def _() -> str:
            return self.success(data={'adapters': self.ap.platform_mgr.get_available_adapters_info()})

        @self.route('/<adapter_name>', methods=['GET'])
        async def _(adapter_name: str) -> str:
            adapter_info = self.ap.platform_mgr.get_available_adapter_info_by_name(adapter_name)

            if adapter_info is None:
                return self.http_status(404, -1, 'adapter not found')

            return self.success(data={'adapter': adapter_info})

        @self.route('/<adapter_name>/icon', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _(adapter_name: str) -> quart.Response:
            adapter_manifest = self.ap.platform_mgr.get_available_adapter_manifest_by_name(adapter_name)

            if adapter_manifest is None:
                return self.http_status(404, -1, 'adapter not found')

            icon_path = adapter_manifest.icon_rel_path

            if icon_path is None:
                return self.http_status(404, -1, 'icon not found')

            return quart.Response(
                importutil.read_resource_file_bytes(icon_path), mimetype=mimetypes.guess_type(icon_path)[0]
            )
