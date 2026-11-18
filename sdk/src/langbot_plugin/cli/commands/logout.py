from __future__ import annotations

import json
from pathlib import Path
from langbot_plugin.cli.i18n import cli_print
from langbot_plugin.cli.utils.cloudsv import get_cloud_service_url

SERVER_URL = get_cloud_service_url()


def logout_process() -> None:
    """
    Implement LangBot CLI logout process

    Process:
    1. Remove credentials for current CLOUD_SERVICE_URL from config
    2. Display logout success message
    """

    try:
        config_file = Path.home() / ".langbot" / "cli" / "config.json"

        if not config_file.exists():
            cli_print("already_logged_out")
            return

        # Load existing config
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            cli_print("already_logged_out")
            return

        # Check if it's old format (flat dict) or new format (nested dict)
        if "access_token" in data:
            # Old format - remove entire file
            config_file.unlink()
            cli_print("logout_successful")
            cli_print("config_file_removed", config_file)
        else:
            # New format - remove credentials for current CLOUD_SERVICE_URL
            if SERVER_URL in data:
                del data[SERVER_URL]

                if data:
                    # Still have other site credentials, save the updated config
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    cli_print("logout_successful")
                else:
                    # No more credentials, remove the file
                    config_file.unlink()
                    cli_print("logout_successful")
                    cli_print("config_file_removed", config_file)
            else:
                cli_print("already_logged_out")

    except Exception as e:
        cli_print("logout_error", e)
