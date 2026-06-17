"""Unit tests for the monitoring trace Alembic migration."""

from __future__ import annotations

from importlib import import_module


class _FakeInspector:
    def __init__(self, tables):
        self._tables = tables

    def get_table_names(self):
        return list(self._tables)


class _FakeOp:
    def __init__(self):
        self.created_tables = []
        self.created_indexes = []
        self.dropped_tables = []

    def get_bind(self):
        return object()

    def create_table(self, table_name, *columns):
        self.created_tables.append((table_name, columns))

    def create_index(self, index_name, table_name, columns):
        self.created_indexes.append((index_name, table_name, columns))

    def drop_table(self, table_name):
        self.dropped_tables.append(table_name)


def _migration_module():
    return import_module('langbot.pkg.persistence.alembic.versions.0006_monitoring_traces')


def test_upgrade_creates_monitoring_trace_tables_and_indexes(monkeypatch):
    migration = _migration_module()
    fake_op = _FakeOp()

    monkeypatch.setattr(migration, 'op', fake_op)
    monkeypatch.setattr(migration.sa, 'inspect', lambda _conn: _FakeInspector(tables=set()))

    migration.upgrade()

    assert [table_name for table_name, _columns in fake_op.created_tables] == [
        'monitoring_traces',
        'monitoring_spans',
    ]
    assert ('ix_monitoring_traces_started_at', 'monitoring_traces', ['started_at']) in fake_op.created_indexes
    assert ('ix_monitoring_spans_trace_id', 'monitoring_spans', ['trace_id']) in fake_op.created_indexes
    assert ('ix_monitoring_spans_pipeline_id', 'monitoring_spans', ['pipeline_id']) in fake_op.created_indexes


def test_upgrade_skips_existing_monitoring_trace_tables(monkeypatch):
    migration = _migration_module()
    fake_op = _FakeOp()

    monkeypatch.setattr(migration, 'op', fake_op)
    monkeypatch.setattr(
        migration.sa,
        'inspect',
        lambda _conn: _FakeInspector(tables={'monitoring_traces', 'monitoring_spans'}),
    )

    migration.upgrade()

    assert fake_op.created_tables == []
    assert fake_op.created_indexes == []


def test_downgrade_drops_spans_before_traces(monkeypatch):
    migration = _migration_module()
    fake_op = _FakeOp()

    monkeypatch.setattr(migration, 'op', fake_op)
    monkeypatch.setattr(
        migration.sa,
        'inspect',
        lambda _conn: _FakeInspector(tables={'monitoring_traces', 'monitoring_spans'}),
    )

    migration.downgrade()

    assert fake_op.dropped_tables == ['monitoring_spans', 'monitoring_traces']
