"""Run inside a container with only Docker socket and same-path host_root binds.

Set LANGBOT_TEST_BOX_SHARED_ROOT to that shared root to enable this acceptance
test. The runtime's private /tmp is deliberately not shared with the daemon.

Manual acceptance on a disposable Docker host, from the repository root::

    docker build -f tests/e2e/Dockerfile.box-socket -t langbot-box-socket-test .
    docker pull alpine:3.21
    shared_root=$(mktemp -d)
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$shared_root:$shared_root" \
        -e LANGBOT_TEST_BOX_SHARED_ROOT="$shared_root" langbot-box-socket-test
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import tempfile

import pytest

from langbot_plugin.artifact import build_tree_manifest
from langbot_plugin.box.backend import DockerBackend
from langbot_plugin.box.models import ARTIFACT_MOUNT_ROOT, BoxMountSpec, BoxSpec
from langbot_plugin.box.runtime import BoxRuntime

pytestmark = pytest.mark.skipif(
    not os.environ.get("LANGBOT_TEST_BOX_SHARED_ROOT"),
    reason="requires a container with host Docker socket and same-path shared root",
)


def test_private_tmp_and_shared_root_with_real_docker():
    assert Path("/.dockerenv").exists(), "Run this test inside the Box container"
    root = Path(os.environ["LANGBOT_TEST_BOX_SHARED_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix="socket-test-") as shared:
        asyncio.run(_exercise(Path(shared)))


async def _exercise(shared):
    logger = logging.getLogger(__name__)
    backend = DockerBackend(logger)
    runtime = BoxRuntime(logger, backends=[backend])
    runtime.init(
        {
            "backend": "docker",
            "local": {"host_root": str(shared)},
            "docker": {"cpu_limit_enabled": False},
        }
    )
    image = os.environ.get("LANGBOT_TEST_BOX_IMAGE", "alpine:3.21")
    empty = BoxSpec(
        session_id="socket-mounts",
        image=image,
        cmd="printf ready",
        network="off",
        host_path=str(shared / "workspace"),
    )
    cache = None
    try:
        # Creating a Box with no packages must still work with a private /tmp.
        result = await runtime.execute(empty)
        assert result.ok and result.stdout == "ready", result.stderr
        session = runtime.get_sessions()[0]
        backend_id = session["backend_session_id"]
        cache = Path(backend._artifact_roots[backend_id])
        assert cache.parent == shared and cache.is_dir()
        inspection = await backend._run_command(
            ["docker", "inspect", backend_id], timeout_sec=10, check=True
        )
        container = json.loads(inspection.stdout)[0]
        assert container["HostConfig"]["ReadonlyRootfs"]
        mounts = container["Mounts"]
        workspace_mount = next(m for m in mounts if m["Destination"] == "/workspace")
        assert workspace_mount["Source"] == empty.host_path and workspace_mount["RW"]
        artifact_mount = next(
            m for m in mounts if m["Destination"] == ARTIFACT_MOUNT_ROOT
        )
        assert artifact_mount["Source"] == str(cache) and not artifact_mount["RW"]

        # Packages prepared in private /tmp are copied into the shared cache;
        # adding one must preserve the already-created sandbox and its state.
        state = await runtime.execute(
            empty.model_copy(update={"cmd": "printf kept >/tmp/state"})
        )
        assert state.ok, state.stderr
        with tempfile.TemporaryDirectory() as private:
            package = Path(private) / "package"
            package.mkdir()
            (package / "value").write_text("package")
            digest, manifest = build_tree_manifest(
                str(package), max_files=10, max_total_bytes=1024
            )
            manifest_path = Path(private) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            mount = BoxMountSpec(
                host_path=str(package),
                mount_path=f"{ARTIFACT_MOUNT_ROOT}/{digest[7:]}",
                mode="ro",
                content_digest=digest,
                manifest_path=str(manifest_path),
            )
            mounted = empty.model_copy(
                update={
                    "extra_mounts": [mount],
                    "cmd": f"cat {mount.mount_path}/value /tmp/state",
                }
            )
            result = await runtime.execute(mounted)
            assert result.ok and result.stdout == "packagekept", result.stderr
            assert runtime.get_sessions()[0]["backend_session_id"] == backend_id
            denied = await runtime.execute(
                mounted.model_copy(
                    update={"cmd": f"printf changed >{mount.mount_path}/value"}
                )
            )
            assert not denied.ok
            assert (package / "value").read_text() == "package"
    finally:
        await runtime.shutdown()
    assert cache is not None and not cache.exists()
