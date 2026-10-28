from __future__ import annotations

from typing import AsyncGenerator

from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.entities.builtin.command.context import (
    CommandReturn,
    ExecuteContext,
)

from powercontext_client import PowerContextError
from scope import binding_key


def _error_text(exc: Exception) -> str:
    if isinstance(exc, PowerContextError):
        return exc.safe_summary()
    return str(exc)[:300] or exc.__class__.__name__


class PowerContext(Command):
    def __init__(self) -> None:
        super().__init__()

        @self.subcommand(
            name="",
            help="Show PowerContext configuration and resolved Scope",
            usage="!powercontext",
            aliases=[],
        )
        async def root(
            self: PowerContext,
            context: ExecuteContext,
        ) -> AsyncGenerator[CommandReturn, None]:
            settings = self.plugin.settings()
            lines = ["[PowerContext]"]
            lines.append(f"Server: {settings.server_url}")
            lines.append(f"Scope mode: {settings.scope_mode}")
            lines.append(f"Explicit Scope: {settings.explicit_scope_id or '(none)'}")
            lines.append(f"Default Scope fallback: {settings.allow_default_scope}")
            lines.append(f"Automatic recall: {settings.auto_recall}")
            lines.append(f"Source capture: {settings.capture_user_messages}")
            try:
                resolved = await self.plugin.resolve_query(
                    session=context.session,
                    query_id=context.query_id,
                    query_uuid=context.query_uuid,
                )
                lines.append(f"Resolved Scope: {resolved.scope_id}")
            except Exception as exc:
                lines.append(f"Resolved Scope: unavailable ({_error_text(exc)})")
            lines.append("Commands: !powercontext health | bind <scope_id> | clear")
            yield CommandReturn(text="\n".join(lines))

        @self.subcommand(
            name="health",
            help="Check Server reachability and Scope resolution",
            usage="!powercontext health",
            aliases=["h"],
        )
        async def health(
            self: PowerContext,
            context: ExecuteContext,
        ) -> AsyncGenerator[CommandReturn, None]:
            lines = ["[PowerContext Health]"]
            try:
                response = await self.plugin.settings().new_client().liveness()
                lines.append(f"- OK: Server {response.data.get('status', 'live')}")
            except Exception as exc:
                lines.append(f"- ERROR: Server unavailable ({_error_text(exc)})")
            try:
                resolved = await self.plugin.resolve_query(
                    session=context.session,
                    query_id=context.query_id,
                    query_uuid=context.query_uuid,
                )
                lines.append(f"- OK: Scope {resolved.scope_id}")
            except Exception as exc:
                lines.append(f"- ERROR: Scope unresolved ({_error_text(exc)})")
            yield CommandReturn(text="\n".join(lines))

        @self.subcommand(
            name="bind",
            help="Bind the current LangBot identity to an existing PowerContext Scope",
            usage="!powercontext bind <scope_id>",
            aliases=[],
        )
        async def bind(
            self: PowerContext,
            context: ExecuteContext,
        ) -> AsyncGenerator[CommandReturn, None]:
            if context.privilege < 2:
                yield CommandReturn(
                    text="Error: administrator privilege is required to change Scope bindings."
                )
                return
            if len(context.crt_params) != 1 or not context.crt_params[0].strip():
                yield CommandReturn(text="Usage: !powercontext bind <scope_id>")
                return
            scope_id = context.crt_params[0].strip()
            settings = self.plugin.settings()
            try:
                identity = await self.plugin.query_identity(
                    session=context.session,
                    query_id=context.query_id,
                    query_uuid=context.query_uuid,
                )
                key = binding_key(identity, settings.scope_mode)
                response = await settings.new_client().set_scope_binding(
                    key=key, scope_id=scope_id
                )
                bound_scope = response.data.get("scope_id")
                if bound_scope != scope_id:
                    raise ValueError("PowerContext returned an unexpected binding")
            except Exception as exc:
                yield CommandReturn(text=f"Error: {_error_text(exc)}")
                return
            yield CommandReturn(
                text=f"Bound current {settings.scope_mode} identity to Scope {scope_id}."
            )

        @self.subcommand(
            name="clear",
            help="Clear the current LangBot identity's PowerContext Scope binding",
            usage="!powercontext clear",
            aliases=[],
        )
        async def clear(
            self: PowerContext,
            context: ExecuteContext,
        ) -> AsyncGenerator[CommandReturn, None]:
            if context.privilege < 2:
                yield CommandReturn(
                    text="Error: administrator privilege is required to change Scope bindings."
                )
                return
            settings = self.plugin.settings()
            try:
                identity = await self.plugin.query_identity(
                    session=context.session,
                    query_id=context.query_id,
                    query_uuid=context.query_uuid,
                )
                key = binding_key(identity, settings.scope_mode)
                response = await settings.new_client().clear_scope_binding(key=key)
            except Exception as exc:
                yield CommandReturn(text=f"Error: {_error_text(exc)}")
                return
            status = "cleared" if response.data.get("cleared") else "not present"
            yield CommandReturn(
                text=f"Current {settings.scope_mode} binding: {status}."
            )
