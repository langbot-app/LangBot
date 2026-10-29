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
            conversation_id = conversation_id_from_command(context)
            await delete_value(self.plugin, storage_key("selected", conversation_id))
            await delete_value(self.plugin, storage_key("last", conversation_id))
            await delete_value(self.plugin, storage_key("list", conversation_id))
            await context.create_new_conversation()
            yield CommandReturn(
                text=_text(
                    self,
                    "✅ 已创建新会话。旧的 OpenCode 会话仍然保留，可通过 !list 查看并切换。",
                    "✅ A new session will be created. The previous OpenCode session is still available in !list.",
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
                yield CommandReturn(text=_text(self, "当前没有 OpenCode 会话。", "No OpenCode sessions found."))
                return
            current_id = str(current.get("session_id") or "")
            lines = [_text(self, "OpenCode 会话：", "OpenCode sessions:")]
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
            await write_json(self.plugin, storage_key("selected", conversation_id), {"session_id": target})
            await context.create_new_conversation()
            yield CommandReturn(text=_text(self, f"✅ 已切换到会话：{target}", f"✅ Switched to session: {target}"))


class DeleteSession(Command):
    async def initialize(self) -> None:
        await super().initialize()

        @self.subcommand(name="", help="Delete current ACP session", usage="delete")
        async def _(self: DeleteSession, context: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            conversation_id, control, current = await _conversation_state(self, context)
            session_id = str(current.get("session_id") or "").strip()
            if not session_id:
                yield CommandReturn(
                    text=_text(
                        self, "当前没有可删除的 OpenCode 会话。", "There is no current OpenCode session to delete."
                    )
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
            await delete_value(self.plugin, storage_key("selected", conversation_id))
            await delete_value(self.plugin, storage_key("last", conversation_id))
            await delete_value(self.plugin, storage_key("list", conversation_id))
            await context.create_new_conversation()
            yield CommandReturn(
                text=_text(
                    self,
                    f"✅ 已删除当前 OpenCode 会话：{session_id}",
                    f"✅ Deleted current OpenCode session: {session_id}",
                )
            )


class StopRun(Command):
    async def initialize(self) -> None:
        await super().initialize()

        @self.subcommand(name="", help="Stop the active run", usage="stop")
        async def _(self: StopRun, context: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            run_id = await context.get_query_var("_acp_stop_run_id")
            if run_id:
                yield CommandReturn(
                    text=_text(
                        self,
                        "⏹️ 已停止当前任务，OpenCode 会话已保留。",
                        "⏹️ The active task was stopped. The OpenCode session was preserved.",
                    )
                )
            else:
                yield CommandReturn(text=_text(self, "当前没有正在执行的任务。", "There is no active task."))
