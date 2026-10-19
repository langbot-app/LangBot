"""Runner-owned Box selection over Host-owned execution and file services."""

from __future__ import annotations

import asyncio
import copy
import base64
import hashlib
import uuid
from dataclasses import dataclass, field, replace

from langbot_plugin.api.entities.builtin.platform import message as pm
from langbot_plugin.api.entities.builtin.runner.box import BoxAcquireRequest
from langbot_plugin.box.errors import BoxValidationError
from .export_errors import export_error


@dataclass
class RunBoxBinding:
    run_id: str
    session_id: str
    spec: dict
    io_scope: str
    imported: dict = field(default_factory=dict)
    exported: dict = field(default_factory=dict)
    submitted: set = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    read_only_mounts: list[dict] = field(default_factory=list)
    exported_fingerprints: dict = field(default_factory=dict)


def prepare_input_files(query, agent_input):
    """Retain provider inputs and issue references without downloading files.

    Only platform-origin components may carry a Host-local path. A path in an
    event envelope is metadata, never permission to read the Host filesystem.
    """
    from langbot_plugin.api.entities.builtin.runner.input import InputAttachment

    originals = input_files(query)
    # References are scoped to this query's previous preparation, not to the
    # platform message order or to any caller-supplied filesystem path.
    prepared = getattr(query, '_box_inputs', None)
    previous_refs = {f'attachment-{i}': item for i, item in enumerate(prepared or [])}
    if not agent_input.attachments:
        from ..agent.runner.query_entry_adapter import QueryEntryAdapter

        agent_input.attachments = [
            InputAttachment.model_validate(item)
            for item in QueryEntryAdapter._build_attachments(query, [c.model_dump() for c in agent_input.contents])
        ]
    inline_images = {
        content.image_base64
        for content in (agent_input.contents or [])
        if content.type == 'image_base64' and content.image_base64
    }
    components = []
    for i, attachment in enumerate(agent_input.attachments):
        kind = (attachment.type or 'file').lower()
        fields = {'url': attachment.url or '', 'base64': attachment.content or ''}
        cls = {'image': pm.Image, 'voice': pm.Voice}.get(kind, pm.File)
        if cls is pm.File:
            fields.update(name=attachment.name or '', id=attachment.id or '')
        component = cls(**fields)
        referenced = previous_refs.get(attachment.ref)
        if type(referenced) is cls and not attachment.content and not attachment.url:
            components.append(referenced)
            attachment.ref, attachment.path = f'attachment-{i}', None
            continue
        # Match by payload, never by list position (contents and message chains
        # can describe attachments in different orders).
        for original in originals:
            if type(original) is not cls:
                continue
            if (
                (attachment.url and attachment.url == original.url)
                or (attachment.content and attachment.content == original.base64)
                or (
                    attachment.id
                    and attachment.id
                    == getattr(original, 'id', getattr(original, 'image_id', getattr(original, 'voice_id', None)))
                )
                or (
                    not attachment.url
                    and not attachment.content
                    and not attachment.id
                    and attachment.name
                    and attachment.name == getattr(original, 'name', None)
                )
            ):
                component = original
                break
        components.append(component)
        attachment.ref, attachment.path = f'attachment-{i}', None
        if kind == 'image' and attachment.content in inline_images:
            attachment.content = None
    object.__setattr__(query, '_box_inputs', components)


def input_files(query):
    prepared = getattr(query, '_box_inputs', None)
    if prepared is not None:
        return prepared
    return [c for c in query.message_chain or [] if isinstance(c, (pm.Image, pm.Voice, pm.File))]


def binding_for(query) -> RunBoxBinding:
    binding = getattr(query, '_box_binding', None)
    if not isinstance(binding, RunBoxBinding):
        raise BoxValidationError('Runner must bind a Box before using sandbox tools or files')
    return binding


