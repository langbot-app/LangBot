# WordFSRS `!word` command — single root command with subcommands.
from __future__ import annotations

from typing import AsyncGenerator

from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.entities.builtin.command.context import (
    ExecuteContext,
    CommandReturn,
)


class WordCommand(Command):

    async def initialize(self) -> None:
        await super().initialize()

        @self.subcommand("add", help="Add a word: !word add <word> [meaning]")
        async def add(
            cmd: WordCommand, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            sid = _session_id(ctx)
            if not ctx.crt_params:
                yield CommandReturn(text=cmd.plugin.t("cmd.add_usage"))
                return
            word = ctx.crt_params[0]
            meaning = " ".join(ctx.crt_params[1:])
            _created, msg = await cmd.plugin.add_word(sid, word, meaning)
            yield CommandReturn(text=msg)

        @self.subcommand("review", help="Next due word", aliases=["next", "r"])
        async def review(
            cmd: WordCommand, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            sid = _session_id(ctx)
            _key, msg = await cmd.plugin.next_due(sid)
            yield CommandReturn(text=msg)

        @self.subcommand("show", help="Show a word's meaning: !word show <word>", aliases=["answer"])
        async def show(
            cmd: WordCommand, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            sid = _session_id(ctx)
            if not ctx.crt_params:
                yield CommandReturn(text=cmd.plugin.t("cmd.show_usage"))
                return
            yield CommandReturn(text=await cmd.plugin.show_answer(sid, ctx.crt_params[0]))

        @self.subcommand(
            "grade", help="Grade recall: !word grade <word> <1-4>", aliases=["g", "rate"]
        )
        async def grade(
            cmd: WordCommand, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            sid = _session_id(ctx)
            if len(ctx.crt_params) < 2:
                yield CommandReturn(text=cmd.plugin.t("cmd.grade_usage"))
                return
            word = ctx.crt_params[0]
            rating = ctx.crt_params[1]
            yield CommandReturn(text=await cmd.plugin.grade(sid, word, rating))

        @self.subcommand("stats", help="Show statistics", aliases=["stat", "s"])
        async def stats(
            cmd: WordCommand, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            sid = _session_id(ctx)
            yield CommandReturn(text=await cmd.plugin.stats(sid))

        @self.subcommand("list", help="List the deck: !word list [page]", aliases=["ls"])
        async def list_(
            cmd: WordCommand, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            sid = _session_id(ctx)
            page = 1
            if ctx.crt_params:
                try:
                    page = int(ctx.crt_params[0])
                except ValueError:
                    page = 1
            yield CommandReturn(text=await cmd.plugin.list_words(sid, page))

        @self.subcommand("del", help="Delete a word: !word del <word>", aliases=["delete", "rm"])
        async def del_(
            cmd: WordCommand, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            sid = _session_id(ctx)
            if not ctx.crt_params:
                yield CommandReturn(text=cmd.plugin.t("cmd.del_usage"))
                return
            yield CommandReturn(text=await cmd.plugin.remove_word(sid, ctx.crt_params[0]))

        @self.subcommand("help", help="Show help", aliases=["h"])
        async def help_(
            cmd: WordCommand, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            yield CommandReturn(text=cmd.plugin.t("help"))

        # Bare `!word` with no/unknown subcommand -> show help.
        @self.subcommand("*")
        async def fallback(
            cmd: WordCommand, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            yield CommandReturn(text=cmd.plugin.t("help"))


def _session_id(ctx: ExecuteContext) -> str:
    """Stable per-conversation key: '{launcher_type}:{launcher_id}'."""
    session = ctx.session
    ltype = session.launcher_type
    ltype_val = getattr(ltype, "value", ltype)
    return f"{ltype_val}:{session.launcher_id}"
