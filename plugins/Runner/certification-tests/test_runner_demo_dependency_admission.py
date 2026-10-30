"""Exercise RunnerDemo dependency admission with the real installed Runtime SDK."""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import tempfile
import unittest
from pathlib import Path

import yaml
from langbot_plugin.runtime.plugin.artifact import PluginArtifact
from langbot_plugin.runtime.plugin.dependency_environment import PluginDependencyEnvironmentStore

ROOT = Path(__file__).resolve().parents[1] / "RunnerDemo"


class RunnerDemoDependencyAdmissionTest(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_sdk_requirement_is_satisfied_without_shadow_install(self):
        manifest = yaml.safe_load((ROOT / "manifest.yaml").read_text())
        sdk_version = importlib.metadata.version("langbot-plugin")
        requirement = (ROOT / "requirements.txt").read_bytes()
        # Source fixture: exact published-archive admission is also checked at release.
        digest = hashlib.sha256(requirement).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            artifact = PluginArtifact(digest, base, ROOT, "langbot-team", "RunnerDemo", manifest["metadata"]["version"])
            store = PluginDependencyEnvironmentStore(base / "runtime")
            observed = []

            async def installer(staging, requirements):
                observed.append(list(requirements))
                self.assertEqual(list(requirements), [], "SDK must be runtime-provided, not separately installed")

            try:
                ready = await store.prepare(
                    artifact, runtime_fingerprint="test-sdk-" + sdk_version, installer=installer
                )
                self.assertEqual(observed, [[]])
                self.assertEqual(ready.artifact_digest, digest)
                self.assertIsNotNone(store.get_ready(ready.digest))
            finally:
                # The SDK publishes immutable trees; restore only this disposable fixture for cleanup.
                for parent, dirs, _ in os.walk(base):
                    os.chmod(parent, 0o700)
                    for child in dirs:
                        os.chmod(Path(parent) / child, 0o700)


if __name__ == "__main__":
    unittest.main()
