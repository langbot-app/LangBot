"""LangBot entry point for package execution"""

import asyncio
import argparse
import sys
import os

# ASCII art banner
asciiart = r"""
 _                   ___      _   
| |   __ _ _ _  __ _| _ ) ___| |_ 
| |__/ _` | ' \/ _` | _ \/ _ \  _|
|____\__,_|_||_\__, |___/\___/\__|
               |___/              

⭐️ Open Source 开源地址: https://github.com/langbot-app/LangBot
📖 Documentation 文档地址: https://docs.langbot.app
"""


async def main_entry(loop: asyncio.AbstractEventLoop):
    """Main entry point for LangBot"""
    parser = argparse.ArgumentParser(description='LangBot')
    parser.add_argument(
        '--standalone-runtime',
        action='store_true',
        help='Use standalone plugin runtime / 使用独立插件运行时',
        default=False,
    )
    parser.add_argument('--debug', action='store_true', help='Debug mode / 调试模式', default=False)
    args = parser.parse_args()

    if args.standalone_runtime:
        from langbot.pkg.utils import platform

        platform.standalone_runtime = True

    if args.debug:
        from langbot.pkg.utils import constants

        constants.debug_mode = True

    print(asciiart)

    # Check dependencies
    from langbot.pkg.core.bootutils import deps

    missing_deps = await deps.check_deps()

    if missing_deps:
        print('以下依赖包未安装，将自动安装，请完成后重启程序：')
        print(
            'These dependencies are missing, they will be installed automatically, please restart the program after completion:'
        )
        for dep in missing_deps:
            print('-', dep)
        await deps.install_deps(missing_deps)
        print('已自动安装缺失的依赖包，请重启程序。')
        print('The missing dependencies have been installed automatically, please restart the program.')
        sys.exit(0)

    # Check configuration files
    from langbot.pkg.core.bootutils import files

    generated_files = await files.generate_files()

    if generated_files:
        print('以下文件不存在，已自动生成：')
        print('Following files do not exist and have been automatically generated:')
        for file in generated_files:
            print('-', file)

    from langbot.pkg.core import boot

    await boot.main(loop)


def main():
    """Main function to be called by console script entry point"""
    # Check Python version
    if sys.version_info < (3, 10, 1):
        print('需要 Python 3.10.1 及以上版本，当前 Python 版本为：', sys.version)
        print('Your Python version is not supported.')
        print('Python 3.10.1 or higher is required. Current version:', sys.version)
        sys.exit(1)

    # Set up the working directory
    # When installed as a package, we need to handle the working directory differently
    # We'll create data directory in current working directory if not exists
    os.makedirs('data', exist_ok=True)

    loop = asyncio.new_event_loop()

    try:
        loop.run_until_complete(main_entry(loop))
    except KeyboardInterrupt:
        print('\n正在退出...')
        print('Exiting...')
    finally:
        loop.close()


if __name__ == '__main__':
    main()
