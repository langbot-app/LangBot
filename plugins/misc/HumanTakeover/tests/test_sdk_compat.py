"""SDK 0.7.20 compatibility contract for the HumanTakeover artifact.

Guards the plugin against silent breakage when the pinned SDK or the
installed entity definitions change:

- every SDK symbol the plugin imports or calls still exists;
- ``manifest.yaml`` declares the capabilities the plugin actually uses;
- the shared-runtime profile required by this plugin is declared;
- the plugin's storage methods still exist on the installed API proxy.

Run from HumanTakeover: python -m pytest tests -q
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PLUGIN_ROOT / "manifest.yaml"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

# (module, attribute) for every SDK symbol this plugin relies on.
_SDK_SYMBOLS = [
    ("langbot_plugin.api.definition.plugin", "BasePlugin"),
    ("langbot_plugin.api.definition.components.page", "Page"),
    ("langbot_plugin.api.definition.components.page", "PageRequest"),
    ("langbot_plugin.api.definition.components.page", "PageResponse"),
    (
        "langbot_plugin.api.definition.components.common.event_listener",
        "EventListener",
    ),
    ("langbot_plugin.api.entities.builtin.platform.message", "MessageChain"),
    ("langbot_plugin.api.entities.builtin.platform.message", "Plain"),
    ("langbot_plugin.api.entities.builtin.platform.message", "Image"),
    ("langbot_plugin.api.entities.builtin.platform.message", "Voice"),
    ("langbot_plugin.api.entities.builtin.platform.message", "File"),
    ("langbot_plugin.api.entities.builtin.platform.message", "Quote"),
    ("langbot_plugin.api.entities.builtin.platform.message", "At"),
    ("langbot_plugin.api.entities.events", "PersonMessageReceived"),
    ("langbot_plugin.api.entities.events", "GroupMessageReceived"),
    ("langbot_plugin.api.entities.events", "NormalMessageResponded"),
    ("langbot_plugin.api.entities.events", "MessageDeleted"),
    ("langbot_plugin.api.entities.builtin.platform.entities", "User"),
    ("langbot_plugin.api.entities.builtin.platform.entities", "ChatType"),
]

# Capabilities the plugin needs: plugin storage, bot read, message send.
# recall_message additionally uses call_platform_api, declared as bot.platform_api.
_REQUIRED_CAPABILITIES = {"storage.plugin", "bot.read", "bot.message.send"}
_ALL_DECLARED = {"storage.plugin", "bot.read", "bot.message.send", "bot.platform_api"}

_EIGHT_LOCALES = {
    "en_US",
    "zh_Hans",
    "zh_Hant",
    "ja_JP",
    "es_ES",
    "ru_RU",
    "th_TH",
    "vi_VN",
}


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


class SDKCompatibilityTests(unittest.TestCase):
    def test_sdk_symbols_exist(self):
        for module_name, attribute in _SDK_SYMBOLS:
            with self.subTest(symbol=f"{module_name}.{attribute}"):
                module = importlib.import_module(module_name)
                self.assertTrue(hasattr(module, attribute), f"missing {attribute}")

    def test_storage_api_proxy_methods_exist(self):
        from main import HumanTakeover

        plugin = HumanTakeover()
        for name in (
            "get_plugin_storage",
            "set_plugin_storage",
            "get_plugin_storage_keys",
            "delete_plugin_storage",
            "send_message",
            "get_bot_info",
            "call_platform_api",
        ):
            with self.subTest(method=name):
                self.assertTrue(hasattr(plugin, name), f"missing SDK method {name}")

    def test_manifest_declares_required_permissions(self):
        manifest = _manifest()
        permissions = manifest.get("spec", {}).get("permissions")
        self.assertIsNotNone(permissions, "manifest must declare spec.permissions")
        capabilities = set(permissions.get("capabilities", []))
        self.assertTrue(
            _REQUIRED_CAPABILITIES.issubset(capabilities),
            f"missing capabilities: {_REQUIRED_CAPABILITIES - capabilities}",
        )
        self.assertLessEqual(capabilities, _ALL_DECLARED)

    def test_manifest_declares_shared_runtime_profile(self):
        manifest = _manifest()
        execution = manifest["execution"]
        self.assertEqual(execution["sharedRuntime"], "shared-runtime-v1")
        self.assertEqual(execution["componentModel"], "stateless-v1")

    def test_manifest_metadata_has_eight_locales(self):
        manifest = _manifest()
        metadata = manifest["metadata"]
        for field in ("label", "description"):
            with self.subTest(field=field):
                locales = set(metadata[field])
                self.assertTrue(
                    _EIGHT_LOCALES.issubset(locales),
                    f"missing locales: {_EIGHT_LOCALES - locales}",
                )

    def test_manifest_config_is_yaml_valid(self):
        manifest = _manifest()
        names = [item["name"] for item in manifest["spec"]["config"]]
        self.assertIn("max_labels_per_user", names)
        self.assertIn("label_colors", names)
        self.assertIn("image_plugin_upload_url", names)
