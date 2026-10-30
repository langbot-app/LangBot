from __future__ import annotations

from pkg.session_management import normalize_sessions, resolve_session_target, storage_key


def test_normalize_sessions_sorts_and_filters_invalid_items():
    result = {
        "sessions": [
            {
                "sessionId": "ses_old",
                "title": "Old",
                "cwd": "/workspace",
                "updatedAt": "2026-01-01T00:00:00Z",
            },
            {"title": "Missing id"},
            {
                "sessionId": "ses_new",
                "title": "New",
                "cwd": "/workspace",
                "updatedAt": "2026-01-02T00:00:00Z",
            },
        ]
    }

    sessions = normalize_sessions(result)

    assert [item["session_id"] for item in sessions] == ["ses_new", "ses_old"]


def test_resolve_session_target_accepts_index_or_exact_id():
    sessions = [
        {"session_id": "ses_one", "title": "One", "cwd": "", "updated_at": ""},
        {"session_id": "ses_two", "title": "Two", "cwd": "", "updated_at": ""},
    ]

    assert resolve_session_target("2", sessions) == "ses_two"
    assert resolve_session_target("ses_one", sessions) == "ses_one"
    assert resolve_session_target("3", sessions) is None
    assert resolve_session_target("ses_missing", sessions) is None


def test_storage_key_does_not_expose_conversation_id():
    key = storage_key("current", "person_sensitive-platform-id")

    assert key.startswith("acp-session:v1:current:")
    assert "sensitive-platform-id" not in key
