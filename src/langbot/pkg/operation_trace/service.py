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

import asyncio
import contextlib
import contextvars
import dataclasses
import datetime
import enum
import hashlib
import hmac
import json
import logging
import time
import typing

import sqlalchemy

from ..api.http.authz import WorkspaceRole
from ..api.http.context import PrincipalType, RequestContext
from ..core import app
from ..entity.persistence import metadata as persistence_metadata
from ..entity.persistence import operation_log as persistence_operation_log
from ..entity.persistence.operation_log import (
    OPERATION_LEVEL_MUTATION,
    OPERATION_LEVEL_NONE,
    OPERATION_LEVEL_READ,
)
from ..utils import constants

logger = logging.getLogger(__name__)


#: Cheap process-wide gate for the Core route wrapper. It is a module-level
#: boolean, so checking it costs a load and a branch with no import, service
#: lookup, JSON parse or database round trip. It stays ``False`` until some
#: Workspace actually opts into tracing, which keeps the isolated subsystem
#: entirely off the hot path for the default (tracing disabled) instance.
_global_enabled = False


def is_globally_enabled() -> bool:
    """Return whether any Workspace may currently produce traces.

    The Core route wrapper reads this before doing any trace work. ``False``
    means the whole subsystem is inert and costs the request path nothing.
    """

    return _global_enabled


def enable_globally() -> None:
    """Open the cheap gate. Idempotent; called when a Workspace turns tracing on."""

    global _global_enabled
    _global_enabled = True


# ---------------------------------------------------------------------------
# Storage keys (WorkspaceMetadata.value is a short string column)
# ---------------------------------------------------------------------------

OPERATION_LEVEL_KEY = 'operation_log_level'
OPERATION_RETENTION_DAYS_KEY = 'operation_log_retention_days'
OPERATION_MAX_ROWS_KEY = 'operation_log_max_rows'
OPERATION_DEDUPE_WINDOW_KEY = 'operation_log_dedupe_seconds'

#: Tracing is opt-in: a Workspace records nothing until an owner or admin
#: explicitly turns it on. This keeps auditing off the hot path by default and
#: avoids collecting administrative activity before the operator asked for it.
DEFAULT_OPERATION_LEVEL = OPERATION_LEVEL_NONE
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

#: How many newest records the integrity summary reads before the numbers
#: beside the list are served from an approximate scan. Verifying a record means
#: recomputing its HMAC, so an unbounded scan on every page/refresh would make the
#: panel latency grow with the history size. ``MAX_MAX_ROWS`` (500k) is the
#: configured ceiling for a Workspace, so a full-table verification at that scale
#: is exactly what this bound avoids.
MAX_INTEGRITY_SCAN_ROWS = 20000

#: Integrity verification is cached per Workspace for this long. Recomputing a
#: row's HMAC is the expensive part of the read path, so a result computed
#: seconds ago is served straight from the cache, which makes a burst of panel
#: opens, refreshes and page turns (all within this window) effectively free.
#:
#: The cache is a latency shield, never a correctness shortcut: a cache miss
#: re-verifies the whole window because an in-place edit to an *already
#: verified* row must still be caught. Skipping previously verified ids would
#: turn the incremental scan into a permanent blind spot for exactly the
#: tampering this feature exists to expose.
INTEGRITY_CACHE_TTL_SECONDS = 30.0

#: ``integrity`` query values accepted by :meth:`query_logs`. ``all`` keeps the
#: previous behaviour; the other two map to the two failure modes the panel
#: surfaces independently (hash mismatch vs. broken chain link).
INTEGRITY_FILTER_ALL = 'all'
INTEGRITY_FILTER_ISSUES = 'issues'
INTEGRITY_FILTER_HASH_MISMATCH = 'hash_mismatch'
INTEGRITY_FILTER_CHAIN_BROKEN = 'chain_broken'
_INTEGRITY_FILTERS = frozenset(
    {
        INTEGRITY_FILTER_ALL,
        INTEGRITY_FILTER_ISSUES,
        INTEGRITY_FILTER_HASH_MISMATCH,
        INTEGRITY_FILTER_CHAIN_BROKEN,
    }
)

#: Upper bound for a single export so a download cannot load the whole table.
MAX_EXPORT_ROWS = 10000

#: Number of inserts a Workspace may accumulate before the row budget is
#: re-checked. Enforcing the budget with a ``COUNT`` on every insert turns a
#: cheap append into a scan of the whole Workspace history; deferring it keeps
#: the overshoot bounded by this stride while the maintenance loop still
#: enforces the exact limit.
_ROW_BUDGET_CHECK_STRIDE = 64

#: Bounded trace queue. The request path never blocks on it: when growing faster
#: than the single writer can drain, the oldest pending traces are dropped rather
#: than slowing the business request down. Dropping audit rows is acceptable;
#: stalling live traffic is not.
_QUEUE_MAX_SIZE = 2048

#: Seconds the writer waits for more work after draining a batch before flushing
#: the row-budget check. Batching turns N inserts into one budget query.
_WRITER_DRAIN_TIMEOUT = 0.2

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


