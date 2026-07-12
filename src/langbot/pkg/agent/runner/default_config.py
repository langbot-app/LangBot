"""Default AgentRunner binding configuration helpers."""

from __future__ import annotations

import sqlalchemy

from ...core import app
from ...entity.persistence import pipeline as persistence_pipeline
from . import config_schema
from .config_resolver import RunnerConfigResolver


class AgentRunnerDefaultConfigService:
    """Apply AgentRunner schema-defined defaults to host binding config."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def _get_runner_descriptor(self, runner_id: str):
        registry = getattr(self.ap, 'agent_runner_registry', None)
        if registry is None:
            return None
        try:
            return await registry.get(runner_id, bound_plugins=None)
        except Exception as e:
            logger = getattr(self.ap, 'logger', None)
            if logger:
                logger.warning(f'Failed to load AgentRunner descriptor while setting default model: {e}')
            return None

    async def auto_set_default_pipeline_llm_model(self, model_uuid: str) -> bool:
        """Set model_uuid into the default pipeline runner config when the selector is empty."""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.is_default == True
            )
        )
        pipeline = result.first()
        if pipeline is None:
            return False

        return await self.set_pipeline_llm_model_if_empty(pipeline, model_uuid)

    async def set_pipeline_llm_model_if_empty(
        self,
        pipeline: persistence_pipeline.LegacyPipeline,
        model_uuid: str,
    ) -> bool:
        """Set model_uuid into a pipeline's schema-defined LLM selector if it is empty."""
        pipeline_config = pipeline.config
        if not isinstance(pipeline_config, dict):
            return False

        runner_id = RunnerConfigResolver.resolve_runner_id(pipeline_config)
        if not runner_id:
            return False

        descriptor = await self._get_runner_descriptor(runner_id)
        if descriptor is None:
            return False

        ai_config = pipeline_config.setdefault('ai', {})
        runner_configs = ai_config.setdefault('runner_config', {})
        runner_config = runner_configs.setdefault(runner_id, {})

        if not config_schema.set_empty_llm_model_selection(descriptor, runner_config, model_uuid):
            return False

        await self.ap.pipeline_service.update_pipeline(pipeline.uuid, {'config': pipeline_config})
        return True
