import hashlib
import io
import logging
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo

import httpx
import pytest

from langbot.pkg.plugin.github import validate_github_plugin_install_info
from langbot.pkg.plugin.github_archive import package_archive
from langbot.pkg.plugin.github_mirror import GitHubSources, parse_refs, source_url
from .test_github_install_security import _patch_client
from .test_connector_methods import create_mock_connector


SHA = 'a' * 40
CONFIG = {'plugin': {'github_mirror': {'mirrors': ['https://mirror.test/{url}']}}}


def advertisement(count=1):
    lines = ['HEAD\0symref=HEAD:refs/heads/0', *(f'refs/heads/{index}' for index in range(count)), 'refs/tags/v1']
    body = b'001e# service=git-upload-pack\n0000'
    for line in lines:
        packet = f'{SHA} {line}\n'.encode()
        body += f'{4 + len(packet):04x}'.encode() + packet
    return body + b'0000'


def archive(name=None, *, link=False):
    result = io.BytesIO()
    with ZipFile(result, 'w') as out:
        entry = ZipInfo(f'plugin-{SHA}/' + (name or 'sub/manifest.yaml'))
        if link:
            entry.external_attr = 0o120777 << 16
        out.writestr(
            entry,
            'kind: Plugin\napiVersion: v1\nmetadata: {author: test, name: test, label: {en_US: Test}}\nspec: {components: {}}\n',
        )
    return result.getvalue()


def test_archive_subdirectory():
    with ZipFile(io.BytesIO(package_archive(archive(), SHA, 'sub'))) as package:
        assert package.namelist() == ['manifest.yaml']


def test_archive_under_symlinked_temp_dir(tmp_path, monkeypatch):
    # macOS /var -> /private/var and Windows 8.3 temp paths resolve elsewhere.
    real = tmp_path / 'real'
    real.mkdir()
    (tmp_path / 'link').symlink_to(real)
    monkeypatch.setattr('tempfile.tempdir', str(tmp_path / 'link'))
    with ZipFile(io.BytesIO(package_archive(archive(), SHA, 'sub'))) as package:
        assert package.namelist() == ['manifest.yaml']


@pytest.mark.parametrize(
    'name,link,sha', [('sub/../other', False, SHA), ('link', True, SHA), ('plain', False, 'b' * 40)]
)
def test_reject_unsafe_archive(name, link, sha):
    with pytest.raises(ValueError):
        package_archive(archive(name, link=link), sha, '')


def test_file_limit():
    result = io.BytesIO()
    with ZipFile(result, 'w') as out:
        for index in range(10001):
            out.writestr(str(index), '')
    with pytest.raises(ValueError, match='limits'):
        package_archive(result.getvalue(), SHA, '')


def test_source_templates_and_validation():
    assert source_url('https://mirror.test/', 'https://github.com/o/r') == 'https://mirror.test/https://github.com/o/r'
    assert (
        source_url('https://mirror.test/?u={url}', 'https://github.com/o/r')
        == 'https://mirror.test/?u=https://github.com/o/r'
    )
    with pytest.raises(ValueError, match='operator'):
        validate_github_plugin_install_info(
            {'owner': 'x', 'repo': 'y', 'source_type': 'branch', 'ref': 'dev', 'mirror_url': 'https://mirror.test'}
        )
    with pytest.raises(ValueError):
        parse_refs(b'not pkt-line')


async def test_ranked_cache_truncation_and_download_fallback(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url)
        if request.url.path.endswith('/info/refs'):
            return httpx.Response(200, content=advertisement(501))
        if request.url.host == 'github.com':
            return httpx.Response(503)
        return httpx.Response(200, content=archive())

    _patch_client(monkeypatch, handler)
    sources = GitHubSources(SimpleNamespace(instance_config=SimpleNamespace(data=CONFIG), logger=logging.getLogger()))
    data = await sources.list_refs('https://github.com/o/r/tree/0/sub')
    assert data['source']['kind'] == 'direct' and data['default_branch'] == '0' and data['truncated']
    assert len(data['branches']) == 500 and data['tags'] == [{'name': 'v1', 'commit_sha': SHA}]
    info = {'owner': 'o', 'repo': 'r', 'ref': '0', 'source_subdir': 'sub'}
    assert await sources.branch_package(info)
    assert info['download_source'] == 'mirror.test' and info['commit_sha'] == SHA
    # Install re-probes both sources so a push after listing is not missed.
    assert len(calls) == 6
    await sources.list_refs('https://github.com/o/r')
    assert len(calls) == 6


@pytest.mark.parametrize('valid', [True, False])
async def test_release_mirror_digest(monkeypatch, valid):
    connector = create_mock_connector()
    connector.ap.instance_config.data = CONFIG
    connector.ap._github_ref_cache = {}

    def handler(request):
        if request.url.path.endswith('/info/refs'):
            return httpx.Response(200, content=advertisement())
        if request.url.path.endswith('/releases/1'):
            return httpx.Response(
                200,
                json={
                    'id': 1,
                    'tag_name': 'v',
                    'assets': [
                        {
                            'id': 2,
                            'size': 7,
                            'digest': 'sha256:' + hashlib.sha256(b'package').hexdigest(),
                            'browser_download_url': 'https://github.com/o/r/releases/download/v/file',
                        }
                    ],
                },
            )
        if request.url.host == 'api.github.com':
            return httpx.Response(503)
        return httpx.Response(200, content=b'package' if valid else b'invalid')

    _patch_client(monkeypatch, handler)
    operation = connector._download_github_package(
        {'owner': 'o', 'repo': 'r', 'release_tag': 'v', 'asset_id': 2, 'release_id': 1}, None
    )
    if valid:
        assert await operation == b'package'
    else:
        with pytest.raises(ValueError, match='No mirror'):
            await operation


async def test_probe_waits_for_workspace_dns_slot(monkeypatch):
    from langbot.pkg.plugin import github_mirror
    from langbot.pkg.utils.bounded_executor import BlockingWorkCapacityError

    real_fetch = github_mirror.fetch
    rejected = []

    async def fetch(client, url, hosts, limit):
        # Simulate the per-workspace DNS pool rejecting concurrent lookups.
        if not rejected:
            rejected.append(url)
            raise BlockingWorkCapacityError('Workspace blocking executor capacity reached', scope='ws')
        return await real_fetch(client, url, hosts, limit)

    _patch_client(monkeypatch, lambda request: httpx.Response(200, content=advertisement()))
    monkeypatch.setattr(github_mirror, 'fetch', fetch)
    sources = GitHubSources(SimpleNamespace(instance_config=SimpleNamespace(data=CONFIG), logger=logging.getLogger()))
    ranked = await sources.ranked('o', 'r')
    assert rejected and len(ranked) == 2
