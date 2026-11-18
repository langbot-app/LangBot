import argparse
import sys

from langbot_plugin.version import __version__
from langbot_plugin.runtime import app as runtime_app
from langbot_plugin.cli.commands.initplugin import init_plugin_process
from langbot_plugin.cli.commands.gencomponent import generate_component_process
from langbot_plugin.cli.commands.runplugin import run_plugin_process
from langbot_plugin.cli.commands.buildplugin import build_plugin_process
from langbot_plugin.cli.commands.login import login_process
from langbot_plugin.cli.commands.logout import logout_process
from langbot_plugin.cli.commands.publish import publish_process
from langbot_plugin.cli.i18n import cli_print

"""
Usage:
    lbp <command>

Commands:
    help: Show the help of the CLI
    ver: Show the version of the CLI
    login: Login to LangBot account
    logout: Logout from LangBot account
    build: Build the plugin
        - [--output]: The output directory, default is `dist`
    publish: Publish the plugin to LangBot Marketplace
    init: Initialize a new plugin
        - <plugin_name>: The name of the plugin
    comp: Generate a component
        - <component_type>: The type of the component
    run: Run/remote debug the plugin
    rt: Run the runtime
        - [--stdio-control -s]: Use stdio for control connection
        - [--ws-control-port]: The port for control connection
        - [--ws-debug-port]: The port for debug connection
    box: Run the sandbox box runtime
        - [--host]: Bind address, default is 0.0.0.0
        - [--stdio-control]: Use stdio for control connection
        - [--ws-control-port]: The port for control connection, default is 5410
"""


def main():
    parser = argparse.ArgumentParser(description="LangBot Plugin CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # help command
    subparsers.add_parser("help", help="Show the help of the CLI")

    # ver command
    subparsers.add_parser("ver", help="Show the version of the CLI")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new plugin")
    init_parser.add_argument("plugin_name", nargs="?", help="The name of the plugin")

    # comp command
    comp_parser = subparsers.add_parser("comp", help="Generate a component")
    comp_parser.add_argument("component_type", help="The type of the component")

    # run command
    run_parser = subparsers.add_parser("run", help="Run/remote debug the plugin")
    run_parser.add_argument(
        "-s", "--stdio", action="store_true", help="Use stdio for control connection"
    )
    run_parser.add_argument(
        "--prod",
        action="store_true",
        help="Mark this process as production plugin process, only used on Windows",
    )
    run_parser.add_argument(
        "--plugin-debug-key",
        type=str,
        help="Debug key for plugin authentication",
        default="",
    )
    run_parser.add_argument(
        "--pypi-index-url",
        type=str,
        help="PyPI index URL for plugin dependency installation (default: https://pypi.org/simple)",
        default="",
    )
    run_parser.add_argument(
        "--pypi-trusted-host",
        type=str,
        help="Comma-separated trusted hosts for plugin dependency installation",
        default="",
    )
    run_parser.add_argument(
        "--tag",
        type=str,
        help="Process label shown by ps/htop (for example author/plugin_name); cosmetic only",
        default="",
    )

    # login command
    login_parser = subparsers.add_parser("login", help="Login to LangBot account")
    login_parser.add_argument(
        "--token", "-t", help="Login with a personal access token", default=None
    )

    # logout command
    subparsers.add_parser("logout", help="Logout from LangBot account")

    # build command
    build_parser = subparsers.add_parser("build", help="Build the plugin to a zip file")
    build_parser.add_argument(
        "-o", "--output", help="The output directory", default="dist"
    )

    # publish command
    publish_parser = subparsers.add_parser(
        "publish", help="Publish the plugin to LangBot Marketplace"
    )
    publish_parser.add_argument(
        "-o", "--output", help="The output directory", default="dist"
    )

    # rt command
    rt_parser = subparsers.add_parser("rt", help="Run the runtime")
    rt_parser.add_argument(
        "-s",
        "--stdio-control",
        action="store_true",
        help="Use stdio for control connection",
    )
    rt_parser.add_argument(
        "--ws-control-port",
        type=int,
        help="The port for control connection",
        default=5400,
    )
    rt_parser.add_argument(
        "--ws-debug-port", type=int, help="The port for debug connection", default=5401
    )
    rt_parser.add_argument(
        "--debug-only", action="store_true", help="Only run the debug server"
    )
    rt_parser.add_argument(
        "--skip-deps-check",
        action="store_true",
        help="Skip checking and installing dependencies for all installed plugins",
    )
    rt_parser.add_argument(
        "--pypi-index-url",
        type=str,
        help="PyPI index URL for plugin dependency installation (default: https://pypi.org/simple)",
        default="",
    )
    rt_parser.add_argument(
        "--pypi-trusted-host",
        type=str,
        help="Comma-separated trusted hosts for plugin dependency installation",
        default="",
    )

    # box command
    box_parser = subparsers.add_parser("box", help="Run the sandbox box runtime")
    box_parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    box_parser.add_argument("--instance-id", help="Stable Box instance ID")
    box_parser.add_argument(
        "--data-dir", help="Persistent Box identity and lock directory"
    )
    box_parser.add_argument(
        "-s",
        "--stdio-control",
        action="store_true",
        help="Use stdio for control connection",
    )
    box_parser.add_argument(
        "--ws-control-port",
        type=int,
        default=5410,
        help="The port for control connection",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    match args.command:
        case "help":
            parser.print_help()
        case "ver":
            cli_print("version_info", __version__)
        case "login":
            login_process(token=args.token)
        case "logout":
            logout_process()
        case "init":
            init_plugin_process(args.plugin_name if args.plugin_name else "")
        case "comp":
            generate_component_process(args.component_type)
        case "run":
            cli_print("running_plugin")
            run_plugin_process(
                args.stdio,
                args.prod,
                args.plugin_debug_key,
                args.pypi_index_url,
                args.pypi_trusted_host,
                tag=args.tag,
            )
        case "build":
            build_plugin_process(args.output)
        case "publish":
            publish_process()
        case "rt":
            runtime_app.main(args)
        case "box":
            from langbot_plugin.box.server import main as box_main

            box_main(args)
        case _:
            cli_print("unknown_command", args.command)
            sys.exit(1)


if __name__ == "__main__":
    main()
