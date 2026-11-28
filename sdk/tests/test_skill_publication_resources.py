"""Publication resources preserve file API rules without creating a cache tree."""

import copy
import hashlib
import io
import json
import stat
import zipfile

import pytest

from langbot_plugin.artifact import validate_tree_manifest
from langbot_plugin.skill_store import SkillRevisionMismatchError, SkillStore


@pytest.fixture
def publication(tmp_path):
    source = tmp_path / "sample"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: sample\ndescription: Resource publication\n---\nRead references.\n"
    )
    (source / "references").mkdir()
    (source / "references/guide.md").write_text("# Guide\nExact UTF-8: 你好\n")
    (source / "references/.hidden").write_text("hidden")
    (source / "references/nested").mkdir()
    (source / "references/nested/note.txt").write_text("Nested note")
    (source / "binary.bin").write_bytes(b"\xff\x00")
    (source / "large.bin").write_bytes(b"large binary\x00" * 180_000)
    store = SkillStore(tmp_path / "store")
    skill = store.import_skill_directory(
        str(source), {"name": "sample"}, source_root=str(tmp_path)
    )
    return store, store.export_skill_publication("sample", skill["revision"])


def listing(publication, path=".", **kwargs):
    _, package = publication
    return SkillStore.list_publication_resources(
        package["skill"], package["manifest"], package["file_bytes"], path, **kwargs
    )


def manifest_listing(publication, path=".", **kwargs):
    _, package = publication
    return SkillStore.list_publication_manifest_resources(
        package["skill"], package["manifest"], path, **kwargs
    )


def reading(publication, path="references/guide.md", **kwargs):
    _, package = publication
    return SkillStore.read_publication_resource(
        package["skill"], package["manifest"], package["file_bytes"], path, **kwargs
    )


@pytest.mark.parametrize(
    "path,hidden,limit",
    [
        (".", False, 200),
        ("references", False, 200),
        ("references/", True, 1),
        ("references/nested", False, 1001),
    ],
)
@pytest.mark.parametrize("list_resources", [listing, manifest_listing])
def test_publication_listing_matches_filesystem_without_writing(
    publication, tmp_path, path, hidden, limit, list_resources
):
    store, package = publication
    before = {str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")}
    expected = store.list_skill_resources(
        "sample", path, hidden, limit, expected_revision=package["skill"]["revision"]
    )
    assert (
        list_resources(publication, path, include_hidden=hidden, max_entries=limit)
        == expected
    )
    assert {str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*")} == before


def test_publication_read_matches_exact_filesystem_result(publication):
    store, package = publication
    result = reading(publication, expected_revision=package["skill"]["revision"])
    assert result == store.read_skill_resource(
        "sample", "references/guide.md", expected_revision=package["skill"]["revision"]
    )
    assert result["content"] == "# Guide\nExact UTF-8: 你好\n"
    assert result["mime_type"] == "text/markdown"
    assert (
        listing(publication, "references", include_hidden=True)["entries"][0]["name"]
        == ".hidden"
    )


@pytest.mark.parametrize(
    "path",
    [
        "../outside",
        "/etc/passwd",
        "references/../../outside",
        "references\\guide.md",
        "a\x00b",
    ],
)
@pytest.mark.parametrize("list_resources", [listing, manifest_listing])
def test_publication_resource_paths_cannot_escape(publication, path, list_resources):
    with pytest.raises(ValueError):
        reading(publication, path)
    with pytest.raises(ValueError):
        list_resources(publication, path)


@pytest.mark.parametrize("limit", [0, -1, True, "1"])
@pytest.mark.parametrize("list_resources", [listing, manifest_listing])
def test_publication_listing_rejects_invalid_limits(publication, limit, list_resources):
    with pytest.raises(ValueError, match="positive integer"):
        list_resources(publication, max_entries=limit)


def test_manifest_listing_needs_no_archive_and_preserves_resource_errors(publication):
    _, package = publication
    expected = listing(publication)
    del package["file_bytes"]
    assert manifest_listing(publication) == expected
    for path in ["references/guide.md", "missing-directory"]:
        with pytest.raises(ValueError, match="not found"):
            manifest_listing(publication, path)
    with pytest.raises(SkillRevisionMismatchError):
        manifest_listing(publication, expected_revision="sha256:" + "0" * 64)


def test_publication_resource_rejects_missing_nontext_or_wrong_revision(publication):
    with pytest.raises(ValueError, match="not found"):
        reading(publication, "missing.md")
    with pytest.raises(ValueError, match="not found"):
        listing(publication, "references/guide.md")
    with pytest.raises(ValueError, match="not found"):
        listing(publication, "missing-directory")
    with pytest.raises(ValueError, match="UTF-8"):
        reading(publication, "binary.bin")
    with pytest.raises(ValueError, match="limit"):
        reading(publication, "large.bin")
    with pytest.raises(SkillRevisionMismatchError):
        reading(publication, expected_revision="sha256:" + "0" * 64)


def modified_package(
    publication, *, change=None, extra=False, duplicate=False, update_manifest=False
):
    store, original = publication
    package = copy.deepcopy(original)
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(original["file_bytes"])) as source,
        zipfile.ZipFile(output, "w") as target,
    ):
        for member in source.infolist():
            body = source.read(member)
            if change is not None:
                member, body = change(member, body)
            target.writestr(member, body)
            if update_manifest:
                entry = next(
                    entry
                    for entry in package["manifest"]["files"]
                    if entry["path"] == member.filename
                )
                entry.update(size=len(body), sha256=hashlib.sha256(body).hexdigest())
            if duplicate and member.filename == "binary.bin":
                with pytest.warns(UserWarning, match="Duplicate name"):
                    target.writestr(member, body)
        if extra:
            target.writestr("unexpected.txt", "unexpected")
    package["file_bytes"] = output.getvalue()
    if update_manifest:
        package["manifest"]["total_bytes"] = sum(
            entry["size"] for entry in package["manifest"]["files"]
        )
        package["skill"]["revision"], _ = validate_tree_manifest(
            package["manifest"], max_files=2048, max_total_bytes=256 * 1024 * 1024
        )
    return store, package


