from pip._internal import main as pipmain


def install(package):
    pipmain(['install', package])


def install_upgrade(package):
    pipmain(
        [
            'install',
            '--upgrade',
            package,
            '-i',
            'https://pypi.tuna.tsinghua.edu.cn/simple',
            '--trusted-host',
            'pypi.tuna.tsinghua.edu.cn',
        ]
    )


def run_pip(params: list):
    pipmain(params)


def install_requirements(file, extra_params: list = []):
    pipmain(
        [
            'install',
            '-r',
            file,
            '-i',
            'https://pypi.tuna.tsinghua.edu.cn/simple',
            '--trusted-host',
            'pypi.tuna.tsinghua.edu.cn',
        ]
        + extra_params
    )
