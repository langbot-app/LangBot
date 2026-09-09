from __future__ import annotations


def resolve_include_secret(raw_value: str | None, *, permitted: bool) -> tuple[bool, str | None]:
    """Resolve the optional secret projection query parameter."""

    if raw_value is None:
        return permitted, None

    value = raw_value.strip().lower()
    if value == 'false':
        return False, None
    if value == 'true':
        return permitted, None
    return False, 'include_secret must be either true or false'
