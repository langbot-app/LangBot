"""LangBot entry point for package execution"""

import asyncio
import argparse
import sys
import os

from langbot.pkg.utils import paths

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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='LangBot')
    parser.add_argument(
        '--standalone-runtime',
        action='store_true',
        help='Use standalone plugin runtime / 使用独立插件运行时',
        default=False,
    )
    parser.add_argument(
        '--standalone-box',
        action='store_true',
        help='Use standalone box runtime / 使用独立 Box 运行时',
        default=False,
    )
    parser.add_argument('--debug', action='store_true', help='Debug mode / 调试模式', default=False)
    subparsers = parser.add_subparsers(dest='command')
    migrate_parser = subparsers.add_parser('migrate', help='Run an operator-only database migration')
    migrate_parser.add_argument(
        '--cloud',
        action='store_true',
        required=True,
        help='Migrate and validate the Cloud PostgreSQL business database',
    )
    return parser


async def main_entry(loop: asyncio.AbstractEventLoop):
    """Main entry point for LangBot"""
    args = _build_parser().parse_args()

    if args.standalone_runtime:
        from langbot.pkg.utils import platform

        platform.standalone_runtime = True

    if args.standalone_box:
        from langbot.pkg.utils import platform

        platform.standalone_box = True

    if args.debug:
        from langbot.pkg.utils import constants

        constants.debug_mode = True

    print(asciiart)

    # A release migration is a deterministic one-shot deployment Job. It must
    # fail with the current image when a dependency is absent, never mutate its
    # environment and ask an orchestrator to restart it.
    if args.command != 'migrate':
        from langbot.pkg.core.bootutils import deps

        missing_deps = await deps.check_deps()

        if missing_deps:
            print('以下依赖包未安装，将自动安装，请完成后重启程序：')
            print(
                'These dependencies are missing, they will be installed automatically, '
                'please restart the program after completion:'
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

    if args.command == 'migrate':
        from langbot.pkg.persistence.release_migration import run_cloud_release_migration_from_config

        await run_cloud_release_migration_from_config(loop)
        return

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
    os.makedirs(paths.get_data_root(), exist_ok=True)

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
