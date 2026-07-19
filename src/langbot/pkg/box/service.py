from __future__ import annotations

import asyncio
import collections
import datetime as _dt
import enum
import hashlib
import json
import os
import secrets
from typing import TYPE_CHECKING

import pydantic

from langbot_plugin.box.client import BoxRuntimeClient
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.box.tenancy import box_namespace
from langbot_plugin.box.security import BOX_SHARED_WORKSPACE_PROBE_PREFIX
from .admission import SandboxAdmissionController, require_cloud_admission_policy
from .connector import BoxRuntimeConnector, _get_box_config
from . import secure_fs
from ..telemetry import features as telemetry_features
from ..api.http.context import ExecutionContext
from ..api.http.service.tenant import TenantContext, require_workspace_uuid
from langbot_plugin.box.errors import BoxAdmissionError, BoxError, BoxValidationError
from langbot_plugin.box.models import (
    BUILTIN_PROFILES,
    BoxExecutionResult,
    BoxManagedProcessInfo,
    BoxManagedProcessSpec,
    BoxProfile,
    BoxSpec,
)

_INT_ADAPTER = pydantic.TypeAdapter(int)
_UTC = _dt.timezone.utc
_MAX_RECENT_ERRORS = 50
_MIB = 1024 * 1024


def _is_path_under(path: str, root: str) -> bool:
    """Check whether *path* equals *root* or is a child of *root*."""
    return path == root or path.startswith(f'{root}{os.sep}')


if TYPE_CHECKING:
    from ..core import app as core_app
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


