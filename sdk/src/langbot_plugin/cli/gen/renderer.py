from __future__ import annotations

from typing import Any, Callable

import pydantic

from jinja2 import Environment, PackageLoader
from langbot_plugin.cli.utils.form import NUMBER_LOWER_UNDERSCORE_REGEXP


def get_template_environment():
    """
    获取Jinja2模板环境
    """
    return Environment(loader=PackageLoader("langbot_plugin.assets", "templates"))


def render_template(template_name: str, **context) -> str:
    """
    渲染模板

    Args:
        template_name: 模板文件名
        **context: 模板变量

    Returns:
        str: 渲染后的内容
    """
    env = get_template_environment()
    template = env.get_template(template_name)
    return template.render(**context)


def simple_render(
    origin_text: str,
    **context,
) -> str:
    return origin_text.format(**context)


init_plugin_files = [
    "manifest.yaml",
    "main.py",
    "README.md",
    "readme/README_zh_Hans.md",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "assets/icon.svg",
    ".vscode/launch.json",
    ".github/workflows/release.yml",
]


class ComponentType(pydantic.BaseModel):
    type_name: str = pydantic.Field(description="The name of the component type")
    target_dir: str = pydantic.Field(
        description="The target directory of the component"
    )
    template_files: list[str] = pydantic.Field(
        description="The template files of the component"
    )
    form_fields: list[dict[str, Any]] = pydantic.Field(
        description="The form fields of the component"
    )
    input_post_process: Callable[[dict[str, Any]], dict[str, Any]] = pydantic.Field(
        description="The input post process of the component",
        default=lambda x: x,
    )


def tool_component_input_post_process(values: dict[str, Any]) -> dict[str, Any]:
    result = {
        "tool_name": values["tool_name"],
        "tool_label": values["tool_name"],
        "tool_description": values["tool_description"],
        "tool_attr": values["tool_name"],
    }

    python_attr_valid_name = "".join(
        word.capitalize() for word in values["tool_name"].split("_")
    )
    result["tool_label"] = python_attr_valid_name
    result["tool_attr"] = python_attr_valid_name
    return result


def command_component_input_post_process(values: dict[str, Any]) -> dict[str, Any]:
    result = {
        "cmd_name": values["cmd_name"],
        "cmd_label": values["cmd_name"],
        "cmd_description": values["cmd_description"],
        "cmd_attr": values["cmd_name"],
    }

    python_attr_valid_name = "".join(
        word.capitalize() for word in values["cmd_name"].split("_")
    )
    result["cmd_label"] = python_attr_valid_name
    result["cmd_attr"] = python_attr_valid_name
    return result


def knowledge_engine_component_input_post_process(
    values: dict[str, Any],
) -> dict[str, Any]:
    result = {
        "knowledge_engine_name": values["knowledge_engine_name"],
        "knowledge_engine_label": values["knowledge_engine_name"],
        "knowledge_engine_description": values["knowledge_engine_description"],
        "knowledge_engine_attr": values["knowledge_engine_name"],
    }

    python_attr_valid_name = "".join(
        word.capitalize() for word in values["knowledge_engine_name"].split("_")
    )
    result["knowledge_engine_label"] = python_attr_valid_name
    result["knowledge_engine_attr"] = python_attr_valid_name
    return result


def parser_component_input_post_process(values: dict[str, Any]) -> dict[str, Any]:
    result = {
        "parser_name": values["parser_name"],
        "parser_label": values["parser_name"],
        "parser_description": values["parser_description"],
        "parser_attr": values["parser_name"],
    }

    python_attr_valid_name = "".join(
        word.capitalize() for word in values["parser_name"].split("_")
    )
    result["parser_label"] = python_attr_valid_name
    result["parser_attr"] = python_attr_valid_name
    return result


def page_component_input_post_process(values: dict[str, Any]) -> dict[str, Any]:
    result = {
        "page_name": values["page_name"],
        "page_label": values["page_name"],
    }

    python_attr_valid_name = "".join(
        word.capitalize() for word in values["page_name"].split("_")
    )
    result["page_label"] = python_attr_valid_name
    return result


