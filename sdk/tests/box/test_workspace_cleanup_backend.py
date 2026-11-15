"""Check container cleanup authority and retries against real workspace paths."""

from __future__ import annotations

import csv
import io
import json
import logging
from types import SimpleNamespace
from unittest import mock

import pytest

from langbot_plugin.box import file_io
from langbot_plugin.box.backend import DockerBackend, _CommandResult
from langbot_plugin.box.errors import BoxError
from langbot_plugin.box.models import BoxNetworkMode, BoxSessionInfo


IMAGE_ID = "sha256:" + "b" * 64


def _values(argv, flag):
    return [argv[index + 1] for index, value in enumerate(argv) if value == flag]


class CleanupCLI:
    """Simulate Docker receipts, not the helper's filesystem implementation."""

    def __init__(self, root):
        self.root = root
        self.calls = []
        self.image = {
            "Id": IMAGE_ID,
            "Config": {
                "Volumes": None,
                "Env": [
                    "LD_PRELOAD=/tenant/startup.so",
                    "PYTHONPATH=/tenant",
                    "PATH=/tenant/bin",
                ],
            },
        }
        self.mount_source = str(root)
        self.name = None
        self.live = False
        self.retirement_fails = False
        self.start_result = _CommandResult(0, "", "")

    async def run(self, argv, *, timeout_sec, check=True):
        self.calls.append(list(argv))
        command = argv[1]
        if argv[1:3] == ["image", "inspect"]:
            assert argv[3] == IMAGE_ID
            return _CommandResult(0, json.dumps([self.image]), "")
        if command == "create":
            self.name = _values(argv, "--name")[0]
            self.live = True
            return _CommandResult(0, "test-helper-id", "")
        if command == "inspect":
            assert argv[-1] == self.name
            receipt = {
                "Image": IMAGE_ID,
                "Mounts": [
                    {
                        "Type": "bind",
                        "Source": self.mount_source,
                        "Destination": "/workspace",
                        "RW": True,
                    }
                ],
            }
            return _CommandResult(0, json.dumps([receipt]), "")
        if command == "start":
            assert argv[-1] == self.name and self.live
            if self.start_result.return_code == 0 and not self.start_result.timed_out:
                # The CLI receipt means this known test payload was cleared.
                (self.root / "private" / "data").unlink()
                (self.root / "private").rmdir()
            return self.start_result
        if command == "rm":
            assert argv[-1] == self.name
            if self.retirement_fails:
                return _CommandResult(1, "", "daemon unavailable")
            self.live = False
            return _CommandResult(0, "", "")
        if command == "ps":
            return _CommandResult(0, self.name if self.live else "", "")
        raise AssertionError(f"Unexpected Docker command: {argv!r}")


