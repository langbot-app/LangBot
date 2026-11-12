from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest

from tests.utils.import_isolation import isolated_sys_modules


def test_milvus_backend_reports_missing_optional_extra() -> None:
    module_name = 'langbot.pkg.vector.vdbs.milvus'

    with isolated_sys_modules({'pymilvus': None}, clear=[module_name]):
        milvus_module = importlib.import_module(module_name)

        assert milvus_module.MILVUS_AVAILABLE is False
        # Filter translation is pure Python and stays usable without pymilvus.
        assert milvus_module._build_milvus_expr({'file_id': 'f1'}) == 'file_id == "f1"'
        with pytest.raises(ImportError, match="Install LangBot with the 'milvus' extra"):
            milvus_module.MilvusVectorDatabase(MagicMock())


def test_valkey_search_backend_reports_missing_optional_extra() -> None:
    module_name = 'langbot.pkg.vector.vdbs.valkey_search'

    with isolated_sys_modules({'glide': None}, clear=[module_name]):
        valkey_module = importlib.import_module(module_name)

        assert valkey_module.VALKEY_SEARCH_AVAILABLE is False
        with pytest.raises(ImportError, match="Install LangBot with the 'valkey' extra"):
            valkey_module.ValkeySearchVectorDatabase(MagicMock())
