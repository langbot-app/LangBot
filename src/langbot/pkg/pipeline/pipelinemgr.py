from __future__ import annotations

import typing
import traceback

import sqlalchemy

from ..core import app
from . import entities as pipeline_entities
from ..entity.persistence import pipeline as persistence_pipeline
from . import stage
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.events as events
from ..utils import importutil

import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from . import (
    resprule,
    bansess,
    cntfilter,
    process,
    longtext,
    respback,
    wrapper,
    preproc,
    ratelimit,
    msgtrun,
)

importutil.import_modules_in_pkgs(
    [
        resprule,
        bansess,
        cntfilter,
        process,
        longtext,
        respback,
        wrapper,
        preproc,
        ratelimit,
        msgtrun,
    ]
)


class StageInstContainer:
    """阶段实例容器"""

    inst_name: str

    inst: stage.PipelineStage

    def __init__(self, inst_name: str, inst: stage.PipelineStage):
        self.inst_name = inst_name
        self.inst = inst


class RuntimePipeline:
    """运行时流水线"""

    ap: app.Application

    pipeline_entity: persistence_pipeline.LegacyPipeline
    """流水线实体"""

    stage_containers: list[StageInstContainer]
    """阶段实例容器"""

    bound_plugins: list[str] | None
    """绑定到此流水线的插件列表（格式：author/plugin_name），None表示启用所有"""

    bound_mcp_servers: list[str] | None
    """绑定到此流水线的MCP服务器列表（格式：uuid），None表示启用所有"""

    enable_all_plugins: bool
    """是否启用所有插件"""

    enable_all_mcp_servers: bool
    """是否启用所有MCP服务器"""

    def __init__(
        self,
        ap: app.Application,
        pipeline_entity: persistence_pipeline.LegacyPipeline,
        stage_containers: list[StageInstContainer],
    ):
        self.ap = ap
        self.pipeline_entity = pipeline_entity
        self.stage_containers = stage_containers

        # Extract bound plugins and MCP servers from extensions_preferences
        extensions_prefs = pipeline_entity.extensions_preferences or {}
        self.enable_all_plugins = extensions_prefs.get('enable_all_plugins', True)
        self.enable_all_mcp_servers = extensions_prefs.get('enable_all_mcp_servers', True)

        if self.enable_all_plugins:
            # None indicates to use all available plugins
            self.bound_plugins = None
        else:
            plugin_list = extensions_prefs.get('plugins', [])
            self.bound_plugins = [f'{p["author"]}/{p["name"]}' for p in plugin_list] if plugin_list else []

        if self.enable_all_mcp_servers:
            # None indicates to use all available MCP servers
            self.bound_mcp_servers = None
        else:
            mcp_server_list = extensions_prefs.get('mcp_servers', [])
            self.bound_mcp_servers = mcp_server_list if mcp_server_list else []

    async def run(self, query: pipeline_query.Query):
        query.pipeline_config = self.pipeline_entity.config
        # Store bound plugins and MCP servers in query for filtering
        query.variables['_pipeline_bound_plugins'] = self.bound_plugins
        query.variables['_pipeline_bound_mcp_servers'] = self.bound_mcp_servers

        # Record query start for monitoring
        try:
            # Get bot name from bot_uuid
            bot_name = 'WebChat'
            if query.bot_uuid:
                try:
                    bot = await self.ap.bot_service.get_bot(query.bot_uuid, include_secret=False)
                    if bot:
                        bot_name = bot.get('name', 'Unknown')
                except Exception:
                    pass

            # Store for later use in process_query
            query.variables['_monitoring_bot_name'] = bot_name
            query.variables['_monitoring_pipeline_name'] = self.pipeline_entity.name
        except Exception as e:
            self.ap.logger.error(f'Failed to prepare monitoring data: {e}')

        await self.process_query(query)

    async def _check_output(self, query: pipeline_query.Query, result: pipeline_entities.StageProcessResult):
        """检查输出"""
        if result.user_notice:
            # 处理str类型

            if isinstance(result.user_notice, str):
                result.user_notice = platform_message.MessageChain([platform_message.Plain(text=result.user_notice)])
            elif isinstance(result.user_notice, list):
                result.user_notice = platform_message.MessageChain(*result.user_notice)

            if query.pipeline_config['output']['misc']['at-sender'] and isinstance(
                query.message_event, platform_events.GroupMessage
            ):
                result.user_notice.insert(0, platform_message.At(target=query.message_event.sender.id))
            if await query.adapter.is_stream_output_supported() and query.resp_messages:
                await query.adapter.reply_message_chunk(
                    message_source=query.message_event,
                    bot_message=query.resp_messages[-1],
                    message=result.user_notice,
                    quote_origin=query.pipeline_config['output']['misc']['quote-origin'],
                    is_final=[msg.is_final for msg in query.resp_messages][0],
                )
            else:
                await query.adapter.reply_message(
                    message_source=query.message_event,
                    message=result.user_notice,
                    quote_origin=query.pipeline_config['output']['misc']['quote-origin'],
                )
        if result.debug_notice:
            self.ap.logger.debug(result.debug_notice)
        if result.console_notice:
            self.ap.logger.info(result.console_notice)
        if result.error_notice:
            self.ap.logger.error(result.error_notice)
            # Mark query as having error
            query.variables['_monitoring_has_error'] = True
            # Record error to monitoring system
            try:
                bot_name = query.variables.get('_monitoring_bot_name', 'Unknown')
                pipeline_name = query.variables.get('_monitoring_pipeline_name', 'Unknown')
                message_id = query.variables.get('_monitoring_message_id', '')
                session_id = f'{query.launcher_type}_{query.launcher_id}'

                # Update message status to error
                if message_id:
                    await self.ap.monitoring_service.update_message_status(
                        message_id=message_id,
                        status='error',
                        level='error',
                    )

                # Record error log
                await self.ap.monitoring_service.record_error(
                    bot_id=query.bot_uuid or 'unknown',
                    bot_name=bot_name,
                    pipeline_id=self.pipeline_entity.uuid,
                    pipeline_name=pipeline_name,
                    error_type='PipelineError',
                    error_message=result.error_notice,
                    session_id=session_id,
                    stack_trace=result.debug_notice if result.debug_notice else None,
                    message_id=message_id,
                )
            except Exception as e:
                self.ap.logger.error(f'Failed to record error to monitoring: {e}')

    async def _execute_from_stage(
        self,
        stage_index: int,
        query: pipeline_query.Query,
    ):
        """从指定阶段开始执行，实现了责任链模式和基于生成器的阶段分叉功能。

        如何看懂这里为什么这么写？
        去问 GPT-4:
            Q1: 现在有一个责任链，其中有多个stage，query对象在其中传递，stage.process可能返回Result也有可能返回typing.AsyncGenerator[Result, None]，
                如果返回的是生成器，需要挨个生成result，检查是否result中是否要求继续，如果要求继续就进行下一个stage。如果此次生成器产生的result处理完了，就继续生成下一个result，
                调用后续的stage，直到该生成器全部生成完。责任链中可能有多个stage会返回生成器
            Q2: 不是这样的，你可能理解有误。如果我们责任链上有这些Stage：

                A B C D E F G

                如果所有的stage都返回Result，且所有Result都要求继续，那么执行顺序是：

                A B C D E F G

                现在假设C返回的是AsyncGenerator，那么执行顺序是：

                A B C D E F G C D E F G C D E F G ...
            Q3: 但是如果不止一个stage会返回生成器呢？
        """
        i = stage_index

        while i < len(self.stage_containers):
            stage_container = self.stage_containers[i]

            query.current_stage_name = stage_container.inst_name  # 标记到 Query 对象里

            result = stage_container.inst.process(query, stage_container.inst_name)

            if isinstance(result, typing.Coroutine):
                result = await result

            if isinstance(result, pipeline_entities.StageProcessResult):  # 直接返回结果
                self.ap.logger.debug(
                    f'Stage {stage_container.inst_name} processed query {query.query_id} res {result.result_type}'
                )
                await self._check_output(query, result)

                if result.result_type == pipeline_entities.ResultType.INTERRUPT:
                    self.ap.logger.debug(f'Stage {stage_container.inst_name} interrupted query {query.query_id}')
                    break
                elif result.result_type == pipeline_entities.ResultType.CONTINUE:
                    query = result.new_query
            elif isinstance(result, typing.AsyncGenerator):  # 生成器
                self.ap.logger.debug(f'Stage {stage_container.inst_name} processed query {query.query_id} gen')

                async for sub_result in result:
                    self.ap.logger.debug(
                        f'Stage {stage_container.inst_name} processed query {query.query_id} res {sub_result.result_type}'
                    )
                    await self._check_output(query, sub_result)

                    if sub_result.result_type == pipeline_entities.ResultType.INTERRUPT:
                        self.ap.logger.debug(f'Stage {stage_container.inst_name} interrupted query {query.query_id}')
                        break
                    elif sub_result.result_type == pipeline_entities.ResultType.CONTINUE:
                        query = sub_result.new_query
                        await self._execute_from_stage(i + 1, query)
                break

            i += 1

    async def process_query(self, query: pipeline_query.Query):
        """处理请求"""
        # Get monitoring metadata
        bot_name = query.variables.get('_monitoring_bot_name', 'Unknown')
        pipeline_name = query.variables.get('_monitoring_pipeline_name', 'Unknown')

        # Get runner name from pipeline config
        runner_name = None
        if query.pipeline_config and 'ai' in query.pipeline_config and 'runner' in query.pipeline_config['ai']:
            runner_name = query.pipeline_config['ai']['runner'].get('runner')

        # Record query start and store message_id
        message_id = ''
        try:
            from . import monitoring_helper

            message_id = await monitoring_helper.MonitoringHelper.record_query_start(
                ap=self.ap,
                query=query,
                bot_id=query.bot_uuid or 'unknown',
                bot_name=bot_name,
                pipeline_id=self.pipeline_entity.uuid,
                pipeline_name=pipeline_name,
                runner_name=runner_name,
            )
            # Store message_id in query variables for LLM call monitoring
            query.variables['_monitoring_message_id'] = message_id
        except Exception as e:
            self.ap.logger.error(f'Failed to record query start: {e}')

        try:
            # Get bound plugins for this pipeline
            bound_plugins = query.variables.get('_pipeline_bound_plugins', None)

            # ======== 触发 MessageReceived 事件 ========
            event_type = (
                events.PersonMessageReceived
                if query.launcher_type == provider_session.LauncherTypes.PERSON
                else events.GroupMessageReceived
            )

            event_obj = event_type(
                query=query,
                launcher_type=query.launcher_type.value,
                launcher_id=query.launcher_id,
                sender_id=query.sender_id,
                message_event=query.message_event,
                message_chain=query.message_chain,
            )

            event_ctx = await self.ap.plugin_connector.emit_event(event_obj, bound_plugins)

            if event_ctx.is_prevented_default():
                return

            self.ap.logger.debug(f'Processing query {query.query_id}')

            await self._execute_from_stage(0, query)

            # Record query success only if no error occurred during processing
            if not query.variables.get('_monitoring_has_error', False):
                try:
                    await monitoring_helper.MonitoringHelper.record_query_success(
                        ap=self.ap,
                        message_id=message_id,
                        query=query,
                    )
                except Exception as e:
                    self.ap.logger.error(f'Failed to record query success: {e}')

        except Exception as e:
            inst_name = query.current_stage_name if query.current_stage_name else 'unknown'
            self.ap.logger.error(f'Error processing query {query.query_id} stage={inst_name} : {e}')
            self.ap.logger.error(f'Traceback: {traceback.format_exc()}')

            # Record query error
            try:
                from . import monitoring_helper

                await monitoring_helper.MonitoringHelper.record_query_error(
                    ap=self.ap,
                    query=query,
                    bot_id=query.bot_uuid or 'unknown',
                    bot_name=bot_name,
                    pipeline_id=self.pipeline_entity.uuid,
                    pipeline_name=pipeline_name,
                    error=e,
                    runner_name=runner_name,
                )
            except Exception as me:
                self.ap.logger.error(f'Failed to record query error: {me}')

        finally:
            self.ap.logger.debug(f'Query {query.query_id} processed')
            del self.ap.query_pool.cached_queries[query.query_id]


