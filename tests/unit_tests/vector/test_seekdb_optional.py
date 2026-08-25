from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest

from tests.utils.import_isolation import isolated_sys_modules


_INSTALL_HINT = "Install LangBot with the 'seekdb' extra"


def test_seekdb_vector_backend_reports_missing_optional_extra() -> None:
    module_name = 'langbot.pkg.vector.vdbs.seekdb'

    with isolated_sys_modules({'pyseekdb': None}, clear=[module_name]):
        seekdb_module = importlib.import_module(module_name)

        assert seekdb_module.SEEKDB_AVAILABLE is False
        with pytest.raises(ImportError, match=_INSTALL_HINT):
            seekdb_module.SeekDBVectorDatabase(MagicMock())


@pytest.mark.asyncio
async def test_seekdb_embedding_reports_missing_optional_extra() -> None:
    module_name = 'langbot.pkg.provider.modelmgr.requesters.seekdbembed'

    with isolated_sys_modules({'pyseekdb': None}, clear=[module_name]):
        seekdb_embedding_module = importlib.import_module(module_name)
        requester = seekdb_embedding_module.SeekDBEmbedding.__new__(seekdb_embedding_module.SeekDBEmbedding)

        with pytest.raises(ImportError, match=_INSTALL_HINT):
            await requester.initialize()
