"""Coalesce a runner's terminal delta and completed snapshot before delivery."""

from collections.abc import AsyncIterable, AsyncIterator

from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk


async def coalesce_stream_results(
    results: AsyncIterable[Message | MessageChunk],
) -> AsyncIterator[Message | MessageChunk]:
    pending: MessageChunk | None = None
    snapshot = ''
    async for result in results:
        if pending is not None:
            # Completion snapshots can add attachments and usage to the final
            # delta. Deliver that richer result once, before closing the card.
            content = pending.all_content if pending.all_content is not None else pending.content
            # Multi-round runners stream a cumulative transcript, but complete
            # with only the last model round. Keep the transcript on the same
            # card while taking attachments and metadata from the completion.
            final_round = (
                isinstance(content, str)
                and isinstance(result.content, str)
                and bool(result.content)
                and content.endswith(result.content)
            )
            same_message = (
                isinstance(result, Message)
                and result.role == pending.role
                and (result.tool_calls or []) == (pending.tool_calls or [])
                and (not content or result.content == content or final_round)
            )
            if same_message and final_round and content != result.content:
                result = result.model_copy(update={'content': content})
            elif not same_message:
                yield pending
            pending = None
            snapshot = ''

        if isinstance(result, MessageChunk) and isinstance(result.content, (str, type(None))):
            # Runner output is already cumulative (unlike raw provider deltas).
            # Explicit all_content also supports runners forwarding raw deltas.
            # Never guess delta semantics from a missing all_content field.
            snapshot = result.all_content if result.all_content is not None else (result.content or snapshot)
            result = result.model_copy(update={'all_content': snapshot})
        elif isinstance(result, Message):
            snapshot = ''

        if isinstance(result, MessageChunk) and result.is_final:
            pending = result
        else:
            yield result

    if pending is not None:
        yield pending
