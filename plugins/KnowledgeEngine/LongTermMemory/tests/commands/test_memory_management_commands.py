from __future__ import annotations

import json

import pytest

from components.commands.memory import Memory
from langbot_plugin.api.entities.builtin.command.context import ExecuteContext
from langbot_plugin.api.entities.builtin.provider.session import Session, LauncherTypes


class FakeAPI:
    async def get_bot_uuid(self) -> str:
        return "bot-1"

    async def get_query_vars(self) -> dict:
        return {"sender_id": "u-1", "sender_name": "Alice"}

    async def list_pipeline_knowledge_bases(self) -> list[dict]:
        return [{"uuid": "kb-1"}]


class FakeStore:
    EPISODE_STATUS_ACTIVE = "active"
    EPISODE_STATUS_SUPERSEDED = "superseded"
    EPISODE_STATUS_ARCHIVED = "archived"
    EPISODE_STATUS_DELETED = "deleted"
    EPISODE_STATUSES = {"active", "superseded", "archived", "deleted"}
    CANDIDATE_STATUS_PENDING = "pending"
    CANDIDATE_STATUS_ACCEPTED = "accepted"
    CANDIDATE_STATUS_REJECTED = "rejected"
    CANDIDATE_STATUSES = {"pending", "accepted", "rejected"}

    def __init__(self):
        self.audit_entries: list[dict] = []
        self.updated: list[tuple[str, str]] = []
        self.export_calls: list[dict] = []
        self.import_calls: list[dict] = []
        self.delete_calls: list[dict] = []
        self.preview_calls: list[dict] = []
        self.apply_calls: list[dict] = []
        self.accepted_candidates: list[str] = []
        self.rejected_candidates: list[str] = []
        self.consolidation_enabled = False

    async def resolve_user_context(self, session, bot_uuid: str = ""):
        return (
            "bot-1:group_1",
            "bot-1:group_1",
            "kb-1",
            "session",
            {
                "embedding_model_uuid": "emb-1",
                "consolidation_enabled": self.consolidation_enabled,
                "consolidation_min_age_days": 7,
                "consolidation_max_candidates": 20,
                "consolidation_apply_profile_updates": False,
            },
        )

    async def get_episode_by_id(self, collection_id, episode_id, user_key):
        if episode_id != "ep-1":
            return None
        return {
            "id": "ep-1",
            "content": "Old memory",
            "tags": ["correction"],
            "importance": 1,
            "timestamp": "2026-01-01T00:00:00Z",
            "sender_id": "u-1",
            "sender_name": "Alice",
            "source": "agent",
            "status": "superseded",
            "superseded_by": "ep-2",
        }

    async def list_episodes(
        self,
        collection_id,
        user_key,
        limit=10,
        offset=0,
        include_statuses=None,
    ):
        if include_statuses == ["superseded"]:
            return [
                {
                    "id": "ep-1",
                    "content": "Old memory",
                    "tags": [],
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ], 1
        return [], 0

    async def update_episode_status(
        self,
        collection_id,
        embedding_model_uuid,
        episode_id,
        user_key,
        status,
    ):
        if episode_id != "ep-1":
            return None
        self.updated.append((episode_id, status))
        return {"id": episode_id, "status": status}

    async def export_episodes_by_user(
        self,
        collection_id,
        user_key,
        include_statuses=None,
    ):
        self.export_calls.append({
            "collection_id": collection_id,
            "user_key": user_key,
            "include_statuses": include_statuses,
        })
        return [
            {
                "id": "ep-1",
                "content": "Old memory",
                "tags": ["correction"],
                "importance": 1,
                "timestamp": "2026-01-01T00:00:00Z",
                "user_key": user_key,
                "sender_id": "u-1",
                "sender_name": "Alice",
                "source": "agent",
                "status": "superseded",
                "superseded_by": "ep-2",
            }
        ]

    async def import_episodes_for_user(
        self,
        collection_id,
        embedding_model_uuid,
        user_key,
        episodes,
        bot_uuid="",
    ):
        self.import_calls.append({
            "collection_id": collection_id,
            "embedding_model_uuid": embedding_model_uuid,
            "user_key": user_key,
            "episodes": episodes,
            "bot_uuid": bot_uuid,
        })
        return [{"id": "new-1", "content": episodes[0]["content"], "user_key": user_key}]

    async def delete_episodes_by_filters(
        self,
        collection_id,
        user_key,
        sender_id="",
        tag="",
        before="",
        include_statuses=None,
    ):
        self.delete_calls.append({
            "collection_id": collection_id,
            "user_key": user_key,
            "sender_id": sender_id,
            "tag": tag,
            "before": before,
            "include_statuses": include_statuses,
        })
        return 2, ["archived-1", "archived-2"]

    async def preview_consolidation(
        self,
        collection_id,
        user_key,
        min_age_days=7,
        max_candidates=20,
        apply_profile_updates=False,
    ):
        self.preview_calls.append({
            "collection_id": collection_id,
            "user_key": user_key,
            "min_age_days": min_age_days,
            "max_candidates": max_candidates,
            "apply_profile_updates": apply_profile_updates,
        })
        return {
            "candidate_episode_ids": ["old-1", "old-2"],
            "candidates": [],
            "summary_episode": "Consolidated two old memories.",
            "profile_updates": [],
            "episodes_to_archive": ["old-1", "old-2"],
            "risk_notes": ["Preview is read-only."],
        }

    async def apply_consolidation(
        self,
        collection_id,
        embedding_model_uuid,
        user_key,
        min_age_days=7,
        max_candidates=20,
        apply_profile_updates=False,
    ):
        self.apply_calls.append({
            "collection_id": collection_id,
            "embedding_model_uuid": embedding_model_uuid,
            "user_key": user_key,
            "min_age_days": min_age_days,
            "max_candidates": max_candidates,
            "apply_profile_updates": apply_profile_updates,
        })
        return {
            "preview": {
                "candidate_episode_ids": ["old-1", "old-2"],
                "episodes_to_archive": ["old-1", "old-2"],
            },
            "archived_episode_ids": ["old-1", "old-2"],
            "summary_episode": {"id": "summary-1", "content": "summary"},
            "profile_updates_applied": [],
        }

    async def list_memory_candidates(
        self,
        scope_key,
        limit=10,
        offset=0,
        include_statuses=None,
    ):
        entries = [
            {
                "candidate_id": "cand-1",
                "status": "pending",
                "candidate_type": "l2_episode",
                "payload": {"content": "Alice has a meeting tomorrow"},
                "reason": "Temporal fact",
            },
            {
                "candidate_id": "cand-2",
                "status": "rejected",
                "candidate_type": "ignore",
                "payload": {"content": "secret"},
                "reason": "Sensitive",
            },
        ]
        statuses = set(include_statuses or ["pending"])
        filtered = [entry for entry in entries if entry["status"] in statuses]
        return filtered[offset: offset + limit], len(filtered)

    async def get_memory_candidate(self, scope_key, candidate_id):
        entries, _total = await self.list_memory_candidates(
            scope_key,
            include_statuses=self.CANDIDATE_STATUSES,
        )
        for entry in entries:
            if entry["candidate_id"] == candidate_id:
                return entry
        return None

    async def accept_memory_candidate(
        self,
        scope_key,
        candidate_id,
        collection_id,
        embedding_model_uuid,
        user_key,
        bot_uuid="",
    ):
        if candidate_id == "missing":
            return None
        self.accepted_candidates.append(candidate_id)
        return {
            "candidate_id": candidate_id,
            "status": "accepted",
            "accepted_result": {"type": "episode", "episode": {"id": "ep-new"}},
        }

    async def reject_memory_candidate(self, scope_key, candidate_id):
        if candidate_id == "missing":
            return None
        self.rejected_candidates.append(candidate_id)
        return {"candidate_id": candidate_id, "status": "rejected"}

    async def append_audit_entry(self, **entry):
        self.audit_entries.append(entry)
        return entry

    @staticmethod
    def _preview_text(value: str, max_len: int = 120) -> str:
        return value[:max_len]


class FakePlugin:
    def __init__(self):
        self.memory_store = FakeStore()
        self.plugin_runtime_handler = object()


def _context(command: str, params: list[str]) -> ExecuteContext:
    return ExecuteContext(
        query_id=1,
        session=Session(launcher_type=LauncherTypes.GROUP, launcher_id="1"),
        command_text=f"memory {command}",
        full_command_text=f"!memory {command}",
        command="memory",
        crt_command=command,
        params=[command, *params],
        crt_params=params,
        privilege=0,
    )


async def _run(command: Memory, subcommand_name: str, params: list[str]) -> str:
    subcommand = command.registered_subcommands[subcommand_name].subcommand
    results = []
    async for item in subcommand(command, _context(subcommand_name, params)):
        results.append(item.text or "")
    return "\n".join(results)


@pytest.mark.asyncio
async def test_memory_show_displays_episode_details(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    command.plugin = FakePlugin()

    output = await _run(command, "show", ["ep-1"])

    assert "Status: superseded" in output
    assert "Superseded by: ep-2" in output
    assert "Old memory" in output


@pytest.mark.asyncio
async def test_memory_superseded_lists_hidden_records(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    command.plugin = FakePlugin()

    output = await _run(command, "superseded", [])

    assert "Superseded episodes" in output
    assert "ep-1" in output


@pytest.mark.asyncio
async def test_archive_and_restore_write_audit(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    archive_output = await _run(command, "archive", ["ep-1"])
    restore_output = await _run(command, "restore", ["ep-1"])

    assert "status set to archived" in archive_output
    assert "status set to active" in restore_output
    assert plugin.memory_store.updated == [("ep-1", "archived"), ("ep-1", "active")]
    assert [entry["operation"] for entry in plugin.memory_store.audit_entries] == [
        "archived",
        "restore",
    ]


@pytest.mark.asyncio
async def test_memory_export_l2_is_scoped_and_writes_audit(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run(command, "export", ["l2"])
    data = json.loads(output)

    assert data["scope_key"] == "bot-1:group_1"
    assert data["user_key"] == "bot-1:group_1"
    assert data["count"] == 1
    assert data["episodes"][0]["id"] == "ep-1"
    assert plugin.memory_store.export_calls == [{
        "collection_id": "kb-1",
        "user_key": "bot-1:group_1",
        "include_statuses": ["active", "archived", "deleted", "superseded"],
    }]
    assert plugin.memory_store.audit_entries[-1]["operation"] == "export_l2"


@pytest.mark.asyncio
async def test_memory_import_l2_forces_current_scope_and_writes_audit(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin
    payload = json.dumps({
        "episodes": [
            {
                "id": "foreign-id",
                "content": "Imported memory",
                "user_key": "foreign-scope",
            }
        ]
    })

    output = await _run(command, "import", ["l2", payload])

    assert "Imported 1 L2 episode" in output
    assert plugin.memory_store.import_calls[0]["user_key"] == "bot-1:group_1"
    assert plugin.memory_store.import_calls[0]["episodes"][0]["user_key"] == "foreign-scope"
    assert plugin.memory_store.audit_entries[-1]["operation"] == "import_l2"


@pytest.mark.asyncio
async def test_memory_delete_l2_bulk_is_scoped_and_writes_audit(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run(command, "delete", ["--status", "archived"])

    assert "Deleted 2 L2 episode" in output
    assert plugin.memory_store.delete_calls == [{
        "collection_id": "kb-1",
        "user_key": "bot-1:group_1",
        "sender_id": "",
        "tag": "",
        "before": "",
        "include_statuses": ["archived"],
    }]
    assert plugin.memory_store.audit_entries[-1]["operation"] == "delete_l2_bulk"
    assert plugin.memory_store.audit_entries[-1]["metadata"]["episode_ids"] == [
        "archived-1",
        "archived-2",
    ]


@pytest.mark.asyncio
async def test_memory_consolidate_preview_is_read_only(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run(command, "consolidate", ["preview"])

    assert "Candidates: 2" in output
    assert "Summary episode: Consolidated two old memories." in output
    assert plugin.memory_store.preview_calls
    assert plugin.memory_store.apply_calls == []
    assert plugin.memory_store.audit_entries == []


@pytest.mark.asyncio
async def test_memory_consolidate_run_requires_enabled_config(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run(command, "consolidate", ["run"])

    assert "Consolidation run is disabled" in output
    assert plugin.memory_store.apply_calls == []
    assert plugin.memory_store.audit_entries == []


@pytest.mark.asyncio
async def test_memory_consolidate_run_writes_audit(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    plugin.memory_store.consolidation_enabled = True
    command.plugin = plugin

    output = await _run(command, "consolidate", ["run"])

    assert "archived 2 episode" in output
    assert plugin.memory_store.apply_calls[0]["user_key"] == "bot-1:group_1"
    assert [entry["operation"] for entry in plugin.memory_store.audit_entries] == [
        "consolidate_archive",
        "consolidate_archive",
        "consolidate_summary",
        "consolidate_run",
    ]


@pytest.mark.asyncio
async def test_memory_candidates_lists_pending_by_default(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run(command, "candidates", [])

    assert "cand-1" in output
    assert "Alice has a meeting tomorrow" in output
    assert "cand-2" not in output


@pytest.mark.asyncio
async def test_memory_candidate_accept_writes_audit(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run(command, "candidate", ["accept", "cand-1"])

    assert "accepted" in output
    assert plugin.memory_store.accepted_candidates == ["cand-1"]
    assert plugin.memory_store.audit_entries[-1]["operation"] == "candidate_accept"


@pytest.mark.asyncio
async def test_memory_candidate_accept_l1_does_not_require_active_kb(monkeypatch):
    class InactiveAPI(FakeAPI):
        async def list_pipeline_knowledge_bases(self) -> list[dict]:
            return []

    class L1Store(FakeStore):
        async def get_memory_candidate(self, scope_key, candidate_id):
            if candidate_id != "cand-l1":
                return None
            return {
                "candidate_id": "cand-l1",
                "status": "pending",
                "candidate_type": "l1_profile",
                "payload": {"field": "preferences", "value": "Alice prefers concise answers"},
            }

        async def accept_memory_candidate(
            self,
            scope_key,
            candidate_id,
            collection_id,
            embedding_model_uuid,
            user_key,
            bot_uuid="",
        ):
            self.accepted_candidates.append(candidate_id)
            return {
                "candidate_id": candidate_id,
                "status": "accepted",
                "accepted_result": {"type": "profile", "profile": {"preferences": ["concise"]}},
            }

    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: InactiveAPI())
    command = Memory()
    plugin = FakePlugin()
    plugin.memory_store = L1Store()
    command.plugin = plugin

    output = await _run(command, "candidate", ["accept", "cand-l1"])

    assert "accepted" in output
    assert plugin.memory_store.accepted_candidates == ["cand-l1"]
    assert plugin.memory_store.audit_entries[-1]["operation"] == "candidate_accept"


@pytest.mark.asyncio
async def test_memory_candidate_reject_writes_audit(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run(command, "candidate", ["reject", "cand-1"])

    assert "rejected" in output
    assert plugin.memory_store.rejected_candidates == ["cand-1"]
    assert plugin.memory_store.audit_entries[-1]["operation"] == "candidate_reject"
