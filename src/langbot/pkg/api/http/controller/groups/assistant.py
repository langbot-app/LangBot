"""Web-session-only assistant endpoints; resource tools use the existing service layer."""

import asyncio
import json

import quart
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .. import group
from ...authz import Permission
from ...context import RequestContext
from ...service.assistant import AssistantError, AssistantService


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
        service = AssistantService(self.ap)

        @self.route('/conversations', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def list_conversations(request_context: RequestContext):
            return self.success(data={'conversations': await service.list_conversations(request_context)})

        @self.route('/conversations/<conversation_id>/stop', methods=['POST'], permission=Permission.RUNTIME_OPERATE)
        async def stop(conversation_id: str, request_context: RequestContext):
            try:
                body = StopInput.model_validate(await quart.request.get_json())
                return self.success(data=await service.stop(request_context, conversation_id, body.revision))
            except ValidationError:
                return self.http_status(400, 'invalid_input', 'Invalid stop request')
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route('/recommended-model', methods=['GET'], permission=Permission.RUNTIME_OPERATE)
        async def recommended_model(request_context: RequestContext):
            try:
                return self.success(data=await service.recommended_model(request_context))
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route('/conversations', methods=['POST'], permission=Permission.RUNTIME_OPERATE)
        async def create(request_context: RequestContext):
            try:
                return self.success(data=service.public_view(await service.create(request_context)))
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route('/conversations/<conversation_id>', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get(conversation_id: str, request_context: RequestContext):
            try:
                return self.success(data=await service.progress(request_context, conversation_id))
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route('/conversations/<conversation_id>/turn', methods=['POST'], permission=Permission.RUNTIME_OPERATE)
        async def turn(conversation_id: str, request_context: RequestContext):
            try:
                body = TurnInput.model_validate(await quart.request.get_json())
                if (body.text is None) == (body.approved is None) or (body.text is not None and not body.text.strip()):
                    return self.http_status(400, 'invalid_input', 'Provide text or an approval decision')
                conversation = await service.turn(
                    request_context,
                    conversation_id,
                    body.revision,
                    body.text,
                    body.approved,
                    str(body.model_uuid) if body.model_uuid else None,
                )
                return self.success(data=service.public_view(conversation))
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
                await service.get(request_context, conversation_id)
            except ValidationError:
                return self.http_status(400, 'invalid_input', 'Invalid assistant request')
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)
            try:
                return assistant_stream_response(service, request_context, conversation_id, body)
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)


def assistant_stream_response(service, context, conversation_id, body):
    """Detach execution from the subscriber; only an explicit stop cancels a run."""
    queue = service.start_run(context, conversation_id, body)

    async def stream():
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield '\n'
                continue
            yield json.dumps(frame, ensure_ascii=False) + '\n'
            if frame['kind'] in {'completed', 'error'}:
                break

    response = quart.Response(stream(), content_type='application/x-ndjson; charset=utf-8')
    response.timeout = None
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Accel-Buffering'] = 'no'
    return response