class PipelineManager:
    """流水线管理器"""

    # ====== 4.0 ======

    ap: app.Application

    pipelines: list[RuntimePipeline]

    stage_dict: dict[str, type[stage.PipelineStage]]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.pipelines = []

    async def initialize(self):
        self.stage_dict = {name: cls for name, cls in stage.preregistered_stages.items()}

        await self.load_pipelines_from_db()

    async def load_pipelines_from_db(self):
        self.ap.logger.info('Loading pipelines from db...')

        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_pipeline.LegacyPipeline))

        pipelines = result.all()

        # load pipelines
        for pipeline in pipelines:
            await self.load_pipeline(pipeline)

    async def load_pipeline(
        self,
        pipeline_entity: persistence_pipeline.LegacyPipeline
        | sqlalchemy.Row[persistence_pipeline.LegacyPipeline]
        | dict,
    ):
        if isinstance(pipeline_entity, sqlalchemy.Row):
            pipeline_entity = persistence_pipeline.LegacyPipeline(**pipeline_entity._mapping)
        elif isinstance(pipeline_entity, dict):
            pipeline_entity = persistence_pipeline.LegacyPipeline(**pipeline_entity)

        # initialize stage containers according to pipeline_entity.stages
        stage_containers: list[StageInstContainer] = []
        for stage_name in pipeline_entity.stages:
            stage_containers.append(StageInstContainer(inst_name=stage_name, inst=self.stage_dict[stage_name](self.ap)))

        for stage_container in stage_containers:
            await stage_container.inst.initialize(pipeline_entity.config)

        runtime_pipeline = RuntimePipeline(self.ap, pipeline_entity, stage_containers)
        self.pipelines.append(runtime_pipeline)

    async def get_pipeline_by_uuid(self, uuid: str) -> RuntimePipeline | None:
        for pipeline in self.pipelines:
            if pipeline.pipeline_entity.uuid == uuid:
                return pipeline
        return None

    async def remove_pipeline(self, uuid: str):
        for pipeline in self.pipelines:
            if pipeline.pipeline_entity.uuid == uuid:
                self.pipelines.remove(pipeline)
                return
