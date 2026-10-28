"""Tests for the skills recall nudge injected into the system prompt.

Skills are surfaced by the host as ``ctx.resources.skills`` facts; the runner
renders a name+description ``<available_skills>`` index (Agent Skills
convention) so the model reliably considers calling ``activate``. Full skill
instructions stay out of context until activation (progressive disclosure).
"""

from __future__ import annotations

from types import SimpleNamespace

from langbot_plugin.api.entities.builtin.runner.resources import (
    AgentResources,
    SkillResource,
)

from pkg.messages import build_skills_system_message


def _ctx(skills: list[SkillResource]) -> SimpleNamespace:
    return SimpleNamespace(resources=AgentResources(skills=skills))


def test_returns_none_when_no_skills() -> None:
    assert build_skills_system_message(_ctx([])) is None
    assert build_skills_system_message(SimpleNamespace(resources=None)) is None
    assert build_skills_system_message(SimpleNamespace()) is None


def test_renders_available_skills_xml_with_activate_instruction() -> None:
    msg = build_skills_system_message(
        _ctx(
            [
                SkillResource(skill_name="pdf-tools", description="Work with PDF files."),
                SkillResource(skill_name="brave-search", description="Web search via Brave."),
            ]
        )
    )
    assert msg is not None
    assert msg.role == "system"
    content = msg.content

    # Progressive-disclosure nudge points at the activate tool, not a file path.
    assert "`activate`" in content
    assert "<available_skills>" in content and "</available_skills>" in content
    assert "<name>pdf-tools</name>" in content
    assert "<description>Work with PDF files.</description>" in content
    assert "<name>brave-search</name>" in content
    # Order preserved (host already sorts), and no full instructions leaked.
    assert content.index("pdf-tools") < content.index("brave-search")


def test_skill_without_description_still_listed() -> None:
    msg = build_skills_system_message(_ctx([SkillResource(skill_name="bare-skill")]))
    assert msg is not None
    assert "<name>bare-skill</name>" in msg.content
    assert "<description>" not in msg.content


def test_xml_special_characters_are_escaped() -> None:
    msg = build_skills_system_message(_ctx([SkillResource(skill_name="x", description='a < b & c "d" <tag>')]))
    assert msg is not None
    assert "&lt;" in msg.content and "&amp;" in msg.content and "&quot;" in msg.content
    # Raw description markup must not pass through verbatim.
    assert "< b & c" not in msg.content


def test_dict_shaped_skills_are_supported() -> None:
    # Defensive: accept dict-shaped skill facts as well as SkillResource models.
    ctx = SimpleNamespace(resources=SimpleNamespace(skills=[{"skill_name": "d", "description": "x"}]))
    msg = build_skills_system_message(ctx)
    assert msg is not None
    assert "<name>d</name>" in msg.content
