from __future__ import annotations

import copy
from dataclasses import dataclass
import typing

import langbot_plugin.api.entities.builtin.provider.message as provider_message

from ..provider.tools.loaders import skill as skill_loader

if typing.TYPE_CHECKING:
    from ..core import app
    import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@dataclass
class PreparedSkillActivation:
    activated_skill_names: list[str]
    cleaned_content: str
    prompt: str


@dataclass
class SkillActivationSnapshot:
    use_funcs: list | None
    variables: dict | None


@dataclass
class SkillActivationPlan:
    activated_skill_names: list[str]
    cleaned_content: str
    system_message: provider_message.Message
    snapshot: SkillActivationSnapshot


class SkillActivationCoordinator:
    """Owns the skill activation protocol around the local-agent runner."""

    def __init__(self, ap: app.Application, skill_mgr: typing.Any):
        self.ap = ap
        self.skill_mgr = skill_mgr

    def inspect_initial_content(self, content: str | None, is_final: bool) -> str:
        if not content:
            return 'emit'

        stripped = content.lstrip()
        if not stripped:
            return 'undecided'

        marker = str(getattr(self.skill_mgr, 'SKILL_ACTIVATION_MARKER', '[ACTIVATE_SKILL:'))
        if stripped.startswith(marker):
            return 'buffer'
        if not is_final and marker.startswith(stripped):
            return 'undecided'
        return 'emit'

    def prepare_followup(
        self,
        query: pipeline_query.Query,
        response_content: str | None,
    ) -> SkillActivationPlan | None:
        snapshot = self._snapshot_query_state(query)
        try:
            activation = prepare_skill_activation(self.ap, query, response_content)
        except Exception:
            self._restore_query_state(query, snapshot)
            raise

        if not activation:
            return None

        return SkillActivationPlan(
            activated_skill_names=activation.activated_skill_names,
            cleaned_content=activation.cleaned_content,
            system_message=provider_message.Message(role='system', content=activation.prompt),
            snapshot=snapshot,
        )

    def rollback(
        self,
        query: pipeline_query.Query,
        snapshot: SkillActivationSnapshot | None,
        response_message: provider_message.Message | provider_message.MessageChunk | None,
    ) -> None:
        if snapshot is not None:
            self._restore_query_state(query, snapshot)

        if response_message is None or not isinstance(response_message.content, str):
            return

        response_message.content = self.skill_mgr.remove_activation_marker(response_message.content)

    @staticmethod
    def _snapshot_use_funcs(use_funcs: list | None) -> list | None:
        if use_funcs is None:
            return None
        return list(use_funcs)

    def _snapshot_query_state(self, query: pipeline_query.Query) -> SkillActivationSnapshot:
        return SkillActivationSnapshot(
            use_funcs=self._snapshot_use_funcs(query.use_funcs),
            variables=copy.deepcopy(query.variables) if query.variables is not None else None,
        )

    @staticmethod
    def _restore_query_state(query: pipeline_query.Query, snapshot: SkillActivationSnapshot) -> None:
        query.use_funcs = snapshot.use_funcs
        query.variables = snapshot.variables


def prepare_skill_activation(
    ap: app.Application,
    query: pipeline_query.Query,
    response_content: str | None,
) -> PreparedSkillActivation | None:
    """Prepare multi-skill activation state on the query."""
    if not response_content or not getattr(ap, 'skill_mgr', None):
        return None

    activated_skill_names = ap.skill_mgr.detect_skill_activations(response_content)
    if not activated_skill_names:
        return None

    prompt = ap.skill_mgr.build_activation_prompt_for_skills(activated_skill_names)
    if not prompt:
        return None

    for skill_name in activated_skill_names:
        skill_data = ap.skill_mgr.get_skill_by_name(skill_name)
        if skill_data:
            skill_loader.register_activated_skill(query, skill_data)

    return PreparedSkillActivation(
        activated_skill_names=activated_skill_names,
        cleaned_content=ap.skill_mgr.remove_activation_marker(response_content),
        prompt=prompt,
    )


def get_skill_activation_coordinator(ap: app.Application) -> SkillActivationCoordinator | None:
    skill_mgr = getattr(ap, 'skill_mgr', None)
    if skill_mgr is None:
        return None

    required_methods = (
        'detect_skill_activations',
        'remove_activation_marker',
    )
    if any(not hasattr(skill_mgr, method_name) for method_name in required_methods):
        return None

    return SkillActivationCoordinator(ap, skill_mgr)
