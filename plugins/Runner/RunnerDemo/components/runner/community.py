"""Typed EBA handlers with deterministic, inspectable processing steps."""

from __future__ import annotations

import asyncio
import json

from langbot_plugin.api.definition.components.runner import (
    Runner,
    RunnerContext,
)
from langbot_plugin.api.entities.builtin.platform.events import (
    FeedbackReceivedEvent,
    FriendRequestReceivedEvent,
    MemberJoinedEvent,
    MemberLeftEvent,
    MessageReactionEvent,
    MessageReceivedEvent,
)
from langbot_plugin.api.entities.builtin.platform.message import Plain


def text(ctx: RunnerContext, english: str, chinese: str) -> str:
    return chinese if ctx.config.get("language", "zh_Hans") == "zh_Hans" else english


def name(user) -> str:
    return user.nickname or str(user.id)


async def reply(ctx: RunnerContext, content: str) -> None:
    await ctx.log(
        text(
            ctx,
            "Sending reply through the Host action API.",
            "通过服务端动作接口回复当前会话。",
        )
    )
    result = await ctx.reply(content)
    simulated = result.get("mock") is True or result.get("delivery") == "simulated"
    await ctx.log(
        text(
            ctx,
            "Mock reply completed; no real message sent."
            if simulated
            else "Reply action completed; see the action result for delivery details.",
            "Mock 回复完成，未发送真实消息。" if simulated else "回复动作已完成，投递情况请查看动作结果。",
        )
    )


