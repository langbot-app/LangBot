"""Archive entry-name validation must match what the SDK will extract.

The host inspects a package (to read manifest/requirements) before the SDK
extracts it. If the two disagree, a package can pass inspection and then fail to
install, and the rules can drift apart. These tests pin inspection to the same
rejections the SDK applies in ``runtime/plugin/artifact.py``.
"""

import io
import zipfile

import pytest

from langbot.pkg.plugin.archive import inspect_plugin_archive

MANIFEST = 'apiVersion: v1\nkind: Plugin\nmetadata:\n  name: good\n  version: 0.0.1\n'


def _package(entries: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.parametrize(
    'bad_name',
    [
        '../escape.py',
        '../../etc/passwd',
        'a/../../manifest.yaml',
        'components/../../outside.py',
        '/absolute.py',
        'C:/windows/system32/evil.py',
        'c:evil.py',
        'dir\\..\\..\\evil.py',
    ],
)
def test_entries_escaping_the_root_are_rejected(bad_name):
    package = _package({'manifest.yaml': MANIFEST, bad_name: 'x'})
    with pytest.raises(ValueError):
        inspect_plugin_archive(package)


def test_nul_in_entry_name_is_rejected():
    # zipfile truncates a name at NUL when writing, so the guard is exercised
    # directly rather than through a crafted archive.
    from langbot.pkg.plugin.archive import _normalize_archive_entry_name

    with pytest.raises(ValueError):
        _normalize_archive_entry_name('evil\x00.py')


def test_duplicate_entry_after_normalization_is_rejected():
    """Two members normalizing to one path make the inspected file ambiguous."""
    package = _package({'manifest.yaml': MANIFEST, './manifest.yaml': MANIFEST})
    with pytest.raises(ValueError, match='duplicate'):
        inspect_plugin_archive(package)


def test_traversal_is_rejected_before_any_duplicate_check():
    """A '..' member is an escape, which is the more severe diagnosis."""
    package = _package({'manifest.yaml': MANIFEST, 'sub/../manifest.yaml': MANIFEST})
    with pytest.raises(ValueError, match='escapes the archive root'):
        inspect_plugin_archive(package)


def test_nested_and_unicode_paths_still_accepted():
    """Normal plugin layouts must keep working."""
    package = _package(
        {
            'manifest.yaml': MANIFEST,
            'components/__init__.py': '',
            'components/commands/帮助.py': '',
            'requirements.txt': 'httpx>=0.27\n',
        }
    )
    inspection = inspect_plugin_archive(package)
    assert (inspection.manifest.get('metadata') or {}).get('name') == 'good'
    assert any('httpx' in dep for dep in inspection.requirements)


def test_leading_dot_slash_and_double_slashes_are_normalized_not_rejected():
    """Cosmetic separators are common in real packages and must not be fatal."""
    package = _package(
        {
            './manifest.yaml': MANIFEST,
            'components//cmd.py': '',
        }
    )
    inspection = inspect_plugin_archive(package)
    assert (inspection.manifest.get('metadata') or {}).get('name') == 'good'
