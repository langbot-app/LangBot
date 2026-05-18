"""
PoC test for CWE-22 path traversal in LocalStorageProvider.

The LocalStorageProvider uses os.path.join(LOCAL_STORAGE_PATH, key) without
validating that the resulting path stays inside LOCAL_STORAGE_PATH.

When `key` is an absolute path (e.g. '/etc/passwd'), os.path.join discards
all previous components and returns the absolute path directly, allowing
arbitrary file reads, writes, and deletes.

This test must FAIL before the fix and PASS after.
"""

import os
import pytest
from unittest.mock import Mock, patch

from langbot.pkg.storage.providers.localstorage import LocalStorageProvider


@pytest.fixture
def storage_provider(tmp_path):
    """Create a LocalStorageProvider with a temporary storage path."""
    storage_path = str(tmp_path / "storage")
    with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
        mock_app = Mock()
        provider = LocalStorageProvider(mock_app)
        yield provider, storage_path


class TestPathTraversalPrevention:
    """Test that LocalStorageProvider rejects path traversal attempts."""

    @pytest.mark.asyncio
    async def test_absolute_path_save_rejected(self, storage_provider, tmp_path):
        """Saving with an absolute path key must be blocked."""
        provider, storage_path = storage_provider
        target_file = str(tmp_path / "pwned.txt")

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            with pytest.raises((ValueError, PermissionError)):
                await provider.save(target_file, b"malicious content")

        # The file must NOT exist outside the storage directory
        assert not os.path.exists(target_file), (
            f"Path traversal succeeded: file was written outside storage to {target_file}"
        )

    @pytest.mark.asyncio
    async def test_absolute_path_load_rejected(self, storage_provider, tmp_path):
        """Loading with an absolute path key must be blocked."""
        provider, storage_path = storage_provider

        # Create a file outside the storage directory
        target_file = str(tmp_path / "secret.txt")
        with open(target_file, "wb") as f:
            f.write(b"secret data")

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            with pytest.raises((ValueError, PermissionError, FileNotFoundError)):
                data = await provider.load(target_file)
                assert data != b"secret data", (
                    "Path traversal succeeded: read file outside storage"
                )

    @pytest.mark.asyncio
    async def test_absolute_path_exists_rejected(self, storage_provider, tmp_path):
        """Exists check with an absolute path key must be blocked or return False."""
        provider, storage_path = storage_provider

        target_file = str(tmp_path / "check_me.txt")
        with open(target_file, "wb") as f:
            f.write(b"data")

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            try:
                result = await provider.exists(target_file)
                assert result is False, (
                    "Path traversal succeeded: exists() returned True for file outside storage"
                )
            except (ValueError, PermissionError):
                pass  # Expected

    @pytest.mark.asyncio
    async def test_absolute_path_delete_rejected(self, storage_provider, tmp_path):
        """Deleting with an absolute path key must be blocked."""
        provider, storage_path = storage_provider

        target_file = str(tmp_path / "do_not_delete.txt")
        with open(target_file, "wb") as f:
            f.write(b"important data")

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            with pytest.raises((ValueError, PermissionError, FileNotFoundError)):
                await provider.delete(target_file)

        assert os.path.exists(target_file), (
            "Path traversal succeeded: file outside storage was deleted"
        )

    @pytest.mark.asyncio
    async def test_absolute_path_size_rejected(self, storage_provider, tmp_path):
        """Size check with an absolute path key must be blocked."""
        provider, storage_path = storage_provider

        target_file = str(tmp_path / "measure_me.txt")
        with open(target_file, "wb") as f:
            f.write(b"some data")

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            with pytest.raises((ValueError, PermissionError, FileNotFoundError)):
                await provider.size(target_file)

    @pytest.mark.asyncio
    async def test_dot_dot_path_traversal_rejected(self, storage_provider, tmp_path):
        """Relative path traversal with '..' must be blocked."""
        provider, storage_path = storage_provider

        target_file = str(tmp_path / "above_storage.txt")
        with open(target_file, "wb") as f:
            f.write(b"above storage secret")

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            relative_key = os.path.join("..", "above_storage.txt")
            with pytest.raises((ValueError, PermissionError, FileNotFoundError)):
                data = await provider.load(relative_key)
                assert data != b"above storage secret"

    @pytest.mark.asyncio
    async def test_delete_dir_recursive_traversal_rejected(self, storage_provider, tmp_path):
        """delete_dir_recursive with traversal path must be blocked."""
        provider, storage_path = storage_provider

        outside_dir = tmp_path / "outside_dir"
        outside_dir.mkdir()
        (outside_dir / "file.txt").write_text("important")

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            with pytest.raises((ValueError, PermissionError)):
                await provider.delete_dir_recursive(str(outside_dir))

        assert outside_dir.exists(), (
            "Path traversal succeeded: directory outside storage was deleted"
        )

    @pytest.mark.asyncio
    async def test_legitimate_key_works(self, storage_provider):
        """Normal keys without traversal must still work."""
        provider, storage_path = storage_provider

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            key = "test_image_abc123.png"
            content = b"PNG image data"

            await provider.save(key, content)
            assert await provider.exists(key) is True
            loaded = await provider.load(key)
            assert loaded == content
            size = await provider.size(key)
            assert size == len(content)
            await provider.delete(key)
            assert await provider.exists(key) is False

    @pytest.mark.asyncio
    async def test_legitimate_subdirectory_key_works(self, storage_provider):
        """Keys with legitimate subdirectories must still work."""
        provider, storage_path = storage_provider

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            key = "bot_log_images/img_001.png"
            content = b"PNG image data"

            await provider.save(key, content)
            assert await provider.exists(key) is True
            loaded = await provider.load(key)
            assert loaded == content
            await provider.delete(key)

    @pytest.mark.asyncio
    async def test_delete_dir_recursive_non_existing_dir(self, storage_provider):
        """delete_dir_recursive should handle non-existing directories gracefully."""
        provider, storage_path = storage_provider

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            # Try to delete a non-existing directory - should not raise
            await provider.delete_dir_recursive("nonexistent_dir")

    @pytest.mark.asyncio
    async def test_delete_dir_recursive_with_files(self, storage_provider):
        """delete_dir_recursive should delete directory with files inside."""
        provider, storage_path = storage_provider

        with patch("langbot.pkg.storage.providers.localstorage.LOCAL_STORAGE_PATH", storage_path):
            # Create a directory with files
            key1 = "test_dir/file1.txt"
            key2 = "test_dir/file2.txt"
            await provider.save(key1, b"content1")
            await provider.save(key2, b"content2")

            # Verify files exist
            assert await provider.exists(key1)
            assert await provider.exists(key2)

            # Delete directory recursively
            await provider.delete_dir_recursive("test_dir")

            # Verify files no longer exist
            assert not await provider.exists(key1)
            assert not await provider.exists(key2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
