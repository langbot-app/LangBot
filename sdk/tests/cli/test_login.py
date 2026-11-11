from __future__ import annotations

import json
import time

import httpx

from langbot_plugin.cli.commands import login


class FakeResponse:
    def __init__(self, json_data, *, raise_error=False):
        self._json_data = json_data
        self.raise_error = raise_error

    def raise_for_status(self):
        if self.raise_error:
            raise httpx.HTTPStatusError("bad", request=None, response=None)

    def json(self):
        return self._json_data


class FakeClient:
    responses: list[FakeResponse] = []
    calls: list[tuple[str, dict]] = []

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class FailingClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        raise httpx.RequestError("network down")


class ErrorClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        raise RuntimeError("boom")


def test_save_config_creates_nested_server_config(tmp_path, monkeypatch):
    monkeypatch.setattr(login.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")

    path = login._save_config({"access_token": "token"})

    assert path == str(tmp_path / ".langbot" / "cli" / "config.json")
    assert json.loads((tmp_path / ".langbot" / "cli" / "config.json").read_text()) == {
        "https://cloud": {"access_token": "token"}
    }


def test_save_config_migrates_old_flat_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".langbot" / "cli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({"access_token": "old"}), encoding="utf-8")
    monkeypatch.setattr(login.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")

    login._save_config({"access_token": "new"})

    assert json.loads(config_file.read_text()) == {
        "https://cloud": {"access_token": "new"}
    }


def test_save_config_recovers_from_corrupt_existing_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".langbot" / "cli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    config_file.write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr(login.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")

    login._save_config({"access_token": "new"})

    assert json.loads(config_file.read_text()) == {
        "https://cloud": {"access_token": "new"}
    }


def test_load_config_supports_flat_and_nested_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".langbot" / "cli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    monkeypatch.setattr(login.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")

    config_file.write_text(json.dumps({"access_token": "flat"}), encoding="utf-8")
    assert login._load_config() == {"access_token": "flat"}

    config_file.write_text(
        json.dumps({"https://cloud": {"access_token": "nested"}}),
        encoding="utf-8",
    )
    assert login._load_config() == {"access_token": "nested"}


def test_load_config_returns_none_for_missing_or_corrupt_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".langbot" / "cli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    monkeypatch.setattr(login.Path, "home", lambda: tmp_path)

    assert login._load_config() is None

    config_file.write_text("{bad json", encoding="utf-8")
    assert login._load_config() is None


def test_is_token_valid_accepts_pat_and_unexpired_oauth_token(monkeypatch):
    monkeypatch.setattr(login.time, "time", lambda: 200)

    assert login._is_token_valid({"token_type": "personal_access_token"}) is True
    assert login._is_token_valid({"login_time": 100, "expires_in": 200}) is True
    assert login._is_token_valid({"login_time": 100, "expires_in": 50}) is False
    assert login._is_token_valid({}) is False


def test_refresh_token_posts_refresh_token_and_persists_new_access_token(
    tmp_path, monkeypatch
):
    FakeClient.calls = []
    FakeClient.responses = [
        FakeResponse({"data": {"access_token": "new-token", "expires_in": 3600}})
    ]
    monkeypatch.setattr(login.httpx, "Client", FakeClient)
    monkeypatch.setattr(login.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")
    monkeypatch.setattr(login.time, "time", lambda: 1234)

    config = {"refresh_token": "refresh-token"}

    assert login._refresh_token(config) is True
    assert config == {
        "refresh_token": "refresh-token",
        "access_token": "new-token",
        "expires_in": 3600,
        "login_time": 1234,
    }
    assert FakeClient.calls == [
        (
            "https://cloud/api/v1/accounts/token/refresh",
            {"json": {"refresh_token": "refresh-token"}},
        )
    ]


def test_refresh_token_returns_false_without_refresh_token():
    assert login._refresh_token({}) is False
    assert login._refresh_token({"access_token": "token"}) is False


def test_refresh_token_returns_false_when_response_lacks_access_token(monkeypatch):
    FakeClient.calls = []
    FakeClient.responses = [FakeResponse({"data": {"expires_in": 3600}})]
    monkeypatch.setattr(login.httpx, "Client", FakeClient)

    assert login._refresh_token({"refresh_token": "refresh-token"}) is False


def test_refresh_token_reports_unexpected_failure(monkeypatch):
    prints = []
    monkeypatch.setattr(login.httpx, "Client", ErrorClient)
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))

    assert login._refresh_token({"refresh_token": "refresh-token"}) is False
    assert len(prints) == 1
    assert prints[0][0] == "token_refresh_failed"


