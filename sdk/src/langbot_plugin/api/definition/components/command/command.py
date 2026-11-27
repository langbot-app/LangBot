from __future__ import annotations

from typing import Any, Callable, Coroutine, AsyncGenerator

import pydantic
from pydantic import BaseModel

from langbot_plugin.api.definition.components.base import BaseComponent
from langbot_plugin.api.entities.builtin.command import context
from langbot_plugin.api.entities.builtin.command.errors import CommandNotFoundError


class Subcommand(BaseModel):
    """The subcommand model."""

    subcommand: Callable[
        [context.ExecuteContext],
        Coroutine[Any, Any, AsyncGenerator[context.CommandReturn, None]],
    ]
    """The subcommand function."""
    help: str
    """The help message."""
    usage: str
    """The usage message."""
    aliases: list[str]
    """The aliases of the subcommand."""


class Command(BaseComponent):
    """The command component."""

    __kind__ = "Command"

    registered_subcommands: dict[str, Subcommand] = pydantic.Field(default_factory=dict)

    def __init__(self):
        self.registered_subcommands = {}

    def subcommand(
        self,
        name: str,
        help: str = "",
        usage: str = "",
        aliases: list[str] = [],
    ) -> Callable[
        [
            Callable[
                [context.ExecuteContext],
                Coroutine[Any, Any, AsyncGenerator[context.CommandReturn, None]],
            ]
        ],
        Callable[
            [context.ExecuteContext],
            Coroutine[Any, Any, AsyncGenerator[context.CommandReturn, None]],
        ],
    ]:
        """Register a subcommand."""

        def decorator(
            subcommand: Callable[
                [context.ExecuteContext],
                Coroutine[Any, Any, AsyncGenerator[context.CommandReturn, None]],
            ],
        ) -> Callable[
            [context.ExecuteContext],
            Coroutine[Any, Any, AsyncGenerator[context.CommandReturn, None]],
        ]:
            self.registered_subcommands[name] = Subcommand(
                subcommand=subcommand,
                help=help,
                usage=usage,
                aliases=aliases,
            )
            return subcommand

        return decorator

    async def _execute(
        self, context: context.ExecuteContext
    ) -> AsyncGenerator[context.CommandReturn, None]:
        """Execute the command."""
        next_crt_command = context.crt_params[0] if len(context.crt_params) > 0 else ""
        if next_crt_command not in self.registered_subcommands:
            # find if there is a subcommand with '*' name
            for subcommand in self.registered_subcommands:
                if subcommand == "*":
                    async for return_value in self.registered_subcommands[
                        subcommand
                    ].subcommand(self, context):
                        yield return_value
                        return

            raise CommandNotFoundError(next_crt_command)

        context.shift()

        subcommand = self.registered_subcommands[context.crt_command]
        async for return_value in subcommand.subcommand(self, context):
            yield return_value
