"""Call Pipeline Node - invoke an existing pipeline

Node metadata is loaded from: ../../templates/metadata/nodes/call_pipeline.yaml
"""

from __future__ import annotations

from typing import Any, ClassVar

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from ..entities import ExecutionContext
from ..node import WorkflowNode, workflow_node, NodePort, NodeConfig


@workflow_node('call_pipeline')
class CallPipelineNode(WorkflowNode):
    """Call pipeline node - invoke an existing pipeline"""

    type_name = "call_pipeline"
    category = "action"
    icon = "⚙️"
    name = "call_pipeline"
    description = "call_pipeline"
    name_zh = "调用 Pipeline"
    name_en = "Call Pipeline"
    description_zh = "调用现有的 Pipeline 进行处理"
    description_en = "Invoke an existing Pipeline for processing"

    inputs: ClassVar[list[NodePort]] = []
    outputs: ClassVar[list[NodePort]] = []
    config_schema: ClassVar[list[NodeConfig]] = []

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        if not self.ap:
            raise RuntimeError('Application instance not available — cannot call pipeline')

        raw_query = inputs.get('query', '')
        query_text = str(raw_query or inputs.get('input') or '')
        pipeline_ref = str(self.get_config('pipeline_uuid', '') or '').strip()

        if not pipeline_ref:
            raise ValueError('No pipeline configured for call pipeline node')

        pipeline_data = await self.ap.pipeline_service.get_pipeline(pipeline_ref)
        if pipeline_data is None:
            pipeline_data = await self.ap.pipeline_service.get_pipeline_by_name(pipeline_ref)
        if pipeline_data is None:
            raise ValueError(f'Pipeline not found: {pipeline_ref}')

        pipeline_uuid = str(pipeline_data.get('uuid', '') or '')
        if not pipeline_uuid:
            raise ValueError(f'Pipeline UUID missing for: {pipeline_ref}')

        runtime_pipeline = await self.ap.pipeline_mgr.get_pipeline_by_uuid(pipeline_uuid)
        if runtime_pipeline is None:
            raise ValueError(f'Runtime pipeline not loaded: {pipeline_uuid}')

        adapter = _WorkflowPipelineCaptureAdapter(context=context)
        adapter.bot_account_id = 'workflow-call-pipeline'

        message_event = self._build_message_event(query_text, context)
        message_chain = message_event.message_chain
        launcher_type = provider_session.LauncherTypes.GROUP if context.message_context and context.message_context.is_group else provider_session.LauncherTypes.PERSON
        launcher_id = context.session_id or context.execution_id
        sender_id = (
            context.message_context.sender_id
            if context.message_context and context.message_context.sender_id
            else context.user_id or f'workflow_{context.execution_id}'
        )

        query = pipeline_query.Query(
            bot_uuid=context.bot_id,
            query_id=-1,
            launcher_type=launcher_type,
            launcher_id=launcher_id,
            sender_id=sender_id,
            message_event=message_event,
            message_chain=message_chain,
            variables={
                '_called_from_workflow': True,
                '_workflow_execution_id': context.execution_id,
                '_workflow_id': context.workflow_id,
                **dict(context.variables or {}),
            },
            resp_messages=[],
            resp_message_chain=[],
            adapter=adapter,
            pipeline_uuid=pipeline_uuid,
        )

        await runtime_pipeline.run(query)

        response_text = adapter.get_last_text_response()
        result = {
            'pipeline_uuid': pipeline_uuid,
            'pipeline_name': pipeline_data.get('name', ''),
            'responses': adapter.responses,
            'query_text': query_text,
        }

        return {'response': response_text, 'result': result}

    def _build_message_event(
        self,
        query_text: str,
        context: ExecutionContext,
    ) -> platform_events.MessageEvent:
        message_chain_data = context.trigger_data.get('message_chain') or context.trigger_data.get('message', [])
        if isinstance(message_chain_data, list) and message_chain_data:
            message_chain = platform_message.MessageChain.model_validate(message_chain_data)
        else:
            message_chain = platform_message.MessageChain([platform_message.Plain(text=query_text)])

        if context.message_context and context.message_context.is_group:
            group = platform_entities.Group(
                id=context.message_context.group_id or context.session_id or 'workflow_group',
                name='Workflow Group',
                permission=platform_entities.Permission.Member,
            )
            sender = platform_entities.GroupMember(
                id=context.message_context.sender_id,
                member_name=context.message_context.sender_name or 'Workflow User',
                permission=platform_entities.Permission.Member,
                group=group,
            )
            return platform_events.GroupMessage(
                sender=sender,
                message_chain=message_chain,
                time=context.message_context.raw_message.get('time') if context.message_context.raw_message else None,
            )

        sender = platform_entities.Friend(
            id=context.message_context.sender_id if context.message_context else context.user_id or 'workflow_user',
            nickname=context.message_context.sender_name if context.message_context else 'Workflow User',
            remark=context.message_context.sender_name if context.message_context else 'Workflow User',
        )
        return platform_events.FriendMessage(
            sender=sender,
            message_chain=message_chain,
            time=context.message_context.raw_message.get('time') if context.message_context and context.message_context.raw_message else None,
        )


class _WorkflowPipelineCaptureAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    responses: list[dict[str, Any]] = []

    def __init__(self, context: ExecutionContext):
        super().__init__(config={}, logger=None)
        self.context = context
        self.responses = []

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        payload = {
            'type': 'send',
            'target_type': target_type,
            'target_id': target_id,
            'content': str(message),
            'message_chain': message.model_dump(),
        }
        self.responses.append(payload)
        return payload

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        payload = {
            'type': 'reply',
            'content': str(message),
            'message_chain': message.model_dump(),
            'quote_origin': quote_origin,
        }
        self.responses.append(payload)
        return payload

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message: dict,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        payload = {
            'type': 'reply_chunk',
            'content': str(message),
            'message_chain': message.model_dump(),
            'quote_origin': quote_origin,
            'is_final': is_final,
        }
        self.responses.append(payload)
        return payload

    async def create_message_card(self, message_id, event: platform_events.MessageEvent) -> bool:
        return False

    def register_listener(self, event_type, callback):
        return None

    def unregister_listener(self, event_type, callback):
        return None

    async def run_async(self):
        return None

    async def is_stream_output_supported(self) -> bool:
        return False

    async def kill(self) -> bool:
        return True

    def get_last_text_response(self) -> str:
        if not self.responses:
            return ''
        return str(self.responses[-1].get('content', '') or '')