def exported_message(query, file_ids: list[str], *, consume: bool = False) -> pm.MessageChain:
    binding = binding_for(query)
    if not isinstance(file_ids, list) or len(file_ids) > 100 or any(type(x) is not str for x in file_ids):
        raise BoxValidationError('file_ids must contain at most 100 exported file IDs')
    if len(set(file_ids)) != len(file_ids):
        raise BoxValidationError('Duplicate exported file ID')
    if any(key not in binding.exported or key in binding.submitted for key in file_ids):
        raise BoxValidationError('Output file does not belong to this run or has already been submitted')
    components = []
    for key in file_ids:
        item = binding.exported[key]
        if item['type'] == 'Image':
            components.append(pm.Image(base64=item['base64']))
        elif item['type'] == 'Voice':
            components.append(pm.Voice(base64=item['base64']))
        else:
            components.append(pm.File(name=item['name'], base64=item['base64']))
    if consume:
        binding.submitted.update(file_ids)
    return pm.MessageChain(components)


class RunnerBoxService:
    def __init__(self, box):
        self.box = box

    async def status(self, context):
        status = await self.box.get_status(context)
        capacity = status.get('capacity', {})
        return {
            'enabled': self.box.enabled,
            'available': status.get('available', False),
            'limit': capacity.get('limit'),
            'used': capacity.get('used'),
            'remaining': capacity.get('remaining'),
            'required_reuse_key': 'global' if self.box.managed_admission_required else None,
            'reason': status.get('connector_error'),
        }

    async def sessions(self, context):
        # Do not hide connection failures behind an empty list.
        context = await self.box.require_workspace_sandbox(context)
        return await self.box.client.get_sessions(action_context=self.box._action_context(context))

    @staticmethod
    def public_session(item):
        return {'id': item['session_id'], 'status': item.get('status', 'idle')}

    async def acquire(self, context, data, query=None):
        request = BoxAcquireRequest.model_validate(data)
        key = request.reuse_key
        if self.box.managed_admission_required:
            if key != 'global':
                raise BoxValidationError('This deployment requires the global Box reuse key')
            session_id = 'global'
        else:
            session_id = 'runner-' + hashlib.sha256(key.encode()).hexdigest()
        # Plugin options cannot override policy, host mounts, or execution identity.
        if set(request.options) - {'image'}:
            raise BoxValidationError('Only the Box image can be specified; resource limits are Host-owned')
        spec = {'session_id': session_id, **request.options}
        from ..provider.tools.loaders.skill import build_execution_mounts

        mounts = build_execution_mounts(self.box.ap, query) if query is not None else []
        result = await self.box.create_session(context, spec, trusted_read_only_mounts=mounts)
        return self.public_session(result)

    async def bind(self, context, query, run_id, box_id):
        current = getattr(query, '_box_binding', None)
        if current is not None:
            if current.run_id != run_id or current.session_id != box_id:
                raise BoxValidationError('A run cannot change its Box after binding')
            return self.binding_info(current)
        sessions = await self.sessions(context)
        item = next((item for item in sessions if item['session_id'] == box_id), None)
        if item is None:
            raise BoxValidationError('Box not found in the current Workspace')
        current = getattr(query, '_box_binding', None)
        if current is not None:
            if current.run_id != run_id or current.session_id != box_id:
                raise BoxValidationError('A run cannot change its Box after binding')
            return self.binding_info(current)
        fields = ('image', 'network', 'cpus', 'memory_mb', 'pids_limit', 'read_only_rootfs', 'persistent')
        spec = {key: item[key] for key in fields if key in item}
        from ..provider.tools.loaders.skill import build_execution_mounts

        binding = RunBoxBinding(
            run_id, box_id, spec, run_id, read_only_mounts=build_execution_mounts(self.box.ap, query)
        )
        object.__setattr__(query, '_box_binding', binding)
        return self.binding_info(binding)

    @staticmethod
    def binding_info(binding):
        return {
            'box_id': binding.session_id,
            'outbox': f'/workspace/outbox/{binding.io_scope}',
        }

    async def import_attachments(self, query, attachment_ids):
        binding = binding_for(query)
        available = {f'attachment-{i}': c for i, c in enumerate(input_files(query))}
        ids = list(available) if attachment_ids is None else attachment_ids
        if not isinstance(ids, list) or any(type(key) is not str or key not in available for key in ids):
            raise BoxValidationError('Unknown input attachment reference')
        if len(ids) != len(set(ids)):
            raise BoxValidationError('Duplicate input attachment reference')
        async with binding.lock:
            for key in ids:
                if key in binding.imported:
                    continue
                transfer = copy.copy(query)
                # Each input has its own directory: repeated imports cannot erase other files.
                object.__setattr__(transfer, '_box_binding', replace(binding, io_scope=f'{binding.io_scope}-{key}'))
                transfer.message_chain = pm.MessageChain([available[key]])
                items = await self.box.materialize_inbound_attachments(transfer)
                if not items:
                    raise BoxValidationError(f'Failed to import input attachment {key}')
                binding.imported[key] = {'id': key, **items[0]}
            return {'items': [binding.imported[key] for key in ids]}

    async def export_files(self, query, paths):
        binding = binding_for(query)
        if not isinstance(paths, list) or not paths or len(paths) > self.box._ATTACHMENT_MAX_FILES:
            raise BoxValidationError(f'paths must contain 1 to {self.box._ATTACHMENT_MAX_FILES} file paths')
        if any(
            not isinstance(p, str)
            or not p.startswith('/')
            or '\\' in p
            or '\x00' in p
            or any(c in {'', '.', '..'} for c in p.split('/')[1:])
            for p in paths
        ):
            raise BoxValidationError('paths must be normalized absolute sandbox file paths')
        if len(set(paths)) != len(paths):
            raise BoxValidationError('Duplicate export file paths')
        async with binding.lock:
            items = await self.box.collect_selected_files(query, paths)
            unseen = {}
            for item in items:
                data = base64.b64decode(item['base64'].split(';base64,')[-1])
                fingerprint = (item.get('_outbox_path', item['name']), item['type'], hashlib.sha256(data).hexdigest())
                if fingerprint not in binding.exported_fingerprints:
                    unseen[fingerprint] = (item, len(data))
            if len(binding.exported) + len(unseen) > 100:
                first = next(iter(unseen.values()))[0]
                raise export_error(
                    'run_files',
                    limit=100,
                    actual=len(binding.exported) + len(unseen),
                    remaining=max(0, 100 - len(binding.exported)),
                    path=first.get('_outbox_path', first['name']),
                    absolute_path=True,
                )
            total_bytes = sum(x['size'] for x in binding.exported.values())
            batch_bytes = sum(size for _, size in unseen.values())
            if unseen and total_bytes + batch_bytes > self.box._ATTACHMENT_MAX_TOTAL_BYTES:
                first = next(iter(unseen.values()))[0]
                raise export_error(
                    'run_bytes',
                    limit=self.box._ATTACHMENT_MAX_TOTAL_BYTES,
                    actual=total_bytes + batch_bytes,
                    remaining=max(0, self.box._ATTACHMENT_MAX_TOTAL_BYTES - total_bytes),
                    path=first.get('_outbox_path', first['name']),
                    absolute_path=True,
                )
            pending = {}
            fingerprints = {}
            for fingerprint, (item, size) in unseen.items():
                key = str(uuid.uuid4())
                pending[key] = {
                    **item,
                    'id': key,
                    'size': size,
                }
                fingerprints[fingerprint] = key
            binding.exported.update(pending)
            binding.exported_fingerprints.update(fingerprints)
            try:
                warning = await self.box.clear_selected_files(query, items)
            except Exception:
                warning = 'Files accepted, but cleanup failed; do not repeat delivery.'
            return {
                'warning': warning,
                'items': [
                    {k: v for k, v in item.items() if k not in {'base64', '_outbox_path'}}
                    for key, item in binding.exported.items()
                    if key not in binding.submitted
                ],
            }
