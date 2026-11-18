"""Opt-in real backend acceptance: LANGBOT_REAL_BOX_TESTS=1 pytest this file."""

import asyncio
import json
import logging
import os

import pytest

from langbot_plugin.artifact import build_tree_manifest
from langbot_plugin.box.backend import CLISandboxBackend
from langbot_plugin.box.errors import BoxSessionConflictError
from langbot_plugin.box.models import (
    ARTIFACT_MOUNT_ROOT,
    BoxManagedProcessSpec,
    BoxMountSpec,
    BoxSpec,
)
from langbot_plugin.box.nsjail_backend import NsjailBackend
from langbot_plugin.box.runtime import BoxRuntime

pytestmark = pytest.mark.skipif(
    os.environ.get("LANGBOT_REAL_BOX_TESTS") != "1",
    reason="requires real nsjail and Docker",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("backend_name", ["nsjail", "docker"])
async def test_shared_box_keeps_state_and_pinned_packages(tmp_path, backend_name):
    logger = logging.getLogger(__name__)
    backend = (
        NsjailBackend(logger, base_dir=str(tmp_path / "sessions"))
        if backend_name == "nsjail"
        else CLISandboxBackend(logger, "docker", "docker")
    )
    runtime = BoxRuntime(logger, backends=[backend])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    mounts = {}
    for version in ("v1", "v2"):
        package = tmp_path / version
        package.mkdir()
        (package / "value").write_text(version)
        digest, manifest = build_tree_manifest(
            str(package), max_files=10, max_total_bytes=1024
        )
        manifest_path = tmp_path / (version + ".json")
        manifest_path.write_text(json.dumps(manifest))
        mounts[version] = BoxMountSpec(
            host_path=str(package),
            mount_path=f"{ARTIFACT_MOUNT_ROOT}/{digest[7:]}",
            mode="ro",
            content_digest=digest,
            manifest_path=str(manifest_path),
        )
    empty = BoxSpec(
        session_id="shared",
        image=os.environ.get("LANGBOT_TEST_BOX_IMAGE", "alpine:latest"),
        host_path=str(workspace),
        network="off",
        timeout_sec=20,
    )

    def spec(version, command=None):
        return empty.model_copy(
            update={
                "extra_mounts": [mounts[version]],
                "cmd": command
                or f"cat {mounts[version].mount_path}/value; cat /tmp/retained",
            }
        )

    try:
        first = await runtime.execute(
            empty.model_copy(update={"cmd": "printf state >/tmp/retained"})
        )
        assert first.ok, first.stderr
        backend_id = runtime.get_sessions()[0]["backend_session_id"]
        await runtime.start_managed_process(
            "shared", BoxManagedProcessSpec(command="sleep", args=["120"])
        )
        results = await asyncio.gather(
            *(runtime.execute(spec(v)) for v in ("v1", "v2", "v1", "v2"))
        )
        assert [r.stdout for r in results] == [
            "v1state",
            "v2state",
            "v1state",
            "v2state",
        ]
        assert all(r.ok for r in results)
        assert runtime.get_sessions()[0]["backend_session_id"] == backend_id
        assert runtime.get_managed_process("shared")["status"] == "running"
        denied = await runtime.execute(
            spec("v1", f"printf changed >{mounts['v1'].mount_path}/value")
        )
        assert not denied.ok
        assert (tmp_path / "v1" / "value").read_text() == "v1"
        assert (await runtime.execute(spec("v1"))).stdout == "v1state"
        assert (
            await runtime.execute(empty.model_copy(update={"cmd": "cat /tmp/retained"}))
        ).stdout == "state"
        if backend_name == "docker":
            changed = empty.model_copy(
                update={
                    "cmd": "true",
                    "extra_mounts": [
                        BoxMountSpec(host_path=str(workspace), mount_path="/different")
                    ],
                }
            )
            with pytest.raises(BoxSessionConflictError, match="preserved"):
                await runtime.execute(changed)
            assert runtime.get_managed_process("shared")["status"] == "running"
    finally:
        await runtime.shutdown()
