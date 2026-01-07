from .. import migration


@migration.migration_class(17)
class MoveCloudServiceUrl(migration.DBMigration):
    """迁移云服务 URL 配置"""

    async def upgrade(self):
        """升级"""
        if 'space' not in self.ap.instance_config.data:
            self.ap.instance_config.data['space'] = {
                'url': 'https://space.langbot.app',
                'models_gateway_api_url': 'https://api.langbot.cloud/v1',
                'oauth_authorize_url': 'https://space.langbot.app/auth/authorize',
                'disable_models_service': False,
            }

        if 'plugin' in self.ap.instance_config.data:
            self.ap.instance_config.data['plugin'].pop('cloud_service_url', None)

        await self.ap.instance_config.dump_config()

    async def downgrade(self):
        """降级"""
        pass
