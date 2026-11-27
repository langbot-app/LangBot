#!/usr/bin/env python3
"""Static consistency check for the action-based runtime protocol.

The runtime protocol (``runtime/io/``) dispatches calls by action name: a sender
calls ``call_action(SomeAction.MEMBER, ...)`` and a receiver must have registered
a handler with ``@handler.action(SomeAction.MEMBER)``. If the handler is missing,
the call fails *at runtime* with ``ValueError: Action <name> not found`` — a class
of bug that unit tests miss because they mock the proxy layer, and that only shows
up end-to-end (this is exactly how ``vector_list`` shipped broken: the enum member,
the plugin-side proxy, and a proxy-level test all existed, but no runtime forwarder
was registered).

This checker parses the SDK with ``ast`` (no imports, no side effects) and enforces:

1. ERROR: every action *invoked* in-repo (``call_action`` / ``call_action_generator``
   with a literal ``EnumClass.MEMBER`` argument) has a matching ``.action(...)``
   registration in-repo — UNLESS the action's receiver is an external process
   (the LangBot host), whose handlers live in a different repository. This is the
   invariant ``vector_list`` violated.
2. ERROR: every ``EnumClass.MEMBER`` referenced by an invocation or registration
   actually exists on that enum class (guards against typos / renames).
3. WARN: enum members that are neither invoked nor registered anywhere in-repo —
   candidate dead wiring ("enum without action"). Warning only, because a member
   may legitimately be invoked or handled by the LangBot host (a separate repo).

Action enum classes follow the ``<Sender>To<Receiver>Action`` naming convention.
The *receiver* is what must hold the handler, so Rule 1 only applies when the
receiver lives in this repository (Runtime or Plugin); actions received by the
LangBot host are handled there and cannot be checked from here.

Known, accepted exceptions are listed in ``KNOWN_EXCEPTIONS`` with a reason so the
gate can go green on a branch while pre-existing debt is tracked explicitly rather
than hidden.

Exit code is non-zero if any unexpected ERROR is found. Run from the repo root:

    python scripts/check_action_consistency.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "langbot_plugin"
ENUMS_FILE = SRC_ROOT / "entities" / "io" / "actions" / "enums.py"

INVOKE_METHODS = {"call_action", "call_action_generator", "call_host_action"}
REGISTER_METHODS = {"action"}

# Receivers whose action handlers live in THIS repository. Actions whose receiver
# is anything else (e.g. the LangBot host) are handled in another repo, so Rule 1
# (invoked => registered) cannot and must not be enforced here.
IN_REPO_RECEIVERS = {"Runtime", "Plugin"}

# Accepted, documented exceptions to keep the gate green while tracking known debt.
# Map (EnumClassName, MEMBER) -> reason. Remove an entry once the underlying issue
# is fixed; the checker reports any entry that has become unnecessary.
KNOWN_EXCEPTIONS: dict[tuple[str, str], str] = {}


class Ref:
    """A literal ``EnumClass.MEMBER`` reference at a source location."""

    __slots__ = ("enum", "member", "file", "line")

    def __init__(self, enum: str, member: str, file: Path, line: int):
        self.enum = enum
        self.member = member
        self.file = file
        self.line = line

    @property
    def key(self) -> tuple[str, str]:
        return (self.enum, self.member)

    def where(self) -> str:
        rel = self.file.relative_to(REPO_ROOT)
        return f"{rel}:{self.line}"


def action_receiver(enum_name: str) -> str | None:
    """Return the receiver segment of a ``<Sender>To<Receiver>Action`` enum name.

    Returns ``None`` for names without a ``To`` segment (e.g. ``CommonAction``),
    which are treated as in-repo.
    """
    if not enum_name.endswith("Action"):
        return None
    core = enum_name[: -len("Action")]
    if "To" not in core:
        return None
    return core.rsplit("To", 1)[1]


def receiver_in_repo(enum_name: str) -> bool:
    receiver = action_receiver(enum_name)
    return receiver is None or receiver in IN_REPO_RECEIVERS


def load_enum_members() -> dict[str, set[str]]:
    """Return {EnumClassName: {MEMBER, ...}} for every action enum class."""
    tree = ast.parse(ENUMS_FILE.read_text(encoding="utf-8"), filename=str(ENUMS_FILE))
    enums: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        members: set[str] = set()
        for stmt in node.body:
            targets: list[ast.expr] = []
            if isinstance(stmt, ast.Assign):
                targets = stmt.targets
            elif isinstance(stmt, ast.AnnAssign) and stmt.target is not None:
                targets = [stmt.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    members.add(target.id)
        if members:
            enums[node.name] = members
    return enums


def _enum_member_arg(arg: ast.expr, enum_names: set[str]) -> tuple[str, str] | None:
    """If ``arg`` is ``EnumClass.MEMBER`` for a known enum, return (enum, member)."""
    if (
        isinstance(arg, ast.Attribute)
        and isinstance(arg.value, ast.Name)
        and arg.value.id in enum_names
    ):
        return (arg.value.id, arg.attr)
    return None


def scan(enum_names: set[str]) -> tuple[list[Ref], list[Ref]]:
    """Walk the source tree, returning (invocations, registrations)."""
    invocations: list[Ref] = []
    registrations: list[Ref] = []

    for path in sorted(SRC_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - defensive
            print(f"WARN: could not parse {path}: {exc}", file=sys.stderr)
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute):
                method = node.func.attr
            elif isinstance(node.func, ast.Name):
                method = node.func.id
            else:
                continue
            if not node.args:
                continue
            ref = _enum_member_arg(node.args[0], enum_names)
            if ref is None:
                continue
            enum, member = ref
            location = Ref(enum, member, path, node.lineno)
            if method in INVOKE_METHODS:
                invocations.append(location)
            elif method in REGISTER_METHODS:
                registrations.append(location)

    return invocations, registrations


def main() -> int:
    if not ENUMS_FILE.exists():
        print(f"ERROR: enum file not found: {ENUMS_FILE}", file=sys.stderr)
        return 2

    enums = load_enum_members()
    enum_names = set(enums)
    invocations, registrations = scan(enum_names)

    registered_keys = {ref.key for ref in registrations}
    invoked_keys = {ref.key for ref in invocations}

    errors: list[str] = []
    acknowledged: list[str] = []
    used_exceptions: set[tuple[str, str]] = set()

    # Rule 2: referenced members must exist on their enum (typo / rename guard).
    for ref in invocations + registrations:
        if ref.member in enums.get(ref.enum, set()):
            continue
        if ref.key in KNOWN_EXCEPTIONS:
            used_exceptions.add(ref.key)
            acknowledged.append(
                f"{ref.enum}.{ref.member} at {ref.where()} — {KNOWN_EXCEPTIONS[ref.key]}"
            )
            continue
        errors.append(
            f"unknown action member {ref.enum}.{ref.member} referenced at "
            f"{ref.where()} (not defined in {ENUMS_FILE.name})"
        )

    # Rule 1: every invoked action whose receiver is in-repo must be registered.
    for ref in invocations:
        if not receiver_in_repo(ref.enum):
            continue  # receiver is the external LangBot host; handler lives there
        if ref.key in registered_keys:
            continue
        if ref.key in KNOWN_EXCEPTIONS:
            used_exceptions.add(ref.key)
            acknowledged.append(
                f"{ref.enum}.{ref.member} invoked at {ref.where()} but not registered "
                f"— {KNOWN_EXCEPTIONS[ref.key]}"
            )
            continue
        errors.append(
            f"{ref.enum}.{ref.member} is invoked at {ref.where()} but no "
            f"`.action({ref.enum}.{ref.member})` handler is registered anywhere in "
            f'src/ — calls will fail at runtime with "Action {ref.member.lower()} not found"'
        )

    # Stale-allowlist guard: every KNOWN_EXCEPTIONS entry should still be needed.
    for key in KNOWN_EXCEPTIONS:
        if key not in used_exceptions:
            errors.append(
                f"stale KNOWN_EXCEPTIONS entry {key[0]}.{key[1]} — the underlying "
                f"inconsistency is gone; remove it from {Path(__file__).name}"
            )

    # Rule 3 (warning): enum members with no invocation and no registration in-repo.
    warnings: list[str] = []
    for enum, members in sorted(enums.items()):
        for member in sorted(members):
            key = (enum, member)
            if key not in invoked_keys and key not in registered_keys:
                warnings.append(
                    f"{enum}.{member} is never invoked nor registered in src/ "
                    f"(handled by the LangBot host, or dead wiring?)"
                )

    print(
        f"action-consistency: {len(enums)} enums, "
        f"{len(invoked_keys)} invoked, {len(registered_keys)} registered"
    )

    if acknowledged:
        print(f"\n{len(acknowledged)} known exception(s) (tracked debt):")
        for line in acknowledged:
            print(f"  KNOWN: {line}")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for line in warnings:
            print(f"  WARN: {line}")

    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for line in errors:
            print(f"  ERROR: {line}", file=sys.stderr)
        print(
            "\nAction protocol consistency check FAILED. "
            "Register the missing handler(s) or fix the reference.",
            file=sys.stderr,
        )
        return 1

    print("\nAction protocol consistency check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
