from __future__ import annotations

import io
import os
import stat
import zipfile
from pathlib import Path

import pytest

import langbot_plugin.skill_store as skill_store_module

from langbot_plugin.skill_store import (
    SkillStore,
    build_skill_md,
    parse_frontmatter,
)


def _skill_zip(name: str = "demo") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            f"{name}/SKILL.md",
            "---\n"
            f"name: {name}\n"
            f"display_name: {name.title()}\n"
            "description: Demo skill\n"
            "---\n\n"
            "Use this skill for tests.\n",
        )
        zf.writestr(f"{name}/notes.txt", "hello")
    return buffer.getvalue()


def _root_skill_zip(name: str = "demo") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "SKILL.md",
            "---\n"
            f"name: {name}\n"
            "description: Demo skill\n"
            "---\n\n"
            "Use this skill for tests.\n",
        )
    return buffer.getvalue()


def _nested_skill_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "repo/packages/alpha/SKILL.md",
            "---\nname: alpha\ndisplay_name: Alpha\ndescription: Alpha skill\n---\n\nAlpha instructions.\n",
        )
        zf.writestr(
            "repo/packages/beta/SKILL.md",
            "---\nname: beta\ndisplay_name: Beta\ndescription: Beta skill\n---\n\nBeta instructions.\n",
        )
    return buffer.getvalue()


def _make_store(tmp_path, skills_root: str = "skills") -> SkillStore:
    return SkillStore(tmp_path / skills_root)


def _write_skill_dir(
    base, name: str, *, frontmatter: bool = True, instructions: str = "Body."
) -> str:
    """Create a SKILL.md package directory on disk, return its path."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    if frontmatter:
        content = (
            "---\n"
            f"name: {name}\n"
            f"display_name: {name.title()}\n"
            "description: A test skill\n"
            f"---\n\n{instructions}\n"
        )
    else:
        content = instructions + "\n"
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return str(skill_dir)


# ── Existing tests (kept) ───────────────────────────────────────────────


def test_skill_store_installs_zip_under_configured_relative_skills_root(tmp_path):
    store = SkillStore(tmp_path / "custom-skills")

    preview = store.preview_zip_upload(file_bytes=_skill_zip(), filename="demo.zip")
    assert preview[0]["package_root"] == str(tmp_path / "custom-skills" / "demo-upload")

    installed = store.install_zip_upload(file_bytes=_skill_zip(), filename="demo.zip")
    assert installed[0]["name"] == "demo"
    assert ".langbot-skill-store" in installed[0]["package_root"]
    assert installed[0]["revision"].startswith("sha256:")

    files = store.list_skill_files("demo")
    assert {entry["name"] for entry in files["entries"]} == {"SKILL.md", "notes.txt"}

    content = store.read_skill_file("demo", "notes.txt")
    assert content["content"] == "hello"

    store.write_skill_file(
        "demo",
        "notes.txt",
        "updated",
        base_revision=installed[0]["revision"],
    )
    assert store.read_skill_file("demo", "notes.txt")["content"] == "updated"


def test_scoped_skill_stores_isolate_same_named_skill_between_workspaces(tmp_path):
    base_store = _make_store(tmp_path)
    first_store = base_store.scoped("workspace-a")
    second_store = base_store.scoped("workspace-b")

    first_skill = first_store.install_zip_upload(
        file_bytes=_skill_zip("demo"),
        filename="demo.zip",
    )[0]
    second_skill = second_store.install_zip_upload(
        file_bytes=_skill_zip("demo"),
        filename="demo.zip",
    )[0]

    assert first_store.root != second_store.root
    assert [skill["name"] for skill in first_store.list_skills()] == ["demo"]
    assert [skill["name"] for skill in second_store.list_skills()] == ["demo"]
    assert first_skill["package_root"].startswith(first_store.root + os.sep)
    assert second_skill["package_root"].startswith(second_store.root + os.sep)
    assert first_skill["package_root"] != second_skill["package_root"]


def test_scoped_skill_store_rejects_cross_workspace_scan_and_import(tmp_path):
    base_store = _make_store(tmp_path)
    first_store = base_store.scoped("workspace-a")
    second_store = base_store.scoped("workspace-b")
    stolen = second_store.create_skill(
        {
            "name": "private",
            "instructions": "workspace-b secret",
        }
    )

    with pytest.raises(ValueError, match="Workspace skill root"):
        first_store.scan_directory(stolen["package_root"])
    with pytest.raises(ValueError, match="Workspace skill root"):
        first_store.create_skill(
            {
                "name": "stolen",
                "package_root": stolen["package_root"],
            }
        )


def test_scoped_skill_store_does_not_follow_directory_symlinks(tmp_path):
    base_store = _make_store(tmp_path)
    first_store = base_store.scoped("workspace-a")
    second_store = base_store.scoped("workspace-b")
    private = second_store.create_skill(
        {
            "name": "private",
            "instructions": "workspace-b secret",
        }
    )
    os.makedirs(first_store.root, exist_ok=True)
    link = os.path.join(first_store.root, "linked-private")
    try:
        os.symlink(private["package_root"], link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are unavailable on this platform")

    assert first_store.list_skills() == []


def test_skill_store_supports_source_subdir_before_selecting_candidates(tmp_path):
    store = SkillStore(tmp_path / "skills")

    preview = store.preview_zip_upload(
        file_bytes=_nested_skill_zip(),
        filename="repo.zip",
        source_subdir="packages",
    )

    assert [skill["source_path"] for skill in preview] == ["alpha", "beta"]

    installed = store.install_zip_upload(
        file_bytes=_nested_skill_zip(),
        filename="repo.zip",
        source_subdir="packages",
        source_paths=["beta"],
    )

    assert [skill["name"] for skill in installed] == ["beta"]
    assert ".langbot-skill-store" in installed[0]["package_root"]


@pytest.mark.parametrize(
    ("directory", "frontmatter", "message"),
    [
        (
            "Demo",
            "---\nname: Demo\ndescription: Demo skill\n---\n\nBody\n",
            "lowercase",
        ),
        (
            "demo",
            "---\nname: other\ndescription: Demo skill\n---\n\nBody\n",
            "match directory",
        ),
        (
            "demo",
            "---\nname: demo\n---\n\nBody\n",
            "non-empty frontmatter description",
        ),
        (
            "a" * 65,
            "---\nname: " + "a" * 65 + "\ndescription: Demo skill\n---\n\nBody\n",
            "64 characters",
        ),
    ],
)
def test_zip_upload_rejects_nonstandard_skill_metadata(
    tmp_path, directory, frontmatter, message
):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(f"{directory}/SKILL.md", frontmatter)

    with pytest.raises(ValueError, match=message):
        _make_store(tmp_path).preview_zip_upload(
            file_bytes=buffer.getvalue(), filename="skill.zip"
        )


# ── parse_frontmatter ───────────────────────────────────────────────────


def test_parse_frontmatter_extracts_metadata_and_instructions():
    content = "---\nname: foo\ndescription: bar\n---\n\nDo the thing.\n"
    metadata, instructions = parse_frontmatter(content)
    assert metadata == {"name": "foo", "description": "bar"}
    assert instructions == "Do the thing.\n"


def test_parse_frontmatter_without_leading_marker_returns_whole_body():
    content = "no frontmatter here\nsecond line\n"
    metadata, instructions = parse_frontmatter(content)
    assert metadata == {}
    assert instructions == content


def test_parse_frontmatter_first_line_not_marker():
    # Starts with '---' but first stripped line is not exactly '---'.
    content = "--- header\nname: foo\n---\nbody"
    metadata, instructions = parse_frontmatter(content)
    assert metadata == {}
    assert instructions == content


def test_parse_frontmatter_unterminated_block_returns_whole_body():
    content = "---\nname: foo\nno closing marker\n"
    metadata, instructions = parse_frontmatter(content)
    assert metadata == {}
    assert instructions == content


def test_parse_frontmatter_non_dict_yaml_is_discarded():
    content = "---\n- just\n- a\n- list\n---\nbody text"
    metadata, instructions = parse_frontmatter(content)
    assert metadata == {}
    assert instructions == "body text"


def test_parse_frontmatter_empty_metadata_block():
    content = "---\n---\nbody only"
    metadata, instructions = parse_frontmatter(content)
    assert metadata == {}
    assert instructions == "body only"


# ── build_skill_md ──────────────────────────────────────────────────────


def test_build_skill_md_roundtrips_with_parse_frontmatter():
    metadata = {"name": "foo", "display_name": "Foo", "description": "desc"}
    md = build_skill_md(metadata, "Hello instructions.")
    assert md.startswith("---\n")
    parsed_meta, parsed_instructions = parse_frontmatter(md)
    assert parsed_meta == metadata
    assert parsed_instructions == "Hello instructions."


def test_build_skill_md_without_metadata_returns_instructions_only():
    md = build_skill_md({}, "just instructions")
    assert md == "just instructions"


def test_build_skill_md_drops_blank_and_none_fields():
    metadata = {"name": "foo", "display_name": "   ", "description": None}
    md = build_skill_md(metadata, "body")
    parsed_meta, _ = parse_frontmatter(md)
    assert parsed_meta == {"name": "foo"}


def test_build_skill_md_preserves_extensions_and_omits_runtime_fields():
    metadata = {
        "name": "foo",
        "description": "desc",
        "license": "Apache-2.0",
        "compatibility": "Requires Python 3.10+",
        "metadata": {"owner": "qa"},
        "allowed-tools": ["Read", "Grep"],
        "package_root": "/should/not/appear",
    }
    md = build_skill_md(metadata, "body")
    parsed_meta, _ = parse_frontmatter(md)
    assert parsed_meta == {
        "name": "foo",
        "description": "desc",
        "license": "Apache-2.0",
        "compatibility": "Requires Python 3.10+",
        "metadata": {"owner": "qa"},
        "allowed-tools": ["Read", "Grep"],
    }


# ── root resolution ─────────────────────────────────────────────────────


def test_root_uses_configured_absolute_host_root(tmp_path):
    store = _make_store(tmp_path, skills_root="my-skills")
    assert store.root == str((tmp_path / "my-skills").resolve())


def test_root_absolute_skills_root_overrides_host_root(tmp_path):
    abs_skills = tmp_path / "elsewhere" / "skills"
    store = SkillStore(abs_skills)
    assert store.root == str(abs_skills.resolve())


# ── list_skills / get_skill ─────────────────────────────────────────────


def test_list_skills_on_empty_root_creates_dir_and_returns_empty(tmp_path):
    store = _make_store(tmp_path)
    assert store.list_skills() == []
    assert os.path.isdir(store.root)


def test_list_skills_returns_managed_skills_sorted_by_updated_at(tmp_path):
    store = _make_store(tmp_path)
    root = tmp_path / "skills"
    older = _write_skill_dir(root, "older")
    _write_skill_dir(root, "newer")
    # Force ordering by mtime: older skill in the past.
    os.utime(os.path.join(older, "SKILL.md"), (1000, 1000))

    skills = store.list_skills()
    names = [s["name"] for s in skills]
    assert names == ["newer", "older"]
    # Serialized form exposes only public fields.
    assert set(skills[0].keys()) <= {
        "name",
        "display_name",
        "description",
        "metadata",
        "instructions",
        "package_root",
        "manifest_path",
        "entry_file",
        "python_project",
        "revision",
        "created_at",
        "updated_at",
    }
    assert all("source_path" not in s for s in skills)


def test_list_skills_skips_corrupt_entries(tmp_path):
    store = _make_store(tmp_path)
    root = tmp_path / "skills"
    _write_skill_dir(root, "good")
    # A directory whose SKILL.md cannot be decoded as UTF-8 should be skipped,
    # not crash list_skills.
    bad_dir = root / "bad"
    bad_dir.mkdir(parents=True)
    (bad_dir / "SKILL.md").write_bytes(b"\xff\xfe\x00bad")

    names = [s["name"] for s in store.list_skills()]
    assert "good" in names
    assert "bad" not in names


def test_list_skills_counts_nested_metadata_toward_text_limit(tmp_path, monkeypatch):
    store = _make_store(tmp_path)
    store.create_skill(
        {
            "name": "nested",
            "description": "Nested metadata",
            "metadata": {"limits": {"payload": "x" * 128}},
            "instructions": "Body",
        }
    )
    monkeypatch.setattr(skill_store_module, "_MAX_SKILL_LIST_TOTAL_TEXT_BYTES", 64)

    with pytest.raises(ValueError, match="listing exceeds"):
        store.list_skills()


def test_skill_discovery_fails_fast_at_entry_limit(tmp_path):
    store = _make_store(tmp_path)
    root = tmp_path / "skills"
    for index in range(3):
        (root / f"directory-{index}").mkdir(parents=True)

    with pytest.raises(ValueError, match="entry limit"):
        store._discover_skill_directories(
            store.root,
            max_depth=6,
            max_scan_entries=2,
        )


def test_get_skill_returns_match_and_none_for_missing(tmp_path):
    store = _make_store(tmp_path)
    _write_skill_dir(tmp_path / "skills", "alpha")
    found = store.get_skill("alpha")
    assert found is not None
    assert found["name"] == "alpha"
    assert store.get_skill("does-not-exist") is None


def test_skill_python_project_metadata_is_computed_by_box_runtime_store(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "python-demo", "instructions": "run it"})

    assert store.get_skill("python-demo")["python_project"] is False

    store.write_skill_file(
        "python-demo",
        "requirements.txt",
        "requests==2.32.0\n",
        base_revision=created["revision"],
    )

    assert store.get_skill("python-demo")["python_project"] is True


def test_load_skill_package_falls_back_to_dir_name_without_frontmatter(tmp_path):
    store = _make_store(tmp_path)
    _write_skill_dir(
        tmp_path / "skills", "plainskill", frontmatter=False, instructions="Just a body"
    )
    skill = store.get_skill("plainskill")
    assert skill is not None
    assert skill["name"] == "plainskill"
    assert skill["display_name"] == "plainskill"
    assert skill["description"] == ""
    assert "Just a body" in skill["instructions"]


def test_load_skill_package_supports_lowercase_entry_file(tmp_path):
    store = _make_store(tmp_path)
    skill_dir = tmp_path / "skills" / "lower"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text(
        "---\nname: lower\n---\n\nbody\n", encoding="utf-8"
    )
    skill = store.get_skill("lower")
    assert skill is not None
    # Entry file is one of the accepted SKILL.md spellings (case-insensitive
    # filesystems may report either casing).
    assert skill["entry_file"].lower() == "skill.md"
    assert "body" in skill["instructions"]


# ── create_skill ────────────────────────────────────────────────────────


def test_create_skill_minimal_managed(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill(
        {
            "name": "fresh",
            "display_name": "Fresh Skill",
            "description": "desc",
            "instructions": "do stuff",
        }
    )
    assert created["name"] == "fresh"
    assert created["display_name"] == "Fresh Skill"
    assert created["description"] == "desc"
    assert created["instructions"].strip() == "do stuff"
    assert os.path.isfile(os.path.join(created["package_root"], "SKILL.md"))


def test_create_skill_rejects_duplicate(tmp_path):
    store = _make_store(tmp_path)
    store.create_skill({"name": "dup", "instructions": "x"})
    with pytest.raises(ValueError, match="already exists"):
        store.create_skill({"name": "dup", "instructions": "y"})


@pytest.mark.parametrize(
    "bad_name, message",
    [
        ("", "required"),
        ("   ", "required"),
        ("bad name!", "letters, numbers"),
        ("a" * 65, "exceed 64"),
    ],
)
def test_create_skill_rejects_invalid_names(tmp_path, bad_name, message):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match=message):
        store.create_skill({"name": bad_name})


def test_create_skill_imports_external_package_by_copy(tmp_path):
    store = _make_store(tmp_path)
    external = tmp_path / "external"
    src = _write_skill_dir(external, "imported", instructions="Imported body")
    (external / "imported" / "extra.txt").write_text("payload", encoding="utf-8")

    created = store.create_skill({"name": "copied", "package_root": src})
    assert created["name"] == "copied"
    # Imported metadata flows through when not overridden.
    assert created["display_name"] == "Imported"
    assert created["description"] == "A test skill"
    # Copied into an immutable content-addressed revision; extra file came along.
    assert os.path.isfile(os.path.join(created["package_root"], "extra.txt"))
    assert created["package_root"] != os.path.realpath(src)


def test_create_skill_import_preserves_agent_skills_frontmatter(tmp_path):
    store = _make_store(tmp_path)
    source = tmp_path / "external" / "portable"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\n"
        "name: portable\n"
        "description: Portable guidance\n"
        "license: Apache-2.0\n"
        "compatibility: Python 3.10+\n"
        "metadata:\n"
        "  owner: qa\n"
        "allowed-tools:\n"
        "  - Read\n"
        "---\n\nInstructions.\n",
        encoding="utf-8",
    )

    created = store.create_skill({"name": "portable", "package_root": str(source)})

    assert created["metadata"]["license"] == "Apache-2.0"
    assert created["metadata"]["compatibility"] == "Python 3.10+"
    assert created["metadata"]["metadata"] == {"owner": "qa"}
    assert created["metadata"]["allowed-tools"] == ["Read"]
    published = parse_frontmatter(
        (Path(created["package_root"]) / "SKILL.md").read_text(encoding="utf-8")
    )[0]
    assert published == created["metadata"]


def test_create_skill_imports_in_place_when_package_under_root(tmp_path):
    store = _make_store(tmp_path)
    # A package that already lives under the managed skills root, in a directory
    # whose name (and frontmatter) does not yet match the requested skill name,
    # so get_skill('native') is None before creation.
    in_root = tmp_path / "skills" / "pkgdir"
    in_root.mkdir(parents=True)
    (in_root / "SKILL.md").write_text(
        "---\nname: placeholder\ndescription: imported desc\n---\n\nImported body\n",
        encoding="utf-8",
    )
    (in_root / "asset.txt").write_text("payload", encoding="utf-8")

    created = store.create_skill(
        {
            "name": "native",
            "package_root": str(in_root),
            "display_name": "Overridden",
        }
    )
    assert created["name"] == "native"
    assert created["display_name"] == "Overridden"
    # The legacy source is only an import source and is not rewritten in place.
    assert created["package_root"] != os.path.realpath(str(in_root))
    assert (in_root / "asset.txt").read_text() == "payload"


def test_create_skill_missing_external_dir_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="Directory does not exist"):
        store.create_skill(
            {
                "name": "ghost",
                "package_root": str(tmp_path / "nope"),
            }
        )


def test_create_skill_external_target_collision_raises(tmp_path):
    store = _make_store(tmp_path)
    # Managed dir already exists.
    _write_skill_dir(tmp_path / "skills", "clash")
    external = _write_skill_dir(tmp_path / "ext", "clash")
    with pytest.raises(ValueError, match="already exists"):
        store.create_skill({"name": "clash", "package_root": external})


# ── update_skill ────────────────────────────────────────────────────────


def test_update_skill_changes_metadata_and_instructions(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "edit", "instructions": "old"})
    updated = store.update_skill(
        "edit",
        {
            "display_name": "Edited",
            "description": "new desc",
            "instructions": "new body",
        },
        base_revision=created["revision"],
    )
    assert updated["display_name"] == "Edited"
    assert updated["description"] == "new desc"
    assert updated["instructions"].strip() == "new body"


def test_update_skill_missing_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        store.update_skill("ghost", {"instructions": "x"}, base_revision=None)


def test_update_skill_rename_rejected(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "keep", "instructions": "x"})
    with pytest.raises(ValueError, match="Renaming"):
        store.update_skill(
            "keep",
            {"name": "renamed"},
            base_revision=created["revision"],
        )


def test_update_skill_changing_package_root_rejected(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "fixed", "instructions": "x"})
    with pytest.raises(ValueError, match="Updating package_root is not supported"):
        store.update_skill(
            "fixed",
            {"package_root": str(tmp_path / "somewhere-else")},
            base_revision=created["revision"],
        )


def test_update_skill_same_package_root_is_not_a_publication_input(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "samep", "instructions": "x"})
    with pytest.raises(ValueError, match="publish a draft"):
        store.update_skill(
            "samep",
            {
                "package_root": created["package_root"],
                "instructions": "changed",
            },
            base_revision=created["revision"],
        )


# ── delete_skill ────────────────────────────────────────────────────────


def test_delete_skill_removes_current_pointer_but_retains_revision(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "gone", "instructions": "x"})
    assert os.path.isdir(created["package_root"])
    result = store.delete_skill("gone")
    assert result == {"deleted": "gone"}
    assert store.get_skill("gone") is None
    assert store.get_skill_snapshot("gone", created["revision"]) is not None


def test_delete_skill_missing_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        store.delete_skill("ghost")


def test_delete_skill_rejects_skill_at_root_level(tmp_path):
    # The store root is registry infrastructure, not a legacy package slot.
    store = _make_store(tmp_path)
    root = store.root
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: rootskill\n---\n\nbody\n")

    assert store.get_skill("rootskill") is None
    with pytest.raises(ValueError, match="not found"):
        store.delete_skill("rootskill")


def test_delete_skill_imported_external_is_managed(tmp_path):
    # An externally imported skill is copied under the managed root, becoming
    # deletable.
    store = _make_store(tmp_path)
    outside = _write_skill_dir(tmp_path / "outside", "external")
    created = store.create_skill({"name": "external", "package_root": outside})
    assert os.path.realpath(created["package_root"]).startswith(
        os.path.realpath(store.root) + os.sep
    )
    assert store.delete_skill("external") == {"deleted": "external"}
    assert store.get_skill("external") is None


# ── scan_directory ──────────────────────────────────────────────────────


def test_scan_directory_finds_single_skill(tmp_path):
    store = _make_store(tmp_path)
    skill_dir = _write_skill_dir(tmp_path / "scan", "one")
    scanned = store.scan_directory(skill_dir)
    assert scanned["name"] == "one"


def test_scan_directory_finds_skill_in_subdir(tmp_path):
    store = _make_store(tmp_path)
    base = tmp_path / "scan"
    _write_skill_dir(base, "nested")
    scanned = store.scan_directory(str(base))
    assert scanned["name"] == "nested"


def test_scan_directory_missing_path_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="Directory does not exist"):
        store.scan_directory(str(tmp_path / "nope"))


def test_scan_directory_no_skill_raises(tmp_path):
    store = _make_store(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="No SKILL.md found"):
        store.scan_directory(str(empty))


def test_scan_directory_multiple_skills_raises(tmp_path):
    store = _make_store(tmp_path)
    base = tmp_path / "multi"
    _write_skill_dir(base, "a")
    _write_skill_dir(base, "b")
    with pytest.raises(ValueError, match="Multiple skill directories"):
        store.scan_directory(str(base))


# ── per-file CRUD ───────────────────────────────────────────────────────


def test_list_skill_files_root_and_subdir(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "files", "instructions": "x"})
    store.write_skill_file(
        "files",
        "sub/inner.txt",
        "hi",
        base_revision=created["revision"],
    )

    top = store.list_skill_files("files")
    assert top["skill"] == {"name": "files"}
    assert top["base_path"] == "."
    names = {e["name"] for e in top["entries"]}
    assert {"SKILL.md", "sub"} <= names
    sub_entry = next(e for e in top["entries"] if e["name"] == "sub")
    assert sub_entry["is_dir"] is True
    assert sub_entry["size"] is None

    inner = store.list_skill_files("files", "sub")
    assert inner["base_path"] == "sub"
    assert [e["name"] for e in inner["entries"]] == ["inner.txt"]
    assert inner["entries"][0]["path"] == "sub/inner.txt"
    assert inner["entries"][0]["size"] == len("hi")


def test_list_skill_files_hidden_filter(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "hid", "instructions": "x"})
    store.write_skill_file(
        "hid",
        ".secret",
        "shh",
        base_revision=created["revision"],
    )

    without = {e["name"] for e in store.list_skill_files("hid")["entries"]}
    assert ".secret" not in without

    with_hidden = {
        e["name"] for e in store.list_skill_files("hid", include_hidden=True)["entries"]
    }
    assert ".secret" in with_hidden


def test_list_skill_files_truncation(tmp_path):
    store = _make_store(tmp_path)
    current = store.create_skill({"name": "many", "instructions": "x"})
    for i in range(5):
        result = store.write_skill_file(
            "many",
            f"file{i}.txt",
            "data",
            base_revision=current["revision"],
        )
        current = store.get_skill_snapshot("many")
        assert current["revision"] == result["revision"]

    result = store.list_skill_files("many", max_entries=3)
    assert len(result["entries"]) == 3
    assert result["truncated"] is True


def test_list_skill_files_missing_skill_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="not found"):
        store.list_skill_files("ghost")


def test_list_skill_files_directory_not_found_raises(tmp_path):
    store = _make_store(tmp_path)
    store.create_skill({"name": "s", "instructions": "x"})
    with pytest.raises(ValueError, match="Skill directory not found"):
        store.list_skill_files("s", "no-such-dir")


def test_read_write_edit_delete_round_trip(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "crud", "instructions": "x"})

    write_result = store.write_skill_file(
        "crud",
        "data/info.txt",
        "hello world",
        base_revision=created["revision"],
    )
    assert write_result["path"] == "data/info.txt"
    assert write_result["bytes_written"] == len("hello world".encode("utf-8"))

    read_result = store.read_skill_file("crud", "data/info.txt")
    assert read_result["content"] == "hello world"
    assert read_result["path"] == "data/info.txt"
    assert read_result["skill"] == {"name": "crud"}

    # "Edit" == overwrite via write_skill_file.
    store.write_skill_file(
        "crud",
        "data/info.txt",
        "edited",
        base_revision=write_result["revision"],
    )
    assert store.read_skill_file("crud", "data/info.txt")["content"] == "edited"
    assert (
        store.read_skill_resource(
            "crud",
            "data/info.txt",
            expected_revision=write_result["revision"],
        )["content"]
        == "hello world"
    )


def test_write_skill_file_handles_unicode(tmp_path):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "uni", "instructions": "x"})
    text = "你好, мир 🌍"
    result = store.write_skill_file(
        "uni",
        "i18n.txt",
        text,
        base_revision=created["revision"],
    )
    assert result["bytes_written"] == len(text.encode("utf-8"))
    assert store.read_skill_file("uni", "i18n.txt")["content"] == text


def test_read_skill_file_non_utf8_raises(tmp_path):
    store = _make_store(tmp_path)
    source = tmp_path / "binary-source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: binskill\n---\n\nx", encoding="utf-8")
    binpath = source / "blob.bin"
    with open(binpath, "wb") as f:
        f.write(b"\xff\xfe\x00\x01")
    store.create_skill(
        {"name": "binskill", "package_root": str(source), "instructions": "x"}
    )
    with pytest.raises(ValueError, match="not valid UTF-8"):
        store.read_skill_file("binskill", "blob.bin")


def test_read_skill_file_rejects_oversized_text(tmp_path, monkeypatch):
    store = _make_store(tmp_path)
    source = tmp_path / "large-source"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: large-read\n---\n\nx", encoding="utf-8"
    )
    (source / "large.txt").write_bytes(b"x" * 129)
    store.create_skill(
        {"name": "large-read", "package_root": str(source), "instructions": "x"}
    )
    monkeypatch.setattr(skill_store_module, "_MAX_SKILL_TEXT_BYTES", 128)

    with pytest.raises(ValueError, match="exceeds"):
        store.read_skill_file("large-read", "large.txt")


def test_write_skill_file_rejects_oversized_text(tmp_path, monkeypatch):
    store = _make_store(tmp_path)
    created = store.create_skill({"name": "large-write", "instructions": "x"})
    monkeypatch.setattr(skill_store_module, "_MAX_SKILL_TEXT_BYTES", 128)

    with pytest.raises(ValueError, match="exceeds"):
        store.write_skill_file(
            "large-write",
            "large.txt",
            "x" * 129,
            base_revision=created["revision"],
        )


def test_read_skill_file_missing_raises(tmp_path):
    store = _make_store(tmp_path)
    store.create_skill({"name": "s", "instructions": "x"})
    with pytest.raises(ValueError, match="Skill file not found"):
        store.read_skill_file("s", "missing.txt")


# ── path traversal rejection in _resolve_skill_path ─────────────────────


@pytest.mark.parametrize("bad_path", ["../escape.txt", "../../etc/passwd", ".."])
def test_skill_file_relative_traversal_rejected(tmp_path, bad_path):
    store = _make_store(tmp_path)
    store.create_skill({"name": "safe", "instructions": "x"})
    with pytest.raises(ValueError, match="stay within the skill package root"):
        store.read_skill_file("safe", bad_path)


def test_skill_file_absolute_path_rejected(tmp_path):
    store = _make_store(tmp_path)
    store.create_skill({"name": "safe", "instructions": "x"})
    with pytest.raises(ValueError, match="must be relative"):
        store.read_skill_file("safe", str(tmp_path / "outside.txt"))


def test_list_skill_files_absolute_path_rejected(tmp_path):
    store = _make_store(tmp_path)
    store.create_skill({"name": "safe", "instructions": "x"})
    with pytest.raises(ValueError, match="must be relative"):
        store.list_skill_files("safe", str(tmp_path))


# ── _safe_extract_zip / zip-slip rejection ──────────────────────────────


def _zip_with_member(arcname: str, data: bytes = b"x") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        # SKILL.md so the extraction has something legitimate too.
        zf.writestr("pkg/SKILL.md", "---\nname: pkg\n---\nbody\n")
        zf.writestr(arcname, data)
    return buffer.getvalue()


def test_safe_extract_zip_extracts_clean_archive(tmp_path):
    target = tmp_path / "out"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("a/b.txt", "data")
        zf.writestr("a/c/", "")  # directory entry, should be skipped without error
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as zf:
        SkillStore._safe_extract_zip(zf, str(target))
    assert (target / "a" / "b.txt").read_text() == "data"


def test_safe_extract_zip_streams_without_extractall(tmp_path, monkeypatch):
    store = _make_store(tmp_path)
    monkeypatch.setattr(
        zipfile.ZipFile,
        "extractall",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("extractall used")
        ),
    )

    preview = store.preview_zip_upload(file_bytes=_skill_zip(), filename="demo.zip")

    assert [item["name"] for item in preview] == ["demo"]


def test_zip_upload_rejects_compressed_byte_cap_for_preview_and_install(
    tmp_path, monkeypatch
):
    store = _make_store(tmp_path)
    payload = _skill_zip()
    monkeypatch.setattr(
        skill_store_module, "_MAX_ZIP_COMPRESSED_BYTES", len(payload) - 1
    )

    with pytest.raises(ValueError, match="compressed size limit"):
        store.preview_zip_upload(file_bytes=payload, filename="demo.zip")
    with pytest.raises(ValueError, match="compressed size limit"):
        store.install_zip_upload(file_bytes=payload, filename="demo.zip")


def test_zip_upload_rejects_entry_count_cap(tmp_path, monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pkg/SKILL.md", "name: pkg")
        archive.writestr("pkg/a", "a")
        archive.writestr("pkg/b", "b")
    monkeypatch.setattr(skill_store_module, "_MAX_ZIP_ENTRIES", 2)

    with pytest.raises(ValueError, match="too many entries"):
        _make_store(tmp_path).preview_zip_upload(
            file_bytes=buffer.getvalue(), filename="pkg.zip"
        )


def test_zip_upload_rejects_per_entry_and_total_uncompressed_caps(
    tmp_path, monkeypatch
):
    per_entry = io.BytesIO()
    with zipfile.ZipFile(per_entry, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("pkg/SKILL.md", b"x" * 33)
    monkeypatch.setattr(skill_store_module, "_MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES", 32)
    with pytest.raises(ValueError, match="entry exceeds the uncompressed size"):
        _make_store(tmp_path).preview_zip_upload(
            file_bytes=per_entry.getvalue(), filename="pkg.zip"
        )

    monkeypatch.setattr(skill_store_module, "_MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES", 64)
    monkeypatch.setattr(skill_store_module, "_MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES", 10)
    total = io.BytesIO()
    with zipfile.ZipFile(total, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("pkg/a", b"a" * 6)
        archive.writestr("pkg/b", b"b" * 6)
    with pytest.raises(ValueError, match="total uncompressed size"):
        _make_store(tmp_path).preview_zip_upload(
            file_bytes=total.getvalue(), filename="pkg.zip"
        )


def test_zip_upload_rejects_compression_ratio_and_symlink(tmp_path, monkeypatch):
    ratio = io.BytesIO()
    with zipfile.ZipFile(ratio, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("pkg/SKILL.md", b"a" * 4096)
    monkeypatch.setattr(skill_store_module, "_MAX_ZIP_COMPRESSION_RATIO", 2.0)
    with pytest.raises(ValueError, match="compression ratio"):
        _make_store(tmp_path).preview_zip_upload(
            file_bytes=ratio.getvalue(), filename="pkg.zip"
        )

    monkeypatch.setattr(skill_store_module, "_MAX_ZIP_COMPRESSION_RATIO", 100.0)
    link_archive = io.BytesIO()
    with zipfile.ZipFile(link_archive, "w") as archive:
        archive.writestr("pkg/SKILL.md", "name: pkg")
        link = zipfile.ZipInfo("pkg/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "../../secret")
    with pytest.raises(ValueError, match="symbolic link"):
        _make_store(tmp_path).preview_zip_upload(
            file_bytes=link_archive.getvalue(), filename="pkg.zip"
        )


def test_safe_extract_zip_rejects_parent_traversal(tmp_path):
    payload = _zip_with_member("../evil.txt")
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="unsafe path"):
        store.preview_zip_upload(file_bytes=payload, filename="evil.zip")


def test_safe_extract_zip_rejects_absolute_member(tmp_path):
    payload = _zip_with_member("/tmp/abs-evil.txt")
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="unsafe path"):
        store.preview_zip_upload(file_bytes=payload, filename="evil.zip")


def test_safe_extract_zip_rejects_nested_parent_escape(tmp_path):
    payload = _zip_with_member("sub/../../escape.txt")
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="unsafe path"):
        store.preview_zip_upload(file_bytes=payload, filename="evil.zip")


# ── zip upload error handling ───────────────────────────────────────────


def test_preview_zip_upload_empty_bytes_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="empty"):
        store.preview_zip_upload(file_bytes=b"", filename="x.zip")


def test_install_zip_upload_empty_bytes_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="empty"):
        store.install_zip_upload(file_bytes=b"", filename="x.zip")


def test_preview_zip_upload_corrupt_archive_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="valid .zip archive"):
        store.preview_zip_upload(file_bytes=b"not a zip at all", filename="x.zip")


def test_preview_zip_upload_no_skill_in_archive_raises(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("pkg/readme.txt", "no skill here")
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="No SKILL.md found"):
        store.preview_zip_upload(file_bytes=buffer.getvalue(), filename="pkg.zip")


def test_install_zip_upload_multiple_without_selection_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="Please choose one or more source_paths"):
        store.install_zip_upload(
            file_bytes=_nested_skill_zip(),
            filename="repo.zip",
            source_subdir="packages",
        )


def test_install_zip_upload_invalid_source_path_raises(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="Invalid source_path"):
        store.install_zip_upload(
            file_bytes=_nested_skill_zip(),
            filename="repo.zip",
            source_subdir="packages",
            source_paths=["gamma"],
        )


def test_install_zip_upload_existing_target_raises(tmp_path):
    store = _make_store(tmp_path)
    # First install succeeds.
    store.install_zip_upload(file_bytes=_skill_zip(), filename="demo.zip")
    # Re-installing into the same computed target dir should fail.
    with pytest.raises(ValueError, match="already exists"):
        store.install_zip_upload(file_bytes=_skill_zip(), filename="demo.zip")


def test_install_zip_upload_installs_multiple_selected(tmp_path):
    store = _make_store(tmp_path)
    installed = store.install_zip_upload(
        file_bytes=_nested_skill_zip(),
        filename="repo.zip",
        source_subdir="packages",
        source_paths=["alpha", "beta"],
    )
    assert sorted(s["name"] for s in installed) == ["alpha", "beta"]
    assert store.get_skill("alpha") is not None
    assert store.get_skill("beta") is not None


def test_install_zip_upload_legacy_source_path_arg(tmp_path):
    # The singular `source_path` argument is honored alongside `source_paths`.
    store = _make_store(tmp_path)
    installed = store.install_zip_upload(
        file_bytes=_nested_skill_zip(),
        filename="repo.zip",
        source_subdir="packages",
        source_path="alpha",
    )
    assert [s["name"] for s in installed] == ["alpha"]


def test_root_level_skill_zip_uses_frontmatter_name(tmp_path):
    store = _make_store(tmp_path)

    preview = store.preview_zip_upload(
        file_bytes=_root_skill_zip("demo"), filename="demo.zip"
    )
    assert preview[0]["name"] == "demo"
    assert preview[0]["source_path"] == ""

    installed = store.install_zip_upload(
        file_bytes=_root_skill_zip("demo"), filename="demo.zip"
    )
    assert [skill["name"] for skill in installed] == ["demo"]


def test_install_zip_upload_multi_top_level_uses_extract_root(tmp_path):
    # An archive with multiple top-level entries is rooted at the extract dir,
    # and skills are discovered within it.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "alpha/SKILL.md", "---\nname: alpha\ndescription: Alpha skill\n---\n\nA\n"
        )
        zf.writestr(
            "beta/SKILL.md", "---\nname: beta\ndescription: Beta skill\n---\n\nB\n"
        )
        zf.writestr("toplevel.txt", "loose file at root")
    payload = buffer.getvalue()

    store = _make_store(tmp_path)
    candidates = store.preview_zip_upload(file_bytes=payload, filename="multi.zip")
    assert sorted(c["source_path"] for c in candidates) == ["alpha", "beta"]

    installed = store.install_zip_upload(
        file_bytes=payload,
        filename="multi.zip",
        source_paths=["alpha"],
    )
    assert [s["name"] for s in installed] == ["alpha"]


# ── source_subdir validation ────────────────────────────────────────────


def test_source_subdir_traversal_rejected(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="stay within the uploaded archive"):
        store.preview_zip_upload(
            file_bytes=_nested_skill_zip(),
            filename="repo.zip",
            source_subdir="../escape",
        )


def test_source_subdir_leading_slash_is_stripped_then_checked(tmp_path):
    # Leading slashes are stripped, so an "/etc" subdir is treated as relative
    # "etc" and rejected for not existing inside the archive (not as absolute).
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="does not exist in the uploaded archive"):
        store.preview_zip_upload(
            file_bytes=_nested_skill_zip(),
            filename="repo.zip",
            source_subdir="/etc",
        )


def test_source_subdir_nonexistent_rejected(tmp_path):
    store = _make_store(tmp_path)
    with pytest.raises(ValueError, match="does not exist in the uploaded archive"):
        store.preview_zip_upload(
            file_bytes=_nested_skill_zip(),
            filename="repo.zip",
            source_subdir="packages/missing",
        )


# ── filename stem sanitization ──────────────────────────────────────────


@pytest.mark.parametrize(
    "filename, expected_prefix",
    [
        ("My Skill!.zip", "My-Skill"),
        ("", "uploaded-skill"),
        ("???.zip", "uploaded-skill"),
        ("clean_name.zip", "clean_name"),
    ],
)
def test_uploaded_skill_target_stem_sanitization(filename, expected_prefix):
    assert SkillStore._uploaded_skill_target_stem(filename) == expected_prefix


def test_preview_target_dir_appends_leaf_and_suffix(tmp_path):
    store = _make_store(tmp_path)
    preview = store.preview_zip_upload(
        file_bytes=_nested_skill_zip(),
        filename="repo.zip",
        source_subdir="packages",
        target_suffix="v2",
    )
    package_roots = {os.path.basename(p["package_root"]) for p in preview}
    assert package_roots == {"repo-alpha-v2", "repo-beta-v2"}