def runner_component_input_post_process(values: dict[str, Any]) -> dict[str, Any]:
    result = {
        "runner_name": values["runner_name"],
        "runner_label": values["runner_name"],
        "runner_description": values["runner_description"],
        "runner_attr": values["runner_name"],
    }

    python_attr_valid_name = "".join(
        word.capitalize() for word in values["runner_name"].split("_")
    )
    result["runner_label"] = python_attr_valid_name
    result["runner_attr"] = python_attr_valid_name
    return result


component_types = [
    ComponentType(
        type_name="EventListener",
        target_dir="components/event_listener",
        template_files=[
            "default.yaml",
            "default.py",
        ],
        form_fields=[],
    ),
    ComponentType(
        type_name="Tool",
        target_dir="components/tools",
        template_files=[
            "{tool_name}.yaml",
            "{tool_name}.py",
        ],
        form_fields=[
            {
                "name": "tool_name",
                "label": {
                    "en_US": "Tool name",
                    "zh_Hans": "工具名称",
                    "zh_Hant": "工具名稱",
                    "ja_JP": "ツール名",
                    "th_TH": "ชื่อเครื่องมือ",
                    "vi_VN": "Tên công cụ",
                    "es_ES": "Nombre de herramienta",
                },
                "required": True,
                "format": {
                    "regexp": NUMBER_LOWER_UNDERSCORE_REGEXP,
                    "error": {
                        "en_US": "Invalid tool name, please use a valid name, which only contains lowercase letters, numbers, underscores and hyphens, and start with a letter.",
                        "zh_Hans": "无效的工具名称，请使用一个有效的名称，只能包含小写字母、数字、下划线和连字符，且以字母开头。",
                        "zh_Hant": "無效的工具名稱，請使用一個有效的名稱，只能包含小寫字母、數字、下劃線和連字符，且以字母開頭。",
                        "ja_JP": "無効なツール名です。有効な名前を使用してください。小文字、数字、アンダースコア、ハイフンのみを使用し、先頭は文字でなければなりません。",
                        "th_TH": "ชื่อเครื่องมือไม่ถูกต้อง กรุณาใช้ชื่อที่ถูกต้อง ซึ่งประกอบด้วยตัวอักษรพิมพ์เล็ก ตัวเลข ขีดล่าง และขีดกลาง และขึ้นต้นด้วยตัวอักษร",
                        "vi_VN": "Tên công cụ không hợp lệ, vui lòng sử dụng tên hợp lệ, chỉ chứa chữ thường, số, dấu gạch dưới và dấu gạch ngang, bắt đầu bằng chữ cái.",
                        "es_ES": "Nombre de herramienta no válido, por favor use un nombre válido que solo contenga letras minúsculas, números, guiones bajos y guiones, comenzando con una letra.",
                    },
                },
            },
            {
                "name": "tool_description",
                "label": {
                    "en_US": "Tool description",
                    "zh_Hans": "工具描述",
                    "zh_Hant": "工具描述",
                    "ja_JP": "ツールの説明",
                    "th_TH": "คำอธิบายเครื่องมือ",
                    "vi_VN": "Mô tả công cụ",
                    "es_ES": "Descripción de herramienta",
                },
                "required": True,
            },
        ],
        input_post_process=tool_component_input_post_process,
    ),
    ComponentType(
        type_name="Command",
        target_dir="components/commands",
        template_files=[
            "{cmd_name}.yaml",
            "{cmd_name}.py",
        ],
        form_fields=[
            {
                "name": "cmd_name",
                "label": {
                    "en_US": "Command name",
                    "zh_Hans": "命令名称",
                    "zh_Hant": "命令名稱",
                    "ja_JP": "コマンド名",
                    "th_TH": "ชื่อคำสั่ง",
                    "vi_VN": "Tên lệnh",
                    "es_ES": "Nombre de comando",
                },
                "required": True,
                "format": {
                    "regexp": NUMBER_LOWER_UNDERSCORE_REGEXP,
                    "error": {
                        "en_US": "Invalid command name, please use a valid name, which only contains lowercase letters, numbers, underscores and hyphens, and start with a letter.",
                        "zh_Hans": "无效的命令名称，请使用一个有效的名称，只能包含小写字母、数字、下划线和连字符，且以字母开头。",
                        "zh_Hant": "無效的命令名稱，請使用一個有效的名稱，只能包含小寫字母、數字、下劃線和連字符，且以字母開頭。",
                        "ja_JP": "無効なコマンド名です。有効な名前を使用してください。小文字、数字、アンダースコア、ハイフンのみを使用し、先頭は文字でなければなりません。",
                        "th_TH": "ชื่อคำสั่งไม่ถูกต้อง กรุณาใช้ชื่อที่ถูกต้อง ซึ่งประกอบด้วยตัวอักษรพิมพ์เล็ก ตัวเลข ขีดล่าง และขีดกลาง และขึ้นต้นด้วยตัวอักษร",
                        "vi_VN": "Tên lệnh không hợp lệ, vui lòng sử dụng tên hợp lệ, chỉ chứa chữ thường, số, dấu gạch dưới và dấu gạch ngang, bắt đầu bằng chữ cái.",
                        "es_ES": "Nombre de comando no válido, por favor use un nombre válido que solo contenga letras minúsculas, números, guiones bajos y guiones, comenzando con una letra.",
                    },
                },
            },
            {
                "name": "cmd_description",
                "label": {
                    "en_US": "Command description",
                    "zh_Hans": "命令描述",
                    "zh_Hant": "命令描述",
                    "ja_JP": "コマンドの説明",
                    "th_TH": "คำอธิบายคำสั่ง",
                    "vi_VN": "Mô tả lệnh",
                    "es_ES": "Descripción de comando",
                },
                "required": True,
            },
        ],
        input_post_process=command_component_input_post_process,
    ),
    ComponentType(
        type_name="KnowledgeEngine",
        target_dir="components/knowledge_engine",
        template_files=[
            "{knowledge_engine_name}.yaml",
            "{knowledge_engine_name}.py",
        ],
        form_fields=[
            {
                "name": "knowledge_engine_name",
                "label": {
                    "en_US": "Knowledge Engine name",
                    "zh_Hans": "知识引擎名称",
                    "zh_Hant": "知識引擎名稱",
                    "ja_JP": "ナレッジエンジン名",
                    "th_TH": "ชื่อเครื่องมือความรู้",
                    "vi_VN": "Tên công cụ tri thức",
                    "es_ES": "Nombre del motor de conocimiento",
                },
                "required": True,
                "format": {
                    "regexp": NUMBER_LOWER_UNDERSCORE_REGEXP,
                    "error": {
                        "en_US": "Invalid Knowledge Engine name, please use a valid name, which only contains lowercase letters, numbers, underscores and hyphens, and start with a letter.",
                        "zh_Hans": "无效的 知识引擎名称，请使用一个有效的名称，只能包含小写字母、数字、下划线和连字符，且以字母开头。",
                        "zh_Hant": "無效的 知識引擎名稱，請使用一個有效的名稱，只能包含小寫字母、數字、下劃線和連字符，且以字母開頭。",
                        "ja_JP": "無効なナレッジエンジン名です。有効な名前を使用してください。小文字、数字、アンダースコア、ハイフンのみを使用し、先頭は文字でなければなりません。",
                        "th_TH": "ชื่อเครื่องมือความรู้ไม่ถูกต้อง กรุณาใช้ชื่อที่ถูกต้อง ซึ่งประกอบด้วยตัวอักษรพิมพ์เล็ก ตัวเลข ขีดล่าง และขีดกลาง และขึ้นต้นด้วยตัวอักษร",
                        "vi_VN": "Tên công cụ tri thức không hợp lệ, vui lòng sử dụng tên hợp lệ, chỉ chứa chữ thường, số, dấu gạch dưới và dấu gạch ngang, bắt đầu bằng chữ cái.",
                        "es_ES": "Nombre del motor de conocimiento no válido, por favor use un nombre válido que solo contenga letras minúsculas, números, guiones bajos y guiones, comenzando con una letra.",
                    },
                },
            },
            {
                "name": "knowledge_engine_description",
                "label": {
                    "en_US": "Knowledge Engine description",
                    "zh_Hans": "知识引擎描述",
                    "zh_Hant": "知識引擎描述",
                    "ja_JP": "ナレッジエンジンの説明",
                    "th_TH": "คำอธิบายเครื่องมือความรู้",
                    "vi_VN": "Mô tả công cụ tri thức",
                    "es_ES": "Descripción del motor de conocimiento",
                },
                "required": True,
            },
        ],
        input_post_process=knowledge_engine_component_input_post_process,
    ),
    ComponentType(
        type_name="Parser",
        target_dir="components/parser",
        template_files=[
            "{parser_name}.yaml",
            "{parser_name}.py",
        ],
        form_fields=[
            {
                "name": "parser_name",
                "label": {
                    "en_US": "Parser name",
                    "zh_Hans": "解析器名称",
                    "zh_Hant": "解析器名稱",
                    "ja_JP": "パーサー名",
                    "th_TH": "ชื่อตัวแยกวิเคราะห์",
                    "vi_VN": "Tên bộ phân tích",
                    "es_ES": "Nombre del analizador",
                },
                "required": True,
                "format": {
                    "regexp": NUMBER_LOWER_UNDERSCORE_REGEXP,
                    "error": {
                        "en_US": "Invalid Parser name, please use a valid name, which only contains lowercase letters, numbers, underscores and hyphens, and start with a letter.",
                        "zh_Hans": "无效的解析器名称，请使用一个有效的名称，只能包含小写字母、数字、下划线和连字符，且以字母开头。",
                        "zh_Hant": "無效的解析器名稱，請使用一個有效的名稱，只能包含小寫字母、數字、下劃線和連字符，且以字母開頭。",
                        "ja_JP": "無効なパーサー名です。有効な名前を使用してください。小文字、数字、アンダースコア、ハイフンのみを使用し、先頭は文字でなければなりません。",
                        "th_TH": "ชื่อตัวแยกวิเคราะห์ไม่ถูกต้อง กรุณาใช้ชื่อที่ถูกต้อง ซึ่งประกอบด้วยตัวอักษรพิมพ์เล็ก ตัวเลข ขีดล่าง และขีดกลาง และขึ้นต้นด้วยตัวอักษร",
                        "vi_VN": "Tên bộ phân tích không hợp lệ, vui lòng sử dụng tên hợp lệ, chỉ chứa chữ thường, số, dấu gạch dưới và dấu gạch ngang, bắt đầu bằng chữ cái.",
                        "es_ES": "Nombre del analizador no válido, por favor use un nombre válido que solo contenga letras minúsculas, números, guiones bajos y guiones, comenzando con una letra.",
                    },
                },
            },
            {
                "name": "parser_description",
                "label": {
                    "en_US": "Parser description",
                    "zh_Hans": "解析器描述",
                    "zh_Hant": "解析器描述",
                    "ja_JP": "パーサーの説明",
                    "th_TH": "คำอธิบายตัวแยกวิเคราะห์",
                    "vi_VN": "Mô tả bộ phân tích",
                    "es_ES": "Descripción del analizador",
                },
                "required": True,
            },
        ],
        input_post_process=parser_component_input_post_process,
    ),
    ComponentType(
        type_name="Page",
        target_dir="components/pages",
        template_files=[
            "{page_name}.yaml",
            "{page_name}.html",
        ],
        form_fields=[
            {
                "name": "page_name",
                "label": {
                    "en_US": "Page name",
                    "zh_Hans": "页面名称",
                    "zh_Hant": "頁面名稱",
                    "ja_JP": "ページ名",
                    "th_TH": "ชื่อหน้า",
                    "vi_VN": "Tên trang",
                    "es_ES": "Nombre de página",
                },
                "required": True,
                "format": {
                    "regexp": NUMBER_LOWER_UNDERSCORE_REGEXP,
                    "error": {
                        "en_US": "Invalid Page name, please use a valid name, which only contains lowercase letters, numbers, underscores and hyphens, and start with a letter.",
                        "zh_Hans": "无效的页面名称，请使用一个有效的名称，只能包含小写字母、数字、下划线和连字符，且以字母开头。",
                        "zh_Hant": "無效的頁面名稱，請使用一個有效的名稱，只能包含小寫字母、數字、下劃線和連字符，且以字母開頭。",
                        "ja_JP": "無効なページ名です。有効な名前を使用してください。小文字、数字、アンダースコア、ハイフンのみを使用し、先頭は文字でなければなりません。",
                        "th_TH": "ชื่อหน้าไม่ถูกต้อง กรุณาใช้ชื่อที่ถูกต้อง ซึ่งประกอบด้วยตัวอักษรพิมพ์เล็ก ตัวเลข ขีดล่าง และขีดกลาง และขึ้นต้นด้วยตัวอักษร",
                        "vi_VN": "Tên trang không hợp lệ, vui lòng sử dụng tên hợp lệ, chỉ chứa chữ thường, số, dấu gạch dưới và dấu gạch ngang, bắt đầu bằng chữ cái.",
                        "es_ES": "Nombre de página no válido, por favor use un nombre válido que solo contenga letras minúsculas, números, guiones bajos y guiones, comenzando con una letra.",
                    },
                },
            },
        ],
        input_post_process=page_component_input_post_process,
    ),
    ComponentType(
        type_name="Runner",
        target_dir="components/runner",
        template_files=[
            "{runner_name}.yaml",
            "{runner_name}.py",
        ],
        form_fields=[
            {
                "name": "runner_name",
                "label": {
                    "en_US": "Runner name",
                    "zh_Hans": "Runner 名称",
                    "zh_Hant": "Runner 名稱",
                    "ja_JP": "Runner名",
                    "th_TH": "ชื่อ Runner",
                    "vi_VN": "Tên Runner",
                    "es_ES": "Nombre de Runner",
                },
                "required": True,
                "format": {
                    "regexp": NUMBER_LOWER_UNDERSCORE_REGEXP,
                    "error": {
                        "en_US": "Invalid Runner name, please use a valid name, which only contains lowercase letters, numbers, underscores and hyphens, and start with a letter.",
                        "zh_Hans": "无效的 Runner 名称，请使用一个有效的名称，只能包含小写字母、数字、下划线和连字符，且以字母开头。",
                        "zh_Hant": "無效的 Runner 名稱，請使用一個有效的名稱，只能包含小寫字母、數字、下劃線和連字符，且以字母開頭。",
                        "ja_JP": "無効なRunner名です。有効な名前を使用してください。小文字、数字、アンダースコア、ハイフンのみを使用し、先頭は文字でなければなりません。",
                        "th_TH": "ชื่อ Runner ไม่ถูกต้อง กรุณาใช้ชื่อที่ถูกต้อง ซึ่งประกอบด้วยตัวอักษรพิมพ์เล็ก ตัวเลข ขีดล่าง และขีดกลาง และขึ้นต้นด้วยตัวอักษร",
                        "vi_VN": "Tên Runner không hợp lệ, vui lòng sử dụng tên hợp lệ, chỉ chứa chữ thường, số, dấu gạch dưới và dấu gạch ngang, bắt đầu bằng chữ cái.",
                        "es_ES": "Nombre de Runner no válido, por favor use un nombre válido que solo contenga letras minúsculas, números, guiones bajos y guiones, comenzando con una letra.",
                    },
                },
            },
            {
                "name": "runner_description",
                "label": {
                    "en_US": "Runner description",
                    "zh_Hans": "Runner 描述",
                    "zh_Hant": "Runner 描述",
                    "ja_JP": "Runnerの説明",
                    "th_TH": "คำอธิบาย Runner",
                    "vi_VN": "Mô tả Runner",
                    "es_ES": "Descripción de Runner",
                },
                "required": True,
            },
        ],
        input_post_process=runner_component_input_post_process,
    ),
]
