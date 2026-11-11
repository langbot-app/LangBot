from __future__ import annotations

import pytest
import pydantic
from pydantic import ValidationError

from langbot_plugin.entities.io.actions.enums import (
    CommonAction,
    LangBotToRuntimeAction,
    PluginToRuntimeAction,
    RuntimeToLangBotAction,
    RuntimeToPluginAction,
)
from langbot_plugin.entities.io.errors import (
    ActionCallError,
    ActionCallTimeoutError,
    ConnectionClosedError,
)
from langbot_plugin.entities.io.req import ActionRequest
from langbot_plugin.entities.io.resp import ActionResponse, ChunkStatus
from langbot_plugin.entities.io.context import (
    ActionContext,
    ApplyPluginInstallationRequest,
    InstallationBinding,
    PluginInstallationDesiredState,
    PluginExecutionMode,
    PluginWorkerPolicy,
    ReconcilePluginInstallationsRequest,
    RuntimeConfig,
    RuntimeIdentity,
)


ARTIFACT_DIGEST = "a" * 64


def test_action_request_factory_preserves_protocol_fields():
    request = ActionRequest.make_request(
        seq_id=42,
        action=PluginToRuntimeAction.GET_BOT_UUID.value,
        data={"query_id": 1001},
    )

    assert request.seq_id == 42
    assert request.action == "get_bot_uuid"
    assert request.data == {"query_id": 1001}
    assert request.model_dump() == {
        "seq_id": 42,
        "action": "get_bot_uuid",
        "data": {"query_id": 1001},
    }


def test_action_request_requires_mapping_data():
    with pytest.raises(ValidationError):
        ActionRequest(seq_id=1, action="ping", data=["not", "a", "dict"])


def test_action_request_serializes_optional_workspace_context_envelope():
    context = ActionContext(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=7,
        installation_uuid="installation-1",
    )

    request = ActionRequest.make_request(7, "ping", {}, context)

    assert request.model_dump() == {
        "seq_id": 7,
        "action": "ping",
        "data": {},
        "context": context.model_dump(),
    }
    assert ActionRequest.model_validate(request.model_dump()).context == context


def test_action_request_preserves_complete_installation_binding():
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=7,
        installation_uuid="installation-1",
        runtime_revision=3,
        artifact_digest=ARTIFACT_DIGEST,
    )

    request = ActionRequest.make_request(8, "list_plugins", {}, binding)
    round_tripped = ActionRequest.model_validate(request.model_dump())

    assert request.model_dump()["context"] == binding.model_dump()
    assert isinstance(round_tripped.context, InstallationBinding)
    assert round_tripped.context == binding
    assert binding.execution_generation == 7


def test_runtime_config_models_are_frozen_and_instance_scoped():
    identity = RuntimeIdentity(instance_uuid="instance-1", runtime_id="runtime-boot-1")
    policy = PluginWorkerPolicy(
        max_cpus=1.0,
        max_memory_mb=512,
        max_pids=128,
        max_open_files=256,
        max_file_size_mb=512,
    )
    config = RuntimeConfig(
        runtime_identity=identity,
        worker_policy=policy,
        cloud_service_url="https://space.example/",
    )

    assert config.cloud_service_url == "https://space.example"
    assert config.runtime_profile == "oss_dev"
    assert policy.require_hard_limits is False
    assert policy.effective_worker_capacity == 8
    assert policy.max_concurrent_restarts == 1
    assert policy.restart_failure_threshold == 8
    assert policy.restart_failure_window_seconds == 30
    assert policy.restart_circuit_open_seconds == 60
    assert policy.max_pending_registrations == 1024
    with pytest.raises(ValidationError):
        identity.runtime_id = "runtime-boot-2"
    with pytest.raises(ValidationError):
        policy.max_pids = 256
    with pytest.raises(ValidationError):
        RuntimeConfig.model_validate(
            {
                **config.model_dump(),
                "workspace_uuid": "workspace-a",
            }
        )


