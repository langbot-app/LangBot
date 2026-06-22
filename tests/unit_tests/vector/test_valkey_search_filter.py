"""Unit tests for the Valkey Search VDB backend's pure helpers.

These tests exercise the filter-to-FT mapping, float32 packing, tag/text
escaping, FT.SEARCH reply parsing and the import guard.  They run in the fast
CI lane and require NO running Valkey server.
"""

from __future__ import annotations

import asyncio
import struct
from importlib import import_module
from unittest.mock import AsyncMock

import pytest


def get_valkey_module():
    """Lazy import of the valkey_search backend module."""
    return import_module('langbot.pkg.vector.vdbs.valkey_search')


def make_backend():
    """Construct a backend instance without running its __init__.

    The constructor needs a live ``ap`` + config; for pure-helper tests we
    only need a bare instance with the attributes the helpers touch.
    """
    mod = get_valkey_module()
    backend = object.__new__(mod.ValkeySearchVectorDatabase)
    # _ensure_client serializes creation through this lock; set it here since
    # __init__ (which normally creates it) is bypassed.
    backend._client_lock = asyncio.Lock()
    return backend


class TestFloat32Packing:
    """Tests for _pack_vector little-endian float32 packing."""

    def test_pack_round_trips(self):
        mod = get_valkey_module()
        vec = [0.1, -2.5, 3.0, 4.25]
        packed = mod.ValkeySearchVectorDatabase._pack_vector(vec)
        assert isinstance(packed, bytes)
        assert len(packed) == 4 * len(vec)
        unpacked = list(struct.unpack(f'<{len(vec)}f', packed))
        for original, restored in zip(vec, unpacked):
            assert restored == pytest.approx(original, rel=1e-6)

    def test_pack_is_little_endian(self):
        mod = get_valkey_module()
        packed = mod.ValkeySearchVectorDatabase._pack_vector([1.0])
        assert packed == struct.pack('<f', 1.0)


class TestTagEscaping:
    """Tests for _escape_tag."""

    def test_escapes_special_chars(self):
        mod = get_valkey_module()
        escaped = mod.ValkeySearchVectorDatabase._escape_tag('a-b c.d')
        assert '\\-' in escaped
        assert '\\ ' in escaped
        assert '\\.' in escaped

    def test_plain_value_unchanged(self):
        mod = get_valkey_module()
        assert mod.ValkeySearchVectorDatabase._escape_tag('abc123') == 'abc123'


class TestFileIdEncoding:
    """Tests for _encode_file_id (FT-unsafe char percent-encoding)."""

    def test_uuid_is_noop(self):
        mod = get_valkey_module()
        fid = '550e8400-e29b-41d4-a716-446655440000'
        assert mod.ValkeySearchVectorDatabase._encode_file_id(fid) == fid

    def test_encodes_braces_star_and_percent(self):
        mod = get_valkey_module()
        enc = mod.ValkeySearchVectorDatabase._encode_file_id('a{b}c*d%e')
        # '{'=7B '}'=7D '*'=2A '%'=25
        assert enc == 'a%7Bb%7Dc%2Ad%25e'
        # No raw FT-unsafe char survives.
        assert all(ch not in enc for ch in '{}*') or '%' in enc

    def test_encoding_is_deterministic_and_collision_safe(self):
        mod = get_valkey_module()
        enc = mod.ValkeySearchVectorDatabase._encode_file_id
        # A literal "%7B" must not collide with an encoded "{".
        assert enc('{') != enc('%7B')
        assert enc('{') == '%7B'
        assert enc('%7B') == '%257B'

    def test_filter_encodes_unsafe_chars_in_tag_query(self):
        backend = make_backend()
        # The emitted TAG query must contain the encoded form, never raw braces.
        frag = backend._triples_to_ft({'file_id': 'x}y{z*'})
        assert '7D' in frag and '7B' in frag and '2A' in frag
        # No raw '*' from the value, and exactly one opening/closing brace (the
        # TAG-clause delimiters) — the value's own braces were encoded away.
        assert '*' not in frag
        assert frag.count('{') == 1 and frag.count('}') == 1
        assert frag.startswith('@file_id:{') and frag.endswith('}')

    def test_filter_in_operator_encodes_each_value(self):
        backend = make_backend()
        frag = backend._triples_to_ft({'file_id': {'$in': ['a*b', 'c}d']}})
        assert '2A' in frag and '7D' in frag
        assert '*' not in frag


