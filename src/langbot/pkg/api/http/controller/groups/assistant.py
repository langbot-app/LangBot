"""Web-session-only assistant endpoints; resource tools use the existing service layer."""

import quart
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .. import group
from ...authz import Permission
from ...context import RequestContext
from ...service.assistant import AssistantError, AssistantService


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

        @self.route('/conversations', methods=['POST'], permission=Permission.RUNTIME_OPERATE)
        async def create(request_context: RequestContext):
            try:
                return self.success(data=service.public_view(await service.create(request_context)))
            except AssistantError as exc:
                return self.http_status(exc.status, exc.code, exc.code)

        @self.route('/conversations/<conversation_id>', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get(conversation_id: str, request_context: RequestContext):
            try:
                return self.success(data=service.public_view(await service.get(request_context, conversation_id)))
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