def test_runtime_config_default_wire_payload_is_compatible_with_legacy_policy_shape():
    class LegacyPluginWorkerPolicy(pydantic.BaseModel):
        max_cpus: float
        max_memory_mb: int
        max_pids: int
        max_open_files: int
        max_file_size_mb: int
        max_workers: int = 16
        max_total_cpus: float = 8.0
        max_total_memory_mb: int = 8192
        max_installations: int = 10_000
        max_concurrent_restarts: int = 1
        restart_failure_threshold: int = 8
        restart_failure_window_seconds: float = 30.0
        restart_circuit_open_seconds: float = 60.0
        require_hard_limits: bool = False

        model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    config = RuntimeConfig(
        runtime_identity=RuntimeIdentity(
            instance_uuid="instance-1",
            runtime_id="runtime-boot-1",
        ),
        worker_policy=PluginWorkerPolicy(
            max_cpus=1.0,
            max_memory_mb=512,
            max_pids=128,
            max_open_files=256,
            max_file_size_mb=512,
            max_pending_registrations=77,
        ),
        runtime_profile="shared",
    )

    wire_payload = config.model_dump()

    assert "max_pending_registrations" not in wire_payload["worker_policy"]
    assert LegacyPluginWorkerPolicy.model_validate(wire_payload["worker_policy"])
    assert (
        RuntimeConfig.model_validate(
            wire_payload
        ).worker_policy.max_pending_registrations
        == 1024
    )
    assert (
        config.model_dump(include_pending_registration_limit=True)["worker_policy"][
            "max_pending_registrations"
        ]
        == 77
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "restart_failure_threshold",
            10_001,
            "cannot exceed max_installations",
        ),
        (
            "restart_failure_window_seconds",
            3601,
            "cannot exceed 3600",
        ),
        (
            "restart_circuit_open_seconds",
            3601,
            "cannot exceed 3600",
        ),
    ],
)
def test_worker_restart_policy_rejects_unsafe_limits(field, value, message):
    policy = {
        "max_cpus": 1.0,
        "max_memory_mb": 512,
        "max_pids": 128,
        "max_open_files": 256,
        "max_file_size_mb": 512,
        field: value,
    }

    with pytest.raises(ValidationError, match=message):
        PluginWorkerPolicy.model_validate(policy)


def test_worker_restart_concurrency_is_not_capped_by_aggregate_worker_capacity():
    policy = PluginWorkerPolicy(
        max_cpus=1.0,
        max_memory_mb=512,
        max_pids=128,
        max_open_files=256,
        max_file_size_mb=512,
        max_workers=1,
        max_total_cpus=1.0,
        max_total_memory_mb=512,
        max_concurrent_restarts=8,
    )

    assert policy.effective_worker_capacity == 1
    assert policy.max_concurrent_restarts == 8


def test_pending_registration_bound_is_independent_from_worker_capacity():
    policy = PluginWorkerPolicy(
        max_cpus=1.0,
        max_memory_mb=512,
        max_pids=128,
        max_open_files=256,
        max_file_size_mb=512,
        max_workers=1,
        max_total_cpus=1.0,
        max_total_memory_mb=512,
        max_pending_registrations=3,
    )

    assert policy.effective_worker_capacity == 1
    assert policy.max_pending_registrations == 3


