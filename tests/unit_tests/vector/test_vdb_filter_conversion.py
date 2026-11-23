"""Tests for VDB backend filter conversion functions.

Tests cover:
- _build_qdrant_filter: Qdrant models.Filter conversion
- _build_milvus_expr: Milvus boolean expression string conversion
- _build_pg_conditions: PostgreSQL SQLAlchemy conditions conversion
"""

from __future__ import annotations

from importlib import import_module

import pytest
from sqlalchemy import create_engine, select, text


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

        result = qdrant_module._build_qdrant_filter(
            {
                'file_id': 'abc',
                'status': {'$ne': 'deleted'},
                'created_at': {'$gte': 100},
            }
        )

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

        result = milvus_module._build_milvus_expr(
            {
                'file_id': 'abc',
                'chunk_uuid': {'$ne': 'def'},
            }
        )
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

    @pytest.fixture
    def matching_file_ids(self):
        """Execute generated predicates against fixed rows, including the range boundary."""
        pgvector_module = get_pgvector_module()
        engine = create_engine('sqlite://')
        try:
            with engine.begin() as connection:
                connection.execute(text('CREATE TABLE langbot_vectors (file_id TEXT, chunk_uuid TEXT, text TEXT)'))
                connection.execute(
                    text('INSERT INTO langbot_vectors VALUES (:file_id, :chunk_uuid, :text)'),
                    [
                        {'file_id': 'abc', 'chunk_uuid': 'uuid_099', 'text': 'keep'},
                        {'file_id': 'deleted', 'chunk_uuid': 'uuid_100', 'text': ''},
                        {'file_id': 'def', 'chunk_uuid': 'uuid_101', 'text': 'keep'},
                        {'file_id': 'outside', 'chunk_uuid': 'uuid_102', 'text': 'keep'},
                    ],
                )

                def matching(filter_dict):
                    entry = pgvector_module.PgVectorEntry
                    statement = (
                        select(entry.file_id)
                        .where(*pgvector_module._build_pg_conditions(filter_dict))
                        .order_by(entry.chunk_uuid)
                    )
                    return connection.execute(statement).scalars().all()

                yield matching
        finally:
            engine.dispose()

    def test_empty_filter_returns_empty_list(self):
        """Empty filter dict returns empty list."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({})
        assert result == []

    def test_eq_operator_creates_equality_condition(self, matching_file_ids):
        """$eq operator creates SQLAlchemy == condition."""
        assert matching_file_ids({'file_id': 'abc'}) == ['abc']

    def test_ne_operator_creates_inequality_condition(self, matching_file_ids):
        """$ne operator creates SQLAlchemy != condition."""
        assert matching_file_ids({'file_id': {'$ne': 'deleted'}}) == ['abc', 'def', 'outside']

    def test_comparison_operators(self, matching_file_ids):
        """$gt, $gte, $lt, $lte create comparison conditions."""
        for op, expected_ids in [
            ('$gt', ['def', 'outside']),
            ('$gte', ['deleted', 'def', 'outside']),
            ('$lt', ['abc']),
            ('$lte', ['abc', 'deleted']),
        ]:
            assert matching_file_ids({'chunk_uuid': {op: 'uuid_100'}}) == expected_ids

    def test_in_operator_creates_in_condition(self, matching_file_ids):
        """$in operator creates SQLAlchemy in_ condition."""
        assert matching_file_ids({'file_id': {'$in': ['abc', 'deleted']}}) == ['abc', 'deleted']

    def test_nin_operator_creates_notin_condition(self, matching_file_ids):
        """$nin operator creates SQLAlchemy notin_ condition."""
        assert matching_file_ids({'file_id': {'$nin': ['abc', 'deleted']}}) == ['def', 'outside']

    def test_multiple_conditions_list(self, matching_file_ids):
        """Multiple conditions return list of conditions."""
        assert matching_file_ids(
            {
                'file_id': {'$in': ['abc', 'deleted']},
                'chunk_uuid': {'$ne': 'uuid_100'},
            }
        ) == ['abc']

    def test_unsupported_field_dropped(self):
        """Unsupported fields are dropped (not in _PG_SUPPORTED_FIELDS)."""
        pgvector_module = get_pgvector_module()

        result = pgvector_module._build_pg_conditions({'unknown_field': 'value'})
        assert result == []

    def test_uuid_alias_resolved(self, matching_file_ids):
        """'uuid' alias is resolved to 'chunk_uuid'."""
        assert matching_file_ids({'uuid': 'uuid_100'}) == ['deleted']

    def test_supported_fields_only(self, matching_file_ids):
        """Only supported fields (text, file_id, chunk_uuid) are kept."""
        assert matching_file_ids(
            {
                'text': {'$ne': ''},
                'file_id': {'$in': ['abc', 'deleted', 'outside']},
                'chunk_uuid': {'$in': ['uuid_099', 'uuid_100', 'uuid_101']},
                'unsupported': 'value',
            }
        ) == ['abc']