@pytest.mark.parametrize(
    "variant",
    [
        "content",
        "unselected_content",
        "symlink",
        "special",
        "duplicate",
        "extra",
        "wrong_name",
        "entry_utf8",
        "size",
        "revision",
    ],
)
def test_publication_resources_reject_invalid_archives(publication, variant):
    def change(member, body):
        selected = "references/guide.md" if variant == "content" else "binary.bin"
        if variant in {"content", "unselected_content"} and member.filename == selected:
            body = b"x" + body[1:]
        if variant in {"symlink", "special"} and member.filename == "binary.bin":
            member.external_attr = (
                stat.S_IFLNK if variant == "symlink" else stat.S_IFIFO
            ) << 16
        if variant == "wrong_name" and member.filename == "SKILL.md":
            body = body.replace(b"name: sample", b"name: other")
        if variant == "entry_utf8" and member.filename == "SKILL.md":
            body = b"\xff\n"
        return member, body

    modified = modified_package(
        publication,
        change=change,
        extra=variant == "extra",
        duplicate=variant == "duplicate",
        update_manifest=variant in {"wrong_name", "entry_utf8"},
    )
    if variant == "revision":
        modified[1]["skill"]["revision"] = "sha256:" + "0" * 64
    if variant == "size":
        package = modified[1]
        package["manifest"]["files"][0]["size"] += 1
        package["manifest"]["total_bytes"] += 1
        package["skill"]["revision"], _ = validate_tree_manifest(
            package["manifest"], max_files=2048, max_total_bytes=256 * 1024 * 1024
        )
    with pytest.raises(ValueError):
        reading(modified)
    with pytest.raises(ValueError):
        listing(modified)


