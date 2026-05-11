"""
Unit tests for image utility functions.

Tests URL parsing and base64 extraction without network calls.
"""

from __future__ import annotations

import pytest
import base64

from langbot.pkg.utils.image import (
    get_qq_image_downloadable_url,
    extract_b64_and_format,
)


class TestGetQQImageDownloadableUrl:
    """Tests for get_qq_image_downloadable_url function."""

    def test_basic_url(self):
        """Parse basic image URL."""
        url = "http://example.com/image.jpg"
        result_url, query = get_qq_image_downloadable_url(url)

        assert result_url == "http://example.com/image.jpg"
        assert query == {}

    def test_url_with_query_params(self):
        """Parse URL with query parameters."""
        url = "http://example.com/image.jpg?param1=value1&param2=value2"
        result_url, query = get_qq_image_downloadable_url(url)

        assert result_url == "http://example.com/image.jpg"
        assert query == {"param1": ["value1"], "param2": ["value2"]}

    def test_url_with_port(self):
        """Parse URL with port number."""
        url = "http://example.com:8080/image.jpg"
        result_url, query = get_qq_image_downloadable_url(url)

        assert result_url == "http://example.com:8080/image.jpg"

    def test_url_with_path(self):
        """Parse URL with complex path."""
        url = "http://example.com/path/to/image.jpg"
        result_url, query = get_qq_image_downloadable_url(url)

        assert result_url == "http://example.com/path/to/image.jpg"

    def test_url_with_fragment(self):
        """Parse URL with fragment (fragment is not part of query)."""
        url = "http://example.com/image.jpg#fragment"
        result_url, query = get_qq_image_downloadable_url(url)

        # Fragment is not included in query string parsing
        assert "http://example.com/image.jpg" in result_url

    def test_https_url(self):
        """Parse HTTPS URL and preserve its scheme."""
        url = "https://example.com/image.jpg"
        result_url, query = get_qq_image_downloadable_url(url)

        assert result_url == "https://example.com/image.jpg"
        assert query == {}

    def test_preserves_qq_https_scheme_and_query(self):
        """QQ image URLs keep HTTPS and query parameters."""
        result_url, query = get_qq_image_downloadable_url(
            'https://gchat.qpic.cn/gchatpic_new/abc/0?term=2&is_origin=1'
        )

        assert result_url == 'https://gchat.qpic.cn/gchatpic_new/abc/0'
        assert query == {'term': ['2'], 'is_origin': ['1']}

    def test_defaults_missing_scheme_to_http(self):
        """Scheme-less image URLs default to HTTP."""
        result_url, query = get_qq_image_downloadable_url('gchat.qpic.cn/gchatpic_new/abc/0?term=2')

        assert result_url == 'http://gchat.qpic.cn/gchatpic_new/abc/0'
        assert query == {'term': ['2']}


class TestExtractB64AndFormat:
    """Tests for extract_b64_and_format function."""

    @pytest.mark.asyncio
    async def test_jpeg_data_uri(self):
        """Extract base64 and format from JPEG data URI."""
        # Create a simple base64 string
        original_data = b"test image data"
        b64_data = base64.b64encode(original_data).decode()
        data_uri = f"data:image/jpeg;base64,{b64_data}"

        result_b64, result_format = await extract_b64_and_format(data_uri)

        assert result_b64 == b64_data
        assert result_format == "jpeg"

    @pytest.mark.asyncio
    async def test_png_data_uri(self):
        """Extract base64 and format from PNG data URI."""
        original_data = b"test png data"
        b64_data = base64.b64encode(original_data).decode()
        data_uri = f"data:image/png;base64,{b64_data}"

        result_b64, result_format = await extract_b64_and_format(data_uri)

        assert result_b64 == b64_data
        assert result_format == "png"

    @pytest.mark.asyncio
    async def test_gif_data_uri(self):
        """Extract base64 and format from GIF data URI."""
        original_data = b"test gif data"
        b64_data = base64.b64encode(original_data).decode()
        data_uri = f"data:image/gif;base64,{b64_data}"

        result_b64, result_format = await extract_b64_and_format(data_uri)

        assert result_b64 == b64_data
        assert result_format == "gif"

    @pytest.mark.asyncio
    async def test_webp_data_uri(self):
        """Extract base64 and format from WebP data URI."""
        original_data = b"test webp data"
        b64_data = base64.b64encode(original_data).decode()
        data_uri = f"data:image/webp;base64,{b64_data}"

        result_b64, result_format = await extract_b64_and_format(data_uri)

        assert result_b64 == b64_data
        assert result_format == "webp"

    @pytest.mark.asyncio
    async def test_complex_base64(self):
        """Handle base64 with special characters."""
        # Base64 can include + and / characters
        original_data = bytes(range(256))  # All byte values
        b64_data = base64.b64encode(original_data).decode()
        data_uri = f"data:image/png;base64,{b64_data}"

        result_b64, result_format = await extract_b64_and_format(data_uri)

        assert result_b64 == b64_data
        # Verify we can decode back to original
        assert base64.b64decode(result_b64) == original_data

    @pytest.mark.asyncio
    async def test_empty_base64(self):
        """Handle empty base64 string."""
        data_uri = "data:image/png;base64,"

        result_b64, result_format = await extract_b64_and_format(data_uri)

        assert result_b64 == ""
        assert result_format == "png"
