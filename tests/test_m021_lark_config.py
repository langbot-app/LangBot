import asyncio
import pytest
from pkg.core.migrations import m021_lark_config

class FakePlatformCfg:
    def __init__(self, data):
        self.data = data
        self.dump_called = False
    async def dump_config(self):
        self.dump_called = True
class FakeAP:
    def __init__(self, platform_cfg):
        self.platform_cfg = platform_cfg
@pytest.mark.asyncio
async def test_run_adds_lark_config():
    """
    Test that the migration run() method properly adds a new "lark" adapter
    configuration when it is not already present, and that dump_config() is invoked.
    """
    fake_data = {'platform-adapters': []}
    fake_config = FakePlatformCfg(fake_data)
    fake_ap = FakeAP(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    # Before running, need_migrate() should return True since there's no "lark" adapter.
    assert await migration_instance.need_migrate() is True, (
        "Expected need_migrate() to return True when no 'lark' adapter exists."
    )
    
    await migration_instance.run()
    
    adapters = fake_config.data['platform-adapters']
    lark_configs = [adapter for adapter in adapters if adapter.get("adapter") == "lark"]
    assert len(lark_configs) == 1, (
        "Expected exactly one 'lark' adapter configuration to be added."
    )
    assert fake_config.dump_called, "Expected dump_config() to have been called during migration run."
@pytest.mark.asyncio
async def test_need_migrate_returns_false_when_lark_adapter_exists():
    """
    Test that need_migrate() returns False when a 'lark' adapter configuration
    already exists in the platform configuration.
    """
    fake_data = {
        'platform-adapters': [
            {
                "adapter": "lark",
                "enable": True,
                "app_id": "existing_app_id",
                "app_secret": "existing_app_secret",
                "bot_name": "ExistingBot",
                "port": 1234
            }
        ]
    }
    fake_config = FakePlatformCfg(fake_data)
    fake_ap = FakeAP(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    result = await migration_instance.need_migrate()
    assert result is False, "Expected need_migrate() to return False when a 'lark' adapter exists."
@pytest.mark.asyncio
async def test_need_migrate_raises_key_error_when_adapter_key_missing():
    """
    Test that need_migrate() raises a KeyError when an adapter configuration is missing the "adapter" key.
    This verifies the edge-case where the adapter dictionary is malformed.
    """
    fake_data = {
        'platform-adapters': [
            {
                "enable": True,
                "app_id": "cli_missing",
                "app_secret": "missing",
                "bot_name": "NoAdapterBot",
                "port": None
            }
        ]
    }
    fake_config = FakePlatformCfg(fake_data)
    fake_ap = FakeAP(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    with pytest.raises(KeyError):
        await migration_instance.need_migrate()
@pytest.mark.asyncio
async def test_need_migrate_raises_key_error_when_platform_adapters_missing():
    """
    Test that need_migrate() raises a KeyError when the platform configuration is missing the
    'platform-adapters' key. This simulates a scenario where the configuration structure is malformed.
    """
    fake_data = {}  # 'platform-adapters' key is missing
    fake_config = FakePlatformCfg(fake_data)
    fake_ap = FakeAP(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    with pytest.raises(KeyError):
        await migration_instance.need_migrate()
@pytest.mark.asyncio
async def test_run_keeps_existing_adapters():
    """
    Test that the migration run() method preserves existing platform adapters
    and still appends a new 'lark' configuration.
    """
    fake_data = {
        'platform-adapters': [
            {"adapter": "slack", "enable": True, "channel": "#general"}
        ]
    }
    fake_config = FakePlatformCfg(fake_data)
    fake_ap = FakeAP(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    await migration_instance.run()
    adapters = fake_config.data['platform-adapters']
    slack_configs = [adapter for adapter in adapters if adapter.get("adapter") == "slack"]
    assert len(slack_configs) == 1, "Expected the existing 'slack' adapter to remain unchanged."
    lark_configs = [adapter for adapter in adapters if adapter.get("adapter") == "lark"]
    assert len(lark_configs) == 1, "Expected exactly one 'lark' adapter configuration to be added."
    assert fake_config.dump_called, "Expected dump_config() to have been called during migration run."
@pytest.mark.asyncio
async def test_run_then_need_migrate_returns_false():
    """
    Test that after executing migration.run(),
    need_migrate() returns False, indicating that the 'lark' adapter configuration is present.
    """
    fake_data = {'platform-adapters': []}
    fake_config = FakePlatformCfg(fake_data)
    fake_ap = FakeAP(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    # Run the migration to add the 'lark' adapter.
    await migration_instance.run()
    # After migration, need_migrate should return False, as the 'lark' adapter now exists.
    result = await migration_instance.need_migrate()
    assert result is False, (
        "Expected need_migrate() to return False after run() is executed, "
        "as the 'lark' adapter configuration has been added."
    )
@pytest.mark.asyncio
async def test_need_migrate_raises_type_error_when_platform_adapters_is_not_list():
    """
    Test that need_migrate() raises a TypeError when the 'platform-adapters' key in the platform
    configuration is not a list. This simulates a misconfigured platform configuration.
    """
    fake_data = {'platform-adapters': "not_a_list"}
    fake_config = FakePlatformCfg(fake_data)
    fake_ap = FakeAP(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    with pytest.raises(TypeError):
        await migration_instance.need_migrate()
@pytest.mark.asyncio
async def test_need_migrate_raises_type_error_when_adapter_not_dict():
    """
    Test that need_migrate() raises a TypeError when one of the platform-adapters
    entries is not a dict (e.g., a string). This simulates a scenario where an adapter 
    entry is malformed.
    """
    fake_data = {'platform-adapters': ["not_a_dict"]}
    fake_config = FakePlatformCfg(fake_data)
    fake_ap = FakeAP(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    with pytest.raises(TypeError):
        await migration_instance.need_migrate()
@pytest.mark.asyncio
async def test_run_raises_key_error_when_platform_adapters_missing():
    """
    Test that run() raises a KeyError when the platform configuration is missing the 'platform-adapters'
    key. This verifies that the migration run() method fails appropriately when the configuration structure
    is malformed.
    """
    fake_data = {}  # 'platform-adapters' key is missing
    fake_config = FakePlatformCfg(fake_data)
    fake_ap = FakeAP(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    with pytest.raises(KeyError):
        await migration_instance.run()
@pytest.mark.asyncio
async def test_run_propagates_exception_from_dump_config():
    """
    Test that the migration run() method propagates exceptions raised by dump_config().
    In this scenario, we simulate a failure in dump_config() and assert that the exception is re-raised.
    """
    # Define a fake platform configuration that raises an exception when dump_config() is called.
    class FakePlatformCfgWithException:
        def __init__(self, data):
            self.data = data
        async def dump_config(self):
            raise Exception("dump fail")
    # Create a fake access point with the above exceptional configuration.
    class FakeAPWithException:
        def __init__(self, platform_cfg):
            self.platform_cfg = platform_cfg
    fake_data = {'platform-adapters': []}
    fake_config = FakePlatformCfgWithException(fake_data)
    fake_ap = FakeAPWithException(fake_config)
    migration_instance = m021_lark_config.LarkConfigMigration()
    migration_instance.ap = fake_ap
    with pytest.raises(Exception, match="dump fail"):
        await migration_instance.run()