from __future__ import annotations

from typing import AsyncGenerator

from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.entities.builtin.command.context import (
    ExecuteContext,
    CommandReturn,
)

# privilege levels (from LangBot command manager): 1 = normal, 2 = admin
PRIVILEGE_ADMIN = 2


class MCBot(Command):
    """Minecraft server helper command.

    Subcommands:
      !mcbot                  show help
      !mcbot bind <addr[:port]>   bind a server to this group (admin only)
      !mcbot unbind               unbind the server (admin only)
      !mcbot status               show live server status & online players
      !mcbot time [minutes]       show per-player playtime (default 1440 = 24h)
    """

    def __init__(self):
        super().__init__()

        @self.subcommand(
            name="",
            help="Show MCBot help",
            usage="mcbot",
        )
        async def root(
            self, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            yield CommandReturn(text=self._help_text())

        @self.subcommand(
            name="bind",
            help="Bind a Minecraft server to this group (admin only)",
            usage="mcbot bind <address[:port]>",
        )
        async def bind(
            self, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            if ctx.privilege < PRIVILEGE_ADMIN:
                yield CommandReturn(text="[MCBot] 仅管理员可执行绑定操作。")
                return
            if not ctx.crt_params:
                yield CommandReturn(
                    text="[MCBot] 参数错误。用法：!mcbot bind <地址[:端口]>"
                )
                return
            server_addr = ctx.crt_params[0].strip()
            group_key = self.plugin.group_key(
                ctx.session.launcher_type.value, ctx.session.launcher_id
            )
            await self.plugin.bind_server(group_key, server_addr)
            yield CommandReturn(text=f"[MCBot] 绑定成功：{server_addr}")

        @self.subcommand(
            name="unbind",
            help="Unbind the Minecraft server from this group (admin only)",
            usage="mcbot unbind",
        )
        async def unbind(
            self, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            if ctx.privilege < PRIVILEGE_ADMIN:
                yield CommandReturn(text="[MCBot] 仅管理员可执行解绑操作。")
                return
            group_key = self.plugin.group_key(
                ctx.session.launcher_type.value, ctx.session.launcher_id
            )
            ok = await self.plugin.unbind_server(group_key)
            if ok:
                yield CommandReturn(text="[MCBot] 解绑成功。")
            else:
                yield CommandReturn(text="[MCBot] 当前未绑定服务器。")

        @self.subcommand(
            name="status",
            help="Show live server status and online players",
            usage="mcbot status",
        )
        async def status(
            self, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            group_key = self.plugin.group_key(
                ctx.session.launcher_type.value, ctx.session.launcher_id
            )
            server_addr = await self.plugin.get_bound_server(group_key)
            if not server_addr:
                yield CommandReturn(text="[MCBot] 当前未绑定服务器。")
                return
            try:
                info = await self.plugin.ping_server(server_addr)
            except Exception as e:
                yield CommandReturn(
                    text=f"[MCBot] 查询失败：{server_addr} 无法连接（{e}）"
                )
                return

            players = info["players"]
            if players:
                player_str = "\n".join(players)
            elif info["online"] > 0:
                player_str = f"(共 {info['online']} 人在线，服务器未公开名单)"
            else:
                player_str = "(无玩家在线)"

            text = (
                f"[MCBot] {server_addr}\n"
                f"{info['motd']}\n"
                f"版本: {info['version']}\n"
                f"在线: {info['online']}/{info['max']}\n"
                f"玩家:\n{player_str}"
            )
            yield CommandReturn(text=text)

        @self.subcommand(
            name="time",
            help="Show per-player playtime over the last N minutes (default 1440)",
            usage="mcbot time [minutes]",
        )
        async def time_(
            self, ctx: ExecuteContext
        ) -> AsyncGenerator[CommandReturn, None]:
            group_key = self.plugin.group_key(
                ctx.session.launcher_type.value, ctx.session.launcher_id
            )
            server_addr = await self.plugin.get_bound_server(group_key)
            if not server_addr:
                yield CommandReturn(text="[MCBot] 当前未绑定服务器。")
                return

            period = 24 * 60
            if ctx.crt_params:
                try:
                    period = int(ctx.crt_params[0])
                    if period <= 0:
                        yield CommandReturn(text="[MCBot] 时长必须为正整数（分钟）。")
                        return
                except ValueError:
                    yield CommandReturn(
                        text="[MCBot] 参数错误。用法：!mcbot time [分钟数]"
                    )
                    return

            stats = await self.plugin.count_playtime(server_addr, period)
            if not stats:
                yield CommandReturn(
                    text=f"[MCBot] 最近 {period} 分钟内暂无在线记录。"
                )
                return

            lines = [
                f"{player}: {int(seconds / 60)} 分钟"
                for player, seconds in stats
            ]
            text = (
                f"[MCBot] 在线时长统计（最近 {period} 分钟）\n"
                + "\n".join(lines)
            )
            yield CommandReturn(text=text)

    @staticmethod
    def _help_text() -> str:
        return (
            "[MCBot] Minecraft 服务器助手\n"
            "!mcbot bind <地址[:端口]> - 绑定服务器到本群（管理员）\n"
            "!mcbot unbind - 解绑服务器（管理员）\n"
            "!mcbot status - 查看服务器状态与在线玩家\n"
            "!mcbot time [分钟] - 查看在线时长统计（默认 1440）"
        )
