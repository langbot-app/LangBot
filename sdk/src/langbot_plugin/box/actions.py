"""Box-specific action types for the action RPC protocol."""

from __future__ import annotations

from langbot_plugin.entities.io.actions.enums import ActionType


class LangBotToBoxAction(ActionType):
    """Actions sent from LangBot to the Box runtime."""

    INIT = "box_init"  # Initialize with full box config (highest priority)
    UPSERT_SANDBOX_ADMISSION_GRANT = "box_upsert_sandbox_admission_grant"
    REVOKE_SANDBOX_ADMISSION_GRANT = "box_revoke_sandbox_admission_grant"
    VERIFY_SHARED_WORKSPACE = "box_verify_shared_workspace"
    HEALTH = "box_health"
    STATUS = "box_status"
    EXEC = "box_exec"
    CREATE_SESSION = "box_create_session"
    GET_SESSION = "box_get_session"
    GET_SESSIONS = "box_get_sessions"
    DELETE_SESSION = "box_delete_session"
    START_MANAGED_PROCESS = "box_start_managed_process"
    GET_MANAGED_PROCESS = "box_get_managed_process"
    STOP_MANAGED_PROCESS = "box_stop_managed_process"
    GET_BACKEND_INFO = "box_get_backend_info"
    GET_STORAGE_ANALYSIS = "box_get_storage_analysis"
    SHUTDOWN = "box_shutdown"
