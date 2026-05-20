"""Tests for vector filter utilities."""

from __future__ import annotations

import pytest

from langbot.pkg.vector.filter_utils import (
    SUPPORTED_OPS,
    normalize_filter,
    strip_unsupported_fields,
)


class TestNormalizeFilter:
    """Tests for normalize_filter function."""

    def test_normalize_filter_empty_dict(self):
        """Empty dict returns empty list."""
        result = normalize_filter({})
        assert result == []

    def test_normalize_filter_none(self):
        """None returns empty list."""
        result = normalize_filter(None)
        assert result == []

    def test_normalize_filter_implicit_eq(self):
        """Bare value becomes implicit $eq."""
        result = normalize_filter({'file_id': 'abc123'})

        assert len(result) == 1
        assert result[0] == ('file_id', '$eq', 'abc123')

    def test_normalize_filter_explicit_eq(self):
        """Explicit $eq operator."""
        result = normalize_filter({'file_id': {'$eq': 'abc123'}})

        assert len(result) == 1
        assert result[0] == ('file_id', '$eq', 'abc123')

    def test_normalize_filter_comparison_operators(self):
        """Test comparison operators: $gt, $gte, $lt, $lte."""
        result = normalize_filter({'created_at': {'$gte': 1700000000}})

        assert len(result) == 1
        assert result[0] == ('created_at', '$gte', 1700000000)

    def test_normalize_filter_ne_operator(self):
        """Test $ne operator."""
        result = normalize_filter({'status': {'$ne': 'deleted'}})

        assert len(result) == 1
        assert result[0] == ('status', '$ne', 'deleted')

    def test_normalize_filter_in_operator(self):
        """Test $in operator with list value."""
        result = normalize_filter({'file_type': {'$in': ['pdf', 'docx', 'txt']}})

        assert len(result) == 1
        assert result[0] == ('file_type', '$in', ['pdf', 'docx', 'txt'])

    def test_normalize_filter_nin_operator(self):
        """Test $nin operator."""
        result = normalize_filter({'status': {'$nin': ['deleted', 'archived']}})

        assert len(result) == 1
        assert result[0] == ('status', '$nin', ['deleted', 'archived'])

    def test_normalize_filter_multiple_conditions(self):
        """Multiple top-level keys are AND-ed (returned as multiple triples)."""
        result = normalize_filter({
            'file_id': 'abc',
            'status': {'$ne': 'deleted'},
            'created_at': {'$gte': 1700000000}
        })

        assert len(result) == 3
        # Order should match dict iteration order
        field_ops = [(field, op) for field, op, _ in result]
        assert ('file_id', '$eq') in field_ops
        assert ('status', '$ne') in field_ops
        assert ('created_at', '$gte') in field_ops

    def test_normalize_filter_unsupported_operator_raises(self):
        """Unsupported operator raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported filter operator'):
            normalize_filter({'field': {'$regex': 'pattern'}})

    def test_normalize_filter_all_supported_ops(self):
        """Test all supported operators are recognized."""
        for op in SUPPORTED_OPS:
            if op in ('$in', '$nin'):
                filter_dict = {'field': {op: ['value1', 'value2']}}
            else:
                filter_dict = {'field': {op: 'value'}}

            result = normalize_filter(filter_dict)
            assert len(result) == 1
            assert result[0][1] == op


class TestStripUnsupportedFields:
    """Tests for strip_unsupported_fields function."""

    def test_strip_keeps_supported_fields(self):
        """Fields in supported_fields are kept."""
        triples = [
            ('file_id', '$eq', 'abc'),
            ('chunk_uuid', '$ne', 'def'),
        ]

        result = strip_unsupported_fields(triples, {'file_id', 'chunk_uuid'})

        assert len(result) == 2
        assert result == triples

    def test_strip_removes_unsupported_fields(self):
        """Fields not in supported_fields are removed."""
        triples = [
            ('file_id', '$eq', 'abc'),
            ('unknown_field', '$ne', 'def'),
        ]

        result = strip_unsupported_fields(triples, {'file_id'})

        assert len(result) == 1
        assert result[0] == ('file_id', '$eq', 'abc')

    def test_strip_empty_triples(self):
        """Empty triples list returns empty list."""
        result = strip_unsupported_fields([], {'file_id'})
        assert result == []

    def test_strip_all_unsupported(self):
        """All fields unsupported returns empty list."""
        triples = [
            ('unknown1', '$eq', 'a'),
            ('unknown2', '$eq', 'b'),
        ]

        result = strip_unsupported_fields(triples, {'file_id'})

        assert result == []

    def test_strip_with_field_aliases(self):
        """Field aliases are resolved before checking support."""
        triples = [
            ('uuid', '$eq', 'abc'),  # alias for chunk_uuid
            ('file_id', '$eq', 'def'),
        ]

        result = strip_unsupported_fields(
            triples,
            {'file_id', 'chunk_uuid'},
            field_aliases={'uuid': 'chunk_uuid'}
        )

        assert len(result) == 2
        # 'uuid' should be resolved to 'chunk_uuid'
        assert result[0] == ('chunk_uuid', '$eq', 'abc')
        assert result[1] == ('file_id', '$eq', 'def')

    def test_strip_alias_not_in_supported(self):
        """Alias resolved but still not in supported_fields is dropped."""
        triples = [
            ('uuid', '$eq', 'abc'),  # alias for chunk_uuid, but not supported
        ]

        result = strip_unsupported_fields(
            triples,
            {'file_id'},  # chunk_uuid not supported
            field_aliases={'uuid': 'chunk_uuid'}
        )

        assert result == []

    def test_strip_preserves_operator_and_value(self):
        """Strip only affects field name, not operator or value."""
        triples = [
            ('file_id', '$in', ['a', 'b', 'c']),
        ]

        result = strip_unsupported_fields(triples, {'file_id'})

        assert result[0] == ('file_id', '$in', ['a', 'b', 'c'])

    def test_strip_none_aliases(self):
        """None field_aliases is treated as empty dict."""
        triples = [
            ('file_id', '$eq', 'abc'),
        ]

        result = strip_unsupported_fields(triples, {'file_id'}, field_aliases=None)

        assert len(result) == 1
        assert result[0] == ('file_id', '$eq', 'abc')


class TestSupportedOpsConstant:
    """Tests for SUPPORTED_OPS constant."""

    def test_supported_ops_contains_expected(self):
        """SUPPORTED_OPS contains all expected operators."""
        expected = {'$eq', '$ne', '$gt', '$gte', '$lt', '$lte', '$in', '$nin'}
        assert SUPPORTED_OPS == expected

    def test_supported_ops_is_frozenset(self):
        """SUPPORTED_OPS is a frozenset for immutability."""
        from collections.abc import Set
        assert isinstance(SUPPORTED_OPS, Set)