import quart

from ... import group


@group.group_class('provider/requesters', '/api/v1/provider/requesters')
class RequestersRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'])
        async def _() -> quart.Response:
            model_type = quart.request.args.get('type', '')
            return self.success(data={'requesters': self.ap.model_mgr.get_available_requesters_info(model_type)})

        @self.route('/<requester_name>', methods=['GET'])
        async def _(requester_name: str) -> quart.Response:
            requester_info = self.ap.model_mgr.get_available_requester_info_by_name(requester_name)

            if requester_info is None:
                return self.http_status(404, -1, 'requester not found')

            return self.success(data={'requester': requester_info})

        @self.route('/<requester_name>/icon', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _(requester_name: str) -> quart.Response:
            requester_manifest = self.ap.model_mgr.get_available_requester_manifest_by_name(requester_name)

            if requester_manifest is None:
                return self.http_status(404, -1, 'requester not found')

            icon_path = requester_manifest.icon_rel_path

            if icon_path is None:
                return self.http_status(404, -1, 'icon not found')

            return await quart.send_file(icon_path)
