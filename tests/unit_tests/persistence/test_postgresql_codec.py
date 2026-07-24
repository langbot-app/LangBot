"""Unit tests for asyncpg JSON/JSONB codec registration in PostgreSQL manager.

Tests cover:
- _register_json_codecs registers both json and jsonb codecs
- _patch_asyncpg_dialect wraps the original connect method
- The patched connect invokes run_async to install codecs on each new connection

Note: Uses import isolation to break circular import chains (same pattern as
test_database_decorator.py).
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi


@contextmanager
def isolated_database_import() -> Generator[None, None, None]:
    """Context manager to isolate circular imports for database testing."""
    mock_app = MagicMock()
    mock_importutil = MagicMock()
    mock_importutil.import_modules_in_pkg = lambda pkg: None
    mock_importutil.import_modules_in_pkgs = lambda pkgs: None
    mock_mgr = MagicMock()

    mocks = {
        'langbot.pkg.core.app': mock_app,
        'langbot.pkg.utils.importutil': mock_importutil,
        'langbot.pkg.persistence.mgr': mock_mgr,
    }

    saved: dict[str, object] = {}
    for name in mocks:
        if name in sys.modules:
            saved[name] = sys.modules[name]

    database_name = 'langbot.pkg.persistence.database'
    if database_name in sys.modules:
        saved[database_name] = sys.modules[database_name]

    for sub in ['sqlite', 'postgresql']:
        full_name = f'langbot.pkg.persistence.databases.{sub}'
        if full_name in sys.modules:
            saved[full_name] = sys.modules[full_name]

    try:
        for name, module in mocks.items():
            sys.modules[name] = module

        sys.modules.pop(database_name, None)
        for sub in ['sqlite', 'postgresql']:
            sys.modules.pop(f'langbot.pkg.persistence.databases.{sub}', None)

        yield
    finally:
        for name in mocks:
            if name in saved:
                sys.modules[name] = saved[name]
            else:
                sys.modules.pop(name, None)

        if database_name in saved:
            sys.modules[database_name] = saved[database_name]
        else:
            sys.modules.pop(database_name, None)

        for sub in ['sqlite', 'postgresql']:
            full_name = f'langbot.pkg.persistence.databases.{sub}'
            if full_name in saved:
                sys.modules[full_name] = saved[full_name]
            else:
                sys.modules.pop(full_name, None)


def get_postgresql_module():
    """Get the postgresql database module with import isolation.

    Saves and restores the original ``AsyncAdapt_asyncpg_dbapi.connect``
    because the module calls ``_patch_asyncpg_dialect()`` at import time.
    """
    orig_connect = AsyncAdapt_asyncpg_dbapi.connect
    try:
        with isolated_database_import():
            from langbot.pkg.persistence.databases import postgresql

            return postgresql
    finally:
        AsyncAdapt_asyncpg_dbapi.connect = orig_connect


class TestRegisterJsonCodecs:
    """Tests for _register_json_codecs."""

    async def test_registers_json_and_jsonb_codecs(self):
        """Test that both json and jsonb codecs are registered on the connection."""
        pg_module = get_postgresql_module()

        mock_conn = MagicMock()
        mock_conn.set_type_codec = AsyncMock()

        await pg_module._register_json_codecs(mock_conn)

        assert mock_conn.set_type_codec.call_count == 2

        first_call = mock_conn.set_type_codec.call_args_list[0]
        assert first_call.args[0] == 'json'
        assert first_call.kwargs['encoder'] == json.dumps
        assert first_call.kwargs['decoder'] == json.loads
        assert first_call.kwargs['schema'] == 'pg_catalog'
        assert first_call.kwargs['format'] == 'text'

        second_call = mock_conn.set_type_codec.call_args_list[1]
        assert second_call.args[0] == 'jsonb'
        assert second_call.kwargs['encoder'] == json.dumps
        assert second_call.kwargs['decoder'] == json.loads
        assert second_call.kwargs['schema'] == 'pg_catalog'
        assert second_call.kwargs['format'] == 'text'

    async def test_codec_decodes_json_string_to_dict(self):
        """Test that the registered decoder correctly parses JSON strings."""
        pg_module = get_postgresql_module()

        mock_conn = MagicMock()
        mock_conn.set_type_codec = AsyncMock()

        await pg_module._register_json_codecs(mock_conn)

        json_call = mock_conn.set_type_codec.call_args_list[0]
        decoder = json_call.kwargs['decoder']
        assert decoder('{"key": "value"}') == {'key': 'value'}

        jsonb_call = mock_conn.set_type_codec.call_args_list[1]
        decoder_b = jsonb_call.kwargs['decoder']
        assert decoder_b('[1, 2, 3]') == [1, 2, 3]

    async def test_codec_encodes_dict_to_json_string(self):
        """Test that the registered encoder correctly serializes Python objects."""
        pg_module = get_postgresql_module()

        mock_conn = MagicMock()
        mock_conn.set_type_codec = AsyncMock()

        await pg_module._register_json_codecs(mock_conn)

        json_call = mock_conn.set_type_codec.call_args_list[0]
        encoder = json_call.kwargs['encoder']
        assert encoder({'key': 'value'}) == '{"key": "value"}'


class TestPatchAsyncpgDialect:
    """Tests for _patch_asyncpg_dialect."""

    def test_patch_replaces_connect_method(self):
        """Test that _patch_asyncpg_dialect replaces the connect method."""
        pg_module = get_postgresql_module()
        orig_connect = AsyncAdapt_asyncpg_dbapi.connect

        try:
            pg_module._patch_asyncpg_dialect()
            assert AsyncAdapt_asyncpg_dbapi.connect is not orig_connect
        finally:
            AsyncAdapt_asyncpg_dbapi.connect = orig_connect

    def test_patched_connect_calls_original_and_run_async(self):
        """Test that the patched connect calls original connect and run_async."""
        pg_module = get_postgresql_module()

        mock_wrapper = MagicMock()
        mock_wrapper.run_async = MagicMock()
        fake_orig_connect = MagicMock(return_value=mock_wrapper)

        orig_connect = AsyncAdapt_asyncpg_dbapi.connect
        AsyncAdapt_asyncpg_dbapi.connect = fake_orig_connect

        try:
            pg_module._patch_asyncpg_dialect()
            patched = AsyncAdapt_asyncpg_dbapi.connect

            mock_self = MagicMock()
            result = patched(mock_self, 'arg1', kwarg='val')

            fake_orig_connect.assert_called_once_with(mock_self, 'arg1', kwarg='val')
            mock_wrapper.run_async.assert_called_once()
            assert result is mock_wrapper
        finally:
            AsyncAdapt_asyncpg_dbapi.connect = orig_connect

    async def test_patched_connect_init_registers_codecs(self):
        """Test that the run_async callback registers JSON codecs on the connection."""
        pg_module = get_postgresql_module()

        mock_wrapper = MagicMock()
        captured_init: list = []
        mock_wrapper.run_async = lambda fn: captured_init.append(fn)

        fake_orig_connect = MagicMock(return_value=mock_wrapper)
        orig_connect = AsyncAdapt_asyncpg_dbapi.connect
        AsyncAdapt_asyncpg_dbapi.connect = fake_orig_connect

        try:
            pg_module._patch_asyncpg_dialect()
            patched = AsyncAdapt_asyncpg_dbapi.connect
            patched(MagicMock())

            assert len(captured_init) == 1

            mock_pg_conn = MagicMock()
            mock_pg_conn.set_type_codec = AsyncMock()
            await captured_init[0](mock_pg_conn)

            assert mock_pg_conn.set_type_codec.call_count == 2
        finally:
            AsyncAdapt_asyncpg_dbapi.connect = orig_connect

    async def test_init_handles_conn_none_fallback(self):
        """Test that _init falls back to wrapper.connection when conn is None."""
        pg_module = get_postgresql_module()

        mock_pg_conn = MagicMock()
        mock_pg_conn.set_type_codec = AsyncMock()

        mock_wrapper = MagicMock()
        captured_init: list = []
        mock_wrapper.run_async = lambda fn: captured_init.append(fn)

        mock_adapt = MagicMock()
        mock_adapt._connection = mock_pg_conn
        mock_wrapper.connection = mock_adapt

        fake_orig_connect = MagicMock(return_value=mock_wrapper)
        orig_connect = AsyncAdapt_asyncpg_dbapi.connect
        AsyncAdapt_asyncpg_dbapi.connect = fake_orig_connect

        try:
            pg_module._patch_asyncpg_dialect()
            patched = AsyncAdapt_asyncpg_dbapi.connect
            patched(MagicMock())

            assert len(captured_init) == 1
            await captured_init[0](None)

            assert mock_pg_conn.set_type_codec.call_count == 2
        finally:
            AsyncAdapt_asyncpg_dbapi.connect = orig_connect

    def test_double_patch_still_works(self):
        """Test that calling _patch_asyncpg_dialect twice still yields a working patch.

        Double-patching stacks wrappers, so run_async fires once per layer.
        This verifies the stacked patch does not break.
        """
        pg_module = get_postgresql_module()

        mock_wrapper = MagicMock()
        mock_wrapper.run_async = MagicMock()

        fake_orig_connect = MagicMock(return_value=mock_wrapper)
        orig_connect = AsyncAdapt_asyncpg_dbapi.connect
        AsyncAdapt_asyncpg_dbapi.connect = fake_orig_connect

        try:
            pg_module._patch_asyncpg_dialect()
            first_patched = AsyncAdapt_asyncpg_dbapi.connect

            pg_module._patch_asyncpg_dialect()
            second_patched = AsyncAdapt_asyncpg_dbapi.connect

            assert first_patched is not second_patched

            mock_wrapper.run_async.reset_mock()
            second_patched(MagicMock())
            assert mock_wrapper.run_async.called
        finally:
            AsyncAdapt_asyncpg_dbapi.connect = orig_connect
