from __future__ import annotations

from langbot_plugin.cli.gen import renderer


def test_component_input_post_processors_create_python_class_names():
    assert renderer.tool_component_input_post_process(
        {"tool_name": "web_search", "tool_description": "Search the web"}
    ) == {
        "tool_name": "web_search",
        "tool_label": "WebSearch",
        "tool_description": "Search the web",
        "tool_attr": "WebSearch",
    }
    assert (
        renderer.command_component_input_post_process(
            {"cmd_name": "hello_world", "cmd_description": "Say hello"}
        )["cmd_attr"]
        == "HelloWorld"
    )
    assert (
        renderer.knowledge_engine_component_input_post_process(
            {
                "knowledge_engine_name": "local_docs",
                "knowledge_engine_description": "Docs",
            }
        )["knowledge_engine_attr"]
        == "LocalDocs"
    )
    assert (
        renderer.parser_component_input_post_process(
            {"parser_name": "pdf_reader", "parser_description": "PDF"}
        )["parser_label"]
        == "PdfReader"
    )
    assert renderer.page_component_input_post_process(
        {"page_name": "settings_page"}
    ) == {
        "page_name": "settings_page",
        "page_label": "SettingsPage",
    }
    assert (
        renderer.runner_component_input_post_process(
            {"runner_name": "local_agent", "runner_description": "Run local agents"}
        )["runner_attr"]
        == "LocalAgent"
    )


def test_component_type_registry_contains_expected_public_component_kinds():
    by_name = {component.type_name: component for component in renderer.component_types}

    assert set(by_name) == {
        "EventListener",
        "Tool",
        "Command",
        "KnowledgeEngine",
        "Runner",
        "Parser",
        "Page",
    }
    assert by_name["Tool"].target_dir == "components/tools"
    assert "{tool_name}.py" in by_name["Tool"].template_files
    assert by_name["Page"].target_dir == "components/pages"
    assert by_name["Runner"].target_dir == "components/runner"


def test_simple_render_uses_python_format_context():
    assert renderer.simple_render("hello {name}", name="plugin") == "hello plugin"


def test_render_template_loads_packaged_templates():
    rendered = renderer.render_template(
        "components/tools/{tool_name}.yaml.example",
        tool_name="weather",
        tool_label="Weather",
        tool_description="Lookup weather",
        tool_attr="Weather",
    )

    assert "name: weather" in rendered
    assert "Weather" in rendered
    assert "Lookup weather" in rendered


def test_runner_template_renders_executable_component():
    context = renderer.runner_component_input_post_process(
        {"runner_name": "welcome", "runner_description": "Welcome members"}
    )
    rendered = renderer.render_template(
        "components/runner/{runner_name}.py.example", **context
    )
    compile(rendered, "welcome.py", "exec")
    assert "class Welcome(Runner)" in rendered
