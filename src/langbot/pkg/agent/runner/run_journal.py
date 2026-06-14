"""Run-side effects for AgentRunner executions."""

from __future__ import annotations

import typing

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .errors import RunnerProtocolError
from .host_models import AgentBinding, AgentEventEnvelope
from .persistent_state_store import PersistentStateStore, get_persistent_state_store


# Maximum inline artifact content size (1MB)
MAX_ARTIFACT_INLINE_BYTES = 1 * 1024 * 1024


class AgentRunJournal:
    """Persist run events, transcript records, artifacts, and state updates."""

    ap: app.Application

    _persistent_state_store: PersistentStateStore | None

    def __init__(self, ap: app.Application):
        self.ap = ap
        self._persistent_state_store = None

    @staticmethod
    def _to_plain_dict(value: typing.Any) -> dict[str, typing.Any]:
        if hasattr(value, 'model_dump'):
            value = value.model_dump(mode='json')
        if isinstance(value, dict):
            return dict(value)
        return {}

    @classmethod
    def _sanitize_content_item(cls, value: typing.Any) -> typing.Any:
        item = cls._to_plain_dict(value)
        if not item:
            return value
        item_type = item.get('type')
        if item_type == 'image_base64' and item.get('image_base64'):
            item['image_base64'] = None
            item['content_redacted'] = True
        elif item_type == 'file_base64' and item.get('file_base64'):
            item['file_base64'] = None
            item['content_redacted'] = True
        return item

    @classmethod
    def _sanitize_attachment_ref(cls, value: typing.Any) -> dict[str, typing.Any]:
        item = cls._to_plain_dict(value)
        if item.get('content'):
            item['content'] = None
            item['content_redacted'] = True
        return item

    @classmethod
    def _sanitize_contents(cls, contents: typing.Iterable[typing.Any]) -> list[typing.Any]:
        return [cls._sanitize_content_item(content) for content in contents]

    @classmethod
    def _sanitize_attachments(cls, attachments: typing.Iterable[typing.Any]) -> list[dict[str, typing.Any]]:
        return [cls._sanitize_attachment_ref(attachment) for attachment in attachments]

    async def handle_state_updated_event(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
        run_id: str | None = None,
    ) -> None:
        """Handle state.updated result in event-first mode."""
        data = result_dict.get('data', {})

        result_run_id = result_dict.get('run_id')
        if run_id and result_run_id and result_run_id != run_id:
            raise RunnerProtocolError(
                descriptor.id,
                f'state.updated run_id mismatch: expected {run_id}, got {result_run_id}',
            )

        scope = data.get('scope')
        if not scope:
            raise RunnerProtocolError(
                descriptor.id,
                'state.updated missing required field: scope',
            )

        key = data.get('key')
        value = data.get('value')

        if not key:
            raise RunnerProtocolError(
                descriptor.id,
                'state.updated missing required field: key',
            )

        if self._persistent_state_store is None:
            self._persistent_state_store = get_persistent_state_store(
                self.ap.persistence_mgr.get_db_engine()
            )

        success, error = await self._persistent_state_store.apply_update_from_event(
            event=event,
            binding=binding,
            descriptor=descriptor,
            scope=scope,
            key=key,
            value=value,
            logger=self.ap.logger,
        )

        if success:
            self.ap.logger.debug(
                f'Runner {descriptor.id} state.updated (event mode): scope={scope}, key={key}'
            )
        elif error:
            self.ap.logger.warning(
                f'Runner {descriptor.id} state.updated rejected: {error}'
            )

    async def write_event_log(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        run_id: str,
        runner_id: str,
        metadata: dict[str, typing.Any] | None = None,
    ) -> str:
        """Write incoming event to EventLog."""
        import datetime

        from .event_log_store import EventLogStore

        store = EventLogStore(self.ap.persistence_mgr.get_db_engine())

        input_summary = None
        input_json = None
        if event.input:
            if event.input.text:
                input_summary = event.input.text[:1000]
            input_json = {
                'text': event.input.text,
                'contents': self._sanitize_contents(event.input.contents),
                'attachments': self._sanitize_attachments(event.input.attachments),
            }

        return await store.append_event(
            event_id=event.event_id,
            event_type=event.event_type,
            source=event.source,
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            conversation_id=event.conversation_id,
            thread_id=event.thread_id,
            actor_type=event.actor.actor_type if event.actor else None,
            actor_id=event.actor.actor_id if event.actor else None,
            actor_name=event.actor.actor_name if event.actor else None,
            subject_type=event.subject.subject_type if event.subject else None,
            subject_id=event.subject.subject_id if event.subject else None,
            input_summary=input_summary,
            input_json=input_json,
            run_id=run_id,
            runner_id=runner_id,
            event_time=(
                datetime.datetime.fromtimestamp(event.event_time, datetime.timezone.utc)
                if event.event_time
                else None
            ),
            metadata=metadata,
        )

    async def register_input_artifacts(
        self,
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
    ) -> None:
        """Register current-event attachments referenced by AgentInput."""
        if not event.input or not event.input.attachments:
            return

        from .artifact_store import ArtifactStore

        store = ArtifactStore(self.ap.persistence_mgr.get_db_engine())

        for attachment in event.input.attachments:
            data = attachment.model_dump(mode='json') if hasattr(attachment, 'model_dump') else attachment
            if not isinstance(data, dict):
                continue

            artifact_id = data.get('artifact_id')
            artifact_type = data.get('artifact_type') or 'file'
            if not artifact_id:
                continue

            content, parsed_mime_type = self.decode_attachment_content(data.get('content'))
            url = data.get('url')
            platform_ref_id = data.get('id')
            storage_key = None
            storage_type = 'metadata_only'
            if content is None:
                if url:
                    storage_key = url
                    storage_type = 'url'
                elif platform_ref_id:
                    storage_key = platform_ref_id
                    storage_type = 'platform_ref'

            metadata = {
                'input_attachment': True,
                'input_source': data.get('source') or 'platform',
            }
            if url:
                metadata['url'] = url
            if platform_ref_id:
                metadata['platform_ref_id'] = platform_ref_id

            try:
                await store.register_artifact(
                    artifact_id=artifact_id,
                    artifact_type=artifact_type,
                    source='platform',
                    storage_key=storage_key,
                    storage_type=storage_type,
                    mime_type=data.get('mime_type') or parsed_mime_type,
                    name=data.get('name'),
                    size_bytes=data.get('size') or (len(content) if content is not None else None),
                    conversation_id=event.conversation_id,
                    run_id=run_id,
                    runner_id=runner_id,
                    bot_id=event.bot_id,
                    workspace_id=event.workspace_id,
                    thread_id=event.thread_id,
                    metadata=metadata,
                    content=content,
                )
            except Exception as e:
                self.ap.logger.warning(
                    f'Failed to register input artifact {artifact_id}: {e}'
                )

    def decode_attachment_content(
        self,
        content: typing.Any,
    ) -> tuple[bytes | None, str | None]:
        """Decode base64 attachment content, including data URLs."""
        if not isinstance(content, str) or not content:
            return None, None

        import base64
        import binascii

        mime_type = None
        payload = content
        if content.startswith('data:') and ',' in content:
            header, payload = content.split(',', 1)
            if ';base64' in header:
                mime_type = header[5:].split(';', 1)[0] or None

        try:
            return base64.b64decode(payload, validate=False), mime_type
        except (binascii.Error, ValueError):
            return None, mime_type

    async def write_user_transcript(
        self,
        event: AgentEventEnvelope,
        event_log_id: str,
    ) -> None:
        """Write user message to Transcript."""
        from .transcript_store import TranscriptStore

        store = TranscriptStore(self.ap.persistence_mgr.get_db_engine())

        content = event.input.text if event.input else None
        content_json = None
        if event.input:
            content_json = {
                'role': 'user',
                'content': self._sanitize_contents(event.input.contents) if event.input.contents else [],
            }

        artifact_refs = []
        if event.input and event.input.attachments:
            for a in event.input.attachments:
                artifact_refs.append(self._sanitize_attachment_ref(a))

        await store.append_transcript(
            transcript_id=None,
            event_id=event_log_id,
            conversation_id=event.conversation_id,
            role='user',
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            content=content,
            content_json=content_json,
            artifact_refs=artifact_refs if artifact_refs else None,
            thread_id=event.thread_id,
            item_type='message',
            metadata={
                'actor_type': event.actor.actor_type if event.actor else None,
                'actor_id': event.actor.actor_id if event.actor else None,
            },
        )

    async def handle_artifact_created(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
    ) -> dict[str, typing.Any]:
        """Handle artifact.created result, register artifact, and write EventLog."""
        import base64
        import uuid

        from .artifact_store import ArtifactStore
        from .event_log_store import EventLogStore

        data = result_dict.get('data', {})

        result_run_id = result_dict.get('run_id')
        if result_run_id and result_run_id != run_id:
            raise RunnerProtocolError(
                runner_id,
                f'artifact.created run_id mismatch: expected {run_id}, got {result_run_id}',
            )

        artifact_id = data.get('artifact_id') or str(uuid.uuid4())
        artifact_type = data.get('artifact_type')
        if not artifact_type:
            raise RunnerProtocolError(
                runner_id,
                'artifact.created missing required field: artifact_type',
            )

        mime_type = data.get('mime_type')
        name = data.get('name')
        size_bytes = data.get('size_bytes')
        sha256 = data.get('sha256')
        metadata = data.get('metadata')
        content_base64 = data.get('content_base64')

        content: bytes | None = None
        if content_base64:
            try:
                content = base64.b64decode(content_base64, validate=True)
            except Exception as e:
                raise RunnerProtocolError(
                    runner_id,
                    f'artifact.created invalid base64 content: {e}',
                )

            if len(content) > MAX_ARTIFACT_INLINE_BYTES:
                raise RunnerProtocolError(
                    runner_id,
                    f'artifact.created content size {len(content)} bytes exceeds limit {MAX_ARTIFACT_INLINE_BYTES} bytes',
                )

        artifact_store = ArtifactStore(self.ap.persistence_mgr.get_db_engine())
        try:
            registered_id = await artifact_store.register_artifact(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                source='runner',
                mime_type=mime_type,
                name=name,
                size_bytes=size_bytes,
                sha256=sha256,
                conversation_id=event.conversation_id,
                run_id=run_id,
                runner_id=runner_id,
                bot_id=event.bot_id,
                workspace_id=event.workspace_id,
                thread_id=event.thread_id,
                metadata=metadata,
                content=content,
            )
        except Exception as e:
            raise RunnerProtocolError(
                runner_id,
                f'artifact.created failed to register artifact: {e}',
            )

        event_log_store = EventLogStore(self.ap.persistence_mgr.get_db_engine())
        await event_log_store.append_event(
            event_id=str(uuid.uuid4()),
            event_type='artifact.created',
            source='runner',
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            conversation_id=event.conversation_id,
            thread_id=event.thread_id,
            actor_type=event.actor.actor_type if event.actor else None,
            actor_id=event.actor.actor_id if event.actor else None,
            actor_name=event.actor.actor_name if event.actor else None,
            input_summary=f'Artifact created: {artifact_type}',
            input_json={
                'artifact_id': registered_id,
                'artifact_type': artifact_type,
                'mime_type': mime_type,
                'name': name,
                'size_bytes': size_bytes,
            },
            run_id=run_id,
            runner_id=runner_id,
        )

        return {
            'artifact_id': registered_id,
            'artifact_type': artifact_type,
            'mime_type': mime_type,
            'name': name,
        }

    def merge_artifact_refs(
        self,
        pending_refs: list[dict[str, typing.Any]],
        result_dict: dict[str, typing.Any],
    ) -> list[dict[str, typing.Any]]:
        """Merge pending artifact refs with a message's own refs."""
        merged = list(pending_refs)
        seen_ids = {ref.get('artifact_id') for ref in pending_refs if ref.get('artifact_id')}

        data = result_dict.get('data', {})
        message = data.get('message', {})
        message_refs = message.get('artifact_refs', [])

        if isinstance(message_refs, list):
            for ref in message_refs:
                if isinstance(ref, dict):
                    artifact_id = ref.get('artifact_id')
                    if artifact_id and artifact_id not in seen_ids:
                        merged.append(ref)
                        seen_ids.add(artifact_id)

        return merged

    async def write_steering_dropped_audits(
        self,
        items: list[dict[str, typing.Any]],
        run_id: str,
        runner_id: str,
        *,
        reason: str = 'run_ended',
    ) -> None:
        """Write terminal audit events for steering items left unconsumed."""
        if not items:
            return

        import datetime
        import uuid

        from .event_log_store import EventLogStore

        store = EventLogStore(self.ap.persistence_mgr.get_db_engine())

        for item in items:
            event = item.get('event') if isinstance(item.get('event'), dict) else {}
            input_data = item.get('input') if isinstance(item.get('input'), dict) else {}
            conversation = item.get('conversation') if isinstance(item.get('conversation'), dict) else {}
            actor = item.get('actor') if isinstance(item.get('actor'), dict) else {}
            subject = item.get('subject') if isinstance(item.get('subject'), dict) else {}

            text = input_data.get('text')
            input_summary = text[:1000] if isinstance(text, str) and text else 'Unconsumed steering input dropped'
            event_time = None
            raw_event_time = event.get('event_time')
            if raw_event_time:
                try:
                    event_time = datetime.datetime.fromtimestamp(
                        raw_event_time,
                        datetime.timezone.utc,
                    )
                except (TypeError, ValueError, OSError):
                    event_time = None

            await store.append_event(
                event_id=str(uuid.uuid4()),
                event_type='steering.dropped',
                source='host',
                bot_id=conversation.get('bot_id'),
                workspace_id=conversation.get('workspace_id'),
                conversation_id=conversation.get('conversation_id'),
                thread_id=conversation.get('thread_id'),
                actor_type=actor.get('actor_type'),
                actor_id=actor.get('actor_id'),
                actor_name=actor.get('actor_name'),
                subject_type=subject.get('subject_type'),
                subject_id=subject.get('subject_id'),
                input_summary=input_summary,
                input_json={
                    'text': text,
                    'contents': self._sanitize_contents(input_data.get('contents') or []),
                    'attachments': self._sanitize_attachments(input_data.get('attachments') or []),
                },
                run_id=run_id,
                runner_id=runner_id,
                event_time=event_time,
                metadata={
                    'steering': {
                        'status': 'dropped',
                        'reason': reason,
                        'original_event_id': event.get('event_id'),
                        'claimed_run_id': item.get('claimed_run_id'),
                        'claimed_runner_id': item.get('runner_id'),
                        'claimed_at': item.get('claimed_at'),
                    },
                },
            )

    async def write_assistant_transcript(
        self,
        result_dict: dict[str, typing.Any],
        event: AgentEventEnvelope,
        run_id: str,
        runner_id: str,
        artifact_refs: list[dict[str, typing.Any]] | None = None,
    ) -> None:
        """Write assistant message to Transcript."""
        import uuid

        from .transcript_store import TranscriptStore

        store = TranscriptStore(self.ap.persistence_mgr.get_db_engine())

        data = result_dict.get('data', {})
        message = data.get('message', {})

        content = None
        content_json = None

        if isinstance(message.get('content'), str):
            content = message['content']
            content_json = message
        elif isinstance(message.get('content'), list):
            text_parts = []
            for c in message['content']:
                if isinstance(c, dict) and c.get('type') == 'text':
                    text_parts.append(c.get('text', ''))
            content = ' '.join(text_parts) if text_parts else None
            content_json = {
                **message,
                'content': self._sanitize_contents(message['content']),
            }

        assistant_event_id = str(uuid.uuid4())

        await store.append_transcript(
            transcript_id=str(uuid.uuid4()),
            event_id=assistant_event_id,
            conversation_id=event.conversation_id,
            role='assistant',
            bot_id=event.bot_id,
            workspace_id=event.workspace_id,
            content=content,
            content_json=content_json,
            artifact_refs=artifact_refs,
            thread_id=event.thread_id,
            item_type='message',
            run_id=run_id,
            runner_id=runner_id,
            metadata={
                'run_id': run_id,
                'runner_id': runner_id,
            },
        )