class CommunityProcessor(Runner):
    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(MemberJoinedEvent)
        async def on_join(ctx: RunnerContext):
            event = ctx.platform_event
            await ctx.log(
                text(
                    ctx,
                    f"Member joined: {name(event.member)}; group={event.group.id}",
                    f"成员加入：{name(event.member)}；群组={event.group.id}",
                )
            )
            await self.profile(ctx, group=True)
            welcome = str(ctx.config.get("welcome_text", "欢迎加入！请友善交流，一起分享与学习。"))
            await reply(ctx, f"{name(event.member)}，{welcome}")
            await ctx.log(
                text(
                    ctx,
                    "Welcome workflow completed: receive → lookup → reply.",
                    "欢迎流程完成：接收事件 → 查询资料 → 回复欢迎消息。",
                )
            )

        @self.handler(MemberLeftEvent)
        async def on_leave(ctx: RunnerContext):
            event = ctx.platform_event
            reason = (
                text(ctx, "removed by an administrator", "被管理员移出")
                if event.is_kicked
                else text(ctx, "left voluntarily", "主动离开")
            )
            await ctx.log(
                text(
                    ctx,
                    f"{name(event.member)} {reason}; group={event.group.id}",
                    f"{name(event.member)} {reason}；群组={event.group.id}",
                ),
                "warning",
            )
            if ctx.config.get("announce_departures", False):
                await reply(
                    ctx,
                    text(
                        ctx,
                        f"{name(event.member)} has left the group.",
                        f"{name(event.member)} 已离开群组。",
                    ),
                )
            else:
                await ctx.log(
                    text(
                        ctx,
                        "Departure announcements are disabled; recorded only.",
                        "退群通知已关闭，本次仅记录日志。",
                    )
                )

        @self.handler(MessageReceivedEvent)
        async def on_message(ctx: RunnerContext):
            event = ctx.platform_event
            content = "".join(part.text for part in event.message_chain if isinstance(part, Plain)).strip()
            attachments = [part.type for part in event.message_chain if not isinstance(part, Plain)]
            await ctx.log(
                text(
                    ctx,
                    f"Message from {name(event.sender)}; attachments={attachments}",
                    f"收到 {name(event.sender)} 的消息；附件类型={attachments}",
                ),
                "debug",
            )
            prefix = str(ctx.config.get("command_prefix", "/demo")).strip() or "/demo"
            if content != prefix and not content.startswith(prefix + " "):
                await ctx.log(
                    text(
                        ctx,
                        f"No {prefix} command; no reply generated.",
                        f"未匹配 {prefix} 指令，本次不回复。",
                    )
                )
                return
            command, _, argument = content[len(prefix) :].strip().partition(" ")
            if command == "echo":
                await reply(
                    ctx,
                    argument.strip()
                    or text(
                        ctx,
                        "Type some text after echo.",
                        "请在 echo 后输入要回显的文字。",
                    ),
                )
            elif command == "profile":
                await self.profile(ctx, group=event.group is not None)
                await reply(
                    ctx,
                    text(
                        ctx,
                        f"Profile lookup completed for {name(event.sender)}. Details are in the action results.",
                        f"已查询 {name(event.sender)} 的资料，详情见动作结果。",
                    ),
                )
            elif command == "slow":
                delay = max(0, min(2000, int(ctx.config.get("delay_ms", 600))))
                await ctx.log(
                    text(
                        ctx,
                        f"Starting a {delay} ms demo task.",
                        f"开始演示任务，等待 {delay} ms。",
                    )
                )
                for step in range(1, 4):
                    await asyncio.sleep(delay / 3000)
                    await ctx.log(text(ctx, f"Progress {step}/3", f"处理进度 {step}/3"))
                await reply(ctx, text(ctx, "The demo task is complete.", "演示任务已完成。"))
            elif command == "fail":
                if not ctx.config.get("allow_demo_failure", False):
                    await ctx.log(
                        text(
                            ctx,
                            "Failure demo is disabled in plugin settings.",
                            "失败演示未开启，请在插件设置中开启后测试。",
                        ),
                        "warning",
                    )
                    return
                await ctx.log(
                    text(
                        ctx,
                        "Intentional failure requested; no reply will be sent.",
                        "即将触发演示错误，本次不会发送回复。",
                    ),
                    "error",
                )
                raise RuntimeError("RunnerDemo: intentional failure requested by /demo fail")
            else:
                await reply(
                    ctx,
                    text(
                        ctx,
                        f"Commands: {prefix} help | echo <text> | profile | slow | fail",
                        f"演示指令：{prefix} help（帮助）｜echo <文字>（回显）｜profile（资料查询）｜slow（进度日志）｜fail（受控失败）",
                    ),
                )

        @self.handler(MessageReactionEvent)
        async def on_reaction(ctx: RunnerContext):
            event = ctx.platform_event
            await ctx.log(
                text(
                    ctx,
                    f"Reaction {'added' if event.is_add else 'removed'}: {event.reaction}; user={event.user.id}; message={event.message_id}",
                    f"{'添加' if event.is_add else '撤销'}表态：{event.reaction}；用户={event.user.id}；消息={event.message_id}",
                )
            )

        @self.handler(FeedbackReceivedEvent)
        async def on_feedback(ctx: RunnerContext):
            event = ctx.platform_event
            category = {1: "positive", 2: "negative", 3: "cancelled"}.get(event.feedback_type, "unknown")
            await ctx.log(
                text(
                    ctx,
                    f"Feedback classified: {category}; id={event.feedback_id}",
                    f"反馈分类：{category}；ID={event.feedback_id}",
                ),
                "warning" if event.feedback_type == 2 else "info",
            )
            await ctx.log(
                json.dumps(
                    {
                        "content": event.feedback_content,
                        "reasons": event.inaccurate_reasons,
                        "message_id": event.message_id,
                    },
                    ensure_ascii=False,
                )
            )
            await ctx.log(
                text(
                    ctx,
                    "Feedback recorded without a platform reply.",
                    "反馈已记录，不发送平台回复。",
                )
            )

        @self.handler(FriendRequestReceivedEvent)
        async def on_friend_request(ctx: RunnerContext):
            event = ctx.platform_event
            await ctx.log(
                text(
                    ctx,
                    f"Friend request from {name(event.user)}: {event.message or ''}",
                    f"收到 {name(event.user)} 的好友申请：{event.message or ''}",
                )
            )
            await ctx.log(
                text(
                    ctx,
                    "Manual review required; this example never approves friend requests automatically.",
                    "请人工审核；此示例不会自动批准好友申请。",
                ),
                "warning",
            )

    async def profile(self, ctx: RunnerContext, *, group: bool) -> None:
        available = {tool["name"] for tool in await ctx.get_available_tools()}
        for tool in ["event_get_actor", "event_get_group"] if group else ["event_get_actor"]:
            if tool not in available:
                continue
            try:
                await ctx.call_tool(tool, {})
                await ctx.log(text(ctx, f"Lookup completed: {tool}", f"资料查询完成：{tool}"))
            except Exception as exc:
                # Optional enrichment should not prevent a welcome reply on adapters without lookup support.
                await ctx.log(
                    text(
                        ctx,
                        f"Lookup unavailable ({tool}): {exc}. Using event data.",
                        f"查询不可用（{tool}）：{exc}；继续使用事件自带资料。",
                    ),
                    "warning",
                )