@pytest.mark.parametrize(
    "payload",
    [
        {
            "installation_uuid": "",
            "runtime_revision": 1,
            "artifact_digest": ARTIFACT_DIGEST,
        },
        {
            "installation_uuid": "installation-1",
            "runtime_revision": "1",
            "artifact_digest": ARTIFACT_DIGEST,
        },
        {
            "installation_uuid": "installation-1",
            "runtime_revision": 0,
            "artifact_digest": ARTIFACT_DIGEST,
        },
        {
            "installation_uuid": "installation-1",
            "runtime_revision": 1,
            "artifact_digest": "not-a-sha256",
        },
    ],
)
def test_installation_binding_rejects_incomplete_worker_tuple(payload):
    with pytest.raises(ValidationError):
        InstallationBinding.model_validate(
            {
                "instance_uuid": "instance-1",
                "workspace_uuid": "workspace-a",
                "placement_generation": 1,
                **payload,
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_cpus", 0),
        ("max_cpus", "1.0"),
        ("max_cpus", float("nan")),
        ("max_cpus", float("inf")),
        ("max_memory_mb", 0),
        ("max_memory_mb", "512"),
        ("max_pids", -1),
        ("max_open_files", False),
        ("max_file_size_mb", 0),
    ],
)
def test_plugin_worker_policy_rejects_non_positive_limits(field, value):
    payload = {
        "max_cpus": 1.0,
        "max_memory_mb": 512,
        "max_pids": 128,
        "max_open_files": 256,
        "max_file_size_mb": 512,
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        PluginWorkerPolicy.model_validate(payload)


def test_desired_state_protocol_requires_unique_complete_bindings():
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-1",
        runtime_revision=1,
        artifact_digest=ARTIFACT_DIGEST,
    )
    desired = PluginInstallationDesiredState(binding=binding, enabled=True)

    request = ReconcilePluginInstallationsRequest(installations=(desired,))

    assert request.installations == (desired,)
    assert desired.execution_mode is PluginExecutionMode.DEDICATED
    assert (
        PluginInstallationDesiredState(
            binding=binding,
            execution_mode="shared-runtime-v1",
        ).execution_mode
        is PluginExecutionMode.SHARED_CERTIFIED
    )
    assert ApplyPluginInstallationRequest(artifact_file_key=None).enabled is True
    assert (
        ApplyPluginInstallationRequest(artifact_file_key=None).execution_mode
        is PluginExecutionMode.DEDICATED
    )
    assert PluginExecutionMode.SHARED_CERTIFIED.value == "shared-runtime-v1"
    with pytest.raises(ValidationError):
        PluginInstallationDesiredState(
            binding=binding,
            execution_mode="shared_certified",
        )
    with pytest.raises(ValidationError, match="unique installation_uuid"):
        ReconcilePluginInstallationsRequest(installations=(desired, desired))


@pytest.mark.parametrize(
    "payload",
    [
        {
            "instance_uuid": "",
            "workspace_uuid": "workspace-a",
            "placement_generation": 1,
        },
        {
            "instance_uuid": "instance-1",
            "workspace_uuid": "",
            "placement_generation": 1,
        },
        {
            "instance_uuid": "instance-1",
            "workspace_uuid": "workspace-a",
            "placement_generation": 0,
        },
    ],
)
def test_action_context_rejects_incomplete_or_unfenced_binding(payload):
    with pytest.raises(ValidationError):
        ActionContext.model_validate(payload)


def test_action_response_success_error_and_chunk_serialization():
    success = ActionResponse.success({"ok": True})
    assert success.seq_id == 0
    assert success.code == 0
    assert success.message == "success"
    assert success.model_dump()["chunk_status"] == "continue"

    error = ActionResponse.error("boom")
    assert error.seq_id is None
    assert error.code == 1
    assert error.data == {}

    end = ActionResponse(
        seq_id=99,
        code=0,
        message="done",
        data={},
        chunk_status=ChunkStatus.END,
    )
    dumped = end.model_dump()
    assert dumped["chunk_status"] == "end"
    assert ActionResponse.model_validate(dumped).chunk_status is ChunkStatus.END


def test_action_response_normalizes_missing_chunk_status_to_continue():
    response = ActionResponse(
        seq_id=1, code=0, message="ok", data={}, chunk_status=None
    )
    assert response.chunk_status is ChunkStatus.CONTINUE


def test_protocol_error_messages_are_stable_strings():
    assert str(ConnectionClosedError("closed")) == "closed"
    assert str(ActionCallTimeoutError("slow")) == "slow"
    assert str(ActionCallError("failed")) == "failed"


def test_action_values_are_unique_inside_each_protocol_direction():
    for action_group in (
        CommonAction,
        PluginToRuntimeAction,
        RuntimeToPluginAction,
        LangBotToRuntimeAction,
        RuntimeToLangBotAction,
    ):
        values = [action.value for action in action_group]
        assert len(values) == len(set(values)), action_group.__name__