@pytest.fixture
def cleanup_case(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir(mode=0o700)
    info = root.stat()
    owner = (str(root), info.st_dev, info.st_ino)
    session = BoxSessionInfo(
        session_id="owned-session",
        backend_name="docker",
        backend_session_id="original-container",
        image="example.invalid/tenant:mutable-tag",
        host_path=str(root),
        network=BoxNetworkMode.OFF,
        created_at="2026-11-15T00:00:00+00:00",
        last_used_at="2026-11-15T00:00:00+00:00",
    )
    session._runtime_workspace_owner = owner
    session._runtime_image_id = IMAGE_ID
    backend = DockerBackend(logging.getLogger("test.workspace-cleanup"))
    backend.instance_id = "runtime-owner"
    cli = CleanupCLI(root)
    monkeypatch.setattr(backend, "_run_command", cli.run)
    return SimpleNamespace(
        root=root, owner=owner, session=session, backend=backend, cli=cli
    )


@pytest.fixture
def host_permission_denied(monkeypatch):
    original = file_io.remove_owned_workspace

    def remove(owner, *, empty_only=False):
        if not empty_only:
            raise PermissionError("foreign-owned directory fixture")
        return original(owner, empty_only=True)

    monkeypatch.setattr(file_io, "remove_owned_workspace", remove)
    return original


def _write_payload(root):
    private = root / "private"
    private.mkdir(mode=0o700)
    payload = private / "data"
    payload.write_bytes(b"owned workspace data")
    return payload


@pytest.mark.anyio
@pytest.mark.parametrize("cpu_limit_enabled", [True, False])
async def test_helper_is_pinned_confined_and_retired_before_root_removal(
    cleanup_case, host_permission_denied, tmp_path, cpu_limit_enabled
):
    case = cleanup_case
    _write_payload(case.root)
    protected = tmp_path / "another-workspace"
    protected.write_bytes(b"must remain")
    case.backend.cpu_limit_enabled = cpu_limit_enabled

    await case.backend.remove_owned_workspace(case.session, case.owner)

    assert not case.root.exists()
    assert protected.read_bytes() == b"must remain"
    assert not case.cli.live
    assert case.session._workspace_cleanup_container is None
    create = next(argv for argv in case.cli.calls if argv[1] == "create")
    assert case.session.image not in create
    image_index = create.index(IMAGE_ID)
    assert create[image_index + 1 : image_index + 4] == ["-I", "-S", "-c"]
    for flag, value in {
        "--pull": "never",
        "--restart": "no",
        "--user": "0:0",
        "--network": "none",
        "--cap-drop": "ALL",
        "--workdir": "/",
        "--entrypoint": "python3",
    }.items():
        assert _values(create, flag) == [value]
    assert {"--read-only", "--no-healthcheck"} <= set(create)
    assert set(_values(create, "--cap-add")) == {"DAC_OVERRIDE", "FOWNER"}
    assert _values(create, "--security-opt") == ["no-new-privileges"]
    assert _values(create, "--mount") == [
        f"type=bind,src={case.root},dst=/workspace,bind-recursive=disabled"
    ]
    assert not {
        "--privileged",
        "--userns",
        "--pid",
        "--volume",
        "--volumes-from",
        "-v",
    }.intersection(create)
    assert int(_values(create, "--pids-limit")[0]) <= 32
    assert _values(create, "--memory") == ["128m"]
    assert bool(_values(create, "--cpus")) is cpu_limit_enabled
    environment = dict(value.split("=", 1) for value in _values(create, "--env"))
    assert environment["LD_PRELOAD"] == environment["PYTHONPATH"] == ""
    assert environment["PATH"] == "/usr/local/bin:/usr/bin:/bin"
    assert {
        "langbot.box=true",
        "langbot.box.instance_id=runtime-owner",
        "langbot.session_id=owned-session",
    } <= set(_values(create, "--label"))
    assert [argv[1] for argv in case.cli.calls][-3:] == ["start", "rm", "ps"]


@pytest.mark.anyio
@pytest.mark.parametrize("name", ['workspace, "quoted"', 'workspace,\n"quoted"'])
async def test_cleanup_mount_preserves_csv_characters_in_workspace_path(
    cleanup_case, host_permission_denied, name
):
    case = cleanup_case
    root = case.root.with_name(name)
    case.root.rename(root)
    case.root = case.cli.root = root
    case.owner = (str(root), *case.owner[1:])
    case.session.host_path = case.cli.mount_source = str(root)
    case.session._runtime_workspace_owner = case.owner
    _write_payload(root)

    await case.backend.remove_owned_workspace(case.session, case.owner)

    create = next(argv for argv in case.cli.calls if argv[1] == "create")
    assert list(csv.reader(io.StringIO(_values(create, "--mount")[0]))) == [
        [
            "type=bind",
            f"src={root}",
            "dst=/workspace",
            "bind-recursive=disabled",
        ]
    ]
    assert not root.exists()
    assert not case.cli.live


@pytest.mark.anyio
@pytest.mark.parametrize("unsafe_receipt", ["image", "volumes", "mount"])
async def test_untrusted_image_or_mount_never_starts_and_preserves_workspace(
    cleanup_case, host_permission_denied, unsafe_receipt
):
    case = cleanup_case
    payload = _write_payload(case.root)
    if unsafe_receipt == "image":
        case.cli.image["Id"] = "sha256:" + "a" * 64
    elif unsafe_receipt == "volumes":
        case.cli.image["Config"]["Volumes"] = {"/extra-volume": {}}
    else:
        case.cli.mount_source = str(case.root.parent / "another-workspace")

    with pytest.raises(BoxError, match="immutable image|mount differs"):
        await case.backend.remove_owned_workspace(case.session, case.owner)

    assert payload.read_bytes() == b"owned workspace data"
    assert "start" not in [argv[1] for argv in case.cli.calls]
    assert not case.cli.live
    assert case.session._workspace_cleanup_container is None


@pytest.mark.anyio
async def test_replaced_workspace_identity_is_rejected_without_starting_helper(
    cleanup_case,
):
    case = cleanup_case
    original = case.root.with_name("original-workspace")
    case.root.rename(original)
    case.root.mkdir()
    replacement = _write_payload(case.root)
    protected = original / "original-data"
    protected.write_bytes(b"original owner")

    with pytest.raises(ValueError, match="ownership changed"):
        await case.backend.remove_owned_workspace(case.session, case.owner)

    assert replacement.read_bytes() == b"owned workspace data"
    assert protected.read_bytes() == b"original owner"
    assert case.cli.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("retirement_fails", [False, True])
async def test_pending_helper_is_retired_even_when_workspace_is_already_empty(
    cleanup_case, retirement_fails
):
    case = cleanup_case
    case.session._workspace_cleanup_container = "pending-helper"
    case.cli.name = "pending-helper"
    case.cli.live = True
    case.cli.retirement_fails = retirement_fails

    if retirement_fails:
        with pytest.raises(BoxError, match="has not stopped"):
            await case.backend.remove_owned_workspace(case.session, case.owner)
        assert case.root.is_dir()
        assert case.session._workspace_cleanup_container == "pending-helper"
        assert case.cli.live
    else:
        await case.backend.remove_owned_workspace(case.session, case.owner)
        assert not case.root.exists()
        assert case.session._workspace_cleanup_container is None
        assert not case.cli.live
    assert [argv[1] for argv in case.cli.calls] == ["rm", "ps"]


@pytest.mark.anyio
async def test_timed_out_helper_is_retired_without_deleting_workspace(
    cleanup_case, host_permission_denied
):
    case = cleanup_case
    payload = _write_payload(case.root)
    case.cli.start_result = _CommandResult(-1, "", "helper timeout", timed_out=True)

    with pytest.raises(BoxError, match="failed or timed out"):
        await case.backend.remove_owned_workspace(case.session, case.owner)

    assert payload.read_bytes() == b"owned workspace data"
    assert not case.cli.live
    assert case.session._workspace_cleanup_container is None


@pytest.mark.anyio
async def test_failed_retirement_after_clearing_root_is_retried_before_removal(
    cleanup_case, host_permission_denied, monkeypatch
):
    case = cleanup_case
    _write_payload(case.root)
    case.cli.retirement_fails = True

    with pytest.raises(BoxError, match="has not stopped"):
        await case.backend.remove_owned_workspace(case.session, case.owner)

    assert case.root.is_dir() and list(case.root.iterdir()) == []
    assert case.session._workspace_cleanup_container == case.cli.name
    assert case.cli.live
    case.cli.calls.clear()
    case.cli.retirement_fails = False
    monkeypatch.setattr(file_io, "remove_owned_workspace", host_permission_denied)

    await case.backend.remove_owned_workspace(case.session, case.owner)

    assert [argv[1] for argv in case.cli.calls] == ["rm", "ps"]
    assert not case.root.exists()
    assert not case.cli.live
    assert case.session._workspace_cleanup_container is None


@pytest.mark.anyio
async def test_image_inspection_exception_does_not_prevent_stopping_original(
    cleanup_case, monkeypatch
):
    case = cleanup_case
    case.session._runtime_image_id = None
    commands = mock.AsyncMock(
        side_effect=[OSError("image inspection failed"), _CommandResult(0, "", "")]
    )
    monkeypatch.setattr(case.backend, "_run_command", commands)

    await case.backend.stop_session(case.session)

    assert [call.args[0][1] for call in commands.call_args_list] == ["inspect", "rm"]
    assert commands.call_args_list[-1].args[0][-1] == "original-container"
    assert case.session._runtime_image_id is None
    assert case.root.is_dir()
