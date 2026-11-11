from __future__ import annotations

from typing import Any

import re
from langbot_plugin.cli.i18n import t, extract_i18n_label


NAME_REGEXP = r"^[a-zA-Z0-9_-]+$"
NUMBER_LOWER_UNDERSCORE_REGEXP = r"^[a-z][0-9a-z_]*$"


def input_form_values(
    form_fields: list[dict[str, Any]],
) -> dict[str, Any]:
    values = {}
    for field in form_fields:
        if field["required"]:
            while True:
                # 检查是否是内置字段类型，使用i18n消息
                if field["name"] == "plugin_author":
                    label = t("plugin_author")
                elif field["name"] == "plugin_description":
                    label = t("plugin_description")
                else:
                    label = extract_i18n_label(field.get("label", {}))  # type: ignore

                value = input(f"{label}: ")
                if "format" in field and "regexp" in field["format"]:  # type: ignore
                    if not re.match(field["format"]["regexp"], value):  # type: ignore
                        # 对于内置错误消息使用i18n
                        if field["name"] == "plugin_author":
                            print("!! " + t("invalid_format_error"))
                        else:
                            # 如果不是内置字段，显示英文错误（向后兼容）
                            print(f"!! {extract_i18n_label(field['format']['error'])}")  # type: ignore
                        continue
                break
            values[field["name"]] = value  # type: ignore
        else:
            # 检查是否是内置字段类型，使用i18n消息
            if field["name"] == "plugin_author":
                label = t("plugin_author")
            elif field["name"] == "plugin_description":
                label = t("plugin_description")
            else:
                label = extract_i18n_label(field.get("label", {}))  # type: ignore

            value = input(f"{label}: ")
            values[field["name"]] = value  # type: ignore

    return values
