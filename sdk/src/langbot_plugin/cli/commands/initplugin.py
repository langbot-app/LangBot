from __future__ import annotations

import ntpath
import os
import platform
import posixpath
import re
import subprocess
import sys

from langbot_plugin.cli.gen.renderer import init_plugin_files, render_template
from langbot_plugin.cli.i18n import cli_print, t
from langbot_plugin.cli.utils.form import NAME_REGEXP, input_form_values


# Check if Git is installed
def is_git_available() -> bool:
    try:
        # Check if Git is available by running git --version
        subprocess.run(
            ["git", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# Get lbp executable path based on platform
def get_lbp_path() -> str:
    """
    Get the path to lbp executable based on the current platform.

    Returns:
        str: Path to lbp executable
    """
    system = platform.system()

    if system == "Windows":
        python_dir = ntpath.dirname(sys.executable)
        scripts_dir = (
            python_dir
            if ntpath.basename(python_dir).casefold() == "scripts"
            else ntpath.join(python_dir, "Scripts")
        )
        return ntpath.join(scripts_dir, "lbp.exe")

    python_dir = posixpath.dirname(sys.executable)
    return posixpath.join(python_dir, "lbp")


# Initialize Git repository and add basic configuration
def init_git_repo(plugin_dir: str) -> None:
    try:
        # Initialize Git repository
        subprocess.run(
            ["git", "init"],
            cwd=plugin_dir,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        cli_print("git_repo_initialized", plugin_dir)

    except subprocess.CalledProcessError as e:
        cli_print("git_init_warning", e.stderr)


form_fields = [
    {
        "name": "plugin_author",
        "label": {
            "en_US": "Plugin author",
            "zh_Hans": "插件作者",
            "th_TH": "ผู้พัฒนาปลั๊กอิน",
            "vi_VN": "Tác giả plugin",
            "es_ES": "Autor del plugin",
        },
        "required": True,
        "format": {
            "regexp": NAME_REGEXP,
            "error": {
                "en_US": "Invalid plugin author, please use a valid name, which only contains letters, numbers, underscores and hyphens.",
                "zh_Hans": "无效的插件作者，请使用一个有效的名称，只能包含字母、数字、下划线和连字符。",
                "th_TH": "ชื่อผู้พัฒนาปลั๊กอินไม่ถูกต้อง กรุณาใช้ชื่อที่ถูกต้อง ซึ่งประกอบด้วยตัวอักษร ตัวเลข ขีดล่าง และขีดกลางเท่านั้น",
                "vi_VN": "Tên tác giả plugin không hợp lệ, vui lòng sử dụng tên hợp lệ, chỉ chứa chữ cái, số, dấu gạch dưới và dấu gạch ngang.",
                "es_ES": "Autor del plugin no válido, por favor use un nombre válido que solo contenga letras, números, guiones bajos y guiones.",
            },
        },
    },
    {
        "name": "plugin_description",
        "label": {
            "en_US": "Plugin description",
            "zh_Hans": "插件描述",
            "th_TH": "คำอธิบายปลั๊กอิน",
            "vi_VN": "Mô tả plugin",
            "es_ES": "Descripción del plugin",
        },
        "required": True,
    },
]


def init_plugin_process(
    plugin_name: str,
) -> None:
    if plugin_name == "":
        cli_print("no_plugin_name")
        plugin_dir = os.getcwd()
        plugin_dir_name = os.path.basename(plugin_dir)
    else:
        # When a name is provided, use that name as both the directory and logical name.
        plugin_dir = plugin_name
        plugin_dir_name = plugin_name

    if not re.match(NAME_REGEXP, plugin_dir_name):
        print("!! " + t("invalid_plugin_name", plugin_dir_name))
        print("!! " + t("invalid_name_format"))
        return

    # check if directory exists and is not empty
    if os.path.exists(plugin_dir):
        # list directory contents (excluding hidden files)
        dir_contents = [f for f in os.listdir(plugin_dir) if not f.startswith(".")]
        if dir_contents:
            print("!! " + t("directory_not_empty", plugin_dir))
            return
    else:
        # only create directory if a plugin name is specified and the directory does not exist
        os.makedirs(plugin_dir, exist_ok=True)

    cli_print("creating_plugin", plugin_dir_name)

    values = {
        "plugin_name": plugin_dir_name,
        "plugin_author": "",
        "plugin_description": "",
        "plugin_label": "",
        "plugin_attr": "",
    }

    input_values = input_form_values(form_fields)
    values.update(input_values)

    values["plugin_attr"] = values["plugin_name"].replace("-", "").replace("_", "")
    values["plugin_label"] = values["plugin_name"].replace("-", " ").replace("_", " ")

    cli_print("creating_files", values["plugin_name"])

    # Add lbp path to template values
    values["lbp_path"] = get_lbp_path()

    # Create necessary directories
    assets_dir = os.path.join(plugin_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    vscode_dir = os.path.join(plugin_dir, ".vscode")
    os.makedirs(vscode_dir, exist_ok=True)
    readme_dir = os.path.join(plugin_dir, "readme")
    os.makedirs(readme_dir, exist_ok=True)
    github_workflows_dir = os.path.join(plugin_dir, ".github", "workflows")
    os.makedirs(github_workflows_dir, exist_ok=True)

    # Create all files from templates
    for file in init_plugin_files:
        content = render_template(f"{file}.example", **values)
        file_path = os.path.join(plugin_dir, file)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    # If Git is available, initialize repository
    if is_git_available():
        # init_git_repo(values["plugin_name"])
        init_git_repo(plugin_dir)
    else:
        cli_print("git_not_found")

    cli_print("plugin_created", plugin_dir_name, plugin_dir)
