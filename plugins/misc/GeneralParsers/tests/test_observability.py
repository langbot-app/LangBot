"""Parser telemetry is scoped to the calling installation binding."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from langbot_plugin.api.definition.components.page import PageRequest
from langbot_plugin.api.proxies.invocation import bind_invocation, current_config
from langbot_plugin.entities.io.context import InstallationBinding

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _binding(installation: str, *, workspace: str = "workspace-1", instance: str = "instance-1"):
    return InstallationBinding(
        instance_uuid=instance,
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


class _StubPlugin:
    """Minimal BasePlugin surface: per-invocation config + runtime handler."""

    def __init__(self, handler):
        self.plugin_runtime_handler = handler

    def get_config(self) -> dict:
        return dict(current_config(self.plugin_runtime_handler) or {})

    def get_plugin_config(self) -> dict:
        return self.get_config()


class ParserTelemetryTests(unittest.TestCase):
    def test_snapshot_records_only_operational_metadata(self) -> None:
        from components.observability.telemetry import ParserTelemetry

        telemetry = ParserTelemetry(recent_limit=2)
        telemetry.record_parse(
            filename="/tmp/report.pdf",
            mime_type="application/pdf",
            extension="pdf",
            extension_source="mime_type",
            duration_ms=12.345,
            text_chars=1200,
            sections_count=4,
            metadata={
                "has_tables": True,
                "has_images": True,
                "images_count": 2,
                "vision_used": True,
                "vision_tasks_count": 3,
                "vision_images_described_count": 2,
                "vision_failed_count": 1,
            },
        )

        snapshot = telemetry.snapshot()

        self.assertEqual(snapshot["summary"]["total_parses"], 1)
        self.assertEqual(snapshot["summary"]["failed_parses"], 0)
        self.assertEqual(snapshot["summary"]["tables_detected"], 1)
        self.assertEqual(snapshot["summary"]["images_detected"], 1)
        self.assertEqual(snapshot["summary"]["vision_tasks_count"], 3)
        self.assertEqual(snapshot["distributions"]["extensions"][0]["key"], "pdf")
        self.assertEqual(snapshot["recent_parses"][0]["filename"], "report.pdf")
        self.assertNotIn("text", snapshot["recent_parses"][0])
        self.assertNotIn("file_content", snapshot["recent_parses"][0])

    def test_ring_buffers_and_errors_are_bounded(self) -> None:
        from components.observability.telemetry import ParserTelemetry

        telemetry = ParserTelemetry(recent_limit=1)
        telemetry.record_parse(
            filename="ok.txt",
            mime_type="text/plain",
            extension="txt",
            extension_source="mime_type",
            duration_ms=1,
            text_chars=2,
            sections_count=1,
        )
        telemetry.record_parse(
            filename="bad.pdf",
            mime_type="application/pdf",
            extension="pdf",
            extension_source="mime_type",
            duration_ms=2,
            text_chars=0,
            sections_count=0,
            metadata={"parser_failed": True, "parse_error": "broken"},
        )

        snapshot = telemetry.snapshot()

        self.assertEqual(snapshot["summary"]["total_parses"], 2)
        self.assertEqual(snapshot["summary"]["failed_parses"], 1)
        self.assertEqual(len(snapshot["recent_parses"]), 1)
        self.assertEqual(snapshot["recent_parses"][0]["filename"], "bad.pdf")
        self.assertEqual(len(snapshot["recent_errors"]), 1)
        self.assertEqual(snapshot["recent_errors"][0]["parse_error"], "broken")


class TelemetryBindingScopeTests(unittest.IsolatedAsyncioTestCase):
    """Two installations through one component object must not share records."""

    def setUp(self) -> None:
        from components.general_parsers.general_parsers import GeneralParsers
        from components.pages.observability import ParserObservabilityPage

        # ONE object graph: a single handler, plugin, Parser and Page instance
        # serve both installations, as in the shared-runtime worker.
        self.handler = SimpleNamespace()
        self.plugin = _StubPlugin(self.handler)
        self.parser = GeneralParsers()
        self.parser.plugin = self.plugin
        self.page = ParserObservabilityPage()
        self.page.plugin = self.plugin

    async def _record_parse(self, binding, filename: str, config: dict | None = None) -> None:
        from langbot_plugin.api.entities.builtin.rag.models import ParseContext

        with bind_invocation(self.handler, config=config or {}, binding=binding):
            await self.parser.parse(
                ParseContext(file_content=b"hello world", filename=filename, mime_type="text/plain")
            )

    async def _snapshot(self, binding, endpoint: str = "/snapshot", method: str = "GET"):
        with bind_invocation(self.handler, binding=binding):
            return await self.page.handle_api(PageRequest(endpoint=endpoint, method=method))

    async def test_records_are_not_visible_across_installations(self) -> None:
        from components.observability import get_telemetry, release_telemetry

        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")
        self.addCleanup(release_telemetry, binding_a)
        self.addCleanup(release_telemetry, binding_b)

        await self._record_parse(binding_a, "tenant-a-secret.pdf")
        await self._record_parse(binding_b, "tenant-b-notes.md")

        snapshot_b = await self._snapshot(binding_b)
        self.assertIsNone(snapshot_b.error)
        filenames_b = [row["filename"] for row in snapshot_b.data["recent_parses"]]
        self.assertIn("tenant-b-notes.md", filenames_b)
        # Pre-fix the module-level singleton leaked A's record into B's page.
        self.assertNotIn("tenant-a-secret.pdf", filenames_b)
        self.assertEqual(snapshot_b.data["summary"]["total_parses"], 1)

        snapshot_a = await self._snapshot(binding_a)
        filenames_a = [row["filename"] for row in snapshot_a.data["recent_parses"]]
        self.assertIn("tenant-a-secret.pdf", filenames_a)
        self.assertNotIn("tenant-b-notes.md", filenames_a)

        self.assertEqual(get_telemetry(binding_a).snapshot()["summary"]["total_parses"], 1)
        self.assertEqual(get_telemetry(binding_b).snapshot()["summary"]["total_parses"], 1)

    async def test_clear_only_resets_the_calling_installation(self) -> None:
        from components.observability import release_telemetry

        binding_a = _binding("installation-clear-a")
        binding_b = _binding("installation-clear-b")
        self.addCleanup(release_telemetry, binding_a)
        self.addCleanup(release_telemetry, binding_b)

        await self._record_parse(binding_a, "clear-a.txt")
        await self._record_parse(binding_b, "clear-b.txt")

        cleared = await self._snapshot(binding_a, endpoint="/clear", method="POST")
        self.assertIsNone(cleared.error)
        self.assertEqual(cleared.data["summary"]["total_parses"], 0)

        snapshot_b = await self._snapshot(binding_b)
        self.assertEqual(snapshot_b.data["summary"]["total_parses"], 1)
        self.assertEqual(snapshot_b.data["recent_parses"][0]["filename"], "clear-b.txt")

    async def test_revocation_drops_only_that_installation(self) -> None:
        from components.observability import get_telemetry, release_telemetry

        binding_a = _binding("installation-revoke-a")
        binding_b = _binding("installation-revoke-b")
        self.addCleanup(release_telemetry, binding_a)
        self.addCleanup(release_telemetry, binding_b)

        await self._record_parse(binding_a, "revoked-a.txt")
        await self._record_parse(binding_b, "kept-b.txt")

        release_telemetry(binding_a)

        self.assertEqual(get_telemetry(binding_a).snapshot()["summary"]["total_parses"], 0)
        self.assertEqual(get_telemetry(binding_b).snapshot()["summary"]["total_parses"], 1)

    async def test_unknown_endpoint_fails(self) -> None:
        from components.observability import release_telemetry

        binding = _binding("installation-unknown-endpoint")
        self.addCleanup(release_telemetry, binding)

        response = await self._snapshot(binding, endpoint="/missing", method="GET")
        self.assertIsNotNone(response.error)


if __name__ == "__main__":
    unittest.main()
