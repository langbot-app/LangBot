"""Tests for VDB backend filter conversion functions.

Tests cover:
- _build_qdrant_filter: Qdrant models.Filter conversion
- _build_milvus_expr: Milvus boolean expression string conversion
- _build_pg_conditions: PostgreSQL SQLAlchemy conditions conversion
"""
from __future__ import annotations

from importlib import import_module


def get_qdrant_module():
    """Lazy import qdrant module."""
    return import_module('langbot.pkg.vector.vdbs.qdrant')


def get_milvus_module():
    """Lazy import milvus module."""
    return import_module('langbot.pkg.vector.vdbs.milvus')


def get_pgvector_module():
    """Lazy import pgvector module."""
    return import_module('langbot.pkg.vector.vdbs.pgvector_db')


class TestQdrantFilterConversion:
    """Tests for _build_qdrant_filter function."""

    def test_empty_filter_returns_empty_must(self):
        """Empty filter dict returns Filter with None must/must_not."""
        qdrant_module = get_qdrant_module()

        result = qdrant_module._build_qdrant_filter({})
        assert result.must is None
        assert result.must_not is None

    def test_eq_operator_creates_must_condition(self):
        """$eq operator creates FieldCondition in must list."""
        qdrant_module = get_qdrant_module()
        from qdrant_client import models

        result = qdrant_module._build_qdrant_filter({'file_id': 'abc'})

        assert result.must is not None
        assert len(result.must) == 1
        condition = result.must[0]
        assert condition.key == 'file_id'
        assert isinstance(condition.match, models.MatchValue)
        assert condition.match.value == 'abc'

    def test_ne_operator_creates_must_not_condition(self):
        """$ne operator creates FieldCondition in must_not list."""
        qdrant_module = get_qdrant_module()
        from qdrant_client import models

        result = qdrant_module._build_qdrant_filter({'status': {'$ne': 'deleted'}})

        assert result.must_not is not None
        assert len(result.must_not) == 1
        condition = result.must_not[0]
        assert condition.key == 'status'
        assert isinstance(condition.match, models.MatchValue)
        assert condition.match.value == 'deleted'

    def test_in_operator_creates_match_any(self):
        """$in operator creates MatchAny condition."""
        qdrant_module = get_qdrant_module()
        from qdrant_client import models

        result = qdrant_module._build_qdrant_filter({'file_type': {'$in': ['pdf', 'docx']}})

        assert result.must is not None
        assert len(result.must) == 1
        condition = result.must[0]
        assert condition.key == 'file_type'
        assert isinstance(condition.match, models.MatchAny)
        assert condition.match.any == ['pdf', 'docx']

    def test_nin_operator_creates_must_not_match_any(self):
        """$nin operator creates MatchAny in must_not."""
        qdrant_module = get_qdrant_module()
        from qdrant_client import models

        result = qdrant_module._build_qdrant_filter({'status': {'$nin': ['deleted', 'archived']}})

        assert result.must_not is not None
        assert len(result.must_not) == 1
        condition = result.must_not[0]
        assert condition.key == 'status'
        assert isinstance(condition.match, models.MatchAny)
        assert condition.match.any == ['deleted', 'archived']

    def test_range_operators_create_range_condition(self):
        """$gt, $gte, $lt, $lte create Range conditions."""
        qdrant_module = get_qdrant_module()
        from qdrant_client import models

        # Test $gt
        result = qdrant_module._build_qdrant_filter({'created_at': {'$gt': 100}})
        condition = result.must[0]
        assert isinstance(condition.range, models.Range)
        assert condition.range.gt == 100

        # Test $gte
        result = qdrant_module._build_qdrant_filter({'created_at': {'$gte': 100}})
        condition = result.must[0]
        assert condition.range.gte == 100

        # Test $lt
        result = qdrant_module._build_qdrant_filter({'created_at': {'$lt': 100}})
        condition = result.must[0]
        assert condition.range.lt == 100

        # Test $lte
        result = qdrant_module._build_qdrant_filter({'created_at': {'$lte': 100}})
        condition = result.must[0]
        assert condition.range.lte == 100

    def test_multiple_conditions_combined(self):
        """Multiple conditions are combined in must/must_not."""
        qdrant_module = get_qdrant_module()

        result = qdrant_module._build_qdrant_filter({
            'file_id': 'abc',
            'status': {'$ne': 'deleted'},
            'created_at': {'$gte': 100},
        })

        assert len(result.must) == 2  # file_id eq + created_at gte
        assert len(result.must_not) == 1  # status ne

    def test_implicit_eq_handled(self):
        """Implicit $eq (bare value) is correctly handled."""
        qdrant_module = get_qdrant_module()
        from qdrant_client import models

        result = qdrant_module._build_qdrant_filter({'field': 'value'})

        assert result.must is not None
        condition = result.must[0]
        assert isinstance(condition.match, models.MatchValue)