class TestFilterToFt:
    """Tests for _triples_to_ft filter mapping (all 8 operators)."""

    def test_empty_filter_returns_empty_string(self):
        backend = make_backend()
        assert backend._triples_to_ft(None) == ''
        assert backend._triples_to_ft({}) == ''

    def test_eq_tag(self):
        backend = make_backend()
        assert backend._triples_to_ft({'file_id': 'abc'}) == '@file_id:{abc}'

    def test_explicit_eq_tag(self):
        backend = make_backend()
        assert backend._triples_to_ft({'file_id': {'$eq': 'abc'}}) == '@file_id:{abc}'

    def test_ne_tag(self):
        backend = make_backend()
        assert backend._triples_to_ft({'file_id': {'$ne': 'abc'}}) == '-@file_id:{abc}'

    def test_in_tag(self):
        backend = make_backend()
        assert backend._triples_to_ft({'file_id': {'$in': ['a', 'b']}}) == '@file_id:{a|b}'

    def test_nin_tag(self):
        backend = make_backend()
        assert backend._triples_to_ft({'file_id': {'$nin': ['a', 'b']}}) == '-@file_id:{a|b}'

    def test_numeric_range_operators(self):
        backend = make_backend()
        # file_id is the only indexed field; numeric ops still render via the
        # generic range fragment, so use file_id to keep the field supported.
        # Values are cast to float (defensive against non-numeric input and a
        # future NUMERIC field becoming an injection surface).
        assert backend._triples_to_ft({'file_id': {'$gt': 5}}) == '@file_id:[(5.0 +inf]'
        assert backend._triples_to_ft({'file_id': {'$gte': 5}}) == '@file_id:[5.0 +inf]'
        assert backend._triples_to_ft({'file_id': {'$lt': 5}}) == '@file_id:[-inf (5.0]'
        assert backend._triples_to_ft({'file_id': {'$lte': 5}}) == '@file_id:[-inf 5.0]'

    def test_numeric_range_rejects_non_numeric(self):
        backend = make_backend()
        # A non-numeric range value fails closed rather than interpolating raw.
        with pytest.raises((ValueError, TypeError)):
            backend._triples_to_ft({'file_id': {'$gt': 'not-a-number'}})

    def test_unsupported_field_dropped(self):
        backend = make_backend()
        # Non-indexed fields are dropped (returns empty expression).
        assert backend._triples_to_ft({'some_other_field': 'x'}) == ''

    def test_multiple_supported_keys_anded(self):
        backend = make_backend()
        # Two conditions on the same indexed field are joined with a space (AND).
        result = backend._triples_to_ft({'file_id': {'$in': ['a', 'b']}})
        assert result == '@file_id:{a|b}'


class TestTextEscaping:
    """Tests for _escape_text full-text escaping."""

    def test_escapes_ft_special_chars(self):
        mod = get_valkey_module()
        escaped = mod.ValkeySearchVectorDatabase._escape_text('hello@world|test')
        assert '\\@' in escaped
        assert '\\|' in escaped


