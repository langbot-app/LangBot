"""Web-session-only assistant endpoints backed by the Application API."""

import asyncio
import json
from contextlib import aclosing

import quart
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .. import group
from ...authz import Permission
from ...context import RequestContext
from ...service.assistant import AssistantError


class StopInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0, strict=True)


class TurnInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0, strict=True)
    text: str | None = Field(default=None, min_length=1, max_length=8000)
    approved: bool | None = Field(default=None, strict=True)
    model_uuid: UUID | None = None


@group.group_class('assistant', '/api/v1/assistant')
class AssistantRouterGroup(group.RouterGroup):
    async def initialize(self):
        @self.route('/conversations', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def list_conversations(request_context: RequestContext):
            return self.success(
                data={'conversations': await self.call_application('assistant.list', request_context, {})}
            )

        @self.route('/conversations/<conversation_id>/stop', methods=['POST'], permission=Permission.RUNTIME_OPERATE)
        async def stop(conversation_id: str, request_context: RequestContext):
            try:
                body = StopInput.model_validate(await quart.request.get_json())
                return self.success(
                    data=await self.call_application(
                        'assistant.stop',
                        request_context,
                        {'conversation_id': conversation_id, 'revision': body.revision},
                    )
                )
            except ValidationError:
                return self.http_status(400, 'invalid_input', 'Invalid stop request')
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route('/recommended-model', methods=['GET'], permission=Permission.RUNTIME_OPERATE)
        async def recommended_model(request_context: RequestContext):
            try:
                return self.success(
                    data=await self.call_application('assistant.recommended_model', request_context, {})
                )
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route('/conversations', methods=['POST'], permission=Permission.RUNTIME_OPERATE)
        async def create(request_context: RequestContext):
            try:
                return self.success(data=await self.call_application('assistant.create', request_context, {}))
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route('/conversations/<conversation_id>', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get(conversation_id: str, request_context: RequestContext):
            try:
                return self.success(
                    data=await self.call_application(
                        'assistant.get', request_context, {'conversation_id': conversation_id}
                    )
                )
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route('/conversations/<conversation_id>/turn', methods=['POST'], permission=Permission.RUNTIME_OPERATE)
        async def turn(conversation_id: str, request_context: RequestContext):
            try:
                body = TurnInput.model_validate(await quart.request.get_json())
                if (body.text is None) == (body.approved is None) or (body.text is not None and not body.text.strip()):
                    return self.http_status(400, 'invalid_input', 'Provide text or an approval decision')
                conversation = await self.call_application(
                    'assistant.turn',
                    request_context,
                    {'conversation_id': conversation_id, **body.model_dump(mode='json')},
                )
                return self.success(data=conversation)
            except ValidationError:
                return self.http_status(400, 'invalid_input', 'Invalid assistant request')
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route(
            '/conversations/<conversation_id>/turn/stream', methods=['POST'], permission=Permission.RUNTIME_OPERATE
        )
        async def stream_turn(conversation_id: str, request_context: RequestContext):
            try:
                body = TurnInput.model_validate(await quart.request.get_json())
                if (body.text is None) == (body.approved is None) or (body.text is not None and not body.text.strip()):
                    return self.http_status(400, 'invalid_input', 'Provide text or an approval decision')
            except ValidationError:
                return self.http_status(400, 'invalid_input', 'Invalid assistant request')
            try:
                return await assistant_stream_response(
                    self.stream_application(
                        'assistant.stream',
                        request_context,
                        {'conversation_id': conversation_id, **body.model_dump(mode='json')},
                    )
                )
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)


async def assistant_stream_response(source):
    """Keep the run alive after disconnect; only an explicit stop cancels it."""
    # Consume the admission frame so startup errors remain HTTP errors without waiting for a model.
    await anext(source)

    async def stream():
        async with aclosing(source):
            while True:
                pending = asyncio.create_task(anext(source))
                try:
                    while not (await asyncio.wait({pending}, timeout=15))[0]:
                        yield '\n'
                    try:
                        frame = pending.result()
                    except StopAsyncIteration:
                        return
                finally:
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                yield json.dumps(frame, ensure_ascii=False) + '\n'
                if frame['kind'] in {'completed', 'error'}:
                    return

    response = quart.Response(stream(), content_type='application/x-ndjson; charset=utf-8')
    response.timeout = None
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Accel-Buffering'] = 'no'
    return response
