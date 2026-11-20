"""The task-owned PostgreSQL acceptance shares one fenced instance across phases."""

from tests.e2e import test_skill_persistence_replicas as acceptance


def test_process_acceptance_uses_same_pair_for_artifact_phase(monkeypatch):
    pair = object()
    calls = []
    monkeypatch.setattr(acceptance, '_exercise_core_pair', lambda supplied: calls.append(('packages', supplied)))
    monkeypatch.setattr(
        acceptance, '_exercise_skill_artifact_recovery', lambda supplied: calls.append(('artifacts', supplied))
    )
    acceptance.test_two_core_processes_share_skill_packages_and_uploaded_media(pair)
    assert calls == [('packages', pair), ('artifacts', pair)]
