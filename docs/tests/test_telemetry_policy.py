"""Validate localized telemetry controls and the rendered collection policy."""
import os
import pathlib
import re
import unittest
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCALES = ("en", "zh", "ja")


class TelemetryPolicyTest(unittest.TestCase):
    def test_locales_document_current_protocol_and_opt_out(self):
        for locale in LOCALES:
            policy = (ROOT / locale / "insight/data-collection-policy.mdx").read_text(encoding="utf-8")
            with self.subTest(locale=locale):
                for literal in (
                    "schema: 2", "execution_node", "execution_chain", "event_id",
                    "instance_id", "workspace_uuid", "instance_heartbeat",
                    "space.execution_trace", "space.execution_trace_sample",
                    "space.telemetry_flush_seconds", "plugin.runtime_ops.enabled",
                    "data/config.yaml", "SPACE__DISABLE_TELEMETRY", "space.url",
                    "feature_execution", "traceback", "hello@langbot.app",
                ):
                    self.assertIn(literal, policy)
                self.assertEqual(
                    re.findall(r"```yaml\n(.*?)\n```", policy, re.S),
                    ["space:\n  disable_telemetry: true"],
                )
                self.assertEqual(
                    re.findall(r"^\| `(all|sampled|failures|off)`", policy, re.M),
                    ["all", "sampled", "failures", "off"],
                )
                self.assertNotIn("disable_beta_diagnostics", policy)
                self.assertNotRegex(policy, r"B2-\d{2}")
                self.assertIn("(../deploy/settings)", policy)

    def test_settings_examples_share_defaults_and_boolean_opt_out(self):
        expected = {
            "execution_trace": "all",
            "execution_trace_sample": "20",
            "telemetry_flush_seconds": "180",
        }
        for locale in LOCALES:
            settings = (ROOT / locale / "deploy/settings.mdx").read_text(encoding="utf-8")
            with self.subTest(locale=locale):
                blocks = re.findall(r"```yaml\n(.*?)\n```", settings, re.S)
                self.assertIn("space:\n  disable_telemetry: true", blocks)
                sampling = [block for block in blocks if "execution_trace:" in block]
                self.assertEqual(len(sampling), 1)
                fields = dict(re.findall(r"^  (\w+):\s*(\S+)", sampling[0], re.M))
                self.assertEqual(fields, expected)
                for literal in ("SPACE__DISABLE_TELEMETRY", "plugin.runtime_ops.enabled"):
                    self.assertIn(literal, settings)
                self.assertIn("(../insight/data-collection-policy)", settings)

    def test_built_policy_html_when_requested(self):
        if os.environ.get("TELEMETRY_POLICY_STATIC") != "1":
            self.skipTest("Run with TELEMETRY_POLICY_STATIC=1 after npm run build")

        class VisibleText(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []
                self.tables = 0
                self.hidden = 0

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style"):
                    self.hidden += 1
                if tag == "table":
                    self.tables += 1

            def handle_endtag(self, tag):
                if tag in ("script", "style"):
                    self.hidden -= 1

            def handle_data(self, data):
                if not self.hidden:
                    self.parts.append(data)

        for locale in LOCALES:
            with self.subTest(locale=locale):
                html = (ROOT / "dist/public" / locale /
                        "insight/data-collection-policy/index.html").read_text(encoding="utf-8")
                parser = VisibleText()
                parser.feed(html)
                text = "".join(parser.parts)
                self.assertEqual(parser.tables, 2)
                for literal in ("schema: 2", "execution_node", "execution_chain",
                                "instance_id", "workspace_uuid", "event_id",
                                "disable_telemetry", "SPACE__DISABLE_TELEMETRY",
                                "space.telemetry_flush_seconds", "plugin.runtime_ops.enabled"):
                    self.assertIn(literal, text)
                self.assertNotIn("disable_beta_diagnostics", text)
                self.assertIn('href="mailto:hello@langbot.app"', html)


if __name__ == "__main__":
    unittest.main()
