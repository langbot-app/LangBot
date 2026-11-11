import os


def get_cloud_service_url() -> str:
    return os.getenv("CLOUD_SERVICE_URL", "https://space.langbot.app")