def _integrity_scan_select(model: typing.Any, *conditions: typing.Any) -> typing.Any:
    """Build a projection-only scan query for integrity verification.

    Verification only re-hashes the row content plus the two chain pointers, so
    selecting the whole row would pull the ``changes`` / ``detail`` Text payloads
    and the client fingerprint for every scanned record. On a cold pass that is
    up to :data:`MAX_INTEGRITY_SCAN_ROWS` rows of payload the verifier never
    reads; projecting the hash columns keeps the read proportional to the hash
    instead of to the payload size.
    """

    columns = [model.id, model.record_hash]
    columns.extend(getattr(model, field) for field in _HASH_FIELDS)
    return sqlalchemy.select(*columns).where(*conditions)


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
    # --- Extension lifecycle (plugins, pages, skills, MCP) --------------
    ActionRule(
        action='plugin_view',
        category='extension',
        bucket='read',
        resource_type='plugin',
    ),
    ActionRule(
        action='plugin_config',
        category='extension',
        bucket='write',
        resource_type='plugin',
    ),
    ActionRule(
        action='plugin_install',
        category='extension',
        bucket='write',
        resource_type='plugin',
    ),
    # Uninstalling is a mutation with its own verb. Without it the DELETE on the
    # shared ``/plugins/<author>/<name>`` route falls through to the read rule
    # and an uninstall is mislabelled as a view.
    ActionRule(
        action='plugin_uninstall',
        category='extension',
        bucket='write',
        resource_type='plugin',
    ),
    ActionRule(
        action='plugin_upgrade',
        category='extension',
        bucket='write',
        resource_type='plugin',
    ),
    ActionRule(
        action='page_view',
        category='extension',
        bucket='read',
        resource_type='plugin_page',
    ),
    ActionRule(
        action='skill_view',
        category='extension',
        bucket='read',
        resource_type='skill',
    ),
    ActionRule(
        action='skill_install',
        category='extension',
        bucket='write',
        resource_type='skill',
    ),
    ActionRule(
        action='skill_update',
        category='extension',
        bucket='write',
        resource_type='skill',
    ),
    ActionRule(
        action='skill_uninstall',
        category='extension',
        bucket='write',
        resource_type='skill',
    ),
    # --- Knowledge & MCP -------------------------------------------------
    ActionRule(
        action='knowledge_base_view',
        category='knowledge',
        bucket='read',
        resource_type='knowledge_base',
    ),
    ActionRule(
        action='knowledge_base_update',
        category='knowledge',
        bucket='write',
        resource_type='knowledge_base',
    ),
    ActionRule(
        action='knowledge_base_delete',
        category='knowledge',
        bucket='write',
        resource_type='knowledge_base',
    ),
    ActionRule(
        action='mcp_view',
        category='integration',
        bucket='read',
        resource_type='mcp_server',
    ),
    ActionRule(
        action='mcp_config',
        category='integration',
        bucket='write',
        resource_type='mcp_server',
    ),
    ActionRule(
        action='mcp_delete',
        category='integration',
        bucket='write',
        resource_type='mcp_server',
    ),
    # --- Pipelines -------------------------------------------------------
    ActionRule(
        action='pipeline_extensions_update',
        category='resource',
        bucket='write',
        resource_type='pipeline',
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
    # --- Data-flow helpers (why a read: nothing to trace) ----------------
    # Uploading a file or indexing a document into a knowledge base is data
    # flowing into a resource, not a change to the resource's definition. It is
    # offered as a read verb so the persist gate drops it for every role, the
    # same way a file view is dropped, keeping the log to definition changes.
    ActionRule(
        action='file_view',
        category='resource',
        bucket='read',
        resource_type='file',
    ),
    ActionRule(
        action='ingest',
        category='resource',
        bucket='read',
        resource_type='knowledge_base',
    ),
    # Removing a document from a knowledge base is destructive and worth tracing,
    # unlike the upload/index that put it there.
    ActionRule(
        action='file_delete',
        category='knowledge',
        bucket='write',
        resource_type='knowledge_base',
    ),
    # --- Platform ingress (external traffic, no Workspace actor) ---------
    ActionRule(
        action='ingress',
        category='runtime',
        bucket='skip',
        resource_type='bot',
    ),
    # --- Provider credential handshake -----------------------------------
    ActionRule(
        action='codex_view',
        category='integration',
        bucket='read',
        resource_type='model_provider',
    ),
    ActionRule(
        action='codex_authorize',
        category='integration',
        bucket='write',
        resource_type='model_provider',
    ),
    ActionRule(
        action='probe',
        category='system',
        bucket='read',
        resource_type='system',
    ),
    # A management-assistant chat session is not a Workspace resource change:
    # creating a conversation and sending a turn produce one opaque
    # ``create/resource`` row each. They carry no "what changed" answer, so the
    # whole family is dropped rather than cluttering the log with noise.
    ActionRule(
        action='assistant_session',
        category='runtime',
        bucket='skip',
        resource_type='assistant_conversation',
    ),
    # Visitor traffic to an embedded public chat widget: unauthenticated, keyed
    # only by a bot UUID, never a Workspace actor. Dropped rather than logged.
    ActionRule(
        action='embed',
        category='runtime',
        bucket='skip',
        resource_type='bot',
    ),
)

ACTION_RULES_BY_ACTION: typing.Final[dict[str, ActionRule]] = {rule.action: rule for rule in ACTION_RULE_TABLE}

_READ_METHODS: typing.Final = frozenset({'GET', 'HEAD', 'OPTIONS'})

# Route rules evaluated in order; the first match wins, so the most specific
# rule must precede its prefix. Each rule is ``(fragments, read_action,
# write_action, delete_action, fallback_action)``: every fragment must appear in
# the lowered route (a tuple expresses an AND, which lets
# ``/plugins/<author>/<name>/config`` be told apart from
# ``/plugins/<author>/<name>``).
#
# The action is selected by the method bucket: a read verb uses ``read_action``,
# ``DELETE`` uses ``delete_action``, a write verb uses ``write_action``. Two
# subtlety guards exist because keying only on fragments and then trusting the
# bucket silently mislabels real operations:
#
# * ``write_action`` may be ``None`` for a read-only surface (``/plugins/github``,
#   the codex auth handshake, the public webhook ingress). A stray non-read verb
#   then uses ``fallback_action`` instead of being recorded as a mutation.
# * the bucket is re-derived from the *actual* method and the resolved action, so
#   a mismatch can never route a real mutation into the read bucket (which is
#   dropped at the mutation level) or a page load into the write bucket.
_ROUTE_RULES: typing.Final[tuple[tuple[tuple[str, ...], str, str | None, str | None, str], ...]] = (
    # --- Audit surface itself -------------------------------------------
    (('/settings/operation-logs/export',), 'export', 'export', None, 'export'),
    (('/settings/operation-logs',), 'audit_log_view', 'audit_log_view', None, 'audit_log_view'),
    (('/settings/operation-level',), 'settings_view', 'settings_update', None, 'settings_view'),
    (('/settings/governance',), 'settings_view', 'settings_update', None, 'settings_view'),
    (('/settings/limits',), 'settings_view', 'settings_update', None, 'settings_view'),
    # --- Extension lifecycle: plugins -----------------------------------
    # ``/plugins/install`` is an install; the bare ``/plugins/<author>/<name>``
    # is a read when fetched and an uninstall when deleted.
    (('/plugins/install',), 'plugin_view', 'plugin_install', None, 'plugin_view'),
    (('/plugins/github',), 'plugin_view', None, None, 'plugin_view'),
    # Editing or deleting a plugin's own config file is a plugin change, not an
    # opaque resource delete. Must precede the ``/config`` rule below, whose
    # fragment also matches ``config-files``.
    (('/plugins/', '/config-files'), 'plugin_view', 'plugin_config', 'plugin_config', 'plugin_view'),
    (('/plugins/', '/config'), 'plugin_view', 'plugin_config', None, 'plugin_view'),
    (('/plugins/', '/page-api'), 'page_view', 'page_view', None, 'page_view'),
    (('/plugins/', '/upgrade'), 'plugin_view', 'plugin_upgrade', None, 'plugin_view'),
    (('/plugins/', '/logs'), 'plugin_view', 'plugin_view', None, 'plugin_view'),
    (('/plugins',), 'plugin_view', 'plugin_view', 'plugin_uninstall', 'plugin_view'),
    # The pipeline extension bindings (plugins / MCP servers / skills) live on
    # ``/pipelines/<uuid>/extensions``, not on a plugin. Without this rule the
    # generic fragment below would classify the change as a plugin config edit.
    # The read keeps the generic ``view`` for backwards-compatible labelling.
    (('/extensions',), 'view', 'pipeline_extensions_update', None, 'view'),
    # --- Extension lifecycle: skills ------------------------------------
    # ``/skills/install/...`` is an install; the bare ``/skills`` collection is
    # created with POST and the item is rewritten with PUT, so the write verb is
    # an update -- not ``skill_view``, which used to drop a real skill edit into
    # the read bucket where a mutation-level Workspace never persisted it.
    (('/skills/', '/install'), 'skill_view', 'skill_install', None, 'skill_view'),
    (('/skills',), 'skill_view', 'skill_update', 'skill_uninstall', 'skill_view'),
    # --- Ingestion helpers (data flowing in, not a definition change) ----
    # Ordered before the knowledge-base rule so a file upload or an index is not
    # mislabelled as a knowledge-base definition update.
    (('/knowledge/', '/files'), 'file_view', 'ingest', 'file_delete', 'file_view'),
    # --- Knowledge bases & MCP servers ----------------------------------
    (('/knowledge/',), 'knowledge_base_view', 'knowledge_base_update', 'knowledge_base_delete', 'knowledge_base_view'),
    (('/mcp/', '/config'), 'mcp_view', 'mcp_config', None, 'mcp_view'),
    (('/mcp',), 'mcp_view', 'mcp_config', 'mcp_delete', 'mcp_view'),
    # --- Member management ----------------------------------------------
    (('/members',), 'member_view', 'member_role_update', None, 'member_view'),
    (('/invitations',), 'member_view', 'member_invite', None, 'member_view'),
    # --- Agent-assistant session chatter (never traced) ------------------
    # Placed before the generic verbs so a conversation turn is not recorded as
    # an opaque ``create`` on a nameless resource.
    (('/assistant',), 'assistant_session', 'assistant_session', 'assistant_session', 'assistant_session'),
    # --- Embedded public chat widget (visitor traffic, never traced) ------
    (('/embed/',), 'embed', 'embed', 'embed', 'embed'),
    # --- Public inbound webhook ingress (external traffic, never traced) --
    # ``/bots/<uuid>`` is unauthenticated platform traffic, not a Workspace
    # mutation; recording it as ``create/resource`` was pure noise.
    (('/bots/',), 'ingress', 'ingress', 'ingress', 'ingress'),
    # --- Provider credential handshake (in-flight pairing state) ---------
    (('/codex/',), 'codex_view', None, 'codex_authorize', 'codex_view'),
    # --- Ingestion helpers: uploading a document is data flowing in, not a
    #     change to a resource definition. --------------------------------
    (('/files/',), 'file_view', 'ingest', 'ingest', 'file_view'),
    # --- Generic resource verbs -----------------------------------------
    (('/export',), 'export', 'export', None, 'export'),
    (('/debug',), 'debug', 'debug', None, 'debug'),
    (('/execute',), 'execute', 'execute', None, 'execute'),
    (('/publish',), 'publish', 'publish', None, 'publish'),
)

