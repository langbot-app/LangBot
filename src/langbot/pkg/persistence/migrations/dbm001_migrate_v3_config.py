from .. import migration
from copy import deepcopy
import uuid
import os
import sqlalchemy
import shutil

from ...config import manager as config_manager
from ...entity.persistence import (
    model as persistence_model,
    pipeline as persistence_pipeline,
    bot as persistence_bot,
)


@migration.migration_class(1)
class DBMigrateV3Config(migration.DBMigration):
    """Migrate v3 config to v4 database"""

    async def upgrade(self):
        """Upgrade"""
        """
        Migrate all config files under data/config.
        After migration, all previous config files are saved under data/legacy/config.
        After migration, all config files under data/metadata/ are saved under data/legacy/metadata.
        """

        if self.ap.provider_cfg is None:
            return

        # ======= Migrate model =======
        # Only migrate the currently selected model
        model_name = self.ap.provider_cfg.data.get('model', 'gpt-4o')

        model_requester = 'openai-chat-completions'
        model_requester_config = {}
        model_api_keys = ['sk-proj-1234567890']
        model_abilities = []
        model_extra_args = {}

        if os.path.exists('data/metadata/llm-models.json'):
            _llm_model_meta = await config_manager.load_json_config('data/metadata/llm-models.json', completion=False)

            for item in _llm_model_meta.data.get('list', []):
                if item.get('name') == model_name:
                    if 'model_name' in item:
                        model_name = item['model_name']
                    if 'requester' in item:
                        model_requester = item['requester']
                    if 'token_mgr' in item:
                        _token_mgr = item['token_mgr']

                        if _token_mgr in self.ap.provider_cfg.data.get('keys', {}):
                            model_api_keys = self.ap.provider_cfg.data.get('keys', {})[_token_mgr]

                    if 'tool_call_supported' in item and item['tool_call_supported']:
                        model_abilities.append('func_call')

                    if 'vision_supported' in item and item['vision_supported']:
                        model_abilities.append('vision')

                    if (
                        model_requester in self.ap.provider_cfg.data.get('requester', {})
                        and 'args' in self.ap.provider_cfg.data.get('requester', {})[model_requester]
                    ):
                        model_extra_args = self.ap.provider_cfg.data.get('requester', {})[model_requester]['args']

                    if model_requester in self.ap.provider_cfg.data.get('requester', {}):
                        model_requester_config = self.ap.provider_cfg.data.get('requester', {})[model_requester]
                        model_requester_config = {
                            'base_url': model_requester_config['base-url'],
                            'timeout': model_requester_config['timeout'],
                        }

                    break

        model_uuid = str(uuid.uuid4())

        llm_model_data = {
            'uuid': model_uuid,
            'name': model_name,
            'description': '由 LangBot v3 迁移而来',
            'requester': model_requester,
            'requester_config': model_requester_config,
            'api_keys': model_api_keys,
            'abilities': model_abilities,
            'extra_args': model_extra_args,
        }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_model.LLMModel).values(**llm_model_data)
        )

        # ======= Migrate pipeline config =======
        # Modify to default pipeline
        default_pipeline = [
            self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)
            for pipeline in (
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                        persistence_pipeline.LegacyPipeline.is_default == True
                    )
                )
            ).all()
        ][0]

        pipeline_uuid = str(uuid.uuid4())
        pipeline_name = 'ChatPipeline'

        if default_pipeline:
            pipeline_name = default_pipeline['name']
            pipeline_uuid = default_pipeline['uuid']

            pipeline_config = default_pipeline['config']

            # ai
            pipeline_config['ai']['runner'] = {
                'runner': self.ap.provider_cfg.data['runner'],
            }
            pipeline_config['ai']['local-agent']['model'] = model_uuid
            pipeline_config['ai']['local-agent']['max-round'] = self.ap.pipeline_cfg.data['msg-truncate']['round'][
                'max-round'
            ]

            pipeline_config['ai']['local-agent']['prompt'] = [
                {
                    'role': 'system',
                    'content': self.ap.provider_cfg.data['prompt']['default'],
                }
            ]
            pipeline_config['ai']['dify-service-api'] = {
                'base-url': self.ap.provider_cfg.data['dify-service-api']['base-url'],
                'app-type': self.ap.provider_cfg.data['dify-service-api']['app-type'],
                'api-key': self.ap.provider_cfg.data['dify-service-api'][
                    self.ap.provider_cfg.data['dify-service-api']['app-type']
                ]['api-key'],
                'thinking-convert': self.ap.provider_cfg.data['dify-service-api']['options']['convert-thinking-tips'],
                'timeout': self.ap.provider_cfg.data['dify-service-api'][
                    self.ap.provider_cfg.data['dify-service-api']['app-type']
                ]['timeout'],
            }
            pipeline_config['ai']['dashscope-app-api'] = {
                'app-type': self.ap.provider_cfg.data['dashscope-app-api']['app-type'],
                'api-key': self.ap.provider_cfg.data['dashscope-app-api']['api-key'],
                'references_quote': self.ap.provider_cfg.data['dashscope-app-api'][
                    self.ap.provider_cfg.data['dashscope-app-api']['app-type']
                ]['references_quote'],
            }

            # trigger
            pipeline_config['trigger']['group-respond-rules'] = self.ap.pipeline_cfg.data['respond-rules']['default']
            pipeline_config['trigger']['access-control'] = self.ap.pipeline_cfg.data['access-control']
            pipeline_config['trigger']['ignore-rules'] = self.ap.pipeline_cfg.data['ignore-rules']

            # safety
            pipeline_config['safety']['content-filter'] = {
                'scope': 'all',
                'check-sensitive-words': self.ap.pipeline_cfg.data['check-sensitive-words'],
            }
            pipeline_config['safety']['rate-limit'] = {
                'window-length': self.ap.pipeline_cfg.data['rate-limit']['fixwin']['default']['window-size'],
                'limitation': self.ap.pipeline_cfg.data['rate-limit']['fixwin']['default']['limit'],
                'strategy': self.ap.pipeline_cfg.data['rate-limit']['strategy'],
            }

            # output
            pipeline_config['output']['long-text-processing'] = self.ap.platform_cfg.data['long-text-process']
            pipeline_config['output']['force-delay'] = self.ap.platform_cfg.data['force-delay']
            pipeline_config['output']['misc'] = {
                'hide-exception': self.ap.platform_cfg.data['hide-exception-info'],
                'quote-origin': self.ap.platform_cfg.data['quote-origin'],
                'at-sender': self.ap.platform_cfg.data['at-sender'],
                'track-function-calls': self.ap.platform_cfg.data['track-function-calls'],
            }

            default_pipeline['description'] = default_pipeline['description'] + ' [已迁移 LangBot v3 配置]'
            default_pipeline['config'] = pipeline_config
            default_pipeline.pop('created_at')
            default_pipeline.pop('updated_at')

            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .values(default_pipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == default_pipeline['uuid'])
            )

        # ======= Migrate bot =======
        # Only migrate enabled bots
        for adapter in self.ap.platform_cfg.data.get('platform-adapters', []):
            if not adapter.get('enable'):
                continue

            args = deepcopy(adapter)
            args.pop('adapter')
            args.pop('enable')

            bot_data = {
                'uuid': str(uuid.uuid4()),
                'name': adapter.get('adapter'),
                'description': '由 LangBot v3 迁移而来',
                'adapter': adapter.get('adapter'),
                'adapter_config': args,
                'enable': True,
                'use_pipeline_uuid': pipeline_uuid,
                'use_pipeline_name': pipeline_name,
            }

            await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_bot.Bot).values(**bot_data))

        # ======= Migrate system settings =======
        self.ap.instance_config.data['admins'] = self.ap.system_cfg.data['admin-sessions']
        self.ap.instance_config.data['api']['port'] = self.ap.system_cfg.data['http-api']['port']
        self.ap.instance_config.data['command'] = {
            'prefix': self.ap.command_cfg.data['command-prefix'],
            'enable': self.ap.command_cfg.data['command-enable']
            if 'command-enable' in self.ap.command_cfg.data
            else True,
            'privilege': self.ap.command_cfg.data['privilege'],
        }
        self.ap.instance_config.data['concurrency']['pipeline'] = self.ap.system_cfg.data['pipeline-concurrency']
        self.ap.instance_config.data['concurrency']['session'] = self.ap.system_cfg.data['session-concurrency'][
            'default'
        ]
        self.ap.instance_config.data['mcp'] = self.ap.provider_cfg.data['mcp']
        self.ap.instance_config.data['proxy'] = self.ap.system_cfg.data['network-proxies']
        await self.ap.instance_config.dump_config()

        # ======= move files =======
        # Migrate all config files under data/config
        all_legacy_dir_name = [
            'config',
            # 'metadata',
            'prompts',
            'scenario',
        ]

        def move_legacy_files(dir_name: str):
            if not os.path.exists(f'data/legacy/{dir_name}'):
                os.makedirs(f'data/legacy/{dir_name}')

            if os.path.exists(f'data/{dir_name}'):
                for file in os.listdir(f'data/{dir_name}'):
                    if file.endswith('.json'):
                        shutil.move(f'data/{dir_name}/{file}', f'data/legacy/{dir_name}/{file}')

                os.rmdir(f'data/{dir_name}')

        for dir_name in all_legacy_dir_name:
            move_legacy_files(dir_name)

    async def downgrade(self):
        """Downgrade"""
