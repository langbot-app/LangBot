import io
import zipfile

import pytest

from langbot_plugin.skill_store import SkillRevisionConflictError, SkillStore


def draft_zip(instructions="version one", *, prefix="", entry="SKILL.md"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            prefix + entry,
            "---\nname: draft\ndescription: Draft guidance\n---\n\n" + instructions,
        )
        archive.writestr(prefix + "guide.txt", instructions)
    return output.getvalue()


def test_zip_import_reads_metadata_and_publishes_one_cas_update(tmp_path):
    store = SkillStore(tmp_path / "skills")
    first = store.import_skill_zip(draft_zip(prefix="package/"), {})
    assert first["name"] == "draft"
    assert first["description"] == "Draft guidance"
    assert first["instructions"] == "version one"
    second = store.import_skill_zip(
        draft_zip("version two"),
        {"display_name": "Published draft", "instructions": "Explicit guidance"},
        base_revision=first["revision"],
    )
    assert second["revision"] != first["revision"]
    assert second["display_name"] == "Published draft"
    assert second["instructions"] == "Explicit guidance"
    assert store.get_skill_snapshot("draft")["revision"] == second["revision"]
    assert (
        store.get_skill_snapshot("draft", first["revision"])["instructions"]
        == "version one"
    )
    assert (
        store.read_skill_resource(
            "draft", "guide.txt", expected_revision=second["revision"]
        )["content"]
        == "version two"
    )


def test_zip_import_conflict_retains_published_revision(tmp_path):
    store = SkillStore(tmp_path / "skills")
    first = store.import_skill_zip(draft_zip(), {})
    second = store.import_skill_zip(
        draft_zip("version two"), {}, base_revision=first["revision"]
    )
    for base_revision in (None, first["revision"]):
        with pytest.raises(SkillRevisionConflictError):
            store.import_skill_zip(
                draft_zip("must not publish"), {}, base_revision=base_revision
            )
        assert store.get_skill_snapshot("draft")["revision"] == second["revision"]
        assert (
            store.read_skill_resource(
                "draft", "guide.txt", expected_revision=second["revision"]
            )["content"]
            == "version two"
        )


@pytest.mark.parametrize("invalid", ["empty", "missing_entry", "traversal"])
def test_invalid_draft_zip_does_not_publish(tmp_path, invalid):
    store = SkillStore(tmp_path / "skills")
    if invalid == "empty":
        payload = b""
    else:
        payload = draft_zip(
            entry="readme.txt" if invalid == "missing_entry" else "../SKILL.md"
        )
    with pytest.raises(ValueError):
        store.import_skill_zip(payload, {})
    assert store.get_skill_snapshot("draft") is None


def test_zip_import_cannot_supply_base_revision_for_missing_skill(tmp_path):
    store = SkillStore(tmp_path / "skills")
    with pytest.raises(SkillRevisionConflictError, match="does not exist"):
        store.import_skill_zip(draft_zip(), {}, base_revision="sha256:" + "0" * 64)
    assert store.get_skill_snapshot("draft") is None
