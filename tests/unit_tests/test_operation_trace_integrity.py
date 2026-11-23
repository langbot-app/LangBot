"""Unit tests for the operation-trace integrity scan optimizations.

The read path must stay fast while proving a record is untampered. These tests
pin the two invariants that make that safe:

* the integrity scan projects only the hash columns (never the whole row), and
* the lightweight verifier returns exactly what the full serializer would, so
  the two verification paths can never drift apart.
"""

from __future__ import annotations

import types

from langbot.pkg.entity.persistence import operation_log as persistence_operation_log
from langbot.pkg.operation_trace import service as operation_trace_service


def _make_row(**overrides: object) -> types.SimpleNamespace:
    """Build a row exposing every column the verifier and serializer touch."""

    fields: dict[str, object] = {
        'id': 1,
        'workspace_uuid': 'ws-1',
        'actor_account_uuid': 'acc-1',
        'actor_name': 'Ada',
        'actor_role': 'owner',
        'principal_type': 'account',
        'api_key_uuid': None,
        'auth_type': 'user_token',
        'request_id': 'req-1',
        'http_method': 'PUT',
        'route': '/api/v1/settings/governance',
        'action': 'settings_update',
        'resource_type': 'workspace_settings',
        'resource_id': None,
        'level': 1,
        'outcome': 'ok',
        'status_code': 200,
        'summary': 'level: 0 → 1',
        'changes': '[{"field": "level", "before": 0, "after": 1}]',
        'detail': '{}',
        'client_ip': '127.0.0.1',
        'user_agent': 'pytest',
        'duration_ms': 3,
        'prev_hash': None,
        'record_hash': None,
        'created_at': None,
    }
    fields.update(overrides)
    row = types.SimpleNamespace(**fields)
    if row.record_hash is None:
        payload = {field: getattr(row, field) for field in operation_trace_service._HASH_FIELDS}
        row.record_hash = operation_trace_service.compute_record_hash(payload)
    return row


class TestIntegrityScanProjection:
    """The scan must not load payload columns it never inspects."""

    def test_projection_selects_exactly_the_hash_columns(self):
        model = persistence_operation_log.WorkspaceOperationLog
        statement = operation_trace_service._integrity_scan_select(model)
        keys = {column.key for column in statement.selected_columns}

        expected = {'id', 'record_hash', *operation_trace_service._HASH_FIELDS}
        assert keys == expected

    def test_projection_skips_expensive_payload_columns(self):
        model = persistence_operation_log.WorkspaceOperationLog
        statement = operation_trace_service._integrity_scan_select(model)
        keys = {column.key for column in statement.selected_columns}

        # ``detail`` and the client fingerprint are never hashed, so the cold
        # scan must not page them in for up to MAX_INTEGRITY_SCAN_ROWS rows.
        assert 'detail' not in keys
        assert 'user_agent' not in keys
        assert 'duration_ms' not in keys
        # ``changes`` IS part of the hash, so it must remain selected.
        assert 'changes' in keys


class TestLightweightVerifier:
    """The fast verifier and the full serializer must agree byte for byte."""

    def test_verifier_matches_serializer_for_a_valid_row(self):
        service = operation_trace_service.WorkspaceSettingsService.__new__(
            operation_trace_service.WorkspaceSettingsService
        )
        previous = _make_row(id=1)
        row = _make_row(id=2, prev_hash=previous.record_hash)

        fast = service._verify_hash_and_chain(row, previous)
        serialized = service._serialize_log(row, previous_row=previous)

        assert fast == (serialized['integrity_ok'], serialized['chain_ok'])
        assert fast == (True, True)

    def test_verifier_detects_a_content_edit(self):
        service = operation_trace_service.WorkspaceSettingsService.__new__(
            operation_trace_service.WorkspaceSettingsService
        )
        row = _make_row(id=2)
        # Simulate a silent edit after the hash was computed.
        row.summary = 'tampered summary'

        integrity_ok, chain_ok = service._verify_hash_and_chain(row, None)
        assert integrity_ok is False
        assert chain_ok is True

    def test_verifier_detects_a_broken_chain_link(self):
        service = operation_trace_service.WorkspaceSettingsService.__new__(
            operation_trace_service.WorkspaceSettingsService
        )
        previous = _make_row(id=1)
        row = _make_row(id=2, prev_hash='not-the-previous-hash')

        integrity_ok, chain_ok = service._verify_hash_and_chain(row, previous)
        # The row content itself is intact; only the link is wrong.
        assert integrity_ok is True
        assert chain_ok is False

    def test_missing_baseline_leaves_chain_ok(self):
        service = operation_trace_service.WorkspaceSettingsService.__new__(
            operation_trace_service.WorkspaceSettingsService
        )
        row = _make_row(id=1, prev_hash=None)

        integrity_ok, chain_ok = service._verify_hash_and_chain(row, None)
        assert integrity_ok is True
        assert chain_ok is True
