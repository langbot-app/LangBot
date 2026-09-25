"""Workspace governance settings and operation traceability.

This service owns everything behind the "成员操作日志溯源" (member operation
traceability) feature:

* the three capture levels and how a Workspace role caps them,
* the action classification table that maps an HTTP request to a normalized
  action / resource pair,
* the append-only writer that persists one row per traced operation while
  answering "what was changed into what",
* the tamper-evidence chain that makes silent edits detectable,
* the dedupe window that keeps an idle WebUI from inflating the log,
* read/prune APIs used by the settings panel.

Every write path is best-effort: auditing must never break the business
request. Failures are logged and swallowed.

Human-readable labels are never returned from this module. The persisted
``action`` value is a stable key and the UI resolves
``operationTrace.actions.<action>`` from the i18n locale files.
"""

from __future__ import annotations

import dataclasses
import datetime
import enum
import hashlib
import hmac
import json
import typing

import sqlalchemy

from ....core import app
from ....entity.persistence import metadata as persistence_metadata
from ....entity.persistence import operation_log as persistence_operation_log
from ....entity.persistence.operation_log import (
    OPERATION_LEVEL_MUTATION,
    OPERATION_LEVEL_NONE,
    OPERATION_LEVEL_READ,
)
from ....utils import constants
from ..authz import WorkspaceRole
from ..context import PrincipalType, RequestContext


# ---------------------------------------------------------------------------
# Storage keys (WorkspaceMetadata.value is a short string column)
# ---------------------------------------------------------------------------

OPERATION_LEVEL_KEY = 'operation_log_level'
OPERATION_RETENTION_DAYS_KEY = 'operation_log_retention_days'
OPERATION_MAX_ROWS_KEY = 'operation_log_max_rows'
OPERATION_DEDUPE_WINDOW_KEY = 'operation_log_dedupe_seconds'

DEFAULT_OPERATION_LEVEL = OPERATION_LEVEL_READ
DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_ROWS = 20000

#: Repeated identical read observations inside this window collapse into one
#: row. This is what stops a live WebUI or a polling client from inflating the
#: log while the page simply stays open.
DEFAULT_DEDUPE_WINDOW_SECONDS = 60

# Hard bounds so a misconfigured Workspace cannot grow the log unbounded.
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3650
MIN_MAX_ROWS = 100
MAX_MAX_ROWS = 500000
MIN_DEDUPE_WINDOW_SECONDS = 0
MAX_DEDUPE_WINDOW_SECONDS = 3600

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50

#: Upper bound for a single export so a download cannot load the whole table.
MAX_EXPORT_ROWS = 10000

#: Number of inserts a Workspace may accumulate before the row budget is
#: re-checked. Enforcing the budget with a ``COUNT`` on every insert turns a
#: cheap append into a scan of the whole Workspace history; deferring it keeps
#: the overshoot bounded by this stride while the maintenance loop still
#: enforces the exact limit.
_ROW_BUDGET_CHECK_STRIDE = 64

_MAX_SUMMARY_FIELDS = 6
_MAX_FIELD_VALUE_CHARS = 320
_MAX_USER_AGENT_CHARS = 512
_MAX_RESOURCE_ID_CHARS = 255
_MAX_ROUTE_CHARS = 512

# Fields that must never be copied into the traceable diff, matched as
# case-insensitive substrings so ``space_access_token`` is covered too.
_SENSITIVE_FIELD_MARKERS: typing.Final = (
    'password',
    'passwd',
    'secret',
    'token',
    'hash',
    'api_key',
    'apikey',
    'credential',
    'private_key',
    'salt',
    'passkey',
    'totp',
    'recovery_code',
    'authorization',
)

#: Machine sentinel written instead of a masked value. It is deliberately not
#: human-readable copy: the frontend maps it to ``operationTrace.redacted`` so
#: no interface text lives in the backend.
REDACTED_SENTINEL = '__redacted__'

#: Domain separator for the tamper-evidence HMAC. Changing it invalidates all
#: previously stored hashes, so it must stay stable across releases.
_HASH_KEY_SALT = 'langbot.operation_log.integrity.v1'
_HASH_FIELDS: typing.Final = (
    'workspace_uuid',
    'actor_account_uuid',
    'actor_name',
    'actor_role',
    'principal_type',
    'api_key_uuid',
    'auth_type',
    'http_method',
    'route',
    'action',
    'resource_type',
    'resource_id',
    'level',
    'outcome',
    'status_code',
    'summary',
    'changes',
    'client_ip',
    'prev_hash',
)


# ---------------------------------------------------------------------------
# Action catalog
# ---------------------------------------------------------------------------


class OperationLevel(enum.IntEnum):
    """The three operator-selectable capture levels."""

    OFF = OPERATION_LEVEL_NONE
    MUTATION = OPERATION_LEVEL_MUTATION
    READ = OPERATION_LEVEL_READ


#: How a role caps the Workspace-selected level. An operator or developer may
#: never force read-level tracing on for the whole Workspace, and a viewer is
#: never traced at all, keeping the write amplification predictable.
_ROLE_LEVEL_CAP: typing.Final[dict[str, int]] = {
    WorkspaceRole.OWNER.value: OPERATION_LEVEL_READ,
    WorkspaceRole.ADMIN.value: OPERATION_LEVEL_READ,
    WorkspaceRole.DEVELOPER.value: OPERATION_LEVEL_MUTATION,
    WorkspaceRole.OPERATOR.value: OPERATION_LEVEL_MUTATION,
    WorkspaceRole.VIEWER.value: OPERATION_LEVEL_NONE,
}

#: Principals without a Workspace role (API keys, legacy keys) behave like a
#: developer: mutations only.
_UNROLED_LEVEL_CAP = OPERATION_LEVEL_MUTATION

#: Roles allowed to change the Workspace tracing level / retention.
_SETTINGS_WRITE_ROLES: typing.Final = frozenset({WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value})