class TestMilvusFilterConversion:
    """Tests for _build_milvus_expr function.

    NOTE: Milvus only supports fields: 'text', 'file_id', 'chunk_uuid'
    Tests use only these supported fields.
    """

    def test_empty_filter_returns_empty_string(self):
        """Empty filter dict returns empty string."""
        milvus_module = get_milvus_module()

        result = milvus_module._build_milvus_expr({})
        assert result == ''

    def test_eq_operator_expression(self):
        """$eq operator creates == expression."""
        milvus_module = get_milvus_module()

        result = milvus_module._build_milvus_expr({'file_id': 'abc'})
        assert result == 'file_id == "abc"'

    def test_ne_operator_expression(self):
        """$ne operator creates != expression."""
        milvus_module = get_milvus_module()

        result = milvus_module._build_milvus_expr({'file_id': {'$ne': 'deleted'}})
        assert result == 'file_id != "deleted"'

    def test_comparison_operators(self):
        """$gt, $gte, $lt, $lte create comparison expressions."""
        milvus_module = get_milvus_module()

        assert milvus_module._build_milvus_expr({'chunk_uuid': {'$gt': 'uuid_100'}}) == 'chunk_uuid > "uuid_100"'
        assert milvus_module._build_milvus_expr({'chunk_uuid': {'$gte': 'uuid_100'}}) == 'chunk_uuid >= "uuid_100"'
        assert milvus_module._build_milvus_expr({'chunk_uuid': {'$lt': 'uuid_100'}}) == 'chunk_uuid < "uuid_100"'
        assert milvus_module._build_milvus_expr({'chunk_uuid': {'$lte': 'uuid_100'}}) == 'chunk_uuid <= "uuid_100"'

    def test_in_operator_expression(self):
        """$in operator creates in [...] expression."""
        milvus_module = get_milvus_module()

        result = milvus_module._build_milvus_expr({'file_id': {'$in': ['pdf', 'docx']}})
        assert result == 'file_id in ["pdf", "docx"]'

    def test_nin_operator_expression(self):
        """$nin operator creates not in [...] expression."""
        milvus_module = get_milvus_module()

        result = milvus_module._build_milvus_expr({'file_id': {'$nin': ['deleted', 'archived']}})
        assert result == 'file_id not in ["deleted", "archived"]'

    def test_multiple_conditions_joined_with_and(self):
        """Multiple conditions are joined with 'and'."""
        milvus_module = get_milvus_module()

        result = milvus_module._build_milvus_expr({
            'file_id': 'abc',
            'chunk_uuid': {'$ne': 'def'},
        })
        assert 'and' in result
        assert 'file_id == "abc"' in result
        assert 'chunk_uuid != "def"' in result

    def test_string_value_escaped(self):
        """String values are properly escaped."""
        milvus_module = get_milvus_module()

        # Test backslash escape
        result = milvus_module._build_milvus_expr({'file_id': 'C:\\Users\\test'})
        assert '\\\\' in result

        # Test quote escape
        result = milvus_module._build_milvus_expr({'file_id': 'test "quoted"'})
        assert '\\"' in result

    def test_text_field_supported(self):
        """text field is supported."""
        milvus_module = get_milvus_module()

        result = milvus_module._build_milvus_expr({'text': 'some text'})
        assert result == 'text == "some text"'

    def test_milvus_literal_function(self):
        """Test _milvus_literal helper."""
        milvus_module = get_milvus_module()

        assert milvus_module._milvus_literal('string') == '"string"'
        assert milvus_module._milvus_literal(42) == '42'
        assert milvus_module._milvus_literal(3.14) == '3.14'

    def test_unsupported_field_dropped(self):
        """Unsupported fields are dropped (not in _MILVUS_SUPPORTED_FIELDS)."""
        milvus_module = get_milvus_module()

        result = milvus_module._build_milvus_expr({'unknown_field': 'value'})
        assert result == ''

    def test_uuid_alias_resolved(self):
        """'uuid' alias is resolved to 'chunk_uuid'."""
        milvus_module = get_milvus_module()

        result = milvus_module._build_milvus_expr({'uuid': 'abc'})
        assert result.startswith('chunk_uuid')
        # uuid substring appears in chunk_uuid which is expected


