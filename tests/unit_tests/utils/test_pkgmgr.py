import inspect

from langbot.pkg.utils import pkgmgr


def test_install_requirements_defaults_extra_params_to_none():
    signature = inspect.signature(pkgmgr.install_requirements)

    assert signature.parameters['extra_params'].default is None


def test_install_requirements_omitted_extra_params_uses_base_command(monkeypatch):
    calls = []
    monkeypatch.setattr(pkgmgr, 'pipmain', calls.append)

    pkgmgr.install_requirements('requirements.txt')
    pkgmgr.install_requirements('requirements-dev.txt')

    assert calls == [
        [
            'install',
            '-r',
            'requirements.txt',
            '-i',
            'https://pypi.tuna.tsinghua.edu.cn/simple',
            '--trusted-host',
            'pypi.tuna.tsinghua.edu.cn',
        ],
        [
            'install',
            '-r',
            'requirements-dev.txt',
            '-i',
            'https://pypi.tuna.tsinghua.edu.cn/simple',
            '--trusted-host',
            'pypi.tuna.tsinghua.edu.cn',
        ],
    ]


def test_install_requirements_preserves_explicit_extra_params(monkeypatch):
    calls = []
    monkeypatch.setattr(pkgmgr, 'pipmain', calls.append)

    pkgmgr.install_requirements('requirements.txt', extra_params=['--no-deps'])

    assert calls == [
        [
            'install',
            '-r',
            'requirements.txt',
            '-i',
            'https://pypi.tuna.tsinghua.edu.cn/simple',
            '--trusted-host',
            'pypi.tuna.tsinghua.edu.cn',
            '--no-deps',
        ]
    ]