@dataclasses.dataclass(frozen=True, slots=True)
class ActionRule:
    """One row of the action classification template.

    ``action`` doubles as the i18n key suffix, so this table never carries a
    human-readable label.
    """

    action: str
    """Normalized action verb persisted in the log and used as the i18n key."""

    category: str
    """Coarse family used for grouping (member, resource, settings, audit...)."""

    bucket: str
    """Capture bucket: ``read``, ``write`` or ``audit``."""

    resource_type: str
    """Default resource family when the route declares none."""

    @property
    def i18n_key(self) -> str:
        """Return the frontend translation key for this action."""

        return f'operationTrace.actions.{self.action}'


#: Ordered template table. Order matters: the first matching rule wins, so
#: specific routes must appear before the generic HTTP-verb fallbacks.
ACTION_RULE_TABLE: typing.Final[tuple[ActionRule, ...]] = (
    # --- Audit surface itself (always traced once tracing is on) --------
    ActionRule(
        action='audit_log_view',
        category='audit',
        bucket='audit',
        resource_type='operation_log',
    ),
    ActionRule(
        action='clear_prune',
        category='audit',
        bucket='write',
        resource_type='operation_log',
    ),
    ActionRule(
        action='settings_update',
        category='settings',
        bucket='write',
        resource_type='workspace_settings',
    ),
    ActionRule(
        action='settings_view',
        category='settings',
        bucket='read',
        resource_type='workspace_settings',
    ),
    # --- Member management ----------------------------------------------
    ActionRule(
        action='member_invite',
        category='member',
        bucket='write',
        resource_type='member_invitation',
    ),
    ActionRule(
        action='member_role_update',
        category='member',
        bucket='write',
        resource_type='member',
    ),
    ActionRule(
        action='member_remove',
        category='member',
        bucket='write',
        resource_type='member',
    ),
    ActionRule(
        action='member_view',
        category='member',
        bucket='read',
        resource_type='member',
    ),
    # --- Generic resource verbs -----------------------------------------
    ActionRule(
        action='export',
        category='resource',
        bucket='read',
        resource_type='resource',
    ),
    ActionRule(
        action='execute',
        category='runtime',
        bucket='write',
        resource_type='runtime',
    ),
    ActionRule(
        action='debug',
        category='runtime',
        bucket='write',
        resource_type='runtime',
    ),
    ActionRule(
        action='publish',
        category='resource',
        bucket='write',
        resource_type='resource',
    ),
    ActionRule(
        action='create',
        category='resource',
        bucket='write',
        resource_type='resource',
    ),
    ActionRule(
        action='update',
        category='resource',
        bucket='write',
        resource_type='resource',
    ),
    ActionRule(
        action='delete',
        category='resource',
        bucket='write',
        resource_type='resource',
    ),
    ActionRule(
        action='view',
        category='resource',
        bucket='read',
        resource_type='resource',
    ),
    ActionRule(
        action='probe',
        category='system',
        bucket='read',
        resource_type='system',
    ),
)

ACTION_RULES_BY_ACTION: typing.Final[dict[str, ActionRule]] = {rule.action: rule for rule in ACTION_RULE_TABLE}

_READ_METHODS: typing.Final = frozenset({'GET', 'HEAD', 'OPTIONS'})

# Route fragments, evaluated in order, that refine the generic verb mapping.
# Longer, more specific fragments must precede their prefixes.
_ROUTE_RULES: typing.Final[tuple[tuple[str, str], ...]] = (
    ('/settings/operation-logs/export', 'export'),
    ('/settings/operation-logs', 'audit_log_view'),
    ('/settings/operation-level', 'settings_update'),
    ('/settings/governance', 'settings_update'),
    ('/settings/limits', 'settings_update'),
    ('/members', 'member_view'),
    ('/invitations', 'member_invite'),
    ('/export', 'export'),
    ('/debug', 'debug'),
    ('/execute', 'execute'),
    ('/publish', 'publish'),
)


def classify(method: str, route: str) -> ActionRule:
    """Map one HTTP request to its normalized action rule.

    ``route`` must be the registered Core route identity, never a raw URL, so
    user identifiers cannot leak into classification.
    """

    upper_method = (method or 'GET').upper()
    lowered_route = (route or '').lower()

    route_action: str | None = None
    for fragment, candidate in _ROUTE_RULES:
        if fragment in lowered_route:
            route_action = candidate
            break

    if route_action is not None:
        if route_action == 'settings_update' and upper_method in _READ_METHODS:
            return ACTION_RULES_BY_ACTION['settings_view']
        if route_action == 'member_view' and upper_method not in _READ_METHODS:
            # POST /members/<id> style routes are writes on the member family.
            return ACTION_RULES_BY_ACTION['member_role_update']
        return ACTION_RULES_BY_ACTION[route_action]

    if upper_method in _READ_METHODS:
        return ACTION_RULES_BY_ACTION['view']
    if upper_method == 'POST':
        return ACTION_RULES_BY_ACTION['create']
    if upper_method in {'PUT', 'PATCH'}:
        return ACTION_RULES_BY_ACTION['update']
    if upper_method == 'DELETE':
        return ACTION_RULES_BY_ACTION['delete']
    return ACTION_RULES_BY_ACTION['probe']


def level_cap_for_role(role: str | None) -> int:
    """Return the maximum capture level a role is allowed to produce."""

    if not role:
        return _UNROLED_LEVEL_CAP
    return _ROLE_LEVEL_CAP.get(str(role), _UNROLED_LEVEL_CAP)


def role_may_configure(role: str | None) -> bool:
    """Return whether a role may change Workspace tracing settings."""

    return str(role or '') in _SETTINGS_WRITE_ROLES


def bucket_allows(bucket: str, effective_level: int) -> bool:
    """Return whether a capture bucket should be persisted at this level."""

    if effective_level <= OPERATION_LEVEL_NONE:
        return False
    if bucket == 'read':
        return effective_level >= OPERATION_LEVEL_READ
    # ``write`` and ``audit`` are both recorded from mutation level upward.
    return effective_level >= OPERATION_LEVEL_MUTATION


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def is_sensitive_field(field_name: str) -> bool:
    """Return whether a field name must never be copied into a diff."""

    lowered = (field_name or '').lower()
    return any(marker in lowered for marker in _SENSITIVE_FIELD_MARKERS)


