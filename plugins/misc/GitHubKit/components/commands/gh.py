# GitHubKit `!gh` command — single root command with subcommands.
from __future__ import annotations

import os
import sys
from typing import AsyncGenerator

from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.entities.builtin.command.context import (
    ExecuteContext,
    CommandReturn,
)

# Allow importing the plugin-level EVENT_ALIASES helper.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
try:
    from main import EVENT_ALIASES
except Exception:  # pragma: no cover - fallback if import path differs
    EVENT_ALIASES = {}


def _sid(ctx: ExecuteContext) -> str:
    s = ctx.session
    lt = getattr(s.launcher_type, "value", s.launcher_type)
    return f"{lt}:{s.launcher_id}"


class GhCommand(Command):

    async def initialize(self) -> None:
        await super().initialize()

        @self.subcommand("repo", help="Repo info: !gh repo <owner/repo>", aliases=["r"])
        async def repo(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            arg = ctx.crt_params[0] if ctx.crt_params else ""
            yield CommandReturn(text=await cmd.plugin.repo_info(arg))

        @self.subcommand("issues", help="Issue list: !gh issues <owner/repo> [state]")
        async def issues(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            if not ctx.crt_params:
                yield CommandReturn(text=cmd.plugin.t("issues.usage"))
                return
            state = ctx.crt_params[1] if len(ctx.crt_params) > 1 else "open"
            yield CommandReturn(text=await cmd.plugin.list_issues(ctx.crt_params[0], state))

        @self.subcommand("prs", help="PR list: !gh prs <owner/repo> [state]", aliases=["pulls"])
        async def prs(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            if not ctx.crt_params:
                yield CommandReturn(text=cmd.plugin.t("prs.usage"))
                return
            state = ctx.crt_params[1] if len(ctx.crt_params) > 1 else "open"
            yield CommandReturn(text=await cmd.plugin.list_prs(ctx.crt_params[0], state))

        @self.subcommand("issue", help="Issue/PR detail: !gh issue <owner/repo> <number>", aliases=["pr"])
        async def issue(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            if len(ctx.crt_params) < 2:
                yield CommandReturn(text=cmd.plugin.t("issue.usage"))
                return
            yield CommandReturn(text=await cmd.plugin.issue_detail(ctx.crt_params[0], ctx.crt_params[1]))

        @self.subcommand("releases", help="Release list: !gh releases <owner/repo>", aliases=["rel"])
        async def releases(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            arg = ctx.crt_params[0] if ctx.crt_params else ""
            yield CommandReturn(text=await cmd.plugin.releases(arg))

        @self.subcommand("user", help="User info: !gh user <username>", aliases=["u"])
        async def user(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            arg = ctx.crt_params[0] if ctx.crt_params else ""
            yield CommandReturn(text=await cmd.plugin.user_info(arg))

        @self.subcommand("search", help="Search repos: !gh search <keyword>", aliases=["s"])
        async def search(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            q = " ".join(ctx.crt_params)
            yield CommandReturn(text=await cmd.plugin.search_repos(q))

        @self.subcommand("sub", help="Subscribe events: !gh sub <owner/repo> [events]", aliases=["subscribe", "watch"])
        async def sub(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            if not ctx.crt_params:
                yield CommandReturn(text=cmd.plugin.t("sub.usage"))
                return
            repo_arg = ctx.crt_params[0]
            raw_events = ctx.crt_params[1:]
            events = None
            if raw_events:
                mapped = []
                for e in raw_events:
                    k = EVENT_ALIASES.get(e.strip().lower())
                    if k and k not in mapped:
                        mapped.append(k)
                events = mapped or None
            bot_uuid = await ctx.get_bot_uuid()
            s = ctx.session
            target_type = getattr(s.launcher_type, "value", s.launcher_type)
            yield CommandReturn(
                text=await cmd.plugin.subscribe(
                    repo_arg, _sid(ctx), bot_uuid, target_type, str(s.launcher_id), events
                )
            )

        @self.subcommand("unsub", help="Unsubscribe: !gh unsub <owner/repo>", aliases=["unsubscribe", "unwatch"])
        async def unsub(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            arg = ctx.crt_params[0] if ctx.crt_params else ""
            yield CommandReturn(text=await cmd.plugin.unsubscribe(arg, _sid(ctx)))

        @self.subcommand("subs", help="List this chat's subscriptions", aliases=["subscriptions", "list"])
        async def subs(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            yield CommandReturn(text=await cmd.plugin.list_subscriptions(_sid(ctx)))

        @self.subcommand("help", help="Show help", aliases=["h"])
        async def help_(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            yield CommandReturn(text=cmd.plugin.t("help"))

        @self.subcommand("*")
        async def fallback(cmd: GhCommand, ctx: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
            yield CommandReturn(text=cmd.plugin.t("help"))