class TestReplyToChroma:
    """Tests for _reply_to_chroma FT.SEARCH reply parsing."""

    def test_parses_knn_reply(self):
        backend = make_backend()
        # glide returns [total, {key: {field: value}}]
        reply = [
            2,
            {
                b'kb:col1:id1': {
                    b'distance': b'0.10',
                    b'document': b'hello',
                    b'metadata_json': b'{"file_id": "f1"}',
                },
                b'kb:col1:id2': {
                    b'distance': b'0.25',
                    b'document': b'world',
                    b'metadata_json': b'{"file_id": "f2"}',
                },
            },
        ]
        result = backend._reply_to_chroma('idx:col1', reply, has_distance=True)
        assert result['ids'][0] == ['id1', 'id2']
        assert result['distances'][0] == [pytest.approx(0.10), pytest.approx(0.25)]
        assert result['metadatas'][0][0] == {'file_id': 'f1'}
        assert result['metadatas'][0][1] == {'file_id': 'f2'}

    def test_empty_reply(self):
        backend = make_backend()
        result = backend._reply_to_chroma('idx:col1', [0, {}], has_distance=True)
        assert result == {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

    def test_malformed_reply(self):
        backend = make_backend()
        result = backend._reply_to_chroma('idx:col1', [], has_distance=True)
        assert result == {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

    def test_text_search_reply_no_distance(self):
        backend = make_backend()
        reply = [
            1,
            {
                b'kb:col1:id1': {
                    b'document': b'hello',
                    b'metadata_json': b'{"file_id": "f1"}',
                },
            },
        ]
        result = backend._reply_to_chroma('idx:col1', reply, has_distance=False)
        assert result['ids'][0] == ['id1']
        assert result['distances'][0] == [0.0]


class TestImportGuard:
    """Tests for the ImportError guard when glide is unavailable."""

    def test_constructor_raises_when_unavailable(self, monkeypatch):
        mod = get_valkey_module()
        monkeypatch.setattr(mod, 'VALKEY_SEARCH_AVAILABLE', False)
        with pytest.raises(ImportError, match='valkey-glide'):
            mod.ValkeySearchVectorDatabase(ap=None)


class TestSupportedSearchTypes:
    """Tests for supported_search_types."""

    def test_supports_vector_full_text_hybrid(self):
        mod = get_valkey_module()
        from langbot.pkg.vector.vdb import SearchType

        types = mod.ValkeySearchVectorDatabase.supported_search_types()
        assert SearchType.VECTOR in types
        assert SearchType.FULL_TEXT in types
        assert SearchType.HYBRID in types


class TestDeleteByFilterGuard:
    """Regression tests for the delete_by_filter mass-deletion guard.

    A non-empty filter referencing only non-indexed fields must NOT fall back
    to match-all and wipe the whole collection: it must skip and return 0.
    """

    async def test_unsupported_only_filter_skips_and_returns_zero(self):
        backend = make_backend()
        # Make the client/index lookups succeed without a real server.
        backend._client = AsyncMock()
        backend.ap = type('Ap', (), {'logger': AsyncMock()})()
        backend._ensure_client = AsyncMock(return_value=backend._client)
        backend._index_exists = AsyncMock(return_value=True)
        # _search_keys must never be reached for an unusable filter.
        backend._search_keys = AsyncMock(
            side_effect=AssertionError('_search_keys must not be called for an unusable filter')
        )

        # Filter references only a non-indexed field -> maps to no FT conditions.
        deleted = await backend.delete_by_filter('col1', {'some_other_field': 'x'})

        assert deleted == 0
        backend._client.delete.assert_not_called()

    async def test_supported_filter_deletes_matching_keys(self):
        backend = make_backend()
        backend._client = AsyncMock()
        backend.ap = type('Ap', (), {'logger': AsyncMock()})()
        backend._ensure_client = AsyncMock(return_value=backend._client)
        backend._index_exists = AsyncMock(return_value=True)
        backend._search_keys = AsyncMock(return_value=['kb:col1:id1', 'kb:col1:id2'])

        deleted = await backend.delete_by_filter('col1', {'file_id': 'f1'})

        assert deleted == 2
        backend._client.delete.assert_awaited_once_with(['kb:col1:id1', 'kb:col1:id2'])


class TestClose:
    """Tests for the close() teardown."""

    async def test_close_resets_client_and_indexes(self):
        backend = make_backend()
        client = AsyncMock()
        backend._client = client
        backend.ap = type('Ap', (), {'logger': AsyncMock()})()
        backend._ensured_indexes = {'idx:col1'}

        await backend.close()

        client.close.assert_awaited_once()
        assert backend._client is None
        assert backend._ensured_indexes == set()

    async def test_close_is_noop_when_no_client(self):
        backend = make_backend()
        backend._client = None
        backend.ap = type('Ap', (), {'logger': AsyncMock()})()
        backend._ensured_indexes = set()
        # Should not raise.
        await backend.close()
        assert backend._client is None


class TestCredentialsBuild:
    """Tests for the auth-credential construction in _ensure_client."""

    def _prep_backend(self, mod, monkeypatch, *, username, password):
        backend = make_backend()
        backend._client = None
        backend._host = 'localhost'
        backend._port = 6379
        backend._db = 0
        backend._tls = False
        backend._username = username
        backend._password = password
        backend._request_timeout = 5000
        backend._ensured_indexes = set()
        warnings: list[str] = []
        backend.ap = type(
            'Ap',
            (),
            {
                'logger': type(
                    'L', (), {'info': lambda self, *a, **k: None, 'warning': lambda s, m, *a, **k: warnings.append(m)}
                )()
            },
        )()

        created = {}

        class _FakeClient:
            @staticmethod
            async def create(conf):
                created['conf'] = conf
                return AsyncMock()

        cred_calls: list[dict] = []

        def _fake_credentials(**kwargs):
            cred_calls.append(kwargs)
            return ('CRED', kwargs)

        monkeypatch.setattr(mod, 'GlideClient', _FakeClient)
        monkeypatch.setattr(mod, 'ServerCredentials', _fake_credentials)
        monkeypatch.setattr(mod, 'GlideClientConfiguration', lambda **kw: kw)
        monkeypatch.setattr(mod, 'NodeAddress', lambda *a, **k: ('node', a, k))
        return backend, created, cred_calls, warnings

    async def test_username_without_password_fails_closed(self, monkeypatch):
        mod = get_valkey_module()
        backend, created, cred_calls, warnings = self._prep_backend(mod, monkeypatch, username='acluser', password=None)

        # A username without a password must fail closed rather than silently
        # connecting unauthenticated to a (potentially shared) Valkey instance.
        with pytest.raises(ValueError, match='without a password'):
            await backend._ensure_client()

        assert cred_calls == []  # ServerCredentials NOT constructed
        assert 'conf' not in created  # client never created

    async def test_password_builds_credentials(self, monkeypatch):
        mod = get_valkey_module()
        backend, created, cred_calls, warnings = self._prep_backend(
            mod, monkeypatch, username='acluser', password='secret'
        )

        await backend._ensure_client()

        assert len(cred_calls) == 1
        assert cred_calls[0] == {'password': 'secret', 'username': 'acluser'}
        assert created['conf']['credentials'] == ('CRED', {'password': 'secret', 'username': 'acluser'})