def truncate(value: typing.Any, limit: int) -> typing.Any:
    """Return ``value`` rendered as a bounded string (or the value itself)."""

    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)] + '…'


def redact_payload(payload: typing.Any, *, depth: int = 0) -> typing.Any:
    """Recursively drop sensitive keys from a payload before persisting it."""

    if depth > 4:
        return truncate(payload, _MAX_FIELD_VALUE_CHARS)
    if isinstance(payload, dict):
        redacted: dict[str, typing.Any] = {}
        for key, value in payload.items():
            if is_sensitive_field(str(key)):
                redacted[str(key)] = REDACTED_SENTINEL
                continue
            redacted[str(key)] = redact_payload(value, depth=depth + 1)
        return redacted
    if isinstance(payload, (list, tuple)):
        return [redact_payload(item, depth=depth + 1) for item in payload]
    return payload


def changed_fields(
    before: typing.Mapping[str, typing.Any] | None,
    after: typing.Mapping[str, typing.Any] | None,
    *,
    ignore: typing.Iterable[str] = (),
) -> list[dict[str, typing.Any]]:
    """Return the field-level diff between two mappings.

    The result is exactly what the traceability UI needs: for every changed
    field it reports the previous and the new value.
    """

    before_map = dict(before or {})
    after_map = dict(after or {})
    ignored = set(ignore)

    changes: list[dict[str, typing.Any]] = []
    for field_name in sorted(set(before_map) | set(after_map)):
        if field_name in ignored:
            continue
        old_value = before_map.get(field_name)
        new_value = after_map.get(field_name)
        if old_value == new_value:
            continue
        if is_sensitive_field(str(field_name)):
            changes.append(
                {
                    'field': str(field_name),
                    'before': REDACTED_SENTINEL,
                    'after': REDACTED_SENTINEL,
                }
            )
            continue
        changes.append(
            {
                'field': str(field_name),
                'before': truncate(old_value, _MAX_FIELD_VALUE_CHARS),
                'after': truncate(new_value, _MAX_FIELD_VALUE_CHARS),
            }
        )
    return changes


def build_summary(rule: ActionRule, changes: list[dict[str, typing.Any]]) -> str:
    """Build a short change digest stored alongside the record.

    The digest is display-neutral: the card renders the localized action label
    from i18n and shows this digest as the concrete ``field: a → b`` detail.
    """

    if not changes:
        return ''
    fragments: list[str] = []
    for change in changes[:_MAX_SUMMARY_FIELDS]:
        fragments.append(f"{change['field']}: {change['before']} → {change['after']}")
    remaining = len(changes) - len(fragments)
    if remaining > 0:
        fragments.append(f'+{remaining}')
    return '; '.join(fragments)


def changes_payload(changes: list[dict[str, typing.Any]]) -> str | None:
    """Serialize a diff into the stored JSON string."""

    if not changes:
        return None
    return json.dumps(changes, ensure_ascii=False, default=str)


def decode_changes(raw: str | None) -> list[dict[str, typing.Any]]:
    """Decode a stored diff, tolerating legacy or corrupt payloads."""

    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def decode_json_object(raw: str | None) -> dict[str, typing.Any]:
    """Decode a stored JSON object, tolerating legacy or corrupt payloads."""

    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def clamp_level(value: typing.Any) -> int:
    """Coerce an untrusted level input into the valid 0..2 range."""

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_OPERATION_LEVEL
    return max(OPERATION_LEVEL_NONE, min(OPERATION_LEVEL_READ, parsed))


def clamp_retention(value: typing.Any) -> int:
    """Coerce an untrusted retention input into the valid day range."""

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    return max(MIN_RETENTION_DAYS, min(MAX_RETENTION_DAYS, parsed))


def clamp_max_rows(value: typing.Any) -> int:
    """Coerce an untrusted row-budget input into the valid range."""

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MAX_ROWS
    return max(MIN_MAX_ROWS, min(MAX_MAX_ROWS, parsed))


def clamp_dedupe_window(value: typing.Any) -> int:
    """Coerce an untrusted dedupe window input into the valid second range."""

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DEDUPE_WINDOW_SECONDS
    return max(MIN_DEDUPE_WINDOW_SECONDS, min(MAX_DEDUPE_WINDOW_SECONDS, parsed))


def level_name(level: int) -> str:
    return persistence_operation_log.OPERATION_LEVEL_NAMES.get(int(level), 'unknown')


def _utcnow() -> datetime.datetime:
    """Return naive UTC, matching the database's ``CURRENT_TIMESTAMP``.

    Comparing a local-time cutoff against a UTC column would silently disable
    dedupe and retention in non-UTC timezones such as UTC+8.
    """

    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Tamper evidence
# ---------------------------------------------------------------------------


def _integrity_secret() -> bytes:
    """Derive the per-instance HMAC key without adding configuration.

    The instance id is generated and persisted by LangBot itself; salting it
    with a domain separator keeps this key independent from other uses.
    """

    return f'{_HASH_KEY_SALT}:{constants.instance_id}'.encode('utf-8')


def compute_record_hash(row: typing.Mapping[str, typing.Any]) -> str:
    """Return the keyed hash over the canonical content of one record.

    The parent pointer (``prev_hash``) is part of the payload, so the whole
    chain is anchored: editing a row or dropping a link changes the hash of
    every record computed after it.
    """

    canonical = {field: row.get(field) for field in _HASH_FIELDS}
    payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
    return hmac.new(_integrity_secret(), payload, hashlib.sha256).hexdigest()


def verify_record_hash(row: typing.Mapping[str, typing.Any], stored_hash: str | None) -> bool:
    """Return whether a stored hash still matches the row content."""

    if not stored_hash:
        return False
    return hmac.compare_digest(compute_record_hash(row), str(stored_hash))


