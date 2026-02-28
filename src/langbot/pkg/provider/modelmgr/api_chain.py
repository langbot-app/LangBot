"""API Chain Manager - handles API failover and health checking.

chain_config item schema (per provider entry):
{
    "provider_uuid": "xxx",
    "priority": 1,              # provider priority in the chain (lower = higher priority)
    "is_aggregated": false,
    "max_retries": 3,
    "timeout_ms": 30000,
    "model_configs": [          # optional: per-model configuration
        {
            "model_name": "gpt-4o",   # model name as stored in LLMModel.name
            "priority": 1,             # priority within this provider
            "api_key_indices": [        # optional: per-API-key priority
                {"index": 0, "priority": 1},
                {"index": 1, "priority": 2}
            ]
        }
    ]
}
If model_configs is absent, the original query model is used with round-robin keys.
If api_key_indices is absent for a model config, round-robin rotation is used.
"""
from __future__ import annotations

import asyncio
import uuid as uuid_lib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator

import sqlalchemy
from ...core import app
from ...entity.persistence import api_chain as api_chain_entity
from . import requester
from . import token

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool


class APIChainManager:
    """Manages API chains with per-model/per-API-key failover and health checking"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.chains: Dict[str, api_chain_entity.APIChain] = {}
        self.health_check_tasks: Dict[str, asyncio.Task] = {}

    async def initialize(self):
        """Initialize API chain manager"""
        await self.load_chains_from_db()
        await self.start_health_check_tasks()

    async def load_chains_from_db(self):
        """Load all API chains from database"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(api_chain_entity.APIChain)
        )
        for chain in result.all():
            self.chains[chain.uuid] = chain

    async def start_health_check_tasks(self):
        """Start background health check tasks for all chains"""
        for chain_uuid, chain in self.chains.items():
            if chain.health_check_enabled:
                task = asyncio.create_task(self._health_check_loop(chain_uuid))
                self.health_check_tasks[chain_uuid] = task

    async def stop_health_check_tasks(self):
        """Stop all health check tasks"""
        for task in self.health_check_tasks.values():
            task.cancel()
        self.health_check_tasks.clear()

    # ==================== Health Check ====================

    async def _health_check_loop(self, chain_uuid: str):
        """Background loop for health checking failed APIs"""
        while True:
            try:
                chain = self.chains.get(chain_uuid)
                if not chain or not chain.health_check_enabled:
                    break
                await asyncio.sleep(chain.health_check_interval)
                await self._perform_health_checks(chain_uuid)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.ap.logger.error(f"Health check loop error for chain {chain_uuid}: {e}")
                await asyncio.sleep(60)

    async def _perform_health_checks(self, chain_uuid: str):
        """Perform health checks on all unhealthy status records in a chain"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(api_chain_entity.APIChainStatus).where(
                sqlalchemy.and_(
                    api_chain_entity.APIChainStatus.chain_uuid == chain_uuid,
                    api_chain_entity.APIChainStatus.is_healthy == False,
                )
            )
        )
        for status in result.all():
            try:
                provider = self.ap.model_mgr.provider_dict.get(status.provider_uuid)
                if not provider:
                    continue

                is_healthy = await self._check_api_health(provider, status.api_key_index)

                if is_healthy:
                    await self._update_status(
                        status.uuid,
                        is_healthy=True,
                        failure_count=0,
                        last_success_time=datetime.now(),
                        last_health_check_time=datetime.now(),
                        last_error_message=None,
                    )
                    self.ap.logger.info(
                        f"API recovered: provider={status.provider_uuid} "
                        f"model={status.model_name} key_index={status.api_key_index}"
                    )
                else:
                    await self._update_status(
                        status.uuid,
                        last_health_check_time=datetime.now(),
                    )
            except Exception as e:
                self.ap.logger.error(
                    f"Health check failed for provider={status.provider_uuid} "
                    f"model={status.model_name} key_index={status.api_key_index}: {e}"
                )

    async def _check_api_health(
        self,
        provider: requester.RuntimeProvider,
        api_key_index: Optional[int],
    ) -> bool:
        """Check health by verifying the API key exists and is non-empty"""
        try:
            tokens = provider.token_mgr.tokens
            if not tokens:
                return False
            if api_key_index is not None:
                if api_key_index >= len(tokens):
                    return False
                return bool(tokens[api_key_index])
            return True
        except Exception:
            return False

    # ==================== Status Helpers ====================

    async def _ensure_status(
        self,
        chain_uuid: str,
        provider_uuid: str,
        model_name: Optional[str],
        api_key_index: Optional[int],
    ) -> api_chain_entity.APIChainStatus:
        """Get or create a status record for the given (chain, provider, model, key) tuple"""
        conditions = [
            api_chain_entity.APIChainStatus.chain_uuid == chain_uuid,
            api_chain_entity.APIChainStatus.provider_uuid == provider_uuid,
        ]
        if model_name is None:
            conditions.append(api_chain_entity.APIChainStatus.model_name == None)
        else:
            conditions.append(api_chain_entity.APIChainStatus.model_name == model_name)

        if api_key_index is None:
            conditions.append(api_chain_entity.APIChainStatus.api_key_index == None)
        else:
            conditions.append(api_chain_entity.APIChainStatus.api_key_index == api_key_index)

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(api_chain_entity.APIChainStatus).where(
                sqlalchemy.and_(*conditions)
            )
        )
        existing = result.first()
        if existing:
            return existing

        new_uuid = str(uuid_lib.uuid4())
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(api_chain_entity.APIChainStatus).values(
                uuid=new_uuid,
                chain_uuid=chain_uuid,
                provider_uuid=provider_uuid,
                model_name=model_name,
                api_key_index=api_key_index,
                is_healthy=True,
                failure_count=0,
            )
        )
        result2 = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(api_chain_entity.APIChainStatus).where(
                api_chain_entity.APIChainStatus.uuid == new_uuid
            )
        )
        return result2.first()

    async def _update_status(
        self,
        status_uuid: str,
        is_healthy: Optional[bool] = None,
        failure_count: Optional[int] = None,
        last_failure_time: Optional[datetime] = None,
        last_success_time: Optional[datetime] = None,
        last_health_check_time: Optional[datetime] = None,
        last_error_message: Optional[str] = None,
    ):
        """Update a status record by UUID"""
        update_data: Dict[str, Any] = {}
        if is_healthy is not None:
            update_data['is_healthy'] = is_healthy
        if failure_count is not None:
            update_data['failure_count'] = failure_count
        if last_failure_time is not None:
            update_data['last_failure_time'] = last_failure_time
        if last_success_time is not None:
            update_data['last_success_time'] = last_success_time
        if last_health_check_time is not None:
            update_data['last_health_check_time'] = last_health_check_time
        if last_error_message is not None:
            update_data['last_error_message'] = last_error_message
        elif is_healthy:
            # Clear error message when marking healthy
            update_data['last_error_message'] = None

        if update_data:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(api_chain_entity.APIChainStatus)
                .where(api_chain_entity.APIChainStatus.uuid == status_uuid)
                .values(**update_data)
            )

    # ==================== Chain CRUD ====================

    async def get_chain(self, chain_uuid: str) -> Optional[api_chain_entity.APIChain]:
        """Get an API chain by UUID"""
        return self.chains.get(chain_uuid)

    async def create_chain(self, chain_data: Dict[str, Any]) -> str:
        """Create a new API chain"""
        chain_uuid = chain_data.get('uuid', str(uuid_lib.uuid4()))

        chain = api_chain_entity.APIChain(
            uuid=chain_uuid,
            name=chain_data['name'],
            description=chain_data.get('description', ''),
            chain_config=chain_data.get('chain_config', []),
            health_check_interval=chain_data.get('health_check_interval', 300),
            health_check_enabled=chain_data.get('health_check_enabled', True),
        )

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(api_chain_entity.APIChain).values(**chain.__dict__)
        )
        self.chains[chain_uuid] = chain

        if chain.health_check_enabled:
            task = asyncio.create_task(self._health_check_loop(chain_uuid))
            self.health_check_tasks[chain_uuid] = task

        return chain_uuid

    async def update_chain(self, chain_uuid: str, chain_data: Dict[str, Any]):
        """Update an existing API chain"""
        chain = self.chains.get(chain_uuid)
        if not chain:
            raise ValueError(f"Chain {chain_uuid} not found")

        for key, value in chain_data.items():
            if hasattr(chain, key) and key != 'uuid':
                setattr(chain, key, value)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(api_chain_entity.APIChain)
            .where(api_chain_entity.APIChain.uuid == chain_uuid)
            .values(**{k: v for k, v in chain_data.items() if k != 'uuid'})
        )

        if chain.health_check_enabled and chain_uuid not in self.health_check_tasks:
            task = asyncio.create_task(self._health_check_loop(chain_uuid))
            self.health_check_tasks[chain_uuid] = task
        elif not chain.health_check_enabled and chain_uuid in self.health_check_tasks:
            self.health_check_tasks[chain_uuid].cancel()
            del self.health_check_tasks[chain_uuid]

    async def delete_chain(self, chain_uuid: str):
        """Delete an API chain"""
        if chain_uuid in self.health_check_tasks:
            self.health_check_tasks[chain_uuid].cancel()
            del self.health_check_tasks[chain_uuid]

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(api_chain_entity.APIChain).where(
                api_chain_entity.APIChain.uuid == chain_uuid
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(api_chain_entity.APIChainStatus).where(
                api_chain_entity.APIChainStatus.chain_uuid == chain_uuid
            )
        )
        self.chains.pop(chain_uuid, None)

    # ==================== Invoke Helpers ====================

    def _build_invoke_tasks(
        self,
        model_configs: List[Dict[str, Any]],
    ) -> List[Tuple[Optional[str], Optional[int]]]:
        """Build an ordered list of (model_name, api_key_index) tuples to try.

        Returns [(None, None)] when model_configs is empty, meaning the caller's
        original model and round-robin key rotation will be used (legacy behaviour).
        """
        if not model_configs:
            return [(None, None)]

        tasks: List[Tuple[Optional[str], Optional[int]]] = []
        sorted_models = sorted(model_configs, key=lambda x: x.get('priority', 0))
        for mc in sorted_models:
            model_name: Optional[str] = mc.get('model_name') or None
            tasks.append((model_name, None))
        return tasks if tasks else [(None, None)]

    def _create_provider_for_key(
        self,
        provider: requester.RuntimeProvider,
        api_key_index: Optional[int],
    ) -> requester.RuntimeProvider:
        """Return a provider restricted to a single API key.

        Creates a lightweight wrapper with a single-token TokenManager so that
        shared mutable state on the original provider is not modified.
        Returns the original provider unchanged when api_key_index is None.
        """
        if api_key_index is None:
            return provider

        tokens = provider.token_mgr.tokens
        if not tokens or api_key_index >= len(tokens):
            return provider  # index out of range 鈥?fall back gracefully

        single_token_mgr = token.TokenManager(
            name=provider.token_mgr.name,
            tokens=[tokens[api_key_index]],
        )
        return requester.RuntimeProvider(
            provider_entity=provider.provider_entity,
            token_mgr=single_token_mgr,
            requester=provider.requester,
        )

    def _resolve_model_entity(
        self,
        provider: requester.RuntimeProvider,
        default_model: Optional[requester.RuntimeLLMModel],
        model_name: Optional[str],
    ) -> Any:
        """Return the model entity for model_name under the given provider.

        Falls back to default_model.model_entity when model_name is None or no
        matching model is found. When default_model is also None, falls back to
        the first available model for the provider.
        """
        if not model_name:
            if default_model is not None:
                return default_model.model_entity
            for m in self.ap.model_mgr.llm_models:
                if m.model_entity.provider_uuid == provider.provider_entity.uuid:
                    return m.model_entity
            return None

        for m in self.ap.model_mgr.llm_models:
            if (
                m.model_entity.provider_uuid == provider.provider_entity.uuid
                and m.model_entity.name == model_name
            ):
                return m.model_entity

        if default_model is not None:
            return default_model.model_entity
        for m in self.ap.model_mgr.llm_models:
            if m.model_entity.provider_uuid == provider.provider_entity.uuid:
                return m.model_entity
        return None

    # ==================== LLM Invocation ====================

    async def invoke_chain_llm(
        self,
        chain_uuid: str,
        query: pipeline_query.Query,
        model: Optional[requester.RuntimeLLMModel],
        messages: List[provider_message.Message],
        funcs: Optional[List[resource_tool.LLMTool]] = None,
        extra_args: Dict[str, Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message:
        """Invoke LLM through API chain with per-model/per-API-key failover"""
        chain = self.chains.get(chain_uuid)
        if not chain:
            raise ValueError(f"Chain {chain_uuid} not found")

        sorted_items = sorted(chain.chain_config, key=lambda x: x.get('priority', 0))
        last_error: Optional[Exception] = None

        for item in sorted_items:
            provider_uuid: str = item['provider_uuid']
            is_aggregated: bool = item.get('is_aggregated', False)
            max_retries: int = item.get('max_retries', 3)
            model_configs: List[Dict] = item.get('model_configs') or []

            provider = self.ap.model_mgr.provider_dict.get(provider_uuid)
            if not provider:
                self.ap.logger.warning(f"Provider {provider_uuid} not found in chain {chain_uuid}")
                continue

            tasks = self._build_invoke_tasks(model_configs)

            for task_model_name, task_api_key_index in tasks:
                status = await self._ensure_status(
                    chain_uuid, provider_uuid, task_model_name, task_api_key_index
                )

                if status and not status.is_healthy and not is_aggregated:
                    self.ap.logger.debug(
                        f"Skipping unhealthy: provider={provider_uuid} "
                        f"model={task_model_name} key={task_api_key_index}"
                    )
                    continue

                temp_provider = self._create_provider_for_key(provider, task_api_key_index)
                model_entity = self._resolve_model_entity(provider, model, task_model_name)
                if model_entity is None:
                    self.ap.logger.warning(
                        f"No model found for provider {provider_uuid} in chain {chain_uuid}, skipping"
                    )
                    continue
                temp_model = requester.RuntimeLLMModel(
                    model_entity=model_entity,
                    provider=temp_provider,
                )

                retry_count = 0 if is_aggregated else max_retries

                for attempt in range(max(1, retry_count + 1)):
                    try:
                        result = await temp_provider.invoke_llm(
                            query=query,
                            model=temp_model,
                            messages=messages,
                            funcs=funcs,
                            extra_args=extra_args,
                            remove_think=remove_think,
                        )

                        if status:
                            await self._update_status(
                                status.uuid,
                                is_healthy=True,
                                failure_count=0,
                                last_success_time=datetime.now(),
                            )
                        return result

                    except Exception as e:
                        last_error = e
                        self.ap.logger.warning(
                            f"Chain {chain_uuid} provider={provider_uuid} "
                            f"model={task_model_name} key={task_api_key_index} "
                            f"attempt {attempt + 1} failed: {e}"
                        )
                        if not is_aggregated:
                            if status:
                                await self._update_status(
                                    status.uuid,
                                    is_healthy=False,
                                    failure_count=(status.failure_count or 0) + 1,
                                    last_failure_time=datetime.now(),
                                    last_error_message=str(e)[:1024],
                                )
                            break  # Move to next (model_name, key_index) task

        error_msg = f"All providers in chain {chain_uuid} failed"
        if last_error:
            error_msg += f": {last_error}"
        raise Exception(error_msg)

    async def invoke_chain_llm_stream(
        self,
        chain_uuid: str,
        query: pipeline_query.Query,
        model: Optional[requester.RuntimeLLMModel],
        messages: List[provider_message.Message],
        funcs: Optional[List[resource_tool.LLMTool]] = None,
        extra_args: Dict[str, Any] = {},
        remove_think: bool = False,
    ) -> AsyncGenerator[provider_message.MessageChunk, None]:
        """Invoke LLM stream through API chain with per-model/per-API-key failover"""
        chain = self.chains.get(chain_uuid)
        if not chain:
            raise ValueError(f"Chain {chain_uuid} not found")

        sorted_items = sorted(chain.chain_config, key=lambda x: x.get('priority', 0))
        last_error: Optional[Exception] = None

        for item in sorted_items:
            provider_uuid: str = item['provider_uuid']
            is_aggregated: bool = item.get('is_aggregated', False)
            model_configs: List[Dict] = item.get('model_configs') or []

            provider = self.ap.model_mgr.provider_dict.get(provider_uuid)
            if not provider:
                self.ap.logger.warning(f"Provider {provider_uuid} not found in chain {chain_uuid}")
                continue

            tasks = self._build_invoke_tasks(model_configs)

            for task_model_name, task_api_key_index in tasks:
                status = await self._ensure_status(
                    chain_uuid, provider_uuid, task_model_name, task_api_key_index
                )

                if status and not status.is_healthy and not is_aggregated:
                    self.ap.logger.debug(
                        f"Skipping unhealthy: provider={provider_uuid} "
                        f"model={task_model_name} key={task_api_key_index}"
                    )
                    continue

                temp_provider = self._create_provider_for_key(provider, task_api_key_index)
                model_entity = self._resolve_model_entity(provider, model, task_model_name)
                if model_entity is None:
                    self.ap.logger.warning(
                        f"No model found for provider {provider_uuid} in chain {chain_uuid}, skipping"
                    )
                    continue
                temp_model = requester.RuntimeLLMModel(
                    model_entity=model_entity,
                    provider=temp_provider,
                )

                try:
                    async for chunk in temp_provider.invoke_llm_stream(
                        query=query,
                        model=temp_model,
                        messages=messages,
                        funcs=funcs,
                        extra_args=extra_args,
                        remove_think=remove_think,
                    ):
                        yield chunk

                    if status:
                        await self._update_status(
                            status.uuid,
                            is_healthy=True,
                            failure_count=0,
                            last_success_time=datetime.now(),
                        )
                    return

                except Exception as e:
                    last_error = e
                    self.ap.logger.warning(
                        f"Chain {chain_uuid} provider={provider_uuid} "
                        f"model={task_model_name} key={task_api_key_index} stream failed: {e}"
                    )
                    if status and not is_aggregated:
                        await self._update_status(
                            status.uuid,
                            is_healthy=False,
                            failure_count=(status.failure_count or 0) + 1,
                            last_failure_time=datetime.now(),
                            last_error_message=str(e)[:1024],
                        )
                    continue  # Try next (model_name, key_index) task

        error_msg = f"All providers in chain {chain_uuid} failed"
        if last_error:
            error_msg += f": {last_error}"
        raise Exception(error_msg)
