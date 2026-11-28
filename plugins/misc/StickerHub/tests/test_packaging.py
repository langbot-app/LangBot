"""The packaged artifact must keep an empty ``assets/stickers`` directory.

The installer materialises stickers into ``assets/stickers/``. ``lbp build``
honours glob patterns in ``.gitignore`` but not gitignore ``!`` negation, so a
bare ``assets/stickers/*`` drops ``.gitkeep`` too, the archived directory
vanishes, and every stable URL 404s on a fresh install.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
GITIGNORE = PLUGIN_ROOT / ".gitignore"
GITKEEP = PLUGIN_ROOT / "assets" / "stickers" / ".gitkeep"


def patterns() -> list[str]:
    """Mirror ``lbp``'s parse: non-empty, non-comment lines only."""

    return [
        line.strip()
        for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def packaged(relative_path: str) -> bool:
    """Mirror ``lbp``'s ``should_ignore``: any matching pattern drops the file."""

    normalized = str(Path(relative_path)).replace("\\", "/")
    for pattern in patterns():
        if pattern.startswith("!"):
            continue
        if fnmatch.fnmatch(normalized, pattern):
            return False
        if fnmatch.fnmatch(Path(normalized).name, pattern):
            return False
    return True


def test_gitkeep_exists():
    assert GITKEEP.is_file(), "an empty assets/stickers needs a tracked placeholder"


def test_gitkeep_survives_packaging():
    assert packaged("assets/stickers/.gitkeep"), "the packager would drop .gitkeep"


def test_sticker_artifacts_stay_out_of_the_package():
    for name in ("cat-abc123.png", "cat-abc123.jpg", "cat-abc123.webp"):
        assert not packaged(f"assets/stickers/{name}")
    assert not packaged("assets/stickers/cat-abc123.png.tmp")


def test_the_plugin_icon_is_packaged():
    assert packaged("assets/icon.svg")
