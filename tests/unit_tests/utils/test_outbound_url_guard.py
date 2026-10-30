"""Outbound fetch guards: SSRF (url) and arbitrary local file reads (path)."""

import socket

import pytest

from langbot.pkg.utils.outbound_url import (
    UnsafeOutboundUrlError,
    assert_safe_local_media_path,
    assert_safe_outbound_url,
)


@pytest.mark.parametrize(
    'url',
    [
        'http://127.0.0.1:5300/api',
        'http://localhost/x',
        'http://10.42.1.5:5300/',
        'http://192.168.1.1/',
        'http://172.16.0.10/',
        'http://169.254.169.254/latest/meta-data/',
        'http://[::1]/',
        'http://0.0.0.0/',
    ],
)
def test_internal_addresses_are_refused(url):
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_outbound_url(url)


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'gopher://x/', 'ftp://example.com/', '', '   '])
def test_non_http_schemes_and_empty_are_refused(url):
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_outbound_url(url)


def test_public_url_is_allowed():
    assert assert_safe_outbound_url('https://example.com/image.png') == 'https://example.com/image.png'


def test_hostname_resolving_to_internal_is_refused(monkeypatch):
    """A public-looking name pointing at a private address must be refused."""
    monkeypatch.setattr(
        socket,
        'getaddrinfo',
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.7', 80))],
    )
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_outbound_url('http://internal.example.com/x')


def test_allowed_domains_restricts_destination(monkeypatch):
    monkeypatch.setattr(
        socket,
        'getaddrinfo',
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))],
    )
    assert assert_safe_outbound_url('https://oapi.dingtalk.com/robot/sendBySession', allowed_domains=('dingtalk.com',))
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_outbound_url('https://evil.example.com/x', allowed_domains=('dingtalk.com',))


def test_allowed_domain_does_not_match_suffix_impostor(monkeypatch):
    """evil-dingtalk.com must not satisfy the dingtalk.com rule."""
    monkeypatch.setattr(
        socket,
        'getaddrinfo',
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))],
    )
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_outbound_url('https://evil-dingtalk.com/x', allowed_domains=('dingtalk.com',))


def test_local_media_path_inside_root_is_allowed(tmp_path):
    media = tmp_path / 'image.png'
    media.write_bytes(b'png')
    assert assert_safe_local_media_path(str(media), allowed_roots=(str(tmp_path),)) == str(media.resolve())


@pytest.mark.parametrize('path', ['/etc/passwd', '/etc/shadow', '//etc/passwd'])
def test_local_media_path_outside_root_is_refused(path):
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_local_media_path(path, allowed_roots=('/tmp',))


def test_relative_local_media_path_is_refused():
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_local_media_path('../../etc/passwd', allowed_roots=('/tmp',))


def test_traversal_out_of_root_is_refused(tmp_path):
    (tmp_path / 'sub').mkdir()
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_local_media_path(str(tmp_path / 'sub' / '..' / '..' / 'etc' / 'passwd'), allowed_roots=(str(tmp_path),))


def test_symlink_escaping_root_is_refused(tmp_path):
    outside = tmp_path / 'secret.txt'
    outside.write_text('secret')
    root = tmp_path / 'root'
    root.mkdir()
    link = root / 'link.txt'
    link.symlink_to(outside)
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_local_media_path(str(link), allowed_roots=(str(root),))


def test_directory_is_not_accepted_as_media(tmp_path):
    with pytest.raises(UnsafeOutboundUrlError):
        assert_safe_local_media_path(str(tmp_path), allowed_roots=(str(tmp_path),))
