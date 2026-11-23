"""The host must share the Runtime's plugin file-transfer root in shared deployments.

A mismatch leaves plugin icons and assets failing with
"Invalid file transfer capability" because the SDK binds one directory inode per
process (mode 0700) and picks the default from the runtime profile.
"""

from __future__ import annotations

import os
from importlib import import_module
from types import SimpleNamespace

from langbot_plugin.runtime.io.handler import SHARED_WORKER_FILE_STORAGE_DIR
from langbot_plugin.runtime.security import PLUGIN_FILE_STORAGE_DIR_ENV


def connector_module():
    import_module('langbot.pkg.core.app')
    return import_module('langbot.pkg.plugin.connector')


def align(profile: str) -> None:
    connector = connector_module()
    connector.PluginRuntimeConnector._align_plugin_file_transfer_root(
        SimpleNamespace(runtime_profile=profile)
    )


def test_shared_profile_pins_the_runtime_transfer_root(monkeypatch):
    monkeypatch.delenv(PLUGIN_FILE_STORAGE_DIR_ENV, raising=False)

    align('shared')

    assert os.environ[PLUGIN_FILE_STORAGE_DIR_ENV] == SHARED_WORKER_FILE_STORAGE_DIR


def test_explicit_operator_value_is_never_overridden(monkeypatch):
    monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, '/var/lib/custom-transfer')

    align('shared')

    assert os.environ[PLUGIN_FILE_STORAGE_DIR_ENV] == '/var/lib/custom-transfer'


def test_oss_profile_leaves_the_default_alone(monkeypatch):
    monkeypatch.delenv(PLUGIN_FILE_STORAGE_DIR_ENV, raising=False)

    align('oss_dev')

    assert PLUGIN_FILE_STORAGE_DIR_ENV not in os.environ