def test_generate_device_code_posts_to_token_generate(monkeypatch):
    FakeClient.calls = []
    FakeClient.responses = [FakeResponse({"code": 0, "data": {"device_code": "d"}})]
    monkeypatch.setattr(login.httpx, "Client", FakeClient)

    assert login._generate_device_code("https://cloud/api/v1") == {
        "code": 0,
        "data": {"device_code": "d"},
    }
    assert FakeClient.calls == [("https://cloud/api/v1/accounts/token/generate", {})]


def test_generate_device_code_reports_network_failure(monkeypatch):
    monkeypatch.setattr(login.httpx, "Client", FailingClient)
    monkeypatch.setattr(login, "t", lambda key, error: f"{key}: {error}")

    assert login._generate_device_code("https://cloud/api/v1") == {
        "code": -1,
        "msg": "network_request_failed: network down",
    }


def test_generate_device_code_reports_unexpected_failure(monkeypatch):
    monkeypatch.setattr(login.httpx, "Client", ErrorClient)
    monkeypatch.setattr(login, "t", lambda key, error: f"{key}: {error}")

    assert login._generate_device_code("https://cloud/api/v1") == {
        "code": -1,
        "msg": "device_code_failed: boom",
    }


def test_poll_for_token_returns_token_data(monkeypatch):
    FakeClient.calls = []
    FakeClient.responses = [
        FakeResponse({"code": 0, "data": {"access_token": "token"}})
    ]
    monkeypatch.setattr(login.httpx, "Client", FakeClient)
    monkeypatch.setattr(login.time, "time", lambda: 0)

    assert login._poll_for_token("https://cloud/api/v1", "dev", "user", 3, 10) == {
        "access_token": "token"
    }
    assert FakeClient.calls == [
        (
            "https://cloud/api/v1/accounts/token/get",
            {"json": {"device_code": "dev", "user_code": "user"}},
        )
    ]


def test_poll_for_token_waits_while_authorization_is_pending(monkeypatch):
    sleeps = []
    times = iter([0, 0, 1])
    FakeClient.calls = []
    FakeClient.responses = [
        FakeResponse({"code": 425, "msg": "pending"}),
        FakeResponse({"code": 0, "data": {"access_token": "token"}}),
    ]
    monkeypatch.setattr(login.httpx, "Client", FakeClient)
    monkeypatch.setattr(login.time, "time", lambda: next(times))
    monkeypatch.setattr(login.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert login._poll_for_token("https://cloud/api/v1", "dev", "user", 3, 10) == {
        "access_token": "token"
    }
    assert sleeps == [3]


def test_poll_for_token_reports_non_pending_api_failure(monkeypatch):
    prints = []
    FakeClient.calls = []
    FakeClient.responses = [FakeResponse({"code": 400, "msg": "bad code"})]
    monkeypatch.setattr(login.httpx, "Client", FakeClient)
    monkeypatch.setattr(login.time, "time", lambda: 0)
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))

    assert login._poll_for_token("https://cloud/api/v1", "dev", "user", 3, 10) is None
    assert prints == [("token_get_failed", "bad code")]


def test_poll_for_token_reports_network_failure(monkeypatch):
    prints = []
    monkeypatch.setattr(login.httpx, "Client", FailingClient)
    monkeypatch.setattr(login.time, "time", lambda: 0)
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))

    assert login._poll_for_token("https://cloud/api/v1", "dev", "user", 3, 10) is None
    assert len(prints) == 1
    assert prints[0][0] == "network_request_failed"


def test_poll_for_token_reports_unexpected_failure(monkeypatch):
    prints = []
    monkeypatch.setattr(login.httpx, "Client", ErrorClient)
    monkeypatch.setattr(login.time, "time", lambda: 0)
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))

    assert login._poll_for_token("https://cloud/api/v1", "dev", "user", 3, 10) is None
    assert len(prints) == 1
    assert prints[0][0] == "token_check_failed"


def test_poll_for_token_returns_none_after_timeout(monkeypatch):
    times = iter([0, 31])
    monkeypatch.setattr(login.time, "time", lambda: next(times))

    assert login._poll_for_token("https://cloud/api/v1", "dev", "user", 3, 0) is None


def test_login_process_rejects_invalid_personal_access_token(monkeypatch):
    prints = []
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))

    login.login_process("bad-token")

    assert prints == [("pat_invalid_format",)]


