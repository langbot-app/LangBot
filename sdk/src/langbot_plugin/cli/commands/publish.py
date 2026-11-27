from __future__ import annotations

import shutil
import httpx

from langbot_plugin.cli.commands.login import check_login_status, get_access_token
from langbot_plugin.cli.commands.buildplugin import build_plugin_process
from langbot_plugin.cli.utils.cloudsv import get_cloud_service_url
from langbot_plugin.cli.i18n import cli_print

SERVER_URL = get_cloud_service_url()


TMP_DIR = "dist/tmp"


def _get_http_error_message(response: httpx.Response) -> str:
    """Return the API's actionable message for an unsuccessful response."""
    try:
        result = response.json()
        if isinstance(result, dict) and result.get("msg"):
            return str(result["msg"])
    except (ValueError, TypeError):
        pass

    body = response.text.strip()
    return body or f"HTTP {response.status_code} {response.reason_phrase}"


def publish_plugin(plugin_path: str, changelog: str, access_token: str) -> None:
    """
    Publish the plugin to LangBot Marketplace

    POST /api/v1/marketplace/plugins/publish
    form-data:
        - file: plugin.zip
        - changelog: changelog
    """
    url = f"{SERVER_URL}/api/v1/marketplace/plugins/publish"
    data = {"changelog": changelog}

    try:
        with open(plugin_path, "rb") as package_file:
            with httpx.Client() as client:
                response = client.post(
                    url,
                    files={"file": package_file},
                    data=data,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=300,
                )

                if response.is_error:
                    cli_print("publish_failed", _get_http_error_message(response))
                    return

                result = response.json()
                if result["code"] != 0:
                    cli_print("publish_failed", result["msg"])
                    return

                if result["data"]["submission"]["status"] == "draft":
                    cli_print("publish_successful_new_plugin", SERVER_URL)
                else:
                    cli_print("publish_successful", SERVER_URL)
                return
    except Exception as e:
        cli_print("publish_failed", e)
        return


def publish_process() -> None:
    """
    Implement LangBot CLI publish process
    """
    if not check_login_status():
        cli_print("not_logged_in")
        return

    access_token = get_access_token()
    if not access_token:
        cli_print("not_logged_in")
        return

    # build plugin
    plugin_path = build_plugin_process(TMP_DIR)

    # publish plugin
    publish_plugin(plugin_path, "", access_token)

    # clean up
    shutil.rmtree(TMP_DIR)
