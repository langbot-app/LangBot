from __future__ import annotations

from contextlib import aclosing
import base64
import json
from typing import Any

import quart
from pydantic import TypeAdapter
from pydantic_core import to_jsonable_python
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from ....application.contracts import ApplicationAPIError, ApplicationAPIException
from ....authz import has_permission
from ....context import RequestContext
from .. import group


_DESCRIPTION_FIELDS = (
    'id',
    'label',
    'summary',
    'description',
    'domain',
    'risk',
    'side_effect',
    'streaming',
    'permission',
    'version',
    'input_schema',
    'output_schema',
)


def _encode_binary(value):
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).decode('ascii')
    if isinstance(value, dict):
        return {key: _encode_binary(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_encode_binary(item) for item in value]
    return value


def _json_output(value):
    return to_jsonable_python(_encode_binary(TypeAdapter(Any).dump_python(value, mode='python')))


def _output_schema(schema):
    if isinstance(schema, list):
        return [_output_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    result = {key: _output_schema(value) for key, value in schema.items()}
    if result.get('type') == 'string' and result.get('format') == 'binary':
        result.pop('format')
        result['contentEncoding'] = 'base64'
    return result


@group.group_class('operations', '/api/v1/operations')
class OperationsRouterGroup(group.RouterGroup):
    def _catalog(self):
        return [item for item in self.ap.application_api.operation_catalog() if item['exposure'] != 'none']

    @staticmethod
    def _allowed(item, context):
        return (
            (item['principals'] is None or context.principal.principal_type in item['principals'])
            and has_permission(context, item['permission'])
            and (context.allowed_operation_ids is None or item['id'] in context.allowed_operation_ids)
        )

    @staticmethod
    def _description(item):
        result = {field: item[field] for field in _DESCRIPTION_FIELDS}
        result['output_schema'] = _output_schema(result['output_schema'])
        return result

    def _operation(self, operation_id):
        for item in self.ap.application_api.operation_catalog():
            if item['id'] == operation_id:
                return item
        raise ApplicationAPIException(ApplicationAPIError('unknown_operation', 'Unknown application operation', 404))

    @staticmethod
    def _error(error):
        return quart.jsonify(code=error.code, msg=error.message, data=error.details), error.status_code

    @staticmethod
    async def _input():
        if not await quart.request.get_data():
            return {}
        try:
            payload = await quart.request.get_json()
        except (BadRequest, UnsupportedMediaType):
            payload = None
        if not isinstance(payload, dict):
            raise ApplicationAPIException(ApplicationAPIError('invalid_input', 'Invalid fields: body', 400))
        return {key: value for key, value in payload.items() if key not in {'workspace', 'workspace_uuid'}}

    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def catalog(request_context: RequestContext):
            domain = quart.request.args.get('domain')
            query = quart.request.args.get('q', '').casefold()
            operations = []
            for item in self._catalog():
                if not self._allowed(item, request_context) or (domain and item['domain'] != domain):
                    continue
                if query and query not in json.dumps(self._description(item), ensure_ascii=False).casefold():
                    continue
                operations.append(self._description(item))
            return quart.jsonify(operations=operations)

        @self.route('/<operation_id>', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def describe(operation_id: str, request_context: RequestContext):
            try:
                item = self._operation(operation_id)
                if item['exposure'] == 'none' or not self._allowed(item, request_context):
                    raise ApplicationAPIException(
                        ApplicationAPIError('unknown_operation', 'Unknown application operation', 404)
                    )
                return quart.jsonify(self._description(item))
            except ApplicationAPIException as exc:
                return self._error(exc.error)

        @self.route('/<operation_id>', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def execute(operation_id: str, request_context: RequestContext):
            try:
                self._operation(operation_id)
                result = await self.ap.application_api.execute(operation_id, request_context, await self._input())
                return self.success(_json_output(result))
            except ApplicationAPIException as exc:
                return self._error(exc.error)

        @self.route('/<operation_id>/stream', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def stream(operation_id: str, request_context: RequestContext):
            try:
                item = self._operation(operation_id)
                if not item['streaming']:
                    raise ApplicationAPIException(
                        ApplicationAPIError('invalid_execution_mode', 'Use the operation execution mode', 400)
                    )
                payload = await self._input()
            except ApplicationAPIException as exc:
                return self._error(exc.error)

            async def events():
                try:
                    async with aclosing(
                        self.ap.application_api.stream(operation_id, request_context, payload)
                    ) as source:
                        async for event in source:
                            yield f'data: {json.dumps(_json_output(event), ensure_ascii=False)}\n\n'
                except ApplicationAPIException as exc:
                    error = {'code': exc.error.code, 'msg': exc.error.message}
                    yield f'event: error\ndata: {json.dumps(error, ensure_ascii=False)}\n\n'
                else:
                    yield 'event: done\ndata: {}\n\n'

            response = quart.Response(events(), mimetype='text/event-stream')
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['X-Accel-Buffering'] = 'no'
            response.timeout = None
            return response