def test_login_process_saves_personal_access_token(tmp_path, monkeypatch):
    prints = []
    monkeypatch.setattr(login.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))
    monkeypatch.setattr(login.time, "time", lambda: 1234)

    login.login_process("lbpat_secret")

    config_file = tmp_path / ".langbot" / "cli" / "config.json"
    assert json.loads(config_file.read_text())["https://cloud"] == {
        "access_token": "lbpat_secret",
        "token_type": "personal_access_token",
        "login_time": 1234,
        "expires_in": 0,
    }
    assert ("pat_login_successful",) in prints
    assert ("pat_saved", str(config_file)) in prints


def test_login_process_reports_device_code_failure(monkeypatch):
    prints = []
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))
    monkeypatch.setattr(
        login,
        "_generate_device_code",
        lambda api_base: {"code": 1, "msg": "denied"},
    )

    login.login_process()

    assert prints == [
        ("starting_login",),
        ("generating_device_code",),
        ("device_code_failed", "denied"),
    ]


def test_login_process_reports_timeout_when_poll_returns_no_token(monkeypatch):
    prints = []
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))
    monkeypatch.setattr(
        login,
        "_generate_device_code",
        lambda api_base: {
            "code": 0,
            "data": {
                "device_code": "dev",
                "user_code": "user",
                "verification_uri": "/verify",
                "expires_in": 60,
            },
        },
    )
    monkeypatch.setattr(
        login,
        "_poll_for_token",
        lambda api_base, device_code, user_code, interval, expires_in: None,
    )

    login.login_process()

    assert prints[-1] == ("login_timeout",)


def test_login_process_saves_device_flow_token(monkeypatch):
    prints = []
    saved_configs = []
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))
    monkeypatch.setattr(login.time, "time", lambda: 1234)
    monkeypatch.setattr(
        login,
        "_generate_device_code",
        lambda api_base: {
            "code": 0,
            "data": {
                "device_code": "dev",
                "user_code": "user",
                "verification_uri": "/verify",
                "expires_in": 60,
            },
        },
    )
    monkeypatch.setattr(
        login,
        "_poll_for_token",
        lambda api_base, device_code, user_code, interval, expires_in: {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
    )
    monkeypatch.setattr(
        login,
        "_save_config",
        lambda config: saved_configs.append(config) or "/tmp/config.json",
    )

    login.login_process()

    assert saved_configs == [
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "token_type": "Bearer",
            "login_time": 1234,
        }
    ]
    assert ("login_successful",) in prints
    assert ("token_saved", "/tmp/config.json") in prints
    assert ("token_type_label", "Bearer") in prints
    assert ("expires_in_label", 3600) in prints


def test_login_process_reports_unexpected_error(monkeypatch):
    prints = []
    error = RuntimeError("boom")
    monkeypatch.setattr(login, "cli_print", lambda *args: prints.append(args))
    monkeypatch.setattr(
        login,
        "_generate_device_code",
        lambda api_base: (_ for _ in ()).throw(error),
    )

    login.login_process()

    assert prints == [
        ("starting_login",),
        ("generating_device_code",),
        ("login_error", error),
    ]


def test_check_login_status_refreshes_expired_token(tmp_path, monkeypatch):
    config_dir = tmp_path / ".langbot" / "cli"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "https://cloud": {
                    "refresh_token": "refresh-token",
                    "login_time": int(time.time()) - 100,
                    "expires_in": 1,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(login.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")
    monkeypatch.setattr(login, "_refresh_token", lambda config: True)

    assert login.check_login_status() is True


def test_get_access_token_returns_only_valid_token(tmp_path, monkeypatch):
    config_dir = tmp_path / ".langbot" / "cli"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    monkeypatch.setattr(login.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(login, "SERVER_URL", "https://cloud")
    monkeypatch.setattr(login.time, "time", lambda: 200)

    config_file.write_text(
        json.dumps(
            {
                "https://cloud": {
                    "access_token": "token",
                    "login_time": 100,
                    "expires_in": 200,
                }
            }
        ),
        encoding="utf-8",
    )
    assert login.get_access_token() == "token"

    config_file.write_text(
        json.dumps(
            {
                "https://cloud": {
                    "access_token": "expired",
                    "login_time": 100,
                    "expires_in": 50,
                }
            }
        ),
        encoding="utf-8",
    )
    assert login.get_access_token() is None