class TestPgVectorFilterConversion:
    """Tests for _build_pg_conditions function.

    NOTE: PGVector only supports fields: 'text', 'file_id', 'chunk_uuid'
    Tests use only these supported fields.
    """

    def test_empty_filter_returns_empty_list(self):
        """Empty filter dict returns empty list."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({})
        assert result == []

    def test_eq_operator_creates_equality_condition(self):
        """$eq operator creates SQLAlchemy == condition."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({'file_id': 'abc'})

        assert len(result) == 1
        # Verify it's a SQLAlchemy BinaryExpression
        from sqlalchemy.sql.expression import BinaryExpression
        assert isinstance(result[0], BinaryExpression)

    def test_ne_operator_creates_inequality_condition(self):
        """$ne operator creates SQLAlchemy != condition."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({'file_id': {'$ne': 'deleted'}})

        assert len(result) == 1
        # Operator should be ne (not equals)
        assert '!=' in str(result[0]) or 'ne' in str(result[0].operator)

    def test_comparison_operators(self):
        """$gt, $gte, $lt, $lte create comparison conditions."""
        pgvector_module = get_pgvector_module()

        # Test all comparison operators with supported field
        for op, expected_op in [
            ('$gt', '>'),
            ('$gte', '>='),
            ('$lt', '<'),
            ('$lte', '<='),
        ]:
            result = pgvector_module._build_pg_conditions({'chunk_uuid': {op: 'uuid_100'}})
            assert len(result) == 1
            assert expected_op in str(result[0])

    def test_in_operator_creates_in_condition(self):
        """$in operator creates SQLAlchemy in_ condition."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({'file_id': {'$in': ['a', 'b', 'c']}})

        assert len(result) == 1
        assert 'IN' in str(result[0]).upper()

    def test_nin_operator_creates_notin_condition(self):
        """$nin operator creates SQLAlchemy notin_ condition."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({'file_id': {'$nin': ['a', 'b']}})

        assert len(result) == 1
        assert 'NOT IN' in str(result[0]).upper()

    def test_multiple_conditions_list(self):
        """Multiple conditions return list of conditions."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({
            'file_id': 'abc',
            'chunk_uuid': {'$ne': 'def'},
        })

        assert len(result) == 2

    def test_unsupported_field_dropped(self):
        """Unsupported fields are dropped (not in _PG_SUPPORTED_FIELDS)."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({'unknown_field': 'value'})
        assert result == []

    def test_uuid_alias_resolved(self):
        """'uuid' alias is resolved to 'chunk_uuid'."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({'uuid': 'abc'})

        assert len(result) == 1
        # Should reference chunk_uuid column
        assert 'chunk_uuid' in str(result[0])

    def test_supported_fields_only(self):
        """Only supported fields (text, file_id, chunk_uuid) are kept."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({
            'text': {'$ne': ''},
            'file_id': 'abc',
            'chunk_uuid': {'$in': ['x', 'y']},
            'unsupported': 'value',
        })

        assert len(result) == 3  # Only supported fields