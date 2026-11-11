from __future__ import annotations

import os
import stat
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import mock

import pytest

from langbot_plugin.skill_store import (
    SkillRevisionConflictError,
    SkillStore,
    skill_namespace,
)


def test_generic_store_uses_an_execution_independent_root(tmp_path):
    store = SkillStore(tmp_path / "skills").scoped("workspace-a")

    created = store.create_skill(
        {
            "name": "docs-only",
            "description": "Read-only guidance",
            "instructions": "Read references/guide.md.",
        }
    )
    updated = store.write_skill_file(
        "docs-only",
        "references/guide.md",
        "# Guide\n\nNo execution needed.",
        base_revision=created["revision"],
    )

    snapshot = store.get_skill_snapshot("docs-only")
    assert snapshot is not None
    assert snapshot["revision"].startswith("sha256:")
    assert snapshot["revision"] == updated["revision"]
    assert (
        f"{os.sep}.langbot-skill-store{os.sep}revisions{os.sep}"
        in snapshot["package_root"]
    )
    assert stat.S_IMODE(os.stat(snapshot["package_root"]).st_mode) & 0o222 == 0
    assert (
        stat.S_IMODE(
            os.stat(
                os.path.join(snapshot["package_root"], "references", "guide.md")
            ).st_mode
        )
        & 0o222
        == 0
    )

    with mock.patch(
        "langbot_plugin.skill_store.mimetypes.guess_type",
        return_value=("text/plain", None),
    ):
        listed = store.list_skill_resources(
            "docs-only",
            "references",
            expected_revision=snapshot["revision"],
        )
        resource = store.read_skill_resource(
            "docs-only",
            "references/guide.md",
            expected_revision=snapshot["revision"],
        )
    assert listed["entries"][0]["mime_type"] == "text/markdown"
    assert resource["mime_type"] == "text/markdown"
    assert resource["content"].startswith("# Guide")
    assert resource["revision"] == snapshot["revision"]


def test_skill_namespace_is_stable_and_workspace_scoped():
    first = skill_namespace("instance-a", "workspace-a")

    assert first == skill_namespace("instance-a", "workspace-a")
    assert first != skill_namespace("instance-a", "workspace-b")
    assert first.startswith("ws-")


def test_pinned_revision_remains_readable_after_publishing_v2(tmp_path):
    store = SkillStore(tmp_path / "skills")
    v1 = store.create_skill({"name": "safe", "instructions": "version one"})
    v2 = store.update_skill(
        "safe",
        {"instructions": "version two"},
        base_revision=v1["revision"],
    )

    assert v1["revision"] != v2["revision"]
    assert v1["package_root"] != v2["package_root"]
    assert store.get_skill_snapshot("safe")["instructions"] == "version two"
    assert (
        store.get_skill_snapshot("safe", v1["revision"])["instructions"]
        == "version one"
    )


def test_resource_reads_use_persisted_revision_without_rescanning_package(tmp_path):
    store = SkillStore(tmp_path / "skills")
    created = store.create_skill({"name": "docs", "instructions": "Read guide.md."})
    store.write_skill_file(
        "docs",
        "guide.md",
        "content",
        base_revision=created["revision"],
    )
    snapshot = store.get_skill_snapshot("docs")
    assert snapshot is not None

    with (
        mock.patch.object(
            store,
            "_package_manifest",
            side_effect=AssertionError("published reads must not digest the package"),
        ),
        mock.patch.object(
            store,
            "_require_skill",
            wraps=store._require_skill,
        ) as require_skill_mock,
    ):
        result = store.read_skill_resource(
            "docs",
            "guide.md",
            expected_revision=snapshot["revision"],
        )

    assert result["content"] == "content"
    assert require_skill_mock.call_count == 1


def test_update_requires_matching_base_revision(tmp_path):
    store = SkillStore(tmp_path / "skills")
    v1 = store.create_skill({"name": "docs", "instructions": "v1"})

    with pytest.raises(SkillRevisionConflictError, match="requires base_revision"):
        store.update_skill("docs", {"instructions": "missing"}, base_revision=None)
    with pytest.raises(SkillRevisionConflictError, match="changed since"):
        store.update_skill(
            "docs",
            {"instructions": "stale"},
            base_revision="sha256:" + "0" * 64,
        )

    assert store.get_skill_snapshot("docs")["revision"] == v1["revision"]


def test_failed_pointer_update_keeps_previous_revision_current(tmp_path):
    store = SkillStore(tmp_path / "skills")
    v1 = store.create_skill({"name": "docs", "instructions": "v1"})

    with (
        mock.patch.object(
            store,
            "_write_registry_atomic",
            side_effect=OSError("simulated interrupted publication"),
        ),
        pytest.raises(OSError, match="interrupted"),
    ):
        store.update_skill(
            "docs",
            {"instructions": "v2"},
            base_revision=v1["revision"],
        )

    reopened = SkillStore(tmp_path / "skills")
    assert reopened.get_skill_snapshot("docs")["revision"] == v1["revision"]
    assert reopened.get_skill_snapshot("docs")["instructions"] == "v1"


def test_storage_lock_rejects_one_of_two_conflicting_publishers(tmp_path):
    first = SkillStore(tmp_path / "skills")
    v1 = first.create_skill({"name": "docs", "instructions": "v1"})
    stores = [first, SkillStore(tmp_path / "skills")]
    barrier = Barrier(2)

    def publish(index: int):
        barrier.wait()
        return stores[index].update_skill(
            "docs",
            {"instructions": f"writer-{index}"},
            base_revision=v1["revision"],
        )

    results: list[dict] = []
    errors: list[Exception] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(publish, index) for index in range(2)]
        for future in futures:
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append(exc)

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], SkillRevisionConflictError)
    assert first.get_skill_snapshot("docs")["revision"] == results[0]["revision"]


def test_deleted_current_skill_retains_revision_for_recovery(tmp_path):
    store = SkillStore(tmp_path / "skills")
    published = store.create_skill({"name": "docs", "instructions": "recover me"})

    store.delete_skill("docs")

    assert store.get_skill("docs") is None
    recovered = store.get_skill_snapshot("docs", published["revision"])
    assert recovered["instructions"] == "recover me"


def test_republished_draft_does_not_retain_deleted_files(tmp_path):
    store = SkillStore(tmp_path / "skills").scoped("workspace-a")
    workspace = tmp_path / "workspace"
    draft = workspace / "draft"
    draft.mkdir(parents=True)
    (draft / "SKILL.md").write_text("---\nname: draft\n---\n\nv1", encoding="utf-8")
    (draft / "removed.txt").write_text("old", encoding="utf-8")
    v1 = store.import_skill_directory(
        str(draft),
        {"name": "draft"},
        source_root=str(workspace),
    )

    (draft / "SKILL.md").write_text("---\nname: draft\n---\n\nv2", encoding="utf-8")
    (draft / "removed.txt").unlink()
    (draft / "added.txt").write_text("new", encoding="utf-8")
    v2 = store.import_skill_directory(
        str(draft),
        {"name": "draft"},
        source_root=str(workspace),
        base_revision=v1["revision"],
    )

    old_files = store.list_skill_resources("draft", expected_revision=v1["revision"])
    new_files = store.list_skill_resources("draft", expected_revision=v2["revision"])
    assert {item["name"] for item in old_files["entries"]} == {
        "SKILL.md",
        "removed.txt",
    }
    assert {item["name"] for item in new_files["entries"]} == {
        "SKILL.md",
        "added.txt",
    }


def test_generic_store_imports_only_from_a_fenced_source_root(tmp_path):
    store = SkillStore(tmp_path / "skills").scoped("workspace-a")
    workspace = tmp_path / "workspace"
    draft = workspace / "draft"
    draft.mkdir(parents=True)
    (draft / "SKILL.md").write_text(
        "---\nname: draft\ndescription: Draft skill\n---\n\nFollow the guide.",
        encoding="utf-8",
    )
    (draft / "guide.md").write_text("Imported resource", encoding="utf-8")

    scanned = store.scan_import_directory(str(draft), source_root=str(workspace))
    imported = store.import_skill_directory(
        str(draft),
        {
            "name": scanned["name"],
            "description": scanned["description"],
            "instructions": scanned["instructions"],
        },
        source_root=str(workspace),
    )
    assert imported["name"] == "draft"
    assert (
        store.read_skill_resource("draft", "guide.md")["content"] == "Imported resource"
    )

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("Outside", encoding="utf-8")
    with pytest.raises(ValueError, match="trusted source root"):
        store.scan_import_directory(str(outside), source_root=str(workspace))


def test_generic_store_rejects_symlinks_during_import(tmp_path):
    store = SkillStore(tmp_path / "skills").scoped("workspace-a")
    workspace = tmp_path / "workspace"
    draft = workspace / "draft"
    draft.mkdir(parents=True)
    (draft / "SKILL.md").write_text("---\nname: draft\n---\n\nDraft", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        (draft / "linked.txt").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable on this platform")

    with pytest.raises(ValueError, match="symbolic links"):
        store.import_skill_directory(
            str(draft),
            {"name": "draft", "instructions": "Draft"},
            source_root=str(workspace),
        )
