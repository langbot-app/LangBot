"""Inclusive LangBot release ranges and marketplace plugin ordering."""

import math
import re


class InvalidCompatibility(ValueError):
    """Invalid LangBot compatibility declaration in a plugin manifest."""


def _mapping(value, field):
    if not isinstance(value, dict):
        raise InvalidCompatibility(f"{field}: expected a mapping, got {value!r}")
    return value


def _endpoint(value, side):
    field = f"metadata.compatibility.langbot.{side}"
    if not isinstance(value, str):
        raise InvalidCompatibility(
            f"{field}: 请用引号包住版本号（YAML 解析值为 {value!r}）"
        )
    parts = value.removeprefix("v").split(".")
    result = []
    for part in parts:
        if re.fullmatch(r"[0-9]+", part) and math.inf not in result:
            result.append(int(part))
        elif side == "max" and result and part in ("x", "*"):
            result.append(math.inf)
        else:
            raise InvalidCompatibility(f"{field}: invalid version {value!r}")
    if len(result) > 3:
        raise InvalidCompatibility(f"{field}: invalid version {value!r}")
    return tuple(result + [0 if side == "min" else math.inf] * (3 - len(result)))


def declared_range(metadata):
    compat = metadata.get("compatibility")
    if compat is None:
        return {}
    bounds = _mapping(compat, "metadata.compatibility").get("langbot")
    return {} if bounds is None else _mapping(bounds, "metadata.compatibility.langbot")


def parse_range(declaration):
    if declaration is None:
        return None, None
    declaration = _mapping(declaration, "metadata.compatibility.langbot")
    lower, upper = (
        _endpoint(declaration[key], key) if key in declaration else None
        for key in ("min", "max")
    )
    if lower and upper and lower > upper:
        raise InvalidCompatibility(
            f"metadata.compatibility.langbot.min: {declaration['min']!r} exceeds max {declaration['max']!r}"
        )
    return lower, upper


def parse_core_version(value):
    match = re.fullmatch(r"v?([0-9]+)\.([0-9]+)\.([0-9]+)(?:[a-zA-Z.+-].*)?", value)
    if not match:
        raise ValueError(f"Invalid LangBot version: {value!r}")
    return tuple(map(int, match.groups()))


def check(manifest_dict, core_version):
    result = dict(status="unspecified", min=None, max=None, current=core_version)
    try:
        metadata = _mapping(manifest_dict.get("metadata", {}), "metadata")
        declaration = declared_range(metadata)
        for key in ("min", "max"):
            if isinstance(declaration.get(key), str):
                result[key] = declaration[key]
        lower, upper = parse_range(declaration)
        if lower or upper:
            current = parse_core_version(core_version)
            matches = (not lower or current >= lower) and (
                not upper or current <= upper
            )
            result["status"] = "compatible" if matches else "incompatible"
    except ValueError:
        result["status"] = "invalid"
    return result


def plugin_version_key(version, created_at="", id=0):
    """Sort descending: stable, prerelease, unparseable; then publication order."""
    match = re.fullmatch(
        r"v?([0-9]+)\.([0-9]+)(?:\.([0-9]+))?"
        r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)|(a|b|rc)([0-9]+))?"
        r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
        version,
    )
    if not match:
        return (0, (), (), created_at, id)
    major, minor, patch, pre, pep, number = match.groups()
    if pep:
        pre = {"a": "alpha", "b": "beta", "rc": "rc"}[pep] + "." + number
    identifiers = (
        tuple(
            (0, int(part)) if part.isascii() and part.isdigit() else (1, part)
            for part in pre.split(".")
        )
        if pre
        else ()
    )
    return (
        1 if pre else 2,
        (int(major), int(minor), int(patch or 0)),
        identifiers,
        created_at,
        id,
    )