#: Refines the resource family for the generic verb rules. The route rules above
#: only cover the extension/tenant surfaces; everything else (bots, providers,
#: pipelines, users, monitoring...) falls back to a nameless ``resource``. This
#: table names the family from the registered route identity, so a read of
#: ``/api/v1/pipelines`` is reported as a Pipeline, not as an opaque Resource.
#: It is only consulted when the matched rule still carries the generic
#: ``resource`` type, so specific rules keep their own family. More specific
#: fragments must precede their prefixes because the first match wins.
_RESOURCE_RULES: typing.Final[tuple[tuple[tuple[str, ...], str], ...]] = (
    (('/platform/bots',), 'bot'),
    (('/platform/',), 'adapter'),
    (('/provider/providers',), 'model_provider'),
    (('/provider/models',), 'llm_model'),
    (('/provider/',), 'model_provider'),
    (('/pipelines',), 'pipeline'),
    (('/user/',), 'user'),
    (('/workspaces/current',), 'workspace'),
    (('/workspaces',), 'workspace'),
    (('/monitoring',), 'monitoring'),
    (('/webhooks',), 'webhook'),
    (('/apikeys',), 'api_key'),
    (('/agents',), 'agent'),
    (('/files/',), 'file'),
    (('/skills',), 'skill'),
    (('/extensions',), 'plugin'),
    (('/assistant',), 'assistant_conversation'),
    # The sandbox, survey and generic system probes share the ``system`` family.
    (('/box/',), 'system'),
    (('/survey',), 'system'),
    (('/system/',), 'system'),
)


def _resource_type_for(route: str) -> str | None:
    """Return the resource family for a route, or ``None`` when unknown."""

    lowered = (route or '').lower()
    for fragments, resource_type in _RESOURCE_RULES:
        if all(fragment in lowered for fragment in fragments):
            return resource_type
    return None


def _with_resource_type(rule: ActionRule, route: str) -> ActionRule:
    """Refine a generic rule's resource family from the route identity.

    Only the generic fallback (``resource``) is refined; a rule that already
    names a family (plugin, skill, member...) is returned unchanged.
    """

    if rule.resource_type != 'resource':
        return rule
    resource_type = _resource_type_for(route)
    if resource_type is None:
        return rule
    return dataclasses.replace(rule, resource_type=resource_type)


#: Action names that describe an observation. A mutation can never be persisted
#: under one of these: the read bucket is dropped at the mutation level, so a
def _action_bucket(action: str, method: str) -> str:
    """Return the capture bucket for a resolved action and the actual method.

    The action table is the single source of truth: an action declares whether it
    is a traceable change (``write``), an observation (``read``), the audit
    surface itself (``audit``) or noise (``skip``). The only adjustment made here
    is that a read *method* is always an observation -- so a GET that somehow
    resolved to a write action still cannot be persisted as a mutation. Because
    the table now names a real write action for every mutating route, trusting it
    no longer lets a skill edit hide in the read bucket the way it used to.
    """

    bucket = ACTION_RULES_BY_ACTION[action].bucket
    if bucket in ('audit', 'skip'):
        return bucket
    if method in _READ_METHODS:
        return 'read'
    return bucket


def _resolve(rule: ActionRule, action: str, method: str, route: str) -> ActionRule:
    """Attach the method-derived bucket to a classified action."""

    refined = _with_resource_type(ACTION_RULES_BY_ACTION[action], route)
    return dataclasses.replace(refined, bucket=_action_bucket(action, method))


