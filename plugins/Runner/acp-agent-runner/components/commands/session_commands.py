"""Commands for managing ACP sessions owned by the current IM conversation."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.entities.builtin.command.context import CommandReturn, ExecuteContext
from pkg.session_management import (
    conversation_id_from_command,
    delete_value,
    normalize_sessions,
    read_json,
    resolve_session_target,
    run_daemon_control,
    storage_key,
    write_json,
)


def _language(component: Command) -> str:
    return str(component.get_plugin_config().get("language") or "zh_Hans")


def _text(component: Command, zh: str, en: str) -> str:
    return zh if _language(component).startswith("zh") else en


def _group_admin_required(context: ExecuteContext) -> bool:
    launcher_type = getattr(getattr(context, "session", None), "launcher_type", None)
    launcher_type = getattr(launcher_type, "value", launcher_type)
    return launcher_type == "group" and context.privilege < 2


def _group_admin_message(component: Command) -> str:
    return _text(
        component,
        "群聊中的会话变更仅允许机器人管理员执行。",
        "Only bot administrators can change ACP sessions in group chats.",
    )


async def _clear_session_values(component: Command, conversation_id: str) -> None:
    for kind in ("selected", "last", "list"):
        await delete_value(component.plugin, storage_key(kind, conversation_id))


async def _session_values(component: Command, conversation_id: str) -> dict[str, object]:
    return {
        kind: await read_json(component.plugin, storage_key(kind, conversation_id), None)
        for kind in ("selected", "last", "list")
    }


async def _restore_session_values(
    component: Command,
    conversation_id: str,
    values: dict[str, object],
) -> None:
    for kind, value in values.items():
        key = storage_key(kind, conversation_id)
        if value is None:
            await delete_value(component.plugin, key)
        else:
            await write_json(component.plugin, key, value)


async def _conversation_state(component: Command, context: ExecuteContext):
    conversation_id = conversation_id_from_command(context)
    control = await read_json(component.plugin, storage_key("control", conversation_id), {})
    selected = await read_json(component.plugin, storage_key("selected", conversation_id), {})
    last = await read_json(component.plugin, storage_key("last", conversation_id), {})
    current = selected if isinstance(selected, dict) and selected.get("session_id") else last
    return conversation_id, control if isinstance(control, dict) else {}, current if isinstance(current, dict) else {}


class NewSession(Command):
    async def initialize(self) -> None:
        await super().initialize()

        @self.subcommand(name="", help="Create a new ACP session", usage="new")
        async def _(self: NewSession, context: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            if _group_admin_required(context):
                yield CommandReturn(text=_group_admin_message(self))
                return
            conversation_id = conversation_id_from_command(context)
            try:
                previous_values = await _session_values(self, conversation_id)
                await _clear_session_values(self, conversation_id)
                await context.create_new_conversation()
            except Exception as exc:
                try:
                    if "previous_values" in locals():
                        await _restore_session_values(self, conversation_id, previous_values)
                except Exception as rollback_exc:
                    exc = RuntimeError(f"{exc}; local state rollback also failed: {rollback_exc}")
                yield CommandReturn(
                    text=_text(
                        self,
                        f"新建会话失败，原会话状态已保留或需要管理员协调：{exc}",
                        f"Failed to create a new session; the previous state was preserved or needs reconciliation: {exc}",
                    )
                )
                return
            yield CommandReturn(
                text=_text(
                    self,
                    "✅ 下一条普通消息将创建新的 ACP 会话。旧会话仍然保留，可通过 !list 查看并切换。",
                    "✅ The next normal message will create a new ACP session. Previous sessions remain available in !list.",
                )
            )


class ListSessions(Command):
    async def initialize(self) -> None:
        await super().initialize()

        @self.subcommand(name="", help="List ACP sessions", usage="list")
        async def _(self: ListSessions, context: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            conversation_id, control, current = await _conversation_state(self, context)
            if not control:
                yield CommandReturn(
                    text=_text(
                        self,
                        "当前会话尚未初始化 ACP 配置，请先发送一条普通消息。",
                        "ACP session configuration is not initialized. Send one normal message first.",
                    )
                )
                return
            try:
                result = await run_daemon_control(
                    self.plugin,
                    control,
                    "session.list",
                    cwd=control.get("session_cwd") or control.get("workspace"),
                )
            except Exception as exc:
                yield CommandReturn(text=_text(self, f"查询会话失败：{exc}", f"Failed to list sessions: {exc}"))
                return
            sessions = normalize_sessions(result)
            await write_json(self.plugin, storage_key("list", conversation_id), sessions)
            if not sessions:
                yield CommandReturn(
                    text=_text(self, "当前没有可管理的 ACP 会话。", "No manageable ACP sessions found.")
                )
                return
            current_id = str(current.get("session_id") or "")
            lines = [_text(self, "ACP 会话：", "ACP sessions:")]
            for index, item in enumerate(sessions[:20], start=1):
                marker = " ★" if item["session_id"] == current_id else ""
                updated = item["updated_at"].replace("T", " ").replace("Z", "")[:16]
                lines.append(f"{index}. {updated}  {item['title']}{marker}")
            lines.append(
                _text(
                    self,
                    "\n使用 !switch <序号> 切换，!new 新建，!delete 删除当前会话。",
                    "\nUse !switch <number>, !new, or !delete.",
                )
            )
            yield CommandReturn(text="\n".join(lines))


class SwitchSession(Command):
    async def initialize(self) -> None:
        await super().initialize()

        @self.subcommand(name="*", help="Switch ACP session", usage="switch <number|session_id>")
        async def _(self: SwitchSession, context: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            if _group_admin_required(context):
                yield CommandReturn(text=_group_admin_message(self))
                return
            reference = context.crt_params[0] if context.crt_params else ""
            if not reference:
                yield CommandReturn(
                    text=_text(self, "用法：!switch <序号或 ses_xxx>", "Usage: !switch <number or ses_xxx>")
                )
                return
            conversation_id, control, _current = await _conversation_state(self, context)
            if not control:
                yield CommandReturn(
                    text=_text(self, "请先发送一条普通消息初始化会话。", "Send one normal message first.")
                )
                return
            capabilities = control.get("session_capabilities")
            if not isinstance(capabilities, dict) or not any(
                capabilities.get(method) is True for method in ("session/load", "session/resume")
            ):
                yield CommandReturn(
                    text=_text(
                        self,
                        "当前 ACP 客户端不支持跨进程恢复 session，无法切换会话。",
                        "The ACP client does not support cross-process session recovery; switching is unavailable.",
                    )
                )
                return
            try:
                result = await run_daemon_control(
                    self.plugin,
                    control,
                    "session.list",
                    cwd=control.get("session_cwd") or control.get("workspace"),
                )
            except Exception as exc:
                yield CommandReturn(text=_text(self, f"查询会话失败：{exc}", f"Failed to list sessions: {exc}"))
                return
            sessions = normalize_sessions(result)
            await write_json(self.plugin, storage_key("list", conversation_id), sessions)
            target = resolve_session_target(reference, sessions)
            if not target:
                yield CommandReturn(
                    text=_text(self, "找不到指定会话，请先使用 !list。", "Session not found. Run !list first.")
                )
                return
            selected_key = storage_key("selected", conversation_id)
            try:
                previous_selected = await read_json(self.plugin, selected_key, None)
                await write_json(self.plugin, selected_key, {"session_id": target})
                await context.create_new_conversation()
            except Exception as exc:
                try:
                    if "previous_selected" in locals():
                        if previous_selected is None:
                            await delete_value(self.plugin, selected_key)
                        else:
                            await write_json(self.plugin, selected_key, previous_selected)
                except Exception as rollback_exc:
                    exc = RuntimeError(f"{exc}; selected-session rollback also failed: {rollback_exc}")
                yield CommandReturn(text=_text(self, f"切换会话失败：{exc}", f"Failed to switch ACP session: {exc}"))
                return
            yield CommandReturn(text=_text(self, f"✅ 已切换到会话：{target}", f"✅ Switched to session: {target}"))


class DeleteSession(Command):
    async def initialize(self) -> None:
        await super().initialize()

        @self.subcommand(name="", help="Delete current ACP session", usage="delete")
        async def _(self: DeleteSession, context: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            if _group_admin_required(context):
                yield CommandReturn(text=_group_admin_message(self))
                return
            conversation_id, control, current = await _conversation_state(self, context)
            session_id = str(current.get("session_id") or "").strip()
            if not session_id:
                yield CommandReturn(
                    text=_text(self, "当前没有可删除的 ACP 会话。", "There is no current ACP session to delete.")
                )
                return
            try:
                await run_daemon_control(
                    self.plugin,
                    control,
                    "session.delete",
                    session_id=session_id,
                )
            except Exception as exc:
                yield CommandReturn(
                    text=_text(
                        self,
                        f"删除会话失败，当前绑定未清理：{exc}",
                        f"Delete failed; current binding was preserved: {exc}",
                    )
                )
                return
            try:
                await _clear_session_values(self, conversation_id)
            except Exception as exc:
                yield CommandReturn(
                    text=_text(
                        self,
                        f"远端 ACP 会话已删除，但本地绑定清理失败；请勿继续使用该会话并联系管理员处理：{exc}",
                        "The remote ACP session was deleted, but local binding cleanup failed. "
                        f"Do not continue using this session; contact an administrator: {exc}",
                    )
                )
                return
            try:
                await context.create_new_conversation()
            except Exception as exc:
                yield CommandReturn(
                    text=_text(
                        self,
                        f"远端 ACP 会话及本地绑定已删除，但 Host 上下文重置失败；请联系管理员处理：{exc}",
                        "The remote ACP session and local binding were deleted, but the Host context reset failed. "
                        f"Contact an administrator: {exc}",
                    )
                )
                return
            yield CommandReturn(
                text=_text(
                    self,
                    f"✅ 已删除当前 ACP 会话：{session_id}",
                    f"✅ Deleted current ACP session: {session_id}",
                )
            )


class StopRun(Command):
    async def initialize(self) -> None:
        await super().initialize()

        @self.subcommand(name="", help="Stop the active run", usage="stop")
        async def _(self: StopRun, context: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            query_vars = await context.get_query_vars()
            if query_vars.get("_stop_command_denied"):
                yield CommandReturn(
                    text=_text(
                        self,
                        "当前活动任务由其他群成员发起，仅机器人管理员可以停止。",
                        "The active run belongs to another group member; only a bot administrator can stop it.",
                    )
                )
                return
            run_id = query_vars.get("_stop_command_run_id")
            if run_id:
                yield CommandReturn(
                    text=_text(
                        self,
                        "⏹️ 已停止当前任务，ACP 会话已保留。",
                        "⏹️ The active task was stopped. The ACP session was preserved.",
                    )
                )
            else:
                yield CommandReturn(text=_text(self, "当前没有正在执行的任务。", "There is no active task."))
