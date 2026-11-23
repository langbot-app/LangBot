"""Three-layer security policy for LangBot Box.

The design separates concerns into three independent layers, aligned with
OpenCode / OpenClaw patterns:

1. **SandboxPolicy** – *where* tools run (host vs sandbox).
2. **ToolPolicy** – *which* tools are allowed (allow/deny lists).
3. **ElevatedPolicy** – *whether* a single exec call may temporarily
   escape the default sandbox boundary.

These three layers are orthogonal:
- ToolPolicy is a hard boundary; ``elevated`` cannot bypass a denied tool.
- SandboxPolicy decides the default execution location.
- ElevatedPolicy only affects ``exec`` and only when the framework allows it.
"""

from __future__ import annotations

import enum
from typing import Sequence


# ── Layer 1: Sandbox Policy ──────────────────────────────────────────


class SandboxMode(str, enum.Enum):
    """Determines when agent execution is routed through the sandbox."""

    OFF = 'off'
    """Sandbox disabled; all exec runs on the host."""

    NON_DEFAULT = 'non_default'
    """Only non-default sessions are sandboxed (e.g. sub-agents, MCP)."""

    ALL = 'all'
    """Every agent exec call is routed through the sandbox."""


class SandboxPolicy:
    """Decides whether a given execution context should use the sandbox."""

    def __init__(self, mode: SandboxMode = SandboxMode.ALL):
        self.mode = mode

    def should_sandbox(self, *, is_default_session: bool = True) -> bool:
        if self.mode == SandboxMode.OFF:
            return False
        if self.mode == SandboxMode.ALL:
            return True
        # NON_DEFAULT: sandbox everything except the default session
        return not is_default_session


# ── Layer 2: Tool Policy ─────────────────────────────────────────────


class ToolPolicy:
    """Controls which tools are available to the current agent/session.

    Rules:
    - ``deny`` always takes precedence over ``allow``.
    - An empty ``allow`` list means "all tools allowed" (no allowlist filter).
    - ``elevated`` cannot bypass a denied tool.
    """

    def __init__(
        self,
        allow: Sequence[str] = (),
        deny: Sequence[str] = (),
    ):
        self._allow: frozenset[str] = frozenset(allow)
        self._deny: frozenset[str] = frozenset(deny)

    def is_tool_allowed(self, tool_name: str) -> bool:
        if tool_name in self._deny:
            return False
        if self._allow and tool_name not in self._allow:
            return False
        return True


# ── Layer 3: Elevated Policy ─────────────────────────────────────────


class ElevatedPolicy:
    """Controls whether ``exec`` may request temporary privilege escalation.

    ``elevated`` only applies to the ``exec`` tool.  It means "run this
    command outside the default sandbox boundary" (e.g. with network, or
    on the host).  The framework decides whether to honor the request.
    """

    def __init__(self, *, allow_elevated: bool = False, require_approval: bool = True):
        self.allow_elevated = allow_elevated
        self.require_approval = require_approval

    def is_elevation_permitted(self) -> bool:
        return self.allow_elevated