def classify(method: str, route: str) -> ActionRule:
    """Map one HTTP request to its normalized action rule.

    ``route`` must be the registered Core route identity, never a raw URL, so
    user identifiers cannot leak into classification.
    """

    upper_method = (method or 'GET').upper()
    lowered_route = (route or '').lower()
    is_read = upper_method in _READ_METHODS
    is_delete = upper_method == 'DELETE'

    for fragments, read_action, write_action, delete_action, fallback_action in _ROUTE_RULES:
        if all(fragment in lowered_route for fragment in fragments):
            if is_read:
                action = read_action
            elif is_delete:
                # Fall back to the generic delete verb when a rule has no
                # dedicated destroy action (still a mutation, never a view).
                action = delete_action or 'delete'
            else:
                # A read-only surface declares no write action; never invent a
                # mutation for it, use the observation action instead.
                action = write_action or fallback_action
            return _resolve(ACTION_RULES_BY_ACTION[action], action, upper_method, route)

    if is_read:
        action = 'view'
    elif is_delete:
        action = 'delete'
    elif upper_method == 'POST':
        action = 'create'
    elif upper_method in {'PUT', 'PATCH'}:
        action = 'update'
    else:
        action = 'probe'
    return _resolve(ACTION_RULES_BY_ACTION[action], action, upper_method, route)


def level_cap_for_role(role: str | None) -> int:
    """Return the maximum capture level a role is allowed to produce."""

    if not role:
        return _UNROLED_LEVEL_CAP
    return _ROLE_LEVEL_CAP.get(str(role), _UNROLED_LEVEL_CAP)


def role_may_configure(role: str | None) -> bool:
    """Return whether a role may change Workspace tracing settings."""

    return str(role or '') in _SETTINGS_WRITE_ROLES


def bucket_allows(bucket: str, effective_level: int) -> bool:
    """Return whether a capture bucket should be persisted at this level.

    ``write`` buckets are recorded from the mutation level upward. ``read``
    and ``audit`` are both *observation* buckets: viewing a resource and
    viewing the audit surface itself are reads, so a mutation-level Workspace
    must not fill its log with page views. They are only persisted once the
    Workspace opts into the read level. ``skip`` is charter noise a Workspace
    never needs traced (an assistant chat session's own turn traffic), so it is
    dropped at every level instead of being mislabelled as a resource change.
    """

    if bucket == 'skip':
        return False
    if effective_level <= OPERATION_LEVEL_NONE:
        return False
    if bucket in ('read', 'audit'):
        return effective_level >= OPERATION_LEVEL_READ
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


#: Ordered key groups that identify the resource a request acts on. Each group
#: is joined with ``/`` so ``author`` + ``plugin_name`` renders as
#: ``author/plugin_name`` — the same identity the UI already shows. Only these
#: keys are consulted: reading arbitrary payload fields would let a caller
#: inject unbounded, unattributed text into the audit trail.
_IDENTITY_KEY_GROUPS: typing.Final[tuple[tuple[str, ...], ...]] = (
    ('plugin_author', 'plugin_name'),
    ('author', 'plugin_name'),
    ('plugin_author', 'name'),
    # GitHub installs (plugins and skills) name the target as owner + repo in
    # the request body rather than in the URL, so without this group a
    # GitHub install would be traced as "a plugin was installed" with no name.
    ('owner', 'repo'),
    ('author', 'name'),
    ('skill_uuid',),
    ('knowledge_base_uuid',),
    ('server_uuid',),
    ('pipeline_uuid',),
    ('provider_uuid',),
    ('model_uuid',),
    ('account_uuid',),
    ('email',),
    ('name',),
    ('uuid',),
)


def resolve_resource_identity(
    path_params: typing.Mapping[str, typing.Any] | None,
    body: typing.Mapping[str, typing.Any] | None,
) -> str | None:
    """Best-effort identity of the resource one request acts on.

    Path parameters describe the resource a route was registered for and are
    therefore trusted; the request body is only consulted for install-style
    endpoints that carry the identity in their payload (a marketplace install
    names the plugin in the body, not in the URL). The result is bounded and
    sensitive-looking keys are skipped so a secret can never be echoed back
    through the trace.
    """

    params = path_params or {}
    payload = body or {}
    for group in _IDENTITY_KEY_GROUPS:
        parts: list[str] = []
        for key in group:
            value = params.get(key)
            if value is None:
                value = payload.get(key)
            if value is None or value == '' or is_sensitive_field(key):
                parts = []
                break
            parts.append(str(value))
        if parts:
            return typing.cast(str, truncate('/'.join(parts), _MAX_RESOURCE_ID_CHARS))
    return None


def build_summary(rule: ActionRule, changes: list[dict[str, typing.Any]]) -> str:
    """Build a short change digest stored alongside the record.

    The digest is display-neutral: the card renders the localized action label
    from i18n and shows this digest as the concrete ``field: a → b`` detail.
    """

    if not changes:
        return ''
    fragments: list[str] = []
    for change in changes[:_MAX_SUMMARY_FIELDS]:
        fragments.append(f'{change["field"]}: {change["before"]} → {change["after"]}')
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


def dedupe_material(
    *,
    actor_account_uuid: str | None,
    action: str,
    route: str | None,
    resource_id: str | None,
) -> str:
    """Return the raw material the dedupe key hashes.

    The request path builds this cheap string; the background writer hashes it,
    so enabling tracing never runs a hash on the request path.
    """

    return '|'.join(
        [
            str(actor_account_uuid or ''),
            str(action or ''),
            str(route or ''),
            str(resource_id or ''),
        ]
    )


def hash_dedupe_material(material: str) -> str:
    """Hash the raw dedupe material into the stored key."""

    return hashlib.sha256(material.encode('utf-8')).hexdigest()