@pytest.mark.parametrize(
    "variant",
    [
        "name",
        "schema",
        "entry_schema",
        "unsafe_path",
        "duplicate_path",
        "size",
        "digest",
        "mode",
        "total",
        "file_count",
        "byte_limit",
        "noncanonical_order",
        "excluded_directory",
        "file_prefix",
        "missing_skill",
        "skill_text_limit",
        "revision",
    ],
)
def test_manifest_listing_validates_complete_publication_metadata(publication, variant):
    store, original = publication
    package = copy.deepcopy(original)
    manifest = package["manifest"]
    files = manifest["files"]
    if variant == "name":
        package["skill"]["name"] = "../sample"
    elif variant == "schema":
        manifest["extra"] = True
    elif variant == "entry_schema":
        files[0]["extra"] = True
    elif variant == "unsafe_path":
        files[0]["path"] = "../SKILL.md"
    elif variant == "duplicate_path":
        files[1]["path"] = files[0]["path"]
    elif variant == "size":
        files[0]["size"] = True
    elif variant == "digest":
        files[0]["sha256"] = "g" * 64
    elif variant == "mode":
        files[0]["executable"] = 1
    elif variant == "total":
        manifest["total_bytes"] += 1
    elif variant == "file_count":
        manifest["files"] = [files[0]] * 2049
    elif variant == "byte_limit":
        files[1]["size"] = 256 * 1024 * 1024
    elif variant == "noncanonical_order":
        files.reverse()
    elif variant == "excluded_directory":
        files[1]["path"] = "node_modules/binary.bin"
    elif variant == "file_prefix":
        files[1]["path"] = "references"
    elif variant == "missing_skill":
        files.pop(0)
    elif variant == "skill_text_limit":
        files[0]["size"] = 1024 * 1024 + 1
    if variant not in {"total", "file_count"}:
        manifest["total_bytes"] = sum(entry["size"] for entry in manifest["files"])
    package["skill"]["revision"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
    )
    if variant == "revision":
        package["skill"]["revision"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        manifest_listing((store, package))


def test_publication_limits_are_not_upload_limits(tmp_path):
    source = tmp_path / "many"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: many\ndescription: Many publication files\n---\nReferences\n"
    )
    for index in range(513):
        (source / f"{index:04}.txt").write_text(str(index))
    store = SkillStore(tmp_path / "store")
    store.import_skill_directory(
        str(source), {"name": "many"}, source_root=str(tmp_path)
    )
    package = store.export_skill_publication("many")
    result = SkillStore.list_publication_resources(
        package["skill"], package["manifest"], package["file_bytes"], max_entries=1000
    )
    assert len(result["entries"]) == 514
    assert (
        SkillStore.list_publication_manifest_resources(
            package["skill"], package["manifest"], max_entries=1000
        )
        == result
    )


@pytest.mark.parametrize("variant", ["noncanonical_order", "excluded_directory"])
def test_resource_validation_matches_restoration_tree_rules(
    publication, tmp_path, variant
):
    store, original = publication
    package = copy.deepcopy(original)
    if variant == "noncanonical_order":
        package["manifest"]["files"].reverse()
    else:
        output = io.BytesIO()
        with (
            zipfile.ZipFile(io.BytesIO(original["file_bytes"])) as source,
            zipfile.ZipFile(output, "w") as target,
        ):
            for member in source.infolist():
                body = source.read(member)
                if member.filename == "binary.bin":
                    member.filename = "node_modules/binary.bin"
                target.writestr(member, body)
        package["file_bytes"] = output.getvalue()
        next(
            entry
            for entry in package["manifest"]["files"]
            if entry["path"] == "binary.bin"
        )["path"] = "node_modules/binary.bin"
    package["skill"]["revision"], _ = validate_tree_manifest(
        package["manifest"], max_files=2048, max_total_bytes=256 * 1024 * 1024
    )
    with pytest.raises(ValueError):
        reading((store, package))
    with pytest.raises(ValueError):
        listing((store, package))
    with pytest.raises(ValueError):
        manifest_listing((store, package))
    cache = SkillStore(tmp_path / "invalid-cache")
    with pytest.raises(ValueError):
        cache.restore_skill_publication(
            package["skill"], package["manifest"], package["file_bytes"]
        )
