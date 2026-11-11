from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from langbot_plugin.cli.utils.cloudsv import get_cloud_service_url
from langbot_plugin.cli.i18n import cli_print, t

SERVER_URL = get_cloud_service_url()


def login_process(token: str | None = None) -> None:
    if token is not None:
        if not token.startswith("lbpat_"):
            cli_print("pat_invalid_format")
            return

        config = {
            "access_token": token,
            "token_type": "personal_access_token",
            "login_time": int(time.time()),
            "expires_in": 0,
        }

        config_file = _save_config(config)

        print("\n" + "=" * 50)
        cli_print("pat_login_successful")
        cli_print("pat_saved", config_file)
        print("=" * 50)
        return

    """
    Implement LangBot CLI login process

    Process:
    1. Generate device code
    2. Display user code and verification URI
    3. Wait for user to input user code
    4. Loop check token acquisition status
    5. Save token to config file
    6. Display login success message
    """

    # Configuration
    API_BASE = f"{SERVER_URL}/api/v1"

    try:
        cli_print("starting_login")

        # 1. Generate device code
        cli_print("generating_device_code")
        device_code_response = _generate_device_code(API_BASE)

        if device_code_response["code"] != 0:
            cli_print("device_code_failed", device_code_response["msg"])
            return

        device_data = device_code_response["data"]
        device_code = device_data["device_code"]
        user_code = device_data["user_code"]
        verification_uri = f"{SERVER_URL}{device_data['verification_uri']}"
        expires_in = device_data["expires_in"]

        # 2. Display user code and verification URI
        print("\n" + "=" * 50)
        cli_print("copy_user_code")
        cli_print("user_code_label", user_code)
        cli_print("verification_url_label", verification_uri)
        cli_print("code_expires_label", expires_in)
        print("=" * 50)
        print("")
        cli_print("waiting_verification")

        # 3. Loop check token acquisition status
        token_data = _poll_for_token(API_BASE, device_code, user_code, 3, expires_in)

        if not token_data:
            cli_print("login_timeout")
            return

        # 4. Save token to config file
        config = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_in": token_data["expires_in"],
            "token_type": token_data["token_type"],
            "login_time": int(time.time()),
        }

        config_file = _save_config(config)

        # 5. Display login success message
        print("\n" + "=" * 50)
        cli_print("login_successful")
        cli_print("token_saved", config_file)
        cli_print("token_type_label", token_data["token_type"])
        cli_print("expires_in_label", token_data["expires_in"])
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n" + t("login_cancelled"))
    except Exception as e:
        cli_print("login_error", e)


def _save_config(config: dict[str, Any]) -> str:
    """Save configuration file with credentials keyed by CLOUD_SERVICE_URL"""
    config_dir = Path.home() / ".langbot" / "cli"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    # Load existing config or create new dict structure
    all_configs = {}
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                # Check if it's old format (flat dict with access_token) or new format (nested dict)
                if "access_token" in existing_data:
                    # Old format - migrate to new format under current SERVER_URL
                    # This preserves credentials for the site currently being used
                    all_configs = {SERVER_URL: existing_data}
                else:
                    # New format - use as is
                    all_configs = existing_data
        except Exception:
            # If file is corrupted, start fresh
            all_configs = {}

    # Save config for current CLOUD_SERVICE_URL
    all_configs[SERVER_URL] = config

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(all_configs, f, indent=2, ensure_ascii=False)
    return str(config_file)


def _generate_device_code(api_base: str) -> dict[str, Any]:
    """Generate device code"""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{api_base}/accounts/token/generate")
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        return {"code": -1, "msg": t("network_request_failed", e)}
    except Exception as e:
        return {"code": -1, "msg": t("device_code_failed", e)}


def _poll_for_token(
    api_base: str, device_code: str, user_code: str, interval: int, expires_in: int
) -> dict[str, Any] | None:
    """Poll for token acquisition status"""
    start_time = time.time()
    max_wait_time = expires_in + 30  # Extra 30 seconds wait

    while time.time() - start_time < max_wait_time:
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{api_base}/accounts/token/get",
                    json={"device_code": device_code, "user_code": user_code},
                )
                response.raise_for_status()
                result = response.json()

                if result["code"] == 0:
                    return result["data"]
                elif result["code"] == 425:  # User not yet authorized
                    # print("Waiting for user authorization...")
                    pass
                else:
                    cli_print("token_get_failed", result["msg"])
                    return None

        except httpx.RequestError as e:
            cli_print("network_request_failed", e)
            return None
        except Exception as e:
            cli_print("token_check_failed", e)
            return None

        # Wait for specified interval
        time.sleep(interval)

    return None


def _load_config() -> dict[str, Any] | None:
    """Load configuration file for current CLOUD_SERVICE_URL"""
    config_file = Path.home() / ".langbot" / "cli" / "config.json"

    if not config_file.exists():
        return None

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)

            # Check if it's old format (flat dict with access_token) or new format (nested dict)
            if "access_token" in data:
                # Old format - return as is for backward compatibility
                # This will be migrated to new format on next save
                return data

            # New format - return config for current CLOUD_SERVICE_URL
            return data.get(SERVER_URL, None)
    except Exception:
        return None


def _is_token_valid(config: dict[str, Any]) -> bool:
    """Check if token is valid"""
    if not config:
        return False

    if config.get("token_type") == "personal_access_token":
        return True

    login_time = config.get("login_time", 0)
    expires_in = config.get("expires_in", 0)

    if not login_time or not expires_in:
        return False

    current_time = int(time.time())
    return current_time - login_time < expires_in


def _refresh_token(config: dict[str, Any]) -> bool:
    """Refresh token"""
    API_BASE = f"{SERVER_URL}/api/v1"
    if not config:
        return False

    refresh_token = config.get("refresh_token", None)
    if not refresh_token:
        return False

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{API_BASE}/accounts/token/refresh",
                json={"refresh_token": refresh_token},
            )
            response.raise_for_status()
            result = response.json()["data"]
            new_access_token = result.get("access_token", None)
            expires_in = result.get("expires_in", 21600)
            if not new_access_token:
                return False

            config["access_token"] = new_access_token
            config["expires_in"] = expires_in
            config["login_time"] = int(time.time())
            _save_config(config)
            return True

    except Exception as e:
        cli_print("token_refresh_failed", e)
        return False


def check_login_status() -> bool:
    """Check login status"""
    config = _load_config()
    if config and config.get("token_type") == "personal_access_token":
        return True
    if not _is_token_valid(config):
        # try refresh token
        if not _refresh_token(config):
            return False
    return True


def get_access_token() -> str | None:
    """Get access token"""
    config = _load_config()
    if _is_token_valid(config):
        return config.get("access_token")
    return None