def compute_dedupe_key(
    *,
    actor_account_uuid: str | None,
    action: str,
    route: str | None,
    resource_id: str | None,
) -> str:
    """Build the key that collapses repeated identical observations."""

    return hash_dedupe_material(
        dedupe_material(
            actor_account_uuid=actor_account_uuid,
            action=action,
            route=route,
            resource_id=resource_id,
        )
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class WorkspaceSettingsService:
    """Governance settings + operation traceability for one Workspace."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        # Publish the cheap gate on the app so the Core route wrapper can read
        # it as a plain attribute without importing this package.
        ap.operation_trace_active = is_globally_enabled()
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
        # Verification cache keyed by (Workspace UUID, listing filters). The
        # verification result is shareable across whatever narrows the listing,
        # so keying on the whole filter set (not just the Workspace) lets the
        # panel's common views -- "everything" and "mutations only" -- both hit
        # the cache instead of forcing a full rescan on every page turn.
        # Single-writer queue. Trace recording must never run on the request
        # path: when tracing is enabled the WebUI fires a burst of parallel
        # requests (login alone touches a dozen endpoints) and doing several
        # database round trips and a serialized write for each one stalls the
        # whole service. Instead the request path only enqueues a plain dict and
        # returns immediately; one background coroutine drains the queue and
        # writes sequentially. Sequential writes also remove the read-newest-hash
        # race that used to manufacture false "chain broken" reports.
        self._queue: asyncio.Queue[dict[str, typing.Any]] = asyncio.Queue(maxsize=_QUEUE_MAX_SIZE)
        self._writer_task: asyncio.Task[None] | None = None
        # Incremental integrity verification cache, keyed by Workspace UUID. The
        # chain is append-only, so once a prefix is verified it stays valid; a
        # later read only has to verify the rows appended since. Without this the
        # panel re-hashed up to MAX_INTEGRITY_SCAN_ROWS rows on every open,
        # refresh and page turn, which is what made reading the log feel slow.
        self._integrity_cache: dict[str, dict[str, typing.Any]] = {}
        self._dropped_count = 0
        # Failed persistence attempts, so a silently broken writer (a missing
        # tenant scope, an RLS rejection) is reported instead of only counted.
        self._write_failures = 0
        # Set while the queue is empty; lets tests/shutdown await a drain.
        self._idle = asyncio.Event()
        self._idle.set()

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

    def _activate(self) -> None:
        """Open the cheap global gate once any Workspace enables tracing."""

        enable_globally()
        self.ap.operation_trace_active = True

    def _workspace_scope(self, workspace_uuid: str) -> typing.AsyncContextManager[typing.Any]:
        """Carry a Workspace scope into persistence work that runs off-request.

        Cloud runtime rejects every database call made without an explicit scope,
        and the audit table is RLS-protected on ``langbot.workspace_uuid``, so the
        background writer and the retention loop have to establish their own
        scope. On the request path the caller already bound the Workspace: that
        scope is the correct one, so the boundary is skipped rather than nested.
        """

        manager = getattr(self.ap, 'persistence_mgr', None)
        tenant_scope = getattr(manager, 'tenant_scope', None)
        current_scope = getattr(manager, 'current_scope', None)
        if not callable(tenant_scope) or not workspace_uuid:
            return contextlib.nullcontext()
        if callable(current_scope):
            try:
                active = current_scope()
            except Exception:
                # A child task that inherited its parent's scope cannot use it;
                # an explicit boundary of its own is exactly what it needs.
                active = None
            if active is not None:
                return contextlib.nullcontext()
        return tenant_scope(workspace_uuid)

    async def prime_global_flag(self) -> None:
        """Open the cheap global gate at startup if a Workspace already opted in.

        Runs once during application build, never per request, so a
        previously-enabled Workspace keeps recording after a restart while a
        disabled instance still pays nothing on the hot path. Workspaces are
        enumerated through the execution bindings this instance owns, because the
        metadata table is RLS-protected per Workspace and a single cross-Workspace
        scan can never see them in cloud runtime.
        """

        try:
            for workspace_uuid in await self._traced_workspace_candidates():
                async with self._workspace_scope(workspace_uuid):
                    level = clamp_level(await self._read_metadata(workspace_uuid, OPERATION_LEVEL_KEY))
                if level > OPERATION_LEVEL_NONE:
                    self._activate()
                    return
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation trace global gate prime skipped: {exc}')

    async def _traced_workspace_candidates(self) -> list[str]:
        """Return the Workspaces that may have tracing enabled.

        A multi-Workspace runtime enumerates the execution bindings discovered for
        this instance. A single-database deployment can scan the metadata table
        directly, which is also the path a lightweight test double takes.
        """

        list_bindings = getattr(
            getattr(self.ap, 'workspace_service', None),
            'list_active_execution_bindings',
            None,
        )
        if callable(list_bindings):
            try:
                bindings = await list_bindings()
            except Exception as exc:  # pragma: no cover - discovery is optional
                self.ap.logger.debug(f'Operation trace Workspace discovery skipped: {exc}')
            else:
                return [str(binding.workspace_uuid) for binding in bindings]
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_metadata.WorkspaceMetadata.workspace_uuid).where(
                persistence_metadata.WorkspaceMetadata.key == OPERATION_LEVEL_KEY,
                persistence_metadata.WorkspaceMetadata.value != str(OPERATION_LEVEL_NONE),
            )
        )
        return [str(workspace_uuid) for workspace_uuid in result.scalars().all()]

    async def _read_metadata(self, workspace_uuid: str, key: str) -> str | None:
        try:
            # Resolved outside the request scope when the route wrapper records a
            # request, so the read has to carry the Workspace itself.
            async with self._workspace_scope(workspace_uuid):
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
        async with self._workspace_scope(workspace_uuid):
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
            async with self._workspace_scope(workspace_uuid):
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
        configured = clamp_level(raw)
        if configured > OPERATION_LEVEL_NONE:
            # Reading an enabled Workspace re-opens the gate, so tracing resumes
            # on its own after a restart even before a write occurs.
            self._activate()
        return configured

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
        if resolved_level > OPERATION_LEVEL_NONE:
            self._activate()
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

    def resolve_resource_identity(
        self,
        path_params: typing.Mapping[str, typing.Any] | None,
        body: typing.Mapping[str, typing.Any] | None,
    ) -> str | None:
        """Identify the resource a request acts on.

        Thin instance wrapper over the module-level resolver so the Core route
        wrapper can name a resource through the service handle without importing
        this package directly.
        """

        return resolve_resource_identity(path_params, body)

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
        """Queue one operation for traceability. Returns whether it was queued.

        This method runs on the request path, so it must never touch the
        database or await slow work: it only builds a bounded dict and pushes it
        onto the writer queue. The background writer persists it later. When the
        queue is full (traffic outruns the writer) the oldest pending trace is
        dropped rather than slowing the request down.
        """

        if level <= OPERATION_LEVEL_NONE:
            return False
        if not bucket_allows(rule.bucket, level):
            return False
        if level < OPERATION_LEVEL_MUTATION:
            return False

        record_fields: dict[str, typing.Any] = {
            'workspace_uuid': workspace_uuid,
            'actor_account_uuid': actor_account_uuid,
            'actor_name': str(actor_name)[:255] if actor_name else None,
            'actor_role': actor_role,
            'principal_type': str(principal_type)[:32] if principal_type else None,
            'api_key_uuid': str(api_key_uuid)[:255] if api_key_uuid else None,
            'auth_type': str(auth_type)[:32] if auth_type else None,
            'request_id': str(request_id)[:128] if request_id else None,
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
            'detail': json.dumps(redact_payload(dict(detail or {})), ensure_ascii=False, default=str)
            if detail
            else None,
            'client_ip': str(client_ip)[:64] if client_ip else None,
            'user_agent': str(user_agent)[:_MAX_USER_AGENT_CHARS] if user_agent else None,
            'duration_ms': max(int(duration_ms), 0),
        }
        # Collapse repeated identical observations (e.g. a WebUI left open
        # polling the same list) so page liveness cannot inflate the log. Only
        # the cheap raw material is built here; the writer hashes it off the
        # request path.
        record_fields['_dedupe_material'] = dedupe_material(
            actor_account_uuid=actor_account_uuid,
            action=rule.action,
            route=record_fields['route'],
            resource_id=record_fields['resource_id'],
        )

        return self._enqueue(record_fields)

    # -- background writer ------------------------------------------------

    def _enqueue(self, record_fields: dict[str, typing.Any]) -> bool:
        """Push one trace onto the writer queue without blocking the request."""

        self._ensure_writer()
        self._idle.clear()
        try:
            self._queue.put_nowait(record_fields)
        except asyncio.QueueFull:
            # Drop the oldest pending trace to make room; never block the request.
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - race, harmless
                pass
            self._dropped_count += 1
            if self._dropped_count % 100 == 1:
                self.ap.logger.warning('Operation trace queue full; dropped %s traces so far', self._dropped_count)
            try:
                self._queue.put_nowait(record_fields)
            except asyncio.QueueFull:  # pragma: no cover - defensive
                pass
        return True

    def _ensure_writer(self) -> None:
        """Start the single-writer task on first use (inside a running loop)."""

        if self._writer_task is not None and not self._writer_task.done():
            return
        # A fresh context: the writer outlives the request that first enqueued a
        # trace. Inheriting that request's persistence scope would make every
        # later write fail, because a child task may not use its parent's scope.
        self._writer_task = asyncio.get_running_loop().create_task(
            self._writer_loop(),
            context=contextvars.Context(),
        )

    async def _writer_loop(self) -> None:
        """Drain the queue and persist traces sequentially.

        A single writer keeps the hash chain correct without a lock: each row is
        linked to the previously written row, so concurrent request producers can
        never both link to the same predecessor.
        """

        while True:
            try:
                record_fields = await self._queue.get()
            except asyncio.CancelledError:
                raise

            batch = [record_fields]
            while True:
                try:
                    batch.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            touched: set[str] = set()
            for fields in batch:
                written = await self._persist(fields)
                if written:
                    touched.add(fields['workspace_uuid'])

            for workspace_uuid in touched:
                await self._maybe_enforce_row_budget(workspace_uuid)

            if self._queue.empty():
                self._idle.set()
            else:
                # More work is already waiting; give the event loop a breath so a
                # sustained burst cannot starve other tasks, then drain again.
                await asyncio.sleep(_WRITER_DRAIN_TIMEOUT)

    async def _persist(self, record_fields: dict[str, typing.Any]) -> bool:
        """Persist one queued trace. Never raises (auditing is best effort)."""

        try:
            workspace_uuid = record_fields['workspace_uuid']
            # The writer drains the queue outside any request, so it has to carry
            # its own Workspace scope: cloud runtime refuses unscoped access and
            # the audit table only accepts rows that match the bound Workspace.
            async with self._workspace_scope(workspace_uuid):
                # Off the request path: hash the dedupe material, resolve the actor
                # display name, then link and insert this row.
                record_fields['dedupe_key'] = hash_dedupe_material(record_fields.pop('_dedupe_material'))
                if record_fields.get('actor_name') is None and record_fields.get('actor_account_uuid'):
                    await self._fill_actor_name(record_fields)
                if await self._is_duplicate_observation(workspace_uuid, record_fields['dedupe_key']):
                    return False
                record_fields['prev_hash'] = await self._latest_record_hash(workspace_uuid)
                record_fields['record_hash'] = compute_record_hash(record_fields)
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_operation_log.WorkspaceOperationLog).values(**record_fields)
                )
                return True
        except Exception as exc:  # pragma: no cover - auditing is best effort
            self._note_write_failure(exc)
            return False

    def _note_write_failure(self, exc: BaseException) -> None:
        """Report a dropped trace without letting it break the caller.

        Recording is best effort, but an audit trail that silently stops growing
        is indistinguishable from an idle Workspace. The first failure and then
        every hundredth are surfaced; the rest stay at debug so a persistent
        failure cannot flood the log.
        """

        self._write_failures += 1
        if self._write_failures == 1 or self._write_failures % 100 == 0:
            self.ap.logger.warning(f'Operation log write failed ({self._write_failures} so far): {exc}')
        else:
            self.ap.logger.debug(f'Operation log write skipped: {exc}')

    async def _fill_actor_name(self, record_fields: dict[str, typing.Any]) -> None:
        """Resolve the actor display name off the request path."""

        if self.ap.user_service is None:
            return
        try:
            account = await self.ap.user_service.get_user_by_uuid(record_fields['actor_account_uuid'])
            if account is not None:
                record_fields['actor_name'] = account.user
        except Exception:  # pragma: no cover - defensive
            pass

    async def flush_pending(self, timeout: float = 5.0) -> None:
        """Wait for the queue to drain. Used by tests and shutdown paths."""

        if self._writer_task is None:
            return
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=timeout)
        except asyncio.TimeoutError:  # pragma: no cover - defensive
            pass

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

        # Enqueue directly: no database read on the request path. The writer
        # resolves the actor display name and hashes the dedupe material later.
        record_fields: dict[str, typing.Any] = {
            'workspace_uuid': target_workspace,
            'actor_account_uuid': actor_account_uuid,
            'actor_name': None,
            'actor_role': role,
            'principal_type': principal_type,
            'api_key_uuid': api_key_uuid,
            'auth_type': auth_type,
            'request_id': str(request_id)[:128] if request_id else None,
            'http_method': (method or '')[:12] or None,
            'route': (route or '')[:_MAX_ROUTE_CHARS] or None,
            'action': rule.action,
            'resource_type': rule.resource_type,
            'resource_id': str(resource_id)[:_MAX_RESOURCE_ID_CHARS] if resource_id else None,
            'level': int(level),
            'outcome': resolved_outcome,
            'status_code': int(status_code) if status_code is not None else None,
            'summary': summary,
            'changes': changes_payload(changes or []),
            'detail': json.dumps(redact_payload(dict(detail or {})), ensure_ascii=False, default=str)
            if detail
            else None,
            'client_ip': str(client_ip)[:64] if client_ip else None,
            'user_agent': str(user_agent)[:_MAX_USER_AGENT_CHARS] if user_agent else None,
            'duration_ms': max(int(duration_ms), 0),
            '_dedupe_material': dedupe_material(
                actor_account_uuid=actor_account_uuid,
                action=rule.action,
                route=route,
                resource_id=resource_id,
            ),
        }
        return self._enqueue(record_fields)

    # -- reader -----------------------------------------------------------

    async def count_logs(
        self,
        workspace_uuid: str,
        *,
        since: datetime.datetime | None = None,
        level: int | None = None,
    ) -> int:
        try:
            query = (
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(persistence_operation_log.WorkspaceOperationLog)
                .where(persistence_operation_log.WorkspaceOperationLog.workspace_uuid == workspace_uuid)
            )
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
        integrity: str | None = None,
        search: str | None = None,
    ) -> dict[str, typing.Any]:
        """Return one page of operation records plus a Workspace-wide summary.

        The three verification counters describe the whole filtered history, not
        just the returned page: an operator opening page 2 must still see that
        39 records are tampered. Only ``total`` and ``records`` follow the
        pagination window.

        ``integrity`` optionally narrows the listing to the records that failed
        verification, which lets the panel make its counters actionable instead
        of decorative.

        ``search`` is a case-insensitive substring match over the action,
        resource type, resource id, actor name and summary. It exists so a
        caller can ask a narrow question ("install", a plugin name, an account)
        without pulling the whole history: the exact ``action`` filter compares
        the stored key, so an approximate term like ``install`` would otherwise
        return nothing and force a full dump.
        """

        resolved_limit = max(1, min(int(limit or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))
        resolved_offset = max(int(offset or 0), 0)
        resolved_integrity = (integrity or INTEGRITY_FILTER_ALL).strip().lower()
        if resolved_integrity not in _INTEGRITY_FILTERS:
            resolved_integrity = INTEGRITY_FILTER_ALL

        try:
            model = persistence_operation_log.WorkspaceOperationLog
            filters = [model.workspace_uuid == workspace_uuid]
            if action:
                filters.append(model.action == action)
            if resource_type:
                filters.append(model.resource_type == resource_type)
            if actor_account_uuid:
                filters.append(model.actor_account_uuid == actor_account_uuid)
            if search:
                needle = f'%{str(search).strip()}%'
                filters.append(
                    sqlalchemy.or_(
                        model.action.ilike(needle),
                        model.resource_type.ilike(needle),
                        model.resource_id.ilike(needle),
                        model.actor_name.ilike(needle),
                        model.summary.ilike(needle),
                    )
                )
            if level is not None:
                filters.append(model.level == int(level))
            if since is not None:
                filters.append(model.created_at >= since)
            if until is not None:
                filters.append(model.created_at <= until)

            # Verify the filtered history once per request, keyed by the listing
            # filters so a view (all / mutations only / a resource) can reuse an
            # already computed result while still paging. ``integrity`` is not
            # part of the key: it only narrows *which* records are returned, not
            # what the verification finds, so its views share the result too.
            summary = await self._integrity_summary(model, filters, resolved_integrity)

            # ``total`` follows the active listing filter so the pagination badge
            # and the pager stay consistent with what the operator asked to see.
            visible_filters = list(filters)
            if resolved_integrity == INTEGRITY_FILTER_ISSUES:
                ids = summary['tampered_ids']
                visible_filters.append(model.id.in_(ids) if ids else sqlalchemy.false())
            elif resolved_integrity == INTEGRITY_FILTER_HASH_MISMATCH:
                ids = summary['integrity_failed_ids']
                visible_filters.append(model.id.in_(ids) if ids else sqlalchemy.false())
            elif resolved_integrity == INTEGRITY_FILTER_CHAIN_BROKEN:
                ids = summary['chain_failed_ids']
                visible_filters.append(model.id.in_(ids) if ids else sqlalchemy.false())

            total_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(model).where(*visible_filters)
            )
            total = int(total_result.scalar_one_or_none() or 0)

            rows_result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(model)
                .where(*visible_filters)
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
            integrity_summary = summary['summary']
        except Exception as exc:  # pragma: no cover - defensive
            self.ap.logger.debug(f'Operation log query skipped: {exc}')
            total = 0
            records = []
            integrity_summary = self._empty_integrity_summary()

        return {
            'records': records,
            'total': total,
            'limit': resolved_limit,
            'offset': resolved_offset,
            # Report the two failure modes separately so the panel can tell a
            # content edit (integrity) apart from a dropped link (chain) instead
            # of collapsing both into a single "tampered" signal. The counters
            # cover the whole filtered history, not only this page.
            'tampered_count': integrity_summary['tampered'],
            'integrity_failed_count': integrity_summary['integrity_failed'],
            'chain_failed_count': integrity_summary['chain_failed'],
            'scanned_count': integrity_summary['scanned'],
            'scan_truncated': integrity_summary['truncated'],
            'integrity_filter': resolved_integrity,
        }

    @staticmethod
    def _empty_integrity_summary() -> dict[str, typing.Any]:
        return {
            'tampered': 0,
            'integrity_failed': 0,
            'chain_failed': 0,
            'scanned': 0,
            'truncated': False,
        }

    def _invalidate_integrity_cache(self, workspace_uuid: str) -> None:
        """Drop every cached verification for one Workspace.

        The cache is keyed by ``(Workspace, listing filters)`` so each view has
        its own entry; a deletion invalidates all of them, not just the
        unfiltered one.
        """

        for key in [key for key in self._integrity_cache if key[0] == workspace_uuid]:
            self._integrity_cache.pop(key, None)

    @staticmethod
    def _verified_lists(verified: dict[int, tuple[bool, bool]]) -> tuple[list[int], list[int], list[int]]:
        """Split a verification map into (tampered, hash-failed, chain-failed) ids."""

        tampered = [rid for rid, (integ, chain) in verified.items() if not integ or not chain]
        hash_failed = [rid for rid, (integ, _chain) in verified.items() if not integ]
        chain_failed = [rid for rid, (_integ, chain) in verified.items() if not chain]
        return tampered, hash_failed, chain_failed

    def _cached_integrity_result(self, cached: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Rebuild the summary payload from a cached verification map."""

        verified: dict[int, tuple[bool, bool]] = cached['verified']
        tampered, hash_failed, chain_failed = self._verified_lists(verified)
        summary = {
            'tampered': len(tampered),
            'integrity_failed': len(hash_failed),
            'chain_failed': len(chain_failed),
            'scanned': min(len(verified), MAX_INTEGRITY_SCAN_ROWS),
            'truncated': cached.get('truncated', False),
        }
        return {
            'summary': summary,
            'tampered_ids': tampered,
            'integrity_failed_ids': hash_failed,
            'chain_failed_ids': chain_failed,
        }

    async def _integrity_summary(
        self,
        model: typing.Any,
        filters: list[typing.Any],
        integrity_filter: str = INTEGRITY_FILTER_ALL,
    ) -> dict[str, typing.Any]:
        """Verify the filtered history and classify every failing record.

        A result computed within :data:`INTEGRITY_CACHE_TTL_SECONDS` is served
        from the cache, which is what keeps the panel responsive: opening,
        refreshing and paging all land inside that window and pay nothing. The
        cache key is ``(Workspace, listing filters)`` -- an integrity drill-down
        reuses the very result it is drilling into, and both "everything" and
        "mutations only" are cached independently -- so a cache miss is rare.
        A miss re-verifies the *whole* window from scratch: the scan projects
        only the hash columns and the verifier only computes two booleans, so
        the cost is bounded, and an edit to a row verified on a previous pass is
        still caught.
        """

        workspace_uuid = None
        for condition in filters:
            try:
                workspace_uuid = condition.right.value
            except AttributeError:
                continue
            break
        cache_key = (workspace_uuid, tuple(str(condition) for condition in filters))
        cacheable = workspace_uuid is not None
        now = time.monotonic()

        if cacheable:
            cached = self._integrity_cache.get(cache_key)
            if cached is not None and now - cached['computed_at'] < INTEGRITY_CACHE_TTL_SECONDS:
                return self._cached_integrity_result(cached)

        started = time.monotonic()
        try:
            rows_result = await self.ap.persistence_mgr.execute_async(
                _integrity_scan_select(model, *filters).order_by(model.id.desc()).limit(MAX_INTEGRITY_SCAN_ROWS)
            )
            rows = list(rows_result.all())

            # Baseline for the oldest scanned row: its link points at a row that
            # sits just outside the window. Reads are bounded by
            # ``MAX_INTEGRITY_SCAN_ROWS``, so only a history larger than that
            # window ever needs this extra row.
            previous_row = None
            oldest_id = rows[-1].id if rows else None
            if oldest_id is not None:
                older_result = await self.ap.persistence_mgr.execute_async(
                    _integrity_scan_select(model, model.workspace_uuid == rows[0].workspace_uuid, model.id < oldest_id)
                    .order_by(model.id.desc())
                    .limit(1)
                )
                previous_row = older_result.first()

            # Every pass re-verifies every scanned row. The map is deliberately
            # not merged with the previous cache: a row verified once is exactly
            # what an attacker would edit afterwards.
            new_verified: dict[int, tuple[bool, bool]] = {}
            for index, row in enumerate(rows):
                predecessor = rows[index + 1] if index + 1 < len(rows) else previous_row
                new_verified[row.id] = self._verify_hash_and_chain(row, predecessor)

            tampered_ids, integrity_failed_ids, chain_failed_ids = self._verified_lists(new_verified)
            scanned = len(new_verified)
            truncated = scanned >= MAX_INTEGRITY_SCAN_ROWS
            summary = {
                'tampered': len(tampered_ids),
                'integrity_failed': len(integrity_failed_ids),
                'chain_failed': len(chain_failed_ids),
                'scanned': min(scanned, MAX_INTEGRITY_SCAN_ROWS),
                'truncated': truncated,
            }
            result = {
                'summary': summary,
                'tampered_ids': tampered_ids,
                'integrity_failed_ids': integrity_failed_ids,
                'chain_failed_ids': chain_failed_ids,
            }
            if cacheable:
                self._integrity_cache[cache_key] = {
                    'verified': new_verified,
                    'computed_at': now,
                    'truncated': truncated,
                }
            if summary['tampered'] or truncated:
                logger.warning(
                    'Operation log integrity scan: %s tampered / %s hash / %s chain over %s rows (truncated=%s)',
                    summary['tampered'],
                    summary['integrity_failed'],
                    summary['chain_failed'],
                    summary['scanned'],
                    truncated,
                )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if elapsed_ms >= 250:
                logger.debug(
                    'Operation log integrity scan took %sms over %s rows',
                    elapsed_ms,
                    summary['scanned'],
                )
            return result
        except Exception as exc:  # pragma: no cover - defensive
            # Never take the whole log panel down because verification failed:
            # fall back to zeroed counters and an unfiltered listing.
            logger.debug(f'Operation log integrity summary skipped: {exc}')
            return {
                'summary': self._empty_integrity_summary(),
                'tampered_ids': [],
                'integrity_failed_ids': [],
                'chain_failed_ids': [],
            }

    @staticmethod
    def _verify_hash_and_chain(row: typing.Any, previous_row: typing.Any | None) -> tuple[bool, bool]:
        """Return ``(integrity_ok, chain_ok)`` for one row without serializing it.

        The integrity scan runs over up to :data:`MAX_INTEGRITY_SCAN_ROWS` rows
        and only needs the two booleans, so it must not build the full display
        dict -- which decodes the ``changes`` / ``detail`` payloads and formats
        timestamps -- for every scanned record. The hash payload here is exactly
        :data:`_HASH_FIELDS`, the same single source of truth ``_serialize_log``
        uses, so both paths can never drift apart.
        """

        hash_payload = {field: getattr(row, field) for field in _HASH_FIELDS}
        integrity_ok = verify_record_hash(hash_payload, row.record_hash)
        chain_ok = True
        if previous_row is not None:
            chain_ok = str(row.prev_hash or '') == str(previous_row.record_hash or '')
        return integrity_ok, chain_ok

    def _serialize_log(self, row: typing.Any, *, previous_row: typing.Any | None = None) -> dict[str, typing.Any]:
        """Serialize one row and re-verify its tamper-evidence chain.

        ``previous_row`` is the chronologically older neighbour. When supplied,
        a mismatch between this row's ``prev_hash`` and the older row's
        ``record_hash`` marks the chain as broken.
        """

        rule = ACTION_RULES_BY_ACTION.get(row.action or '')
        integrity_ok, chain_ok = self._verify_hash_and_chain(row, previous_row)

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
                (
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.select(model.action).where(model.workspace_uuid == workspace_uuid).distinct()
                    )
                )
                .scalars()
                .all()
            )
            resources = (
                (
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.select(model.resource_type).where(model.workspace_uuid == workspace_uuid).distinct()
                    )
                )
                .scalars()
                .all()
            )
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
        # Runs from the writer task, which holds no scope of its own.
        async with self._workspace_scope(workspace_uuid):
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
                (
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.select(model.id)
                        .where(model.workspace_uuid == workspace_uuid)
                        .order_by(model.id.asc())
                        .limit(int(count))
                    )
                )
                .scalars()
                .all()
            )
            if not oldest_ids:
                return 0
            await self.ap.persistence_mgr.execute_async(sqlalchemy.delete(model).where(model.id.in_(list(oldest_ids))))
            # Cached verification no longer matches the surviving prefix.
            self._invalidate_integrity_cache(workspace_uuid)
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

        # The maintenance loop runs per Workspace without holding a scope, so
        # retention has to bind one itself; on the settings route the request
        # scope is already active and this is a no-op.
        async with self._workspace_scope(workspace_uuid):
            days = (
                await self.get_retention_days(workspace_uuid)
                if retention_days is None
                else clamp_retention(retention_days)
            )
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

            if expired > 0:
                # Age-based retention removed the oldest rows, so any cached
                # verification -- including its boundary baseline link -- no longer
                # describes the surviving chain.
                self._invalidate_integrity_cache(workspace_uuid)

            total = await self.count_logs(workspace_uuid)
            trimmed = await self._delete_oldest(workspace_uuid, max(total - budget, 0))
            # The budget was just enforced in full, so the deferred counter restarts.
            self._insert_counters[workspace_uuid] = 0
            return {'expired': expired, 'trimmed': trimmed, 'remaining': await self.count_logs(workspace_uuid)}