def compute_dedupe_key(
    *,
    actor_account_uuid: str | None,
    action: str,
    route: str | None,
    resource_id: str | None,
) -> str:
    """Build the key that collapses repeated identical observations."""

    material = '|'.join(
        [
            str(actor_account_uuid or ''),
            str(action or ''),
            str(route or ''),
            str(resource_id or ''),
        ]
    )
    return hashlib.sha256(material.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class WorkspaceSettingsService:
    """Governance settings + operation traceability for one Workspace."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        # Level cache keyed by Workspace UUID: {"level": int, "expires": float}
        self._level_cache: dict[str, tuple[int, float]] = {}
        self._level_cache_ttl = 5.0
        # Retention / row budget / dedupe window cache keyed by Workspace UUID.
        # Reading all three on every insert would add up to three metadata
        # round trips to the hot write path; they change only through the
        # governance route, which invalidates this cache.
        self._policy_cache: dict[str, tuple[dict[str, int], float]] = {}
        self._policy_cache_ttl = 5.0
        # Inserts since the last row-budget check, keyed by Workspace UUID.
        self._insert_counters: dict[str, int] = {}

    # -- level resolution -------------------------------------------------

    def _cache_level(self, workspace_uuid: str, level: int) -> None:
        self._level_cache[workspace_uuid] = (
            int(level),
            datetime.datetime.now().timestamp() + self._level_cache_ttl,
        )

    def _cached_level(self, workspace_uuid: str) -> int | None:
        entry = self._level_cache.get(workspace_uuid)
        if entry is None:
            return None
        level, expires_at = entry
        if expires_at < datetime.datetime.now().timestamp():
            self._level_cache.pop(workspace_uuid, None)
            return None
        return level

    def invalidate_level(self, workspace_uuid: str) -> None:
        """Drop the cached level and policy after a settings change."""

        self._level_cache.pop(workspace_uuid, None)
        self._policy_cache.pop(workspace_uuid, None)

    async def _read_metadata(self, workspace_uuid: str, key: str) -> str | None:
        try:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_metadata.WorkspaceMetadata.value).where(
                    persistence_metadata.WorkspaceMetadata.workspace_uuid == workspace_uuid,
                    persistence_metadata.WorkspaceMetadata.key == key,
                )
            )
            return result.scalar_one_or_none()
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log metadata read failed for {key}: {exc}')
            return None

    async def _write_metadata(self, workspace_uuid: str, values: dict[str, str]) -> None:
        for key, value in values.items():
            try:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.delete(persistence_metadata.WorkspaceMetadata).where(
                        persistence_metadata.WorkspaceMetadata.workspace_uuid == workspace_uuid,
                        persistence_metadata.WorkspaceMetadata.key == key,
                    )
                )
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_metadata.WorkspaceMetadata).values(
                        workspace_uuid=workspace_uuid,
                        key=key,
                        value=value,
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive
                self.ap.logger.warning(f'Operation log metadata write failed for {key}: {exc}')

    async def _read_metadata_values(self, workspace_uuid: str, keys: typing.Iterable[str]) -> dict[str, str]:
        """Read several metadata rows for one Workspace in a single query."""

        wanted = list(dict.fromkeys(keys))
        if not wanted:
            return {}
        try:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(
                    persistence_metadata.WorkspaceMetadata.key,
                    persistence_metadata.WorkspaceMetadata.value,
                ).where(
                    persistence_metadata.WorkspaceMetadata.workspace_uuid == workspace_uuid,
                    persistence_metadata.WorkspaceMetadata.key.in_(wanted),
                )
            )
            return {row[0]: row[1] for row in result.all()}
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log metadata batch read failed: {exc}')
            return {}

    def _resolve_policy(self, values: dict[str, str]) -> dict[str, int]:
        """Clamp the raw policy values, falling back to the defaults."""

        def _coerce(key: str, clamp: typing.Callable[[typing.Any], int], default: int) -> int:
            raw = values.get(key)
            return default if raw is None else clamp(raw)

        return {
            'retention_days': _coerce(OPERATION_RETENTION_DAYS_KEY, clamp_retention, DEFAULT_RETENTION_DAYS),
            'max_rows': _coerce(OPERATION_MAX_ROWS_KEY, clamp_max_rows, DEFAULT_MAX_ROWS),
            'dedupe_window_seconds': _coerce(
                OPERATION_DEDUPE_WINDOW_KEY, clamp_dedupe_window, DEFAULT_DEDUPE_WINDOW_SECONDS
            ),
        }

    async def _operations_policy(self, workspace_uuid: str) -> dict[str, int]:
        """Return the cached retention / budget / dedupe configuration.

        Every recorded operation consults this policy (row budget and dedupe
        window), so it is cached per Workspace and invalidated whenever the
        governance route changes it.
        """

        entry = self._policy_cache.get(workspace_uuid)
        if entry is not None:
            values, expires_at = entry
            if expires_at >= datetime.datetime.now().timestamp():
                return values
            self._policy_cache.pop(workspace_uuid, None)

        raw = await self._read_metadata_values(
            workspace_uuid,
            (OPERATION_RETENTION_DAYS_KEY, OPERATION_MAX_ROWS_KEY, OPERATION_DEDUPE_WINDOW_KEY),
        )
        policy = self._resolve_policy(raw)
        self._policy_cache[workspace_uuid] = (
            policy,
            datetime.datetime.now().timestamp() + self._policy_cache_ttl,
        )
        return policy

    async def get_configured_level(self, workspace_uuid: str) -> int:
        """Return the Workspace-selected capture level (uncapped)."""

        raw = await self._read_metadata(workspace_uuid, OPERATION_LEVEL_KEY)
        if raw is None:
            return DEFAULT_OPERATION_LEVEL
        return clamp_level(raw)

    async def effective_level(self, workspace_uuid: str, role: str | None) -> int:
        """Return the level actually used for a request by ``role``."""

        cached = self._cached_level(workspace_uuid)
        if cached is None:
            cached = await self.get_configured_level(workspace_uuid)
            self._cache_level(workspace_uuid, cached)
        return min(cached, level_cap_for_role(role))

    async def set_operation_level(
        self,
        workspace_uuid: str,
        level: typing.Any,
        *,
        retention_days: typing.Any = None,
        max_rows: typing.Any = None,
        dedupe_window_seconds: typing.Any = None,
    ) -> dict[str, typing.Any]:
        """Persist a new capture level together with optional retention.

        Changing the level only changes whether *future* operations are
        stored. Records already written are never hidden, rewritten or
        deleted; only the retention policy may prune them. The new retention
        values apply immediately through ``prune``.
        """

        resolved_level = clamp_level(level)
        values = {
            OPERATION_LEVEL_KEY: str(resolved_level),
        }
        if retention_days is not None:
            values[OPERATION_RETENTION_DAYS_KEY] = str(clamp_retention(retention_days))
        if max_rows is not None:
            values[OPERATION_MAX_ROWS_KEY] = str(clamp_max_rows(max_rows))
        if dedupe_window_seconds is not None:
            values[OPERATION_DEDUPE_WINDOW_KEY] = str(clamp_dedupe_window(dedupe_window_seconds))
        await self._write_metadata(workspace_uuid, values)
        self.invalidate_level(workspace_uuid)
        # Apply the retention policy right away; the maintenance loop keeps
        # enforcing it afterwards. There is no manual prune action.
        await self.prune(workspace_uuid)
        return await self.describe_governance(workspace_uuid)

    async def get_retention_days(self, workspace_uuid: str) -> int:
        return (await self._operations_policy(workspace_uuid))['retention_days']

    async def get_max_rows(self, workspace_uuid: str) -> int:
        return (await self._operations_policy(workspace_uuid))['max_rows']

    async def get_dedupe_window(self, workspace_uuid: str) -> int:
        """Return the dedupe window in seconds for repeated observations."""

        return (await self._operations_policy(workspace_uuid))['dedupe_window_seconds']

    async def describe_governance(self, workspace_uuid: str) -> dict[str, typing.Any]:
        """Return the governance payload rendered by the settings panel.

        Every human-readable string is expressed as an i18n key so the frontend
        can localize without the backend shipping translations.
        """

        # One query resolves the level together with the retention policy; the
        # four ``get_*`` helpers below would otherwise issue four round trips.
        raw = await self._read_metadata_values(
            workspace_uuid,
            (
                OPERATION_LEVEL_KEY,
                OPERATION_RETENTION_DAYS_KEY,
                OPERATION_MAX_ROWS_KEY,
                OPERATION_DEDUPE_WINDOW_KEY,
            ),
        )
        configured = clamp_level(raw[OPERATION_LEVEL_KEY]) if OPERATION_LEVEL_KEY in raw else DEFAULT_OPERATION_LEVEL
        policy = self._resolve_policy(raw)
        return {
            'configured_level': configured,
            'configured_level_name': level_name(configured),
            'retention_days': policy['retention_days'],
            'max_rows': policy['max_rows'],
            'dedupe_window_seconds': policy['dedupe_window_seconds'],
            'supported_levels': [
                {'level': OPERATION_LEVEL_NONE, 'i18n_key': 'operationTrace.levels.off'},
                {'level': OPERATION_LEVEL_MUTATION, 'i18n_key': 'operationTrace.levels.mutation'},
                {'level': OPERATION_LEVEL_READ, 'i18n_key': 'operationTrace.levels.read'},
            ],
            'limits': {
                'min_retention_days': MIN_RETENTION_DAYS,
                'max_retention_days': MAX_RETENTION_DAYS,
                'min_max_rows': MIN_MAX_ROWS,
                'max_max_rows': MAX_MAX_ROWS,
                'min_dedupe_window_seconds': MIN_DEDUPE_WINDOW_SECONDS,
                'max_dedupe_window_seconds': MAX_DEDUPE_WINDOW_SECONDS,
            },
        }

    # -- writer -----------------------------------------------------------

    async def record(
        self,
        workspace_uuid: str,
        *,
        rule: ActionRule,
        level: int,
        actor_account_uuid: str | None = None,
        actor_name: str | None = None,
        actor_role: str | None = None,
        principal_type: str | None = None,
        api_key_uuid: str | None = None,
        auth_type: str | None = None,
        request_id: str | None = None,
        http_method: str | None = None,
        route: str | None = None,
        resource_id: str | None = None,
        outcome: str = 'ok',
        status_code: int | None = None,
        summary: str | None = None,
        changes: list[dict[str, typing.Any]] | None = None,
        detail: typing.Mapping[str, typing.Any] | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
        duration_ms: int = 0,
    ) -> bool:
        """Append one operation row. Returns whether a row was persisted.

        The level only decides *whether* an operation is stored; it never
        rewrites or hides records already written.
        """

        if level <= OPERATION_LEVEL_NONE:
            return False
        if not bucket_allows(rule.bucket, level):
            return False
        if level < OPERATION_LEVEL_MUTATION:
            return False

        try:
            record_fields: dict[str, typing.Any] = {
                'workspace_uuid': workspace_uuid,
                'actor_account_uuid': actor_account_uuid,
                'actor_name': str(actor_name)[:255] if actor_name else None,
                'actor_role': actor_role,
                'principal_type': str(principal_type)[:32] if principal_type else None,
                'api_key_uuid': str(api_key_uuid)[:255] if api_key_uuid else None,
                'auth_type': str(auth_type)[:32] if auth_type else None,
                'http_method': (http_method or '')[:12] or None,
                'route': (route or '')[:_MAX_ROUTE_CHARS] or None,
                'action': rule.action,
                'resource_type': rule.resource_type,
                'resource_id': str(resource_id)[:_MAX_RESOURCE_ID_CHARS] if resource_id else None,
                'level': int(level),
                'outcome': outcome,
                'status_code': int(status_code) if status_code is not None else None,
                'summary': summary,
                'changes': changes_payload(changes or []),
                'client_ip': str(client_ip)[:64] if client_ip else None,
            }

            # Collapse repeated identical observations (e.g. a WebUI left open
            # polling the same list) so page liveness cannot inflate the log.
            dedupe_key = compute_dedupe_key(
                actor_account_uuid=actor_account_uuid,
                action=rule.action,
                route=record_fields['route'],
                resource_id=record_fields['resource_id'],
            )
            record_fields['dedupe_key'] = dedupe_key
            if await self._is_duplicate_observation(workspace_uuid, dedupe_key):
                return False

            # Link each record to its predecessor so silent edits or removals
            # become detectable when the chain is re-verified on read.
            record_fields['prev_hash'] = await self._latest_record_hash(workspace_uuid)
            record_fields['record_hash'] = compute_record_hash(record_fields)

            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_operation_log.WorkspaceOperationLog).values(
                    **record_fields,
                    request_id=str(request_id)[:128] if request_id else None,
                    detail=json.dumps(redact_payload(dict(detail or {})), ensure_ascii=False, default=str)
                    if detail
                    else None,
                    user_agent=str(user_agent)[:_MAX_USER_AGENT_CHARS] if user_agent else None,
                    duration_ms=max(int(duration_ms), 0),
                )
            )
            await self._maybe_enforce_row_budget(workspace_uuid)
            return True
        except Exception as exc:  # pragma: no cover - auditing is best effort
            self.ap.logger.debug(f'Operation log write skipped: {exc}')
            return False

    async def _latest_record_hash(self, workspace_uuid: str) -> str | None:
        """Return the hash of the newest record, forming the chain link."""

        try:
            model = persistence_operation_log.WorkspaceOperationLog
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(model.record_hash)
                .where(model.workspace_uuid == workspace_uuid)
                .order_by(model.id.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log chain read skipped: {exc}')
            return None

    async def _is_duplicate_observation(self, workspace_uuid: str, dedupe_key: str) -> bool:
        """Return whether the same observation was just recorded."""

        window = await self.get_dedupe_window(workspace_uuid)
        if window <= 0:
            return False
        cutoff = _utcnow() - datetime.timedelta(seconds=window)
        try:
            model = persistence_operation_log.WorkspaceOperationLog
            # Existence only: ``LIMIT 1`` stops at the first match instead of
            # counting every row inside the window, which keeps the check a
            # single index seek even under a burst of identical observations.
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(model.id)
                .where(
                    model.workspace_uuid == workspace_uuid,
                    model.dedupe_key == dedupe_key,
                    model.created_at >= cutoff,
                )
                .limit(1)
            )
            return result.first() is not None
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log dedupe check skipped: {exc}')
            return False

    async def record_request(
        self,
        ctx: RequestContext | None,
        *,
        workspace_uuid: str | None = None,
        method: str,
        route: str,
        status_code: int | None = None,
        outcome: str | None = None,
        duration_ms: int = 0,
        resource_id: str | None = None,
        changes: list[dict[str, typing.Any]] | None = None,
        detail: typing.Mapping[str, typing.Any] | None = None,
    ) -> bool:
        """Classify and persist one HTTP request from the route wrapper."""

        target_workspace = workspace_uuid or (ctx.workspace_uuid if ctx is not None else None)
        if not target_workspace:
            return False

        role = ctx.workspace.role if ctx is not None else None
        level = await self.effective_level(target_workspace, role)
        rule = classify(method, route)

        if not bucket_allows(rule.bucket, level):
            return False

        resolved_outcome = outcome or ('ok' if (status_code is None or status_code < 400) else 'error')
        summary = build_summary(rule, changes or []) or None

        actor_name: str | None = None
        actor_account_uuid: str | None = None
        api_key_uuid: str | None = None
        principal_type: str | None = None
        auth_type: str | None = None
        request_id: str | None = None
        if ctx is not None:
            principal_type = (
                ctx.principal.principal_type.value
                if isinstance(ctx.principal.principal_type, PrincipalType)
                else str(ctx.principal.principal_type)
            )
            actor_account_uuid = ctx.principal.account_uuid or ctx.principal.actor_account_uuid
            api_key_uuid = ctx.principal.api_key_uuid
            auth_type = ctx.auth_type
            request_id = ctx.request_id

        if actor_account_uuid and self.ap.user_service is not None:
            try:
                account = await self.ap.user_service.get_user_by_uuid(actor_account_uuid)
                if account is not None:
                    actor_name = account.user
            except Exception:  # pragma: no cover - defensive
                actor_name = None

        client_ip = None
        user_agent = None
        try:
            import quart

            client_ip = quart.request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or None
            if not client_ip:
                client_ip = quart.request.remote_addr
            user_agent = quart.request.headers.get('User-Agent')
        except Exception:  # pragma: no cover - no active request context
            client_ip = None
            user_agent = None

        return await self.record(
            target_workspace,
            rule=rule,
            level=level,
            actor_account_uuid=actor_account_uuid,
            actor_name=actor_name,
            actor_role=role,
            principal_type=principal_type,
            api_key_uuid=api_key_uuid,
            auth_type=auth_type,
            request_id=request_id,
            http_method=method,
            route=route,
            resource_id=resource_id,
            outcome=resolved_outcome,
            status_code=status_code,
            summary=summary,
            changes=changes,
            detail=detail,
            client_ip=client_ip,
            user_agent=user_agent,
            duration_ms=duration_ms,
        )

    # -- reader -----------------------------------------------------------

    async def count_logs(
        self,
        workspace_uuid: str,
        *,
        since: datetime.datetime | None = None,
        level: int | None = None,
    ) -> int:
        try:
            query = sqlalchemy.select(sqlalchemy.func.count()).select_from(
                persistence_operation_log.WorkspaceOperationLog
            ).where(persistence_operation_log.WorkspaceOperationLog.workspace_uuid == workspace_uuid)
            if since is not None:
                query = query.where(persistence_operation_log.WorkspaceOperationLog.created_at >= since)
            if level is not None:
                query = query.where(persistence_operation_log.WorkspaceOperationLog.level == int(level))
            result = await self.ap.persistence_mgr.execute_async(query)
            return int(result.scalar_one_or_none() or 0)
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log count skipped: {exc}')
            return 0

    async def query_logs(
        self,
        workspace_uuid: str,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        action: str | None = None,
        resource_type: str | None = None,
        actor_account_uuid: str | None = None,
        level: int | None = None,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
    ) -> dict[str, typing.Any]:
        """Return one page of operation records plus a coarse summary."""

        resolved_limit = max(1, min(int(limit or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))
        resolved_offset = max(int(offset or 0), 0)

        try:
            model = persistence_operation_log.WorkspaceOperationLog
            filters = [model.workspace_uuid == workspace_uuid]
            if action:
                filters.append(model.action == action)
            if resource_type:
                filters.append(model.resource_type == resource_type)
            if actor_account_uuid:
                filters.append(model.actor_account_uuid == actor_account_uuid)
            if level is not None:
                filters.append(model.level == int(level))
            if since is not None:
                filters.append(model.created_at >= since)
            if until is not None:
                filters.append(model.created_at <= until)

            total_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(model).where(*filters)
            )
            total = int(total_result.scalar_one_or_none() or 0)

            rows_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(model)
                .where(*filters)
                .order_by(model.id.desc())
                .limit(resolved_limit)
                .offset(resolved_offset)
            )
            rows = list(rows_result.all())

            # Fetch one extra older row so the oldest visible record can still
            # have its chain link verified instead of being reported as broken.
            chain_rows: list[typing.Any] = list(rows)
            if rows:
                oldest_id = rows[-1].id
                older_result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(model)
                    .where(model.workspace_uuid == workspace_uuid, model.id < oldest_id)
                    .order_by(model.id.desc())
                    .limit(1)
                )
                chain_rows = list(rows) + list(older_result.all())

            records = [
                self._serialize_log(
                    row,
                    previous_row=chain_rows[index + 1] if index + 1 < len(chain_rows) else None,
                )
                for index, row in enumerate(rows)
            ]
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log query skipped: {exc}')
            total = 0
            records = []

        return {
            'records': records,
            'total': total,
            'limit': resolved_limit,
            'offset': resolved_offset,
            'tampered_count': sum(1 for record in records if record.get('tampered')),
        }

    def _serialize_log(self, row: typing.Any, *, previous_row: typing.Any | None = None) -> dict[str, typing.Any]:
        """Serialize one row and re-verify its tamper-evidence chain.

        ``previous_row`` is the chronologically older neighbour. When supplied,
        a mismatch between this row's ``prev_hash`` and the older row's
        ``record_hash`` marks the chain as broken.
        """

        rule = ACTION_RULES_BY_ACTION.get(row.action or '')
        hash_payload = {
            'workspace_uuid': row.workspace_uuid,
            'actor_account_uuid': row.actor_account_uuid,
            'actor_name': row.actor_name,
            'actor_role': row.actor_role,
            'principal_type': row.principal_type,
            'api_key_uuid': row.api_key_uuid,
            'auth_type': row.auth_type,
            'http_method': row.http_method,
            'route': row.route,
            'action': row.action,
            'resource_type': row.resource_type,
            'resource_id': row.resource_id,
            'level': row.level,
            'outcome': row.outcome,
            'status_code': row.status_code,
            'summary': row.summary,
            'changes': row.changes,
            'client_ip': row.client_ip,
            'prev_hash': row.prev_hash,
        }
        integrity_ok = verify_record_hash(hash_payload, row.record_hash)
        chain_ok = True
        if previous_row is not None:
            chain_ok = str(row.prev_hash or '') == str(previous_row.record_hash or '')

        return {
            'id': row.id,
            'workspace_uuid': row.workspace_uuid,
            'integrity_ok': integrity_ok,
            'chain_ok': chain_ok,
            'tampered': (not integrity_ok) or (not chain_ok),
            'record_hash': row.record_hash,
            'prev_hash': row.prev_hash,
            'actor_account_uuid': row.actor_account_uuid,
            'actor_name': row.actor_name,
            'actor_role': row.actor_role,
            'principal_type': row.principal_type,
            'api_key_uuid': row.api_key_uuid,
            'auth_type': row.auth_type,
            'request_id': row.request_id,
            'http_method': row.http_method,
            'route': row.route,
            'action': row.action,
            'action_category': rule.category if rule else 'resource',
            'action_i18n_key': rule.i18n_key if rule else f'operationTrace.actions.{row.action or "unknown"}',
            'resource_type': row.resource_type,
            'resource_id': row.resource_id,
            'level': row.level,
            'level_name': level_name(row.level),
            'outcome': row.outcome,
            'status_code': row.status_code,
            'summary': row.summary,
            'changes': decode_changes(row.changes),
            'detail': decode_json_object(row.detail),
            'client_ip': row.client_ip,
            'user_agent': row.user_agent,
            'duration_ms': row.duration_ms,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }

    async def export_logs(
        self,
        workspace_uuid: str,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        actor_account_uuid: str | None = None,
        level: int | None = None,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
        max_rows: int | None = None,
    ) -> dict[str, typing.Any]:
        """Export the filtered records as a structured document.

        Export is capped so a download can never materialize an unbounded table
        in memory. The document carries the records, the effective filters and
        the integrity summary, which keeps the artifact self-describing.
        """

        limit = MAX_EXPORT_ROWS if max_rows is None else max(1, min(int(max_rows), MAX_EXPORT_ROWS))

        try:
            model = persistence_operation_log.WorkspaceOperationLog
            filters = [model.workspace_uuid == workspace_uuid]
            if action:
                filters.append(model.action == action)
            if resource_type:
                filters.append(model.resource_type == resource_type)
            if actor_account_uuid:
                filters.append(model.actor_account_uuid == actor_account_uuid)
            if level is not None:
                filters.append(model.level == int(level))
            if since is not None:
                filters.append(model.created_at >= since)
            if until is not None:
                filters.append(model.created_at <= until)

            rows_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(model).where(*filters).order_by(model.id.desc()).limit(limit)
            )
            rows = list(rows_result.all())

            # One extra older row so the oldest exported record still has its
            # chain link verifiable inside the artifact.
            chain_rows: list[typing.Any] = list(rows)
            if rows:
                oldest_id = rows[-1].id
                older_result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(model)
                    .where(model.workspace_uuid == workspace_uuid, model.id < oldest_id)
                    .order_by(model.id.desc())
                    .limit(1)
                )
                chain_rows = list(rows) + list(older_result.all())

            records = [
                self._serialize_log(
                    row,
                    previous_row=chain_rows[index + 1] if index + 1 < len(chain_rows) else None,
                )
                for index, row in enumerate(rows)
            ]
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log export skipped: {exc}')
            records = []

        return {
            'exported_at': _utcnow().isoformat(timespec='seconds'),
            'exported': len(records),
            'tampered_count': sum(1 for record in records if record.get('tampered')),
            # Echo the effective filters so the artifact is self-describing:
            # an operator can tell which slice of the log a file represents.
            'filters': {
                'action': action,
                'resource_type': resource_type,
                'actor_account_uuid': actor_account_uuid,
                'level': int(level) if level is not None else None,
                'since': since.isoformat() if since is not None else None,
                'until': until.isoformat() if until is not None else None,
            },
            'limit': limit,
            'records': records,
        }

    async def list_filter_options(self, workspace_uuid: str) -> dict[str, typing.Any]:
        """Return the distinct filter values available in the panel."""

        try:
            model = persistence_operation_log.WorkspaceOperationLog
            actions = (
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(model.action).where(model.workspace_uuid == workspace_uuid).distinct()
                )
            ).scalars().all()
            resources = (
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(model.resource_type).where(model.workspace_uuid == workspace_uuid).distinct()
                )
            ).scalars().all()
            actors = (
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(model.actor_account_uuid, model.actor_name)
                    .where(model.workspace_uuid == workspace_uuid)
                    .distinct()
                )
            ).all()
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log filter options skipped: {exc}')
            actions, resources, actors = [], [], []

        return {
            'actions': sorted({item for item in actions if item}),
            'resource_types': sorted({item for item in resources if item}),
            'actors': [
                {'account_uuid': actor[0], 'name': actor[1] or actor[0]} for actor in actors if actor and actor[0]
            ],
        }

    # -- maintenance ------------------------------------------------------

    async def _maybe_enforce_row_budget(self, workspace_uuid: str) -> None:
        """Check the Workspace row budget once every few inserts.

        A ``COUNT`` on every append would make each recorded operation scan the
        whole Workspace history. The counter defers the check so the overshoot
        never exceeds ``_ROW_BUDGET_CHECK_STRIDE`` rows, while the maintenance
        loop and ``prune`` still enforce the exact budget.
        """

        pending = self._insert_counters.get(workspace_uuid, 0) + 1
        if pending < _ROW_BUDGET_CHECK_STRIDE:
            self._insert_counters[workspace_uuid] = pending
            return
        self._insert_counters[workspace_uuid] = 0
        await self._enforce_row_budget(workspace_uuid)

    async def _enforce_row_budget(self, workspace_uuid: str) -> None:
        """Drop the oldest rows when the Workspace row budget is exceeded."""

        budget = await self.get_max_rows(workspace_uuid)
        total = await self.count_logs(workspace_uuid)
        if total <= budget:
            return
        await self._delete_oldest(workspace_uuid, total - budget)

    async def _delete_oldest(self, workspace_uuid: str, count: int) -> int:
        if count <= 0:
            return 0
        try:
            model = persistence_operation_log.WorkspaceOperationLog
            oldest_ids = (
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(model.id)
                    .where(model.workspace_uuid == workspace_uuid)
                    .order_by(model.id.asc())
                    .limit(int(count))
                )
            ).scalars().all()
            if not oldest_ids:
                return 0
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(model).where(model.id.in_(list(oldest_ids)))
            )
            return len(oldest_ids)
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log trim skipped: {exc}')
            return 0

    async def prune(
        self,
        workspace_uuid: str,
        *,
        retention_days: int | None = None,
        max_rows: int | None = None,
    ) -> dict[str, int]:
        """Enforce retention by age and by row budget for one Workspace.

        Operation records are immutable. This retention policy is the only
        deletion path in the product, so evidence cannot be erased on demand
        by a privileged click.
        """

        days = await self.get_retention_days(workspace_uuid) if retention_days is None else clamp_retention(retention_days)
        budget = await self.get_max_rows(workspace_uuid) if max_rows is None else clamp_max_rows(max_rows)
        cutoff = _utcnow() - datetime.timedelta(days=days)

        expired = 0
        try:
            model = persistence_operation_log.WorkspaceOperationLog
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(model).where(
                    model.workspace_uuid == workspace_uuid,
                    model.created_at < cutoff,
                )
            )
            expired = int(result.rowcount or 0)
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log retention prune skipped: {exc}')

        total = await self.count_logs(workspace_uuid)
        trimmed = await self._delete_oldest(workspace_uuid, max(total - budget, 0))
        # The budget was just enforced in full, so the deferred counter restarts.
        self._insert_counters[workspace_uuid] = 0
        return {'expired': expired, 'trimmed': trimmed, 'remaining': await self.count_logs(workspace_uuid)}

    async def prune_all_workspaces(self) -> dict[str, int]:
        """Run retention pruning for every Workspace that enabled tracing.

        Returns a coarse report; individual Workspace failures are contained.
        """

        processed = 0
        removed = 0
        try:
            workspaces = (
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_metadata.WorkspaceMetadata.workspace_uuid).where(
                        persistence_metadata.WorkspaceMetadata.key == OPERATION_LEVEL_KEY
                    )
                )
            ).scalars().all()
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log workspace enumeration skipped: {exc}')
            return {'workspaces': 0, 'removed': 0}

        for workspace_uuid in {item for item in workspaces if item}:
            try:
                report = await self.prune(workspace_uuid)
            except Exception as exc:  # pragma: no cover - defensive
                self.ap.logger.debug(f'Operation log prune failed for {workspace_uuid}: {exc}')
                continue
            processed += 1
            removed += report['expired'] + report['trimmed']
        return {'workspaces': processed, 'removed': removed}
