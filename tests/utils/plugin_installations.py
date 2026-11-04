import pytest

from langbot.pkg.entity.persistence.plugin import PluginSetting


@pytest.fixture
def installed_legacy_plugin(monkeypatch):
    async def load_installation(application, workspace_uuid, installation_uuid):
        setting = application.test_plugin_installation
        assert setting.workspace_uuid == workspace_uuid
        assert setting.installation_uuid == installation_uuid
        return setting

    monkeypatch.setattr('langbot.pkg.api.application.plugin_permissions.load_installation', load_installation)


def install_legacy_plugin(application, binding, plugin_author, plugin_name):
    application.test_plugin_installation = PluginSetting(
        workspace_uuid=binding.workspace_uuid,
        installation_uuid=binding.installation_uuid,
        runtime_revision=binding.runtime_revision,
        artifact_digest=binding.artifact_digest,
        plugin_author=plugin_author,
        plugin_name=plugin_name,
        enabled=True,
        permission_declaration=None,
        permission_grants=None,
        permission_snapshot=None,
    )
