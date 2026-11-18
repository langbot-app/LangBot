from __future__ import annotations

import os

import yaml

from langbot_plugin.cli.gen.renderer import component_types, render_template
from langbot_plugin.cli.utils.form import input_form_values
from langbot_plugin.cli.gen.renderer import simple_render
from langbot_plugin.cli.i18n import cli_print, t


def generate_component_process(component_type: str) -> None:
    if not os.path.exists("manifest.yaml"):
        print("!! " + t("run_in_plugin_root"))
        return

    component_type_obj = None

    for component_type_obj in component_types:
        if component_type_obj.type_name == component_type:
            cli_print("generating_component", component_type_obj.type_name)
            component_type_obj = component_type_obj
            break
    else:
        print("!! " + t("component_not_found", component_type))
        print("!! " + t("available_components"))
        for component_type_obj in component_types:
            print(f"!! - {component_type_obj.type_name}")
        return

    values = {}

    if component_type_obj.form_fields:
        values = input_form_values(component_type_obj.form_fields)

    values = component_type_obj.input_post_process(values)  # type: ignore

    if not os.path.exists("components"):
        os.makedirs("components")
        if component_type_obj.type_name != "Page":
            with open("components/__init__.py", "w", encoding="utf-8") as f:
                f.write("")

    if not os.path.exists(component_type_obj.target_dir):
        os.makedirs(component_type_obj.target_dir)

    if component_type_obj.type_name != "Page":
        if not os.path.exists(f"{component_type_obj.target_dir}/__init__.py"):
            with open(
                f"{component_type_obj.target_dir}/__init__.py", "w", encoding="utf-8"
            ) as f:
                f.write("")

    # render templates
    for file in component_type_obj.template_files:
        content = render_template(
            f"{component_type_obj.target_dir}/{file}.example", **values
        )

        rendered_file_name = simple_render(file, **values)
        with open(
            f"{component_type_obj.target_dir}/{rendered_file_name}",
            "w",
            encoding="utf-8",
        ) as f:
            f.write(content)

    # update plugin manifest
    with open("manifest.yaml", "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    plugin_components = manifest["spec"]["components"]

    if component_type_obj.type_name not in plugin_components:
        plugin_components[component_type_obj.type_name] = {
            "fromDirs": [
                {
                    "path": f"{component_type_obj.target_dir}/",
                }
            ]
        }

    with open("manifest.yaml", "w", encoding="utf-8") as f:
        yaml.dump(manifest, f, allow_unicode=True, sort_keys=False)

    cli_print("component_generated", component_type_obj.type_name)