class BoxService:
    def __init__(
        self,
        ap: core_app.Application,
        client: BoxRuntimeClient | None = None,
        output_limit_chars: int = 4000,
    ):
        self.ap = ap
        self._cloud_managed = bool(getattr(getattr(ap, 'deployment', None), 'multi_workspace_enabled', False))
        self._enabled = self._load_enabled()
        self._runtime_connector: BoxRuntimeConnector | None = None
        if client is None:
            # Always construct a connector — its __init__ is side-effect free
            # (no I/O, no subprocess). When ``box.enabled = false`` we simply
            # skip ``connector.initialize()`` so no connection is attempted.
            self._runtime_connector = BoxRuntimeConnector(ap, runtime_disconnect_callback=self._on_runtime_disconnect)
            client = self._runtime_connector.client
        self.client = client
        self.output_limit_chars = output_limit_chars
        self.host_root = self._load_host_root()
        self.allowed_mount_roots = self._load_allowed_mount_roots()
        self.default_workspace = self._load_default_workspace()
        self.profile = self._load_profile()
        self.custom_image = self._load_custom_image()
        self.workspace_quota_mb = self._load_workspace_quota_mb()
        self._admission_policy = (
            require_cloud_admission_policy(_get_box_config(ap).get('admission')) if self._cloud_managed else None
        )
        self._admission = (
            SandboxAdmissionController(
                ap,
                self.client,
                policy=self._admission_policy,
            )
            if self._cloud_managed and self._admission_policy is not None
            else None
        )
        self._recent_errors: collections.deque[dict] = collections.deque(maxlen=_MAX_RECENT_ERRORS)
        self._shutdown_task = None
        self._available = False
        self._connector_error: str = ''
        self._reconnecting = False
        # Optional explicit override for shares_filesystem_with_box. None means
        # "derive from the connector transport". Set by tests / embedders that
        # know the real LangBot<->Box filesystem topology.
        self._shares_filesystem_with_box_override: bool | None = None

    @property
    def enabled(self) -> bool:
        """Whether Box is enabled in config. False means the operator has
        deliberately turned the sandbox off via ``box.enabled = false``.
        Disabled and "enabled but unavailable" are reported as the same
        ``available = False`` to consumers, but distinguished in get_status."""
        return self._enabled

    @property
    def managed_admission_required(self) -> bool:
        return self._cloud_managed

    async def initialize(self):
        if not self._enabled:
            # Disabled by config: do NOT connect to a remote runtime, do NOT
            # fork a stdio subprocess. Every consumer of box_service should
            # gate on ``available`` and degrade gracefully.
            self._available = False
            self._connector_error = 'Box runtime is disabled in config (box.enabled = false)'
            self.ap.logger.info(
                'Box runtime disabled by config; sandbox features (exec/read/write/edit, '
                'skill add/edit, stdio MCP) will be unavailable.'
            )
            return
        try:
            if self._runtime_connector is not None:
                await self._runtime_connector.initialize()
            else:
                await self.client.initialize()
            self._ensure_default_workspace()
            await self._verify_cloud_runtime()
            self._available = True
            self._connector_error = ''
            self.ap.logger.info(
                f'LangBot Box runtime initialized: profile={self.profile.name} '
                f'default_workspace={self.default_workspace or "(none)"}'
            )
            # Cloud query directories use globally opaque query UUIDs. Never
            # sweep all tenants when a future replica joins the same logical
            # instance; that could delete another replica's in-flight files.
            if not self._cloud_managed:
                await self._purge_attachment_dirs()
        except Exception as exc:
            self.ap.logger.warning(f'LangBot Box runtime unavailable, sandbox features disabled: {exc}')
            self._available = False
            self._connector_error = str(exc)
            if self._cloud_managed:
                raise

    async def _on_runtime_disconnect(self, connector: BoxRuntimeConnector) -> None:
        """Called by the connector when the Box runtime connection drops.

        Spawns a background reconnection loop so the caller is not blocked.
        Skipped entirely when Box is disabled by config — that path should
        never have connected in the first place.
        """
        if not self._enabled:
            return
        if self._reconnecting:
            return  # Another reconnect loop is already running
        self._reconnecting = True
        self._available = False
        self._connector_error = 'Disconnected from Box runtime'
        self.ap.logger.warning('Box runtime disconnected, sandbox features temporarily disabled.')
        asyncio.create_task(self._reconnect_loop(connector))

    async def _reconnect_loop(self, connector: BoxRuntimeConnector) -> None:
        """Retry reconnection with exponential backoff (3s → 60s max)."""
        delay = 3
        max_delay = 60
        try:
            while True:
                self.ap.logger.info(f'Attempting to reconnect to Box runtime in {delay}s...')
                await asyncio.sleep(delay)
                try:
                    connector.dispose()
                    await connector.initialize()
                    await self._verify_cloud_runtime()
                    self._available = True
                    self._connector_error = ''
                    self.ap.logger.info('Box runtime reconnected, sandbox features restored.')
                    return
                except Exception as exc:
                    self._connector_error = str(exc)
                    self.ap.logger.warning(f'Box runtime reconnection failed: {exc}')
                    delay = min(delay * 2, max_delay)
        finally:
            self._reconnecting = False

    async def _verify_cloud_runtime(self) -> None:
        if not self._cloud_managed:
            return
        self._ensure_cloud_shared_workspace()
        await self._challenge_cloud_shared_workspace()
        backend_info = await self.client.get_backend_info()
        if (
            not isinstance(backend_info, dict)
            or backend_info.get('name') != 'nsjail'
            or backend_info.get('available') is not True
        ):
            raise BoxValidationError('Cloud Box nsjail isolation readiness failed')

    async def _challenge_cloud_shared_workspace(self) -> None:
        """Prove Core and Box Runtime see the same durable filesystem.

        Equal configured path strings are not evidence of a shared container
        volume. Core creates one high-entropy, no-follow marker under its
        canonical root and the authenticated Runtime host-control action reads
        that basename only. Any mismatch fails Cloud startup/reconnect closed.
        """

        if self.default_workspace is None:
            raise BoxValidationError('Cloud Box shared default_workspace is unavailable')

        marker_name = f'{BOX_SHARED_WORKSPACE_PROBE_PREFIX}{secrets.token_hex(16)}'
        marker_payload = secrets.token_bytes(64)
        expected_digest = hashlib.sha256(marker_payload).hexdigest()
        directory_flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
        nofollow = getattr(os, 'O_NOFOLLOW', 0)
        root_fd: int | None = None
        marker_fd: int | None = None
        marker_created = False
        try:
            root_fd = os.open(self.default_workspace, directory_flags | nofollow)
            marker_fd = os.open(
                marker_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
                0o600,
                dir_fd=root_fd,
            )
            marker_created = True
            remaining = memoryview(marker_payload)
            while remaining:
                written = os.write(marker_fd, remaining)
                if written <= 0:
                    raise BoxValidationError('Failed to write Cloud Box shared-volume probe')
                remaining = remaining[written:]
            os.fsync(marker_fd)
            os.close(marker_fd)
            marker_fd = None

            result = await self.client.verify_shared_workspace(marker_name)
            if (
                not isinstance(result, dict)
                or result.get('marker_name') != marker_name
                or result.get('size') != len(marker_payload)
                or not secrets.compare_digest(str(result.get('sha256') or ''), expected_digest)
            ):
                raise BoxValidationError(
                    'Cloud Box Core and Runtime do not share the configured durable Workspace volume'
                )
        except BoxValidationError:
            raise
        except Exception as exc:
            raise BoxValidationError('Cloud Box shared durable Workspace volume verification failed') from exc
        finally:
            if marker_fd is not None:
                os.close(marker_fd)
            if root_fd is not None:
                if marker_created:
                    try:
                        os.unlink(marker_name, dir_fd=root_fd)
                    except FileNotFoundError:
                        pass
                os.close(root_fd)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def shares_filesystem_with_box(self) -> bool:
        """Whether LangBot and the Box runtime share a filesystem view.

        This is True only when Box runs as a local stdio child process of
        LangBot (same container/host). In that case paths the Box runtime
        reports — notably skill ``package_root`` — resolve identically on the
        LangBot side, so LangBot may validate them against its own filesystem.

        It is False for every separated deployment (Docker Compose, k8s
        sidecar, ``--standalone-box``, or an explicit ``runtime.endpoint``),
        where the Box runtime owns its own filesystem and LangBot must trust
        the paths it reports rather than checking them locally.

        When Box is wired up with an injected client (tests, custom embeds)
        there is no connector to introspect; we conservatively report False so
        LangBot never wrongly drops Box-reported skills. An explicit override
        can be set via ``_shares_filesystem_with_box`` (used by tests and any
        embedder that knows the real topology).
        """
        if self._shares_filesystem_with_box_override is not None:
            return self._shares_filesystem_with_box_override
        if self._runtime_connector is None:
            return False
        return not self._runtime_connector.uses_websocket()

    @staticmethod
    def _execution_context(context: TenantContext) -> ExecutionContext:
        workspace_uuid = require_workspace_uuid(context)
        instance_uuid = str(getattr(context, 'instance_uuid', '') or '').strip()
        generation = getattr(context, 'placement_generation', None)
        if not instance_uuid:
            raise BoxValidationError('Box operations require an explicit instance UUID')
        if isinstance(generation, bool) or not isinstance(generation, int) or generation <= 0:
            raise BoxValidationError('Box operations require a positive placement generation')
        return ExecutionContext(
            instance_uuid=instance_uuid,
            workspace_uuid=workspace_uuid,
            placement_generation=generation,
            bot_uuid=getattr(context, 'bot_uuid', None),
            pipeline_uuid=getattr(context, 'pipeline_uuid', None),
            query_uuid=getattr(context, 'query_uuid', None),
            entitlement_revision=getattr(context, 'entitlement_revision', 0),
        )

    @classmethod
    def _query_execution_context(cls, query: pipeline_query.Query) -> ExecutionContext:
        attached_context = getattr(query, '_execution_context', None)
        if isinstance(attached_context, ExecutionContext):
            return cls._execution_context(attached_context)
        return cls._execution_context(
            ExecutionContext(
                instance_uuid=str(getattr(query, 'instance_uuid', '') or ''),
                workspace_uuid=str(getattr(query, 'workspace_uuid', '') or ''),
                placement_generation=getattr(query, 'placement_generation', 0) or 0,
                bot_uuid=getattr(query, 'bot_uuid', None),
                pipeline_uuid=getattr(query, 'pipeline_uuid', None),
                query_uuid=getattr(query, 'query_uuid', None),
                entitlement_revision=getattr(query, 'entitlement_revision', 0),
            )
        )

    @classmethod
    def _action_context(cls, context: TenantContext) -> ActionContext:
        execution_context = cls._execution_context(context)
        return ActionContext(
            instance_uuid=execution_context.instance_uuid,
            workspace_uuid=execution_context.workspace_uuid,
            placement_generation=execution_context.placement_generation,
        )

    async def _validated_execution_context(self, context: TenantContext) -> ExecutionContext:
        """Resolve and fence a tenant context before touching shared Box state."""

        execution_context = self._execution_context(context)
        binding = await self.ap.workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )
        if binding.instance_uuid != execution_context.instance_uuid:
            raise BoxValidationError('Box execution context belongs to another LangBot instance')
        if (
            str(getattr(binding, 'workspace_uuid', '') or '') != execution_context.workspace_uuid
            or getattr(binding, 'placement_generation', None) != execution_context.placement_generation
        ):
            raise BoxValidationError('Box execution context belongs to a stale Workspace placement')
        return execution_context

    async def require_workspace_sandbox(self, context: TenantContext) -> ExecutionContext:
        """Fence a Workspace and install its short-lived Cloud admission grant.

        OSS keeps the existing singleton behavior and does not require a
        Control Plane entitlement. Cloud always resolves a fresh generic
        entitlement before a sandbox-visible operation.
        """

        execution_context = await self._validated_execution_context(context)
        await self._require_validated_workspace_sandbox(execution_context)
        return execution_context

    async def _require_validated_workspace_sandbox(self, execution_context: ExecutionContext) -> None:
        if not self._available:
            raise BoxError('Box runtime is not available. Install and start Docker to use sandbox features.')
        if self._cloud_managed:
            if self._admission is None:
                raise BoxAdmissionError('Cloud Box sandbox admission is unavailable')
            await self._admission.require(execution_context)

    async def is_workspace_sandbox_available(self, context: TenantContext) -> bool:
        """Return tenant-specific availability for UI and tool discovery.

        This method deliberately catches entitlement failures so callers can
        hide tools without leaking plan details. Direct execution APIs use
        :meth:`require_workspace_sandbox` and retain an explicit failure.
        """

        if not self._available:
            return False
        try:
            await self.require_workspace_sandbox(context)
            return True
        except Exception:
            return False

    def _managed_policy_payload(
        self,
        context: TenantContext,
        spec_payload: dict,
    ) -> dict:
        """Reject tenant-owned policy fields and apply the Cloud hard policy."""

        payload = dict(spec_payload)
        if not self._cloud_managed:
            return payload
        policy = self._admission_policy
        if policy is None:
            raise BoxAdmissionError('Cloud Box sandbox admission policy is unavailable')

        forged_fields = {
            'plan',
            'subscription',
            'managed_sandbox',
            'entitlement',
            'entitlement_revision',
            'max_sessions',
            'max_managed_processes',
            'backend',
        }
        submitted_forged_fields = sorted(forged_fields.intersection(payload))
        if submitted_forged_fields:
            raise BoxAdmissionError(
                'Managed sandbox policy fields are host-controlled: ' + ', '.join(submitted_forged_fields)
            )

        submitted_session_id = str(payload.get('session_id', '') or '').strip()
        if submitted_session_id and submitted_session_id != policy.logical_session_id:
            raise BoxAdmissionError('Managed sandbox session_id is runtime-owned')
        submitted_network = str(getattr(payload.get('network'), 'value', payload.get('network', 'off')) or 'off')
        if submitted_network != 'off':
            raise BoxAdmissionError('Managed sandbox network access is disabled')
        if payload.get('extra_mounts'):
            raise BoxAdmissionError('Managed sandbox additional host mounts are disabled')
        submitted_mount_path = str(payload.get('mount_path', '/workspace') or '/workspace')
        if submitted_mount_path != '/workspace':
            raise BoxAdmissionError('Managed sandbox mount_path is runtime-owned')

        canonical_host_path = self._tenant_workspace(context)
        if canonical_host_path is None:
            raise BoxAdmissionError('Managed sandbox Workspace path is unavailable')
        submitted_host_path = str(payload.get('host_path', '') or '').strip()
        if submitted_host_path and os.path.realpath(submitted_host_path) != os.path.realpath(canonical_host_path):
            raise BoxAdmissionError('Managed sandbox host_path is runtime-owned')

        timeout = payload.get('timeout_sec', policy.max_timeout_sec)
        if isinstance(timeout, bool) or not isinstance(timeout, int):
            raise BoxValidationError('timeout_sec must be an integer')
        payload.update(
            {
                'session_id': policy.logical_session_id,
                'network': 'off',
                'host_path': canonical_host_path,
                'mount_path': '/workspace',
                'extra_mounts': [],
                'persistent': True,
                'timeout_sec': min(timeout, policy.max_timeout_sec),
                'cpus': policy.cpus,
                'memory_mb': policy.memory_mb,
                'pids_limit': policy.pids_limit,
                'read_only_rootfs': policy.read_only_rootfs,
                'workspace_quota_mb': policy.workspace_quota_mb,
            }
        )
        return payload

    def _reject_cloud_managed_process(self) -> None:
        if self._cloud_managed:
            raise BoxAdmissionError('Managed processes are disabled for Cloud sandboxes')

    def _tenant_workspace(self, context: TenantContext) -> str | None:
        if self.default_workspace is None:
            return None
        namespace = box_namespace(self._action_context(context))
        return os.path.join(self.default_workspace, 'tenants', namespace)

    async def execute_spec_payload(
        self,
        spec_payload: dict,
        query: pipeline_query.Query,
        *,
        skip_host_mount_validation: bool = False,
    ) -> dict:
        if not self._available:
            raise BoxError('Box runtime is not available. Install and start Docker to use sandbox features.')
        execution_context = await self._validated_execution_context(self._query_execution_context(query))
        spec_payload = self._managed_policy_payload(execution_context, spec_payload)
        await self._require_validated_workspace_sandbox(execution_context)
        if spec_payload.get('host_path') in (None, ''):
            tenant_workspace = self._tenant_workspace(execution_context)
            if tenant_workspace is not None:
                spec_payload['host_path'] = tenant_workspace
                if self.shares_filesystem_with_box:
                    os.makedirs(tenant_workspace, exist_ok=True)
        try:
            spec = self.build_spec(spec_payload, skip_host_mount_validation=skip_host_mount_validation)
        except BoxError as exc:
            self._record_error(exc, query)
            raise
        self.ap.logger.info(
            'LangBot Box request: '
            f'query_id={query.query_id} '
            f'spec={json.dumps(self._summarize_spec(spec), ensure_ascii=False)}'
        )
        try:
            await self._enforce_workspace_quota(spec, phase='before execution')
        except BoxError as exc:
            self._record_error(exc, query)
            raise
        try:
            result = await self.client.execute(
                spec,
                action_context=self._action_context(execution_context),
            )
            # A placement may be cut over while a long-running sandbox call is
            # in flight.  Never accept a result produced by the superseded
            # generation.  Runtime-side generation fencing prevents new work;
            # this second Core check closes the response race.
            await self._validated_execution_context(execution_context)
        except BoxError as exc:
            self._record_error(exc, query)
            raise
        try:
            await self._enforce_workspace_quota(spec, phase='after execution')
        except BoxError as exc:
            await self._cleanup_exceeded_session(execution_context, spec)
            self._record_error(exc, query)
            raise
        self.ap.logger.info(
            'LangBot Box result: '
            f'query_id={query.query_id} '
            f'summary={json.dumps(self._summarize_result(result), ensure_ascii=False)}'
        )
        telemetry_features.increment(query, 'sandbox', 'execs')
        return self._serialize_result(result)

    def resolve_box_session_id(self, query: pipeline_query.Query) -> str:
        """Resolve the Box session_id from the pipeline's template and query variables.

        When ``system.limitation.force_box_session_id_template`` is set to a
        non-empty value, that template overrides whatever the pipeline
        configured. This is the authoritative SaaS guard: it runs on every
        ``exec`` call, so a tenant cannot escape a single shared sandbox even
        by editing the pipeline config directly through the API (which only
        gates the web UI).
        """
        if self._cloud_managed:
            return 'global'
        forced_template = self._forced_box_session_id_template()
        if forced_template:
            template = forced_template
        else:
            template = (
                (query.pipeline_config or {})
                .get('ai', {})
                .get('local-agent', {})
                .get('box-session-id-template', '{launcher_type}_{launcher_id}')
            )
        variables = dict(query.variables or {})
        launcher_type = getattr(query, 'launcher_type', None)
        if hasattr(launcher_type, 'value'):
            launcher_type = launcher_type.value
        launcher_id = getattr(query, 'launcher_id', None)
        sender_id = getattr(query, 'sender_id', None)
        query_id = getattr(query, 'query_id', None)

        variables.setdefault('query_id', str(query_id or 'unknown'))
        variables.setdefault('launcher_type', str(launcher_type or 'query'))
        variables.setdefault('launcher_id', str(launcher_id or query_id or 'unknown'))
        variables.setdefault('sender_id', str(sender_id or launcher_id or query_id or 'unknown'))
        variables.setdefault('global', 'global')
        return template.format_map(collections.defaultdict(lambda: 'unknown', variables))

    def build_skill_extra_mounts(self, query: pipeline_query.Query) -> list[dict]:
        """Build extra_mounts entries for all pipeline-bound skills.

        This ensures that when a container is first created it already has
        all skill packages mounted, regardless of which skill is currently
        activated.

        Path validation is filesystem-topology dependent. When LangBot and the
        Box runtime share a filesystem (local stdio mode), a skill whose
        ``package_root`` is missing or no longer a directory is skipped with a
        warning instead of being passed through to the backend. Without that
        guard the three backends behave inconsistently on a stale mount: nsjail
        refuses to start the sandbox (failing every exec in the session),
        Docker silently auto-creates a root-owned empty directory on the host,
        and E2B silently skips the upload — none of which surfaces an
        actionable error.

        When Box runs as a separate process (Docker Compose, k8s sidecar,
        ``--standalone-box``, or a remote ``runtime.endpoint``), the
        ``package_root`` reported by ``list_skills`` is the Box runtime's own
        filesystem path and is NOT resolvable on the LangBot side. Validating
        it locally would wrongly drop every skill, so LangBot trusts the path
        and lets the Box runtime resolve it. The Box runtime only ever reports
        skills it discovered on its own filesystem, so the path is valid there
        by construction.
        """
        if self._cloud_managed:
            return []
        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        if skill_mgr is None:
            return []

        from ..provider.tools.loaders import skill as skill_loader

        validate_locally = self.shares_filesystem_with_box

        visible_skills = skill_loader.get_visible_skills(self.ap, query)
        mounts: list[dict] = []
        for skill_name, skill_data in visible_skills.items():
            package_root = str(skill_data.get('package_root', '') or '').strip()
            if not package_root:
                continue
            if validate_locally and not os.path.isdir(package_root):
                self.ap.logger.warning(
                    f'Skill "{skill_name}" package_root missing on filesystem '
                    f'({package_root}); skipping mount to prevent sandbox failures. '
                    f'The skill cache may be stale — consider reloading skills.'
                )
                continue
            mounts.append(
                {
                    'host_path': package_root,
                    'mount_path': f'/workspace/.skills/{skill_name}',
                    'mode': 'rw',
                }
            )
        return mounts

    async def execute_tool(
        self,
        parameters: dict,
        query: pipeline_query.Query,
        *,
        skill_name: str | None = None,
    ) -> dict:
        """Execute an agent-facing ``exec`` tool call.

        Translates the agent-facing ``command`` field to the internal
        ``BoxSpec.cmd`` field and injects the session id from the query.
        """
        spec_payload: dict = {'cmd': parameters['command']}
        if skill_name is not None:
            spec_payload['skill_name'] = skill_name

        # Pass through allowed agent-facing fields
        for key in ('workdir', 'timeout_sec', 'env'):
            if key in parameters:
                spec_payload[key] = parameters[key]

        # Inject context the agent must not control
        spec_payload.setdefault('session_id', self.resolve_box_session_id(query))

        # Mount all pipeline-bound skills so they are available in the container
        if 'extra_mounts' not in spec_payload:
            spec_payload['extra_mounts'] = self.build_skill_extra_mounts(query)

        return await self.execute_spec_payload(spec_payload, query)

    async def execute_in_context(
        self,
        context: TenantContext,
        spec_payload: dict,
        *,
        skip_host_mount_validation: bool = False,
    ) -> BoxExecutionResult:
        """Execute trusted internal Box work inside one Workspace namespace."""

        execution_context = await self._validated_execution_context(context)
        payload = self._managed_policy_payload(execution_context, spec_payload)
        await self._require_validated_workspace_sandbox(execution_context)
        if payload.get('host_path') in (None, ''):
            tenant_workspace = self._tenant_workspace(execution_context)
            if tenant_workspace is not None:
                payload['host_path'] = tenant_workspace
                if self.shares_filesystem_with_box:
                    os.makedirs(tenant_workspace, exist_ok=True)
        spec = self.build_spec(payload, skip_host_mount_validation=skip_host_mount_validation)
        result = await self.client.execute(spec, action_context=self._action_context(execution_context))
        await self._validated_execution_context(execution_context)
        return result

    # ── Attachment passthrough (inbound / outbound) ──────────────────
    #
    # IM/webchat attachments (images, voices, files) reach the LLM as
    # multimodal content, but historically never landed on the sandbox
    # filesystem, so the agent's exec/read/write tools could not operate on
    # them. Conversely, files the agent produced inside the sandbox were
    # never surfaced back to the user. These two helpers close both gaps:
    #
    #   inbound  : message_chain attachments -> /workspace/inbox/<query_id>/
    #   outbound : /workspace/outbox/<query_id>/ -> reply MessageChain
    #
    # Transfer prefers DIRECT HOST FILESYSTEM access to the bind-mounted
    # workspace (default_workspace on the host maps to /workspace inside the
    # container), which has no size limit. This covers the local docker /
    # nsjail / stdio backends. For backends where the workspace is NOT visible
    # on the LangBot host (E2B, an external remote runtime.endpoint), it falls
    # back to a base64-through-exec round-trip. The exec channel can only move
    # small files reliably — the docker backend passes the command as a single
    # argv (ARG_MAX) and exec stdout is truncated by output_limit_chars — so
    # the host path is strongly preferred and used whenever available.

    INBOX_MOUNT_DIR = '/workspace/inbox'
    OUTBOX_MOUNT_DIR = '/workspace/outbox'
    INBOX_SUBDIR = 'inbox'
    OUTBOX_SUBDIR = 'outbox'
    # Hard cap on a single attachment. The HTTP upload endpoints already cap
    # uploads at 10MiB; keep parity.
    _ATTACHMENT_MAX_BYTES = 10 * _MIB
    _ATTACHMENT_MAX_FILES = 20
    _ATTACHMENT_MAX_TOTAL_BYTES = 50 * _MIB
    # Conservative cap for the exec FALLBACK path only (ARG_MAX / stdout
    # truncation). The host-filesystem path has no such limit.
    _EXEC_FALLBACK_MAX_BYTES = 256 * 1024

    def _attachment_query_key(self, query: pipeline_query.Query) -> str:
        query_uuid = str(getattr(query, 'query_uuid', '') or '').strip()
        if query_uuid:
            if query_uuid in {'.', '..'} or '/' in query_uuid or '\\' in query_uuid or '\x00' in query_uuid:
                raise BoxValidationError('Query attachment identity is invalid')
            return query_uuid
        if self._cloud_managed:
            raise BoxValidationError('Cloud attachment transfer requires query_uuid')
        return str(query.query_id)

    def _host_query_dir(self, subdir: str, query: pipeline_query.Query) -> str | None:
        """Host path for ``/workspace/<subdir>/<query_id>`` when LangBot can
        access the bind-mounted workspace directly, else ``None``.

        ``default_workspace`` is the host directory bind-mounted to
        ``/workspace`` for the local docker/nsjail backends and shared
        outright in stdio mode, so a file written there by LangBot is visible
        to the sandbox (and vice-versa). It is ``None`` / not a local dir for
        E2B and remote runtimes, where we must fall back to the exec channel.
        """
        root = self._tenant_workspace(self._query_execution_context(query))
        if not root or not os.path.isdir(root) or os.path.islink(root):
            return None
        return os.path.join(root, subdir, self._attachment_query_key(query))

    async def _purge_attachment_dirs(self) -> None:
        """Remove leftover inbox/outbox directories on startup.

        ``query_id`` is a process-local counter (see pipeline query pool) that
        resets to 0 on every restart, so per-query attachment directories from
        a previous process would otherwise be silently reused — leaking a prior
        run's inbound files and re-sending stale outbound files.

        Tenant workspaces live below ``default_workspace/tenants``. Startup has
        no authenticated Workspace context, so cleanup is deliberately limited
        to direct host-filesystem deletion. It must never issue an unscoped Box
        exec merely to remove root-owned container output.
        """
        root = self.default_workspace
        if not root or not os.path.isdir(root):
            return

        host_survivors: list[str] = []

        def _host_purge() -> list[str]:
            candidates: list[tuple[str, str]] = [
                (root, self.INBOX_SUBDIR),
                (root, self.OUTBOX_SUBDIR),
            ]
            tenants_root = os.path.join(root, 'tenants')
            if os.path.isdir(tenants_root):
                with os.scandir(tenants_root) as tenant_entries:
                    for tenant_entry in tenant_entries:
                        if not tenant_entry.is_dir(follow_symlinks=False):
                            continue
                        candidates.extend(
                            [
                                (tenant_entry.path, self.INBOX_SUBDIR),
                                (tenant_entry.path, self.OUTBOX_SUBDIR),
                            ]
                        )
            survivors: list[str] = []
            for candidate_root, subdir in candidates:
                path = os.path.join(candidate_root, subdir)
                try:
                    secure_fs.purge_subdirectory(candidate_root, subdir)
                except OSError:
                    if os.path.lexists(path):
                        survivors.append(path)
            return survivors

        try:
            host_survivors = await asyncio.to_thread(_host_purge)
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.warning(f'Host-side purge of sandbox attachment dirs failed: {exc}')
            host_survivors = [self.INBOX_SUBDIR, self.OUTBOX_SUBDIR]

        if not host_survivors:
            self.ap.logger.info('Purged leftover sandbox attachment dirs from a previous process.')
            return

        self.ap.logger.warning(
            'Could not purge root-owned sandbox attachment directories from the host; '
            'skipping an unsafe unscoped Box exec because startup has no trusted '
            f'Workspace context: {host_survivors}'
        )

    @staticmethod
    def _sanitize_attachment_name(name: str, fallback: str) -> str:
        """Reduce an arbitrary attachment name to a safe basename.

        Strips directory separators and parent refs so a crafted file name
        can never escape the inbox/outbox directory.
        """
        base = os.path.basename(str(name or '').replace('\\', '/').strip())
        base = base.lstrip('.') or ''
        # Drop anything that is not a conservative filename charset.
        cleaned = ''.join(c for c in base if c.isalnum() or c in ('.', '_', '-', ' ')).strip()
        cleaned = cleaned.replace(' ', '_')
        return cleaned or fallback

    @staticmethod
    async def _component_to_bytes(component) -> tuple[bytes, str] | None:
        """Best-effort extraction of (bytes, mime) from a platform component.

        Handles base64, http(s) url and local path sources. Returns None when
        no payload can be resolved.
        """
        import base64 as _b64

        b64 = getattr(component, 'base64', None)
        if b64:
            data = b64
            mime = 'application/octet-stream'
            if isinstance(data, str) and data.startswith('data:'):
                split_index = data.find(';base64,')
                if split_index != -1:
                    mime = data[5:split_index]
                    data = data[split_index + 8 :]
            try:
                return _b64.b64decode(data), mime
            except Exception:
                return None

        url = getattr(component, 'url', None)
        if url:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp.content, resp.headers.get('Content-Type', 'application/octet-stream')
            except Exception:
                return None

        path = getattr(component, 'path', None)
        if path:
            try:
                import aiofiles

                async with aiofiles.open(path, 'rb') as f:
                    return await f.read(), 'application/octet-stream'
            except Exception:
                return None

        return None

    async def _write_files_into_sandbox(
        self,
        query: pipeline_query.Query,
        subdir: str,
        target_mount_dir: str,
        files: list[tuple[str, bytes]],
    ) -> list[str]:
        """Write *files* (name, bytes) into the per-query directory.

        Prefers a direct host-filesystem write to the bind-mounted workspace
        (no size limit). Falls back to a base64-through-exec round-trip only
        when the workspace is not visible on the LangBot host (E2B / remote).
        Returns the list of in-sandbox paths actually written.
        """
        if not files:
            return []

        host_dir = self._host_query_dir(subdir, query)
        if host_dir is not None:
            return await asyncio.to_thread(self._write_files_host, host_dir, target_mount_dir, files)

        return await self._write_files_via_exec(query, target_mount_dir, files)

    def _write_files_host(
        self,
        host_dir: str,
        target_mount_dir: str,
        files: list[tuple[str, bytes]],
    ) -> list[str]:
        """Write attachments straight onto the bind-mounted host directory.

        Recreates the per-query directory from scratch so a reused query_id
        (the webchat session uses small sequential ids) never inherits stale
        files from an earlier turn.
        """
        query_key = os.path.basename(host_dir)
        subdir = os.path.basename(os.path.dirname(host_dir))
        tenant_root = os.path.dirname(os.path.dirname(host_dir))
        try:
            secure_fs.write_files(tenant_root, subdir, query_key, files)
        except secure_fs.UnsafeWorkspacePathError as exc:
            raise BoxValidationError('Sandbox attachment path contains an unsafe symbolic link') from exc
        written: list[str] = []
        for name, _data in files:
            written.append(f'{target_mount_dir}/{name}')
        return written

    async def _write_files_via_exec(
        self,
        query: pipeline_query.Query,
        target_dir: str,
        files: list[tuple[str, bytes]],
    ) -> list[str]:
        """Fallback: ship files into the sandbox over the exec channel.

        Only used for backends without host-filesystem access (E2B / remote).
        Each file is base64-decoded inside the sandbox. Files larger than the
        conservative exec cap are skipped (ARG_MAX / stdout limits).
        """
        import base64 as _b64
        import json as _json

        manifest = []
        for name, data in files:
            if len(data) > self._EXEC_FALLBACK_MAX_BYTES:
                self.ap.logger.warning(
                    f'Attachment "{name}" ({len(data)} bytes) exceeds the exec-channel '
                    f'fallback limit ({self._EXEC_FALLBACK_MAX_BYTES} bytes); skipping. '
                    f'Configure a host-shared workspace to transfer large files.'
                )
                continue
            manifest.append({'name': name, 'b64': _b64.b64encode(data).decode('ascii')})
        if not manifest:
            return []

        manifest_b64 = _b64.b64encode(_json.dumps(manifest).encode('utf-8')).decode('ascii')
        script = (
            'import base64, json, os, shutil\n'
            f'target = {target_dir!r}\n'
            'shutil.rmtree(target, ignore_errors=True)\n'
            'os.makedirs(target, exist_ok=True)\n'
            f'manifest = json.loads(base64.b64decode({manifest_b64!r}))\n'
            'written = []\n'
            'for item in manifest:\n'
            "    p = os.path.join(target, item['name'])\n"
            "    with open(p, 'wb') as f:\n"
            "        f.write(base64.b64decode(item['b64']))\n"
            '    written.append(p)\n'
            'print(json.dumps(written))\n'
        )
        result = await self.execute_tool(
            {'command': f"python3 - <<'LBPY'\n{script}\nLBPY", 'timeout_sec': 120},
            query,
        )
        if not result.get('ok'):
            self.ap.logger.warning(
                f'Failed to write inbound attachments into sandbox via exec: '
                f'query_id={query.query_id} stderr={result.get("stderr", "")[:200]}'
            )
            return []
        try:
            return _json.loads(str(result.get('stdout') or '').strip().splitlines()[-1])
        except Exception:
            return []

    async def materialize_inbound_attachments(self, query: pipeline_query.Query) -> list[dict]:
        """Persist message-chain attachments into the sandbox inbox.

        Returns a list of ``{path, name, type, size}`` describing what was
        written, so the runner can tell the LLM the exact in-sandbox paths.
        Returns ``[]`` when sandbox is unavailable or there are no attachments.
        """
        if not self._available:
            return []
        if self._cloud_managed:
            await self.require_workspace_sandbox(self._query_execution_context(query))

        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        message_chain = getattr(query, 'message_chain', None)
        if not message_chain:
            return []

        type_map = [
            (platform_message.Image, 'Image', 'image', 'png'),
            (platform_message.Voice, 'Voice', 'voice', 'wav'),
            (platform_message.File, 'File', 'file', 'bin'),
        ]

        pending: list[tuple[str, bytes]] = []
        descriptors: list[dict] = []
        index = 0
        for component in message_chain:
            matched = None
            for cls, kind, prefix, default_ext in type_map:
                if isinstance(component, cls):
                    matched = (kind, prefix, default_ext)
                    break
            if matched is None:
                continue
            kind, prefix, default_ext = matched

            payload = await self._component_to_bytes(component)
            if payload is None:
                continue
            data, _mime = payload
            if not data or len(data) > self._ATTACHMENT_MAX_BYTES:
                continue

            index += 1
            raw_name = getattr(component, 'name', None) or f'{prefix}_{index}.{default_ext}'
            safe_name = self._sanitize_attachment_name(raw_name, f'{prefix}_{index}.{default_ext}')
            pending.append((safe_name, data))
            descriptors.append(
                {
                    'name': safe_name,
                    'type': kind,
                    'size': len(data),
                }
            )

        if not pending:
            return []

        query_key = self._attachment_query_key(query)
        target_dir = f'{self.INBOX_MOUNT_DIR}/{query_key}'
        written = await self._write_files_into_sandbox(query, self.INBOX_SUBDIR, target_dir, pending)
        written_basenames = {os.path.basename(p) for p in written}

        result: list[dict] = []
        for desc in descriptors:
            if desc['name'] in written_basenames:
                desc['path'] = f'{target_dir}/{desc["name"]}'
                result.append(desc)
        if result:
            self.ap.logger.info(
                f'Materialized {len(result)} inbound attachment(s) into sandbox: '
                f'query_id={query.query_id} dir={target_dir}'
            )
        return result

    async def collect_outbound_attachments(self, query: pipeline_query.Query) -> list[dict]:
        """Collect files the agent produced in the sandbox outbox.

        Reads ``/workspace/outbox/<query_id>/`` (recursively) — directly from
        the bind-mounted host directory when available (no size limit), else
        via the exec channel — returns a list of ``{type, name, base64}``
        ready to become platform message components, then clears the outbox so
        a later turn in the same session does not re-send stale files. Returns
        ``[]`` when nothing was produced.
        """
        if not self._available:
            return []
        if self._cloud_managed:
            await self.require_workspace_sandbox(self._query_execution_context(query))

        host_dir = self._host_query_dir(self.OUTBOX_SUBDIR, query)
        if host_dir is not None:
            entries = await asyncio.to_thread(self._read_outbox_host, host_dir)
        else:
            entries = await self._read_outbox_via_exec(query)

        attachments = self._classify_outbound_entries(entries)

        # Always clear the per-query outbox after reading — even when nothing
        # was collected — so a later turn that reuses the same query_id (the
        # counter resets across restarts) never inherits stale files.
        await self._clear_outbox(query, host_dir)
        if attachments:
            self.ap.logger.info(
                f'Collected {len(attachments)} outbound attachment(s) from sandbox: query_id={query.query_id}'
            )
        return attachments

    def _read_outbox_host(self, host_dir: str) -> list[dict]:
        """Read outbox files straight off the bind-mounted host directory."""
        import base64 as _b64

        query_key = os.path.basename(host_dir)
        subdir = os.path.basename(os.path.dirname(host_dir))
        tenant_root = os.path.dirname(os.path.dirname(host_dir))
        try:
            files = secure_fs.read_regular_files(
                tenant_root,
                subdir,
                query_key,
                max_file_bytes=self._ATTACHMENT_MAX_BYTES,
                max_files=self._ATTACHMENT_MAX_FILES,
                max_total_bytes=self._ATTACHMENT_MAX_TOTAL_BYTES,
            )
        except secure_fs.UnsafeWorkspacePathError as exc:
            raise BoxValidationError('Sandbox outbox contains an unsafe symbolic link') from exc
        return [{'name': name, 'b64': _b64.b64encode(data).decode('ascii')} for name, data in files]

    async def _read_outbox_via_exec(self, query: pipeline_query.Query) -> list[dict]:
        """Fallback: read the outbox over the exec channel (E2B / remote).

        Note: exec stdout is truncated by ``output_limit_chars``, so this path
        only reliably transfers small files. The host path is preferred.
        """
        import json as _json

        target_dir = f'{self.OUTBOX_MOUNT_DIR}/{self._attachment_query_key(query)}'
        max_bytes = self._EXEC_FALLBACK_MAX_BYTES
        script = (
            'import base64, json, os\n'
            f'target = {target_dir!r}\n'
            f'max_bytes = {max_bytes}\n'
            'out = []\n'
            'if os.path.isdir(target):\n'
            '    for root, _dirs, names in os.walk(target):\n'
            '        for n in sorted(names):\n'
            '            p = os.path.join(root, n)\n'
            '            try:\n'
            '                if os.path.getsize(p) > max_bytes:\n'
            '                    continue\n'
            "                with open(p, 'rb') as f:\n"
            '                    data = f.read()\n'
            '            except OSError:\n'
            '                continue\n'
            '            rel = os.path.relpath(p, target)\n'
            "            out.append({'name': rel, 'b64': base64.b64encode(data).decode('ascii')})\n"
            'print(json.dumps(out))\n'
        )
        result = await self.execute_tool(
            {'command': f"python3 - <<'LBPY'\n{script}\nLBPY", 'timeout_sec': 120},
            query,
        )
        if not result.get('ok'):
            return []
        try:
            return _json.loads(str(result.get('stdout') or '').strip().splitlines()[-1])
        except Exception:
            return []

    async def _clear_outbox(self, query: pipeline_query.Query, host_dir: str | None) -> None:
        """Empty the per-query outbox after collection.

        Tries a host-side ``rmtree`` first (fast, no container round-trip).
        Outbox files are created by the sandbox container as root over the
        bind-mount, so when LangBot runs as a non-root user the host delete
        fails silently and the files survive — they would then be re-collected
        on the next turn that reuses the same query_id. So if anything survives
        the host delete, clear it from *inside* the sandbox via exec, where the
        container's root can remove its own files. Best-effort: never raise
        into the pipeline.
        """
        target_dir = f'{self.OUTBOX_MOUNT_DIR}/{self._attachment_query_key(query)}'

        if host_dir is not None:

            def _clear() -> bool:
                query_key = os.path.basename(host_dir)
                subdir = os.path.basename(os.path.dirname(host_dir))
                tenant_root = os.path.dirname(os.path.dirname(host_dir))
                try:
                    secure_fs.reset_directory(tenant_root, subdir, query_key)
                    return False
                except OSError:
                    return True

            survived = await asyncio.to_thread(_clear)
            if not survived:
                return
            # Root-owned container files survived the host delete — fall through.

        try:
            await self.execute_tool(
                {'command': f'rm -rf {target_dir} && mkdir -p {target_dir}', 'timeout_sec': 30},
                query,
            )
        except Exception as exc:
            self.ap.logger.warning(f'Failed to clear sandbox outbox {target_dir}: {exc}')

    @staticmethod
    def _classify_outbound_entries(entries: list[dict]) -> list[dict]:
        """Classify outbox files into Image/Voice/File component descriptors."""
        image_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
        voice_exts = {'wav', 'mp3', 'silk', 'amr', 'ogg', 'm4a', 'aac'}
        mime_by_ext = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'bmp': 'image/bmp',
        }
        attachments: list[dict] = []
        for entry in entries or []:
            name = str(entry.get('name', '') or '')
            b64 = entry.get('b64')
            if not name or not b64:
                continue
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            base_name = os.path.basename(name)
            if ext in image_exts:
                mime = mime_by_ext.get(ext, 'image/png')
                attachments.append({'type': 'Image', 'name': base_name, 'base64': f'data:{mime};base64,{b64}'})
            elif ext in voice_exts:
                attachments.append({'type': 'Voice', 'name': base_name, 'base64': f'data:audio/{ext};base64,{b64}'})
            else:
                attachments.append({'type': 'File', 'name': base_name, 'base64': b64})
        return attachments

    async def shutdown(self):
        await self.client.shutdown()

    def dispose(self):
        if self._runtime_connector is not None:
            self._runtime_connector.dispose()
        loop = getattr(self.ap, 'event_loop', None)
        if loop is not None and not loop.is_closed() and (self._shutdown_task is None or self._shutdown_task.done()):
            self._shutdown_task = loop.create_task(self.shutdown())

    async def get_sessions(self, context: TenantContext) -> list[dict]:
        if not self._available:
            return []
        execution_context = await self.require_workspace_sandbox(context)
        try:
            return await self.client.get_sessions(action_context=self._action_context(execution_context))
        except Exception:
            return []

    def build_spec(self, spec_payload: dict, skip_host_mount_validation: bool = False) -> BoxSpec:
        spec_payload = dict(spec_payload)
        spec_payload.setdefault('env', {})
        if spec_payload.get('host_path') in (None, '') and self.default_workspace is not None:
            spec_payload['host_path'] = self.default_workspace
        if spec_payload.get('workspace_quota_mb') in (None, '') and self.workspace_quota_mb is not None:
            spec_payload['workspace_quota_mb'] = self.workspace_quota_mb

        # Global custom image overrides profile default (but not caller-specified image)
        if self.custom_image and 'image' not in spec_payload:
            spec_payload['image'] = self.custom_image

        self._apply_profile(spec_payload)

        try:
            spec = BoxSpec.model_validate(spec_payload)
        except pydantic.ValidationError as exc:
            first_error = exc.errors()[0]
            raise BoxValidationError(first_error.get('msg', 'invalid box arguments')) from exc

        if not skip_host_mount_validation:
            self._validate_host_mount(spec)
        return spec

    async def create_session(
        self,
        context: TenantContext,
        spec_payload: dict,
        *,
        skip_host_mount_validation: bool = False,
    ) -> dict:
        execution_context = await self._validated_execution_context(context)
        spec_payload = self._managed_policy_payload(execution_context, spec_payload)
        await self._require_validated_workspace_sandbox(execution_context)
        if spec_payload.get('host_path') in (None, ''):
            tenant_workspace = self._tenant_workspace(execution_context)
            if tenant_workspace is not None:
                spec_payload['host_path'] = tenant_workspace
                if self.shares_filesystem_with_box:
                    os.makedirs(tenant_workspace, exist_ok=True)
        spec = self.build_spec(spec_payload, skip_host_mount_validation=skip_host_mount_validation)
        return await self.client.create_session(spec, action_context=self._action_context(execution_context))

    async def start_managed_process(
        self,
        context: TenantContext,
        session_id: str,
        process_payload: dict,
    ) -> BoxManagedProcessInfo:
        self._reject_cloud_managed_process()
        execution_context = await self._validated_execution_context(context)
        process_spec = BoxManagedProcessSpec.model_validate(process_payload)
        return await self.client.start_managed_process(
            session_id,
            process_spec,
            action_context=self._action_context(execution_context),
        )

    async def get_managed_process(
        self,
        context: TenantContext,
        session_id: str,
        process_id: str = 'default',
    ) -> BoxManagedProcessInfo:
        self._reject_cloud_managed_process()
        execution_context = await self._validated_execution_context(context)
        return await self.client.get_managed_process(
            session_id,
            process_id,
            action_context=self._action_context(execution_context),
        )

    async def stop_managed_process(
        self,
        context: TenantContext,
        session_id: str,
        process_id: str = 'default',
    ) -> None:
        self._reject_cloud_managed_process()
        execution_context = await self._validated_execution_context(context)
        return await self.client.stop_managed_process(
            session_id,
            process_id,
            action_context=self._action_context(execution_context),
        )

    def _get_managed_process_websocket_url(
        self,
        context: TenantContext,
        session_id: str,
        process_id: str = 'default',
    ) -> str:
        getter = getattr(self.client, 'get_managed_process_websocket_url', None)
        if getter is None:
            raise BoxValidationError('box runtime client does not support managed process websocket attach')
        ws_relay_base_url = (
            self._runtime_connector.ws_relay_base_url
            if self._runtime_connector is not None
            else 'http://127.0.0.1:5410'
        )
        return getter(
            session_id,
            ws_relay_base_url,
            process_id,
            action_context=self._action_context(context),
        )

    async def get_managed_process_websocket_connection(
        self,
        context: TenantContext,
        session_id: str,
        process_id: str = 'default',
    ) -> tuple[str, dict[str, str]]:
        """Resolve a relay URL and headers after fencing the placement.

        The shared Box control secret is transported only in headers.  The
        Workspace and generation headers bind the relay to the same trusted
        execution context used by the action RPC that created the process.
        """

        self._reject_cloud_managed_process()
        execution_context = await self._validated_execution_context(context)
        if self._runtime_connector is None:
            raise BoxValidationError(
                'box runtime connector does not support authenticated managed process websocket attach'
            )
        action_context = self._action_context(execution_context)
        return (
            self._get_managed_process_websocket_url(
                execution_context,
                session_id,
                process_id,
            ),
            self._runtime_connector.get_relay_headers(action_context),
        )

    async def list_skills(self, context: TenantContext) -> list[dict]:
        execution_context = await self._validated_skill_execution_context(context)
        return await self.client.list_skills(action_context=self._action_context(execution_context))

    async def get_skill(self, context: TenantContext, name: str) -> dict | None:
        execution_context = await self._validated_skill_execution_context(context)
        return await self.client.get_skill(name, action_context=self._action_context(execution_context))

    async def create_skill(self, context: TenantContext, skill: dict) -> dict:
        execution_context = await self._validated_skill_execution_context(context)
        payload = dict(skill)
        payload.pop('workspace_uuid', None)
        if self._cloud_managed and str(payload.get('package_root', '') or '').strip():
            raise BoxAdmissionError('Cloud skill package_root is runtime-owned')
        if self._cloud_managed:
            payload.pop('package_root', None)
        return await self.client.create_skill(payload, action_context=self._action_context(execution_context))

    async def update_skill(self, context: TenantContext, name: str, skill: dict) -> dict:
        execution_context = await self._validated_skill_execution_context(context)
        payload = dict(skill)
        payload.pop('workspace_uuid', None)
        if self._cloud_managed:
            # The runtime already owns the package path for an existing skill.
            # A serialized read response may contain it, but it is never an
            # authority-bearing update field in shared Cloud mode.
            payload.pop('package_root', None)
        return await self.client.update_skill(
            name,
            payload,
            action_context=self._action_context(execution_context),
        )

    async def delete_skill(self, context: TenantContext, name: str) -> None:
        execution_context = await self._validated_skill_execution_context(context)
        await self.client.delete_skill(name, action_context=self._action_context(execution_context))

    async def scan_skill_directory(self, context: TenantContext, path: str) -> dict:
        execution_context = await self._validated_skill_execution_context(context)
        if self._cloud_managed:
            raise BoxAdmissionError('Scanning arbitrary host skill directories is disabled in Cloud')
        return await self.client.scan_skill_directory(path, action_context=self._action_context(execution_context))

    async def _validated_skill_execution_context(self, context: TenantContext) -> ExecutionContext:
        execution_context = await self._validated_execution_context(context)
        await self._require_validated_workspace_sandbox(execution_context)
        return execution_context

    async def list_skill_files(
        self,
        context: TenantContext,
        name: str,
        path: str = '.',
        include_hidden: bool = False,
        max_entries: int = 200,
    ) -> dict:
        execution_context = await self._validated_skill_execution_context(context)
        return await self.client.list_skill_files(
            name,
            path,
            include_hidden,
            max_entries,
            action_context=self._action_context(execution_context),
        )

    async def read_skill_file(self, context: TenantContext, name: str, path: str) -> dict:
        execution_context = await self._validated_skill_execution_context(context)
        return await self.client.read_skill_file(
            name,
            path,
            action_context=self._action_context(execution_context),
        )

    async def write_skill_file(self, context: TenantContext, name: str, path: str, content: str) -> dict:
        execution_context = await self._validated_skill_execution_context(context)
        return await self.client.write_skill_file(
            name,
            path,
            content,
            action_context=self._action_context(execution_context),
        )

    async def preview_skill_zip(
        self,
        context: TenantContext,
        file_bytes: bytes,
        filename: str,
        source_subdir: str = '',
        target_suffix: str = 'upload',
    ) -> list[dict]:
        execution_context = await self._validated_skill_execution_context(context)
        return await self.client.preview_skill_zip(
            file_bytes,
            filename,
            source_subdir,
            target_suffix,
            action_context=self._action_context(execution_context),
        )

    async def install_skill_zip(
        self,
        context: TenantContext,
        file_bytes: bytes,
        filename: str,
        source_paths: list[str] | None = None,
        source_path: str = '',
        source_subdir: str = '',
        target_suffix: str = 'upload',
    ) -> list[dict]:
        execution_context = await self._validated_skill_execution_context(context)
        return await self.client.install_skill_zip(
            file_bytes,
            filename,
            source_paths,
            source_path,
            source_subdir,
            target_suffix,
            action_context=self._action_context(execution_context),
        )

    def _serialize_result(self, result: BoxExecutionResult) -> dict:
        stdout, stdout_truncated = self._truncate(result.stdout)
        stderr, stderr_truncated = self._truncate(result.stderr)

        return {
            'session_id': result.session_id,
            'backend': result.backend_name,
            'status': result.status.value,
            'ok': result.ok,
            'exit_code': result.exit_code,
            'stdout': stdout,
            'stderr': stderr,
            'stdout_truncated': stdout_truncated,
            'stderr_truncated': stderr_truncated,
            'duration_ms': result.duration_ms,
        }

    def _truncate(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.output_limit_chars:
            return text, False
        if self.output_limit_chars <= 0:
            return '', True

        head_size = 0
        tail_size = 0
        notice = ''
        # Recompute once the omitted count is known so the final payload
        # stays within output_limit_chars even after adding the notice.
        for _ in range(4):
            omitted = max(len(text) - head_size - tail_size, 0)
            notice = f'\n\n... [{omitted} characters truncated] ...\n\n'
            available = self.output_limit_chars - len(notice)
            if available <= 0:
                return notice[: self.output_limit_chars], True

            new_head_size = int(available * 0.6)
            new_tail_size = available - new_head_size
            if new_head_size == head_size and new_tail_size == tail_size:
                break
            head_size = new_head_size
            tail_size = new_tail_size

        head = text[:head_size]
        tail = text[-tail_size:] if tail_size else ''
        truncated = f'{head}{notice}{tail}'
        return truncated[: self.output_limit_chars], True

    def _summarize_spec(self, spec: BoxSpec) -> dict:
        cmd = spec.cmd.strip()
        if len(cmd) > 400:
            cmd = f'{cmd[:397]}...'

        return {
            'session_id': spec.session_id,
            'workdir': spec.workdir,
            'mount_path': spec.mount_path,
            'timeout_sec': spec.timeout_sec,
            'network': spec.network.value,
            'image': spec.image,
            'host_path': spec.host_path,
            'host_path_mode': spec.host_path_mode.value,
            'cpus': spec.cpus,
            'memory_mb': spec.memory_mb,
            'pids_limit': spec.pids_limit,
            'read_only_rootfs': spec.read_only_rootfs,
            'workspace_quota_mb': spec.workspace_quota_mb,
            'env_keys': sorted(spec.env.keys()),
            'cmd': cmd,
        }

    def _summarize_result(self, result: BoxExecutionResult) -> dict:
        stdout_preview = result.stdout[:200]
        stderr_preview = result.stderr[:200]
        if len(result.stdout) > 200:
            stdout_preview = f'{stdout_preview}...'
        if len(result.stderr) > 200:
            stderr_preview = f'{stderr_preview}...'

        return {
            'session_id': result.session_id,
            'backend': result.backend_name,
            'status': result.status.value,
            'exit_code': result.exit_code,
            'duration_ms': result.duration_ms,
            'stdout_preview': stdout_preview,
            'stderr_preview': stderr_preview,
        }

    def _local_config(self) -> dict:
        """Return ``box.local`` from instance config.

        Environment overrides are applied uniformly by
        ``LoadConfigStage._apply_env_overrides_to_config`` (e.g.
        ``BOX__LOCAL__HOST_ROOT``) before this is read, so no box-specific
        env parsing happens here.
        """
        return dict(_get_box_config(self.ap).get('local') or {})

    def _load_allowed_mount_roots(self) -> list[str]:
        configured_roots = self._local_config().get('allowed_mount_roots', [])
        # The unified env-override mechanism stores a brand-new key as a raw
        # string when the key is absent from config.yaml. Accept a
        # comma-separated string as well as a list so that
        # ``BOX__LOCAL__ALLOWED_MOUNT_ROOTS="/a,/b"`` keeps working even when
        # the config file has no ``box.local.allowed_mount_roots`` entry.
        if isinstance(configured_roots, str):
            configured_roots = [item.strip() for item in configured_roots.split(',') if item.strip()]

        normalized_roots: list[str] = []
        for root in configured_roots:
            root_value = str(root).strip()
            if not root_value:
                continue
            normalized_roots.append(os.path.realpath(os.path.abspath(root_value)))

        if not normalized_roots and self.host_root is not None:
            normalized_roots.append(self.host_root)

        return normalized_roots

    def _load_host_root(self) -> str | None:
        host_root = str(self._local_config().get('host_root', '')).strip()
        if not host_root:
            return None
        return os.path.realpath(os.path.abspath(host_root))

    def _load_default_workspace(self) -> str | None:
        default_workspace = str(self._local_config().get('default_workspace', '')).strip()
        if not default_workspace:
            if self.host_root is None:
                return None
            default_workspace = os.path.join(self.host_root, 'default')
        elif not os.path.isabs(default_workspace) and self.host_root is not None:
            default_workspace = os.path.join(self.host_root, default_workspace)
        return os.path.realpath(os.path.abspath(default_workspace))

    def get_skills_root(self) -> str | None:
        skills_root = str(self._local_config().get('skills_root', '') or 'skills').strip()
        if not skills_root:
            skills_root = 'skills'
        if not os.path.isabs(skills_root) and self.host_root is not None:
            skills_root = os.path.join(self.host_root, skills_root)
        return os.path.realpath(os.path.abspath(skills_root))

    def _load_enabled(self) -> bool:
        """Read ``box.enabled`` (top-level, not ``box.local.*``). Default True
        — disabling is opt-in. Accepts bool, ``'true'``/``'false'`` strings,
        and the standard env-overridden truthy values that
        ``LoadConfigStage._apply_env_overrides_to_config`` produces."""
        raw = _get_box_config(self.ap).get('enabled', True)
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() not in ('false', '0', 'no', 'off', '')

    def _load_custom_image(self) -> str | None:
        raw = str(self._local_config().get('image', '') or '').strip()
        return raw or None

    def _forced_box_session_id_template(self) -> str:
        """Return the SaaS-forced sandbox-scope template, or '' when unset.

        Read from ``system.limitation.force_box_session_id_template``. A
        non-empty value pins every pipeline to a single sandbox scope
        (e.g. ``'{global}'``) and cannot be overridden per-pipeline.
        """
        limitation = (
            (self.ap.instance_config.data or {}).get('system', {}).get('limitation', {})
            if getattr(self.ap, 'instance_config', None) is not None
            else {}
        )
        return str(limitation.get('force_box_session_id_template', '') or '').strip()

    def _load_workspace_quota_mb(self) -> int | None:
        raw_value = self._local_config().get('workspace_quota_mb')
        if raw_value in (None, ''):
            return None
        try:
            value = _INT_ADAPTER.validate_python(raw_value)
        except pydantic.ValidationError as exc:
            raise BoxValidationError('workspace_quota_mb must be an integer greater than or equal to 0') from exc
        if value < 0:
            raise BoxValidationError('workspace_quota_mb must be greater than or equal to 0')
        return value

    def _ensure_default_workspace(self):
        if self.default_workspace is None:
            return

        if not self.shares_filesystem_with_box:
            return

        if os.path.isdir(self.default_workspace):
            return

        if os.path.exists(self.default_workspace):
            raise BoxValidationError('box.local.default_workspace must point to a directory on the host')

        if not self.allowed_mount_roots:
            raise BoxValidationError(
                'box.local.default_workspace cannot be created because no allowed_mount_roots are configured'
            )

        for allowed_root in self.allowed_mount_roots:
            if _is_path_under(self.default_workspace, allowed_root):
                os.makedirs(self.default_workspace, exist_ok=True)
                return

        allowed_roots = ', '.join(self.allowed_mount_roots)
        raise BoxValidationError(f'box.local.default_workspace is outside allowed_mount_roots: {allowed_roots}')

    def _ensure_cloud_shared_workspace(self) -> None:
        """Require the Core-side view of the Cloud Box durable volume."""

        if self.default_workspace is None:
            raise BoxValidationError('Cloud Box requires box.local.default_workspace')
        if not os.path.isabs(self.default_workspace) or not os.path.isdir(self.default_workspace):
            raise BoxValidationError('Cloud Box shared default_workspace must be an existing absolute directory')
        if not os.access(self.default_workspace, os.R_OK | os.W_OK | os.X_OK):
            raise BoxValidationError('Cloud Box shared default_workspace must be writable by LangBot Core')
        if not self.allowed_mount_roots or not any(
            _is_path_under(self.default_workspace, allowed_root) for allowed_root in self.allowed_mount_roots
        ):
            raise BoxValidationError('Cloud Box shared default_workspace is outside allowed_mount_roots')

    def _validate_host_mount(self, spec: BoxSpec):
        if spec.host_path is None:
            return

        host_path = os.path.realpath(spec.host_path)
        if self.shares_filesystem_with_box and not os.path.isdir(host_path):
            raise BoxValidationError('host_path must point to an existing directory on the host')

        if not self.allowed_mount_roots:
            raise BoxValidationError('host_path mounting is disabled because no allowed_mount_roots are configured')

        for allowed_root in self.allowed_mount_roots:
            if _is_path_under(host_path, allowed_root):
                return

        allowed_roots = ', '.join(self.allowed_mount_roots)
        raise BoxValidationError(f'host_path is outside allowed_mount_roots: {allowed_roots}')

    def _load_profile(self) -> BoxProfile:
        profile_name = str(self._local_config().get('profile', 'default')).strip() or 'default'

        profile = BUILTIN_PROFILES.get(profile_name)
        if profile is None:
            available = ', '.join(sorted(BUILTIN_PROFILES))
            raise BoxValidationError(f"unknown box profile '{profile_name}', available profiles: {available}")
        return profile

    def _apply_profile(self, params: dict):
        """Merge profile defaults into *params* in-place, enforce locked fields and clamp timeout."""
        profile = self.profile
        _PROFILE_FIELDS = (
            'image',
            'network',
            'timeout_sec',
            'host_path_mode',
            'cpus',
            'memory_mb',
            'pids_limit',
            'read_only_rootfs',
            'workspace_quota_mb',
        )

        for field in _PROFILE_FIELDS:
            profile_value = getattr(profile, field)
            raw_value = profile_value.value if isinstance(profile_value, enum.Enum) else profile_value

            if field in profile.locked:
                params[field] = raw_value
            elif field not in params:
                params[field] = raw_value

        timeout = params.get('timeout_sec')
        try:
            normalized_timeout = _INT_ADAPTER.validate_python(timeout)
        except pydantic.ValidationError:
            return

        if normalized_timeout > profile.max_timeout_sec:
            params['timeout_sec'] = profile.max_timeout_sec

    def _get_workspace_size_bytes(self, root: str) -> int:
        total = 0

        def _walk(path: str):
            nonlocal total
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        try:
                            if entry.is_symlink():
                                total += entry.stat(follow_symlinks=False).st_size
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                _walk(entry.path)
                                continue
                            total += entry.stat(follow_symlinks=False).st_size
                        except FileNotFoundError:
                            continue
            except FileNotFoundError:
                return

        _walk(root)
        return total

    async def _enforce_workspace_quota(self, spec: BoxSpec, *, phase: str) -> None:
        if spec.host_path is None or spec.workspace_quota_mb <= 0:
            return

        host_path = os.path.realpath(spec.host_path)
        if not os.path.isdir(host_path):
            return

        # Walk the workspace off the event loop — this runs on every
        # quota-enforced exec, and a large tree would otherwise block the whole
        # asyncio runtime (all bots/pipelines) for the duration of the scan.
        used_bytes = await asyncio.to_thread(self._get_workspace_size_bytes, host_path)
        limit_bytes = spec.workspace_quota_mb * _MIB
        if used_bytes <= limit_bytes:
            return

        raise BoxValidationError(
            f'workspace quota exceeded {phase}: '
            f'used={used_bytes} bytes limit={limit_bytes} bytes '
            f'host_path={host_path} session_id={spec.session_id}'
        )

    async def _cleanup_exceeded_session(self, context: TenantContext, spec: BoxSpec) -> None:
        try:
            await self.client.delete_session(
                spec.session_id,
                action_context=self._action_context(context),
            )
        except Exception as exc:
            self.ap.logger.warning(
                'Failed to clean up Box session after workspace quota was exceeded: '
                f'session_id={spec.session_id} error={exc}'
            )

    # ── Observability ─────────────────────────────────────────────────

    def _record_error(self, exc: Exception, query: pipeline_query.Query):
        telemetry_features.increment(query, 'sandbox', 'errors')
        self._recent_errors.append(
            {
                'timestamp': _dt.datetime.now(_UTC).isoformat(),
                'type': type(exc).__name__,
                'message': str(exc),
                'query_id': str(query.query_id),
                'instance_uuid': str(getattr(query, 'instance_uuid', '') or ''),
                'workspace_uuid': str(getattr(query, 'workspace_uuid', '') or ''),
            }
        )

    def get_recent_errors(self, context: TenantContext) -> list[dict]:
        execution_context = self._execution_context(context)
        return [
            error
            for error in self._recent_errors
            if error.get('instance_uuid') == execution_context.instance_uuid
            and error.get('workspace_uuid') == execution_context.workspace_uuid
        ]

    def get_system_guidance(self, query: pipeline_query.Query | int | str | None = None) -> str:
        """Return LLM system-prompt guidance for the exec tool.

        All execution-specific prompt text is kept here so that callers
        (e.g. LocalAgentRunner) stay free of box domain knowledge.

        ``query`` is the current turn's pipeline query. When provided,
        the guidance ALWAYS advertises the per-query outbox path so the agent
        knows how to deliver generated files back to the user — even on turns
        where the user sent no inbound attachment (e.g. "generate a QR code"),
        which is exactly when the inbound-attachment note never fires. Outbound
        collection in the wrapper runs on every turn regardless of inbound
        files, so without this the file would be produced and silently dropped.
        """
        guidance = (
            'When the exec tool is available, use it for exact calculations, statistics, structured data parsing, '
            'and code execution instead of estimating mentally. If the user provides numbers, tables, CSV-like text, '
            'JSON, or other data and asks for a computed answer, prefer running a short Python script via exec '
            'and then answer from the tool result. Unless the user explicitly asks for the script, code, or implementation '
            'details, do not include the generated script in the final answer; return the result and a brief explanation only.'
        )
        if self.default_workspace:
            guidance += (
                ' A default workspace is mounted at /workspace for file tasks. When the user asks to read, create, or '
                'modify local files in the working directory, use exec with /workspace paths directly; do not ask the '
                'user for directory parameters unless they explicitly need a different directory.'
            )
        if query is not None:
            if not isinstance(query, (int, str)):
                query_key = self._attachment_query_key(query)
            else:
                # Backwards compatibility for OSS callers/tests that passed
                # the old process-local integer identity. Cloud callers must
                # pass the full Query so an opaque UUID is always advertised.
                if self._cloud_managed:
                    raise BoxValidationError('Cloud outbox guidance requires a pipeline Query')
                query_key = str(query)
            outbox_dir = f'{self.OUTBOX_MOUNT_DIR}/{query_key}'
            guidance += (
                f' If you produce any file (image, audio, document, etc.) that should be sent back to the user, '
                f'write it into {outbox_dir}/ (create the directory if needed). Every file placed there will be '
                'delivered to the user automatically; do not paste file contents or base64 into your reply.'
            )
        return guidance

    async def get_backend_status(self) -> dict:
        """Return instance-level backend readiness without tenant resource data."""

        if not self._available:
            return {'available': False, 'enabled': self._enabled, 'connector_error': self._connector_error}
        backend = await self.client.get_backend_info()
        return {'available': bool(backend.get('available', False)), 'enabled': self._enabled, 'backend': backend}

    async def get_status(self, context: TenantContext) -> dict:
        execution_context = await self._validated_execution_context(context)
        if self._cloud_managed and self._available:
            await self._require_validated_workspace_sandbox(execution_context)
        action_context = self._action_context(execution_context)
        recent_error_count = len(self.get_recent_errors(execution_context))
        if not self._available:
            return {
                'available': False,
                'enabled': self._enabled,
                'profile': self.profile.name,
                'recent_error_count': recent_error_count,
                'connector_error': self._connector_error,
            }
        try:
            runtime_status = await self.client.get_status(action_context=action_context)
        except Exception as exc:
            # RPC failed — the runtime likely just disconnected and the
            # heartbeat hasn't flipped _available yet.
            return {
                'available': False,
                'enabled': self._enabled,
                'profile': self.profile.name,
                'recent_error_count': recent_error_count,
                'connector_error': str(exc),
            }
        # Backend state can be unavailable even when the connector is healthy
        # (operator selected nsjail but the binary is missing, Docker daemon
        # went down after the runtime started, E2B credentials wrong, ...).
        # Report the combined state in the top-level ``available`` so the
        # frontend banner / ``useBoxStatus`` hook / native-tool gate all
        # agree on "actually usable" rather than "connector alive". The
        # detailed ``backend`` object stays in the payload so the dialog
        # can still show which backend was tried.
        backend_info = runtime_status.get('backend') if isinstance(runtime_status, dict) else None
        backend_ok = bool(backend_info and backend_info.get('available', False))
        payload = {
            **runtime_status,
            'available': backend_ok,
            'enabled': self._enabled,
            'profile': self.profile.name,
            'recent_error_count': recent_error_count,
        }
        if not backend_ok and 'connector_error' not in payload:
            backend_name = backend_info.get('name') if backend_info else None
            if backend_name:
                payload['connector_error'] = f'Configured sandbox backend "{backend_name}" is unavailable'
            else:
                payload['connector_error'] = 'No supported sandbox backend (Docker / nsjail / E2B) is available'
        return payload
