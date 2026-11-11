from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import pytest
import yaml

from langbot_plugin.utils import packaging

FIXTURE_PLUGIN = (
    Path(__file__).resolve().parent.parent / "fixtures" / "eba_event_probe_plugin"
)


def _copy_fixture(tmp_path: Path) -> Path:
    destination = tmp_path / "plugin"
    shutil.copytree(FIXTURE_PLUGIN, destination)
    return destination


# --------------------------------------------------------------------------- #
# gitignore helpers
# --------------------------------------------------------------------------- #
def test_parse_gitignore_reads_patterns_and_skips_comments(tmp_path):
    path = tmp_path / ".gitignore"
    path.write_text("# comment\n\nbuild/\n*.log\n", encoding="utf-8")

    assert packaging.parse_gitignore(path) == ["build/", "*.log"]


def test_parse_gitignore_missing_file_returns_empty(tmp_path):
    assert packaging.parse_gitignore(tmp_path / "does-not-exist") == []


def test_should_ignore_directory_pattern():
    assert packaging.should_ignore("build", ["build/"])
    assert packaging.should_ignore("sub/build", ["build/"])
    assert not packaging.should_ignore("builder", ["build/"])


def test_should_ignore_root_relative_pattern():
    assert packaging.should_ignore("dist/file.txt", ["/dist"])
    assert not packaging.should_ignore("nested/dist/file.txt", ["/dist"])


def test_should_ignore_wildcard_and_exact():
    assert packaging.should_ignore("a/b.pyc", ["*.pyc"])
    assert packaging.should_ignore("logs", ["logs"])
    assert not packaging.should_ignore("other", [""])


# --------------------------------------------------------------------------- #
# manifest overrides
# --------------------------------------------------------------------------- #
def test_localized_override_shapes():
    assert packaging._localized_override(None) is None
    assert packaging._localized_override({"en_US": "x"}) == {"en_US": "x"}

    result = packaging._localized_override("Hi")
    assert result["en_US"] == "Hi"
    assert result["zh_Hans"] == "Hi"


def test_apply_manifest_overrides_none_returns_same_object():
    manifest = {"metadata": {"name": "demo"}}

    assert packaging.apply_manifest_overrides(manifest, None) is manifest


def test_apply_manifest_overrides_edits_and_ignores_unknown():
    manifest = {"metadata": {"name": "demo"}}

    updated = packaging.apply_manifest_overrides(
        manifest,
        {
            "label": "Label",
            "description": "Desc",
            "version": "1.2.3",
            "repository": "https://example.com/repo",
            "author": "new-author",
            "license": "MIT",
            "icon": "assets/icon.png",
            "bogus": "ignored",
        },
    )

    metadata = updated["metadata"]
    assert metadata["label"]["en_US"] == "Label"
    assert metadata["description"]["en_US"] == "Desc"
    assert metadata["version"] == "1.2.3"
    assert metadata["repository"] == "https://example.com/repo"
    assert metadata["author"] == "new-author"
    assert metadata["license"] == "MIT"
    assert metadata["icon"] == "assets/icon.png"
    assert "bogus" not in metadata
    # The original manifest is not mutated.
    assert manifest["metadata"] == {"name": "demo"}


# --------------------------------------------------------------------------- #
# manifest loading / reading
# --------------------------------------------------------------------------- #
def test_load_plugin_manifest_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        packaging.load_plugin_manifest(str(tmp_path))


def test_read_plugin_manifest_metadata_roundtrip(tmp_path):
    root = _copy_fixture(tmp_path)

    manifest = packaging.read_plugin_manifest_metadata(str(root))

    assert manifest["metadata"]["name"] == "EBAEventProbe"


def test_read_plugin_manifest_metadata_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        packaging.read_plugin_manifest_metadata(str(tmp_path))


# --------------------------------------------------------------------------- #
# package building
# --------------------------------------------------------------------------- #
def test_build_plugin_package_contents_and_overrides(tmp_path, monkeypatch):
    root = _copy_fixture(tmp_path)
    (root / ".env").write_text("SECRET=1", encoding="utf-8")
    (root / "notes.md").write_text("hello", encoding="utf-8")

    # Component discovery resolves manifest paths relative to the working
    # directory, exactly as the plugin process does.
    monkeypatch.chdir(root)

    package_bytes, filename = packaging.build_plugin_package(
        str(root),
        manifest_overrides={"version": "9.9.9"},
        extra_files={"assets/icon.png": b"\x89PNG"},
    )

    assert filename == "Codex-EBAEventProbe-9.9.9.lbpkg"

    with zipfile.ZipFile(io.BytesIO(package_bytes)) as archive:
        names = set(archive.namelist())
        assert "manifest.yaml" in names
        assert ".env" not in names
        assert "assets/icon.png" in names
        assert "notes.md" in names

        manifest = yaml.safe_load(archive.read("manifest.yaml"))
        assert manifest["metadata"]["version"] == "9.9.9"


def test_build_plugin_package_ignores_unsafe_extra_files(tmp_path, monkeypatch):
    root = _copy_fixture(tmp_path)
    monkeypatch.chdir(root)

    package_bytes, _ = packaging.build_plugin_package(
        str(root),
        extra_files={"../escape.txt": b"nope", "manifest.yaml": b"nope"},
    )

    with zipfile.ZipFile(io.BytesIO(package_bytes)) as archive:
        names = set(archive.namelist())
        manifest = yaml.safe_load(archive.read("manifest.yaml"))

    assert "../escape.txt" not in names
    assert manifest["apiVersion"] == "v1"


# --------------------------------------------------------------------------- #
# persistence helpers
# --------------------------------------------------------------------------- #
def test_write_manifest_overrides_noop_and_write(tmp_path):
    root = _copy_fixture(tmp_path)

    packaging.write_manifest_overrides(str(root), None)
    packaging.write_manifest_overrides(str(root), {"version": "3.0.0"})

    manifest = packaging.read_plugin_manifest_metadata(str(root))
    assert manifest["metadata"]["version"] == "3.0.0"


def test_write_extra_files_writes_and_skips_unsafe(tmp_path):
    root = _copy_fixture(tmp_path)

    packaging.write_extra_files(str(root), None)
    packaging.write_extra_files(
        str(root),
        {
            "assets/x.txt": b"data",
            "../escape.txt": b"no",
            "manifest.yaml": b"no",
        },
    )

    assert (root / "assets" / "x.txt").read_bytes() == b"data"
    assert not (tmp_path / "escape.txt").exists()


def test_safe_archive_relative_path():
    assert packaging.safe_archive_relative_path("../x") is None
    assert packaging.safe_archive_relative_path("") is None
    assert packaging.safe_archive_relative_path("a\\b") == "a/b"
    assert packaging.safe_archive_relative_path("assets/icon.png") == "assets/icon.png"
