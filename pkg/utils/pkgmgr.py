from pip._internal import main as pipmain

import pkg.utils.log as log


def install(package):
    pipmain(['install', package])
    log.reset_logging()

def install_upgrade(package):
    pipmain(['install', '--upgrade', package, "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
                    "--trusted-host", "pypi.tuna.tsinghua.edu.cn"])
    log.reset_logging()


def run_pip(params: list):
    pipmain(params)
    log.reset_logging()


def install_requirements(file):
    pipmain(['install', '-r', file, "--upgrade", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
                    "--trusted-host", "pypi.tuna.tsinghua.edu.cn"])
    log.reset_logging()


def ensure_dulwich():
    # 尝试三次
    for i in range(3):
        try:
            import dulwich
            return
        except ImportError:
            install('dulwich')

    raise ImportError("无法自动安装dulwich库")


if __name__ == "__main__":
    try:
        install("openai11")
    except Exception as e:
        print(111)
        print(e)

    print(222)