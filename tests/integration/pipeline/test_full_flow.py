"""
Pipeline full-flow integration tests.

Tests real pipeline stages with fake runner/provider.
Validates RuntimePipeline dispatch through PreProcessor, Processor, ResponseWrapper,
and SendResponseBackStage, with external services replaced by deterministic doubles.

Uses RuntimePipeline directly (not PipelineManager) to avoid DB dependency.

Run: uv run pytest tests/integration/pipeline -q --tb=short
"""

from __future__ import annotations

import pytest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from tests.factories import FakeApp, text_query, mock_platform_adapter
from tests.factories.provider import FakeProvider
from tests.factories.platform import FakePlatform


pytestmark = pytest.mark.integration


# ============== NORMAL APPLICATION IMPORT BOOTSTRAP ==============


@pytest.fixture(scope='module')
def load_pipeline_modules():
    """Initialize the real import graph before importing individual stages.

    This matches normal startup and the pipeline unit-test bootstrap. No
    sys.modules/package attributes are replaced, so later tests keep real
    module identities and the complete stage registry.
    """
    from importlib import import_module

    import_module('langbot.pkg.pipeline.pipelinemgr')


# ============== FAKE RUNNER ==============


class FakeRunner:
    """Minimal fake runner class for pipeline integration tests.

    The test orchestrator instantiates this class for each configured run.
    """

    name = 'local-agent'

    def __init__(self, app=None, config=None):
        self.app = app
        self.config = config or {}
        self._provider = FakeProvider()
        # Instance-level configuration set via class attribute
        self._response_text = 'fake response'
        self._raise_error = None

    @classmethod
    def returns(cls, text: str):
        """Create a runner class configured to return specific text."""

        # We create a subclass with configured response
        class ConfiguredRunner(cls):
            name = cls.name
            _response_text = text
            _raise_error = None

            def __init__(self, app=None, config=None):
                super().__init__(app, config)
                self._response_text = text

        return ConfiguredRunner

    @classmethod
    def raises(cls, error: Exception):
        """Create a runner class configured to raise an error."""

        class ConfiguredRunner(cls):
            name = cls.name
            _response_text = None
            _raise_error = error

            def __init__(self, app=None, config=None):
                super().__init__(app, config)
                self._raise_error = error

        return ConfiguredRunner

    async def run(self, query):
        """Run the fake provider and yield messages."""
        from langbot_plugin.api.entities.builtin.provider.message import Message

        # Use the configured response/error
        if self._raise_error:
            raise self._raise_error

        # Yield a simple message
        yield Message(role='assistant', content=self._response_text)


# ============== PIPELINE APP FIXTURE ==============


@pytest.fixture
def pipeline_app():
    """
    Create FakeApp with all dependencies required by pipeline stages.

    PreProcessor needs: sess_mgr, model_mgr, tool_mgr, plugin_connector
    Processor needs: instance_config, plugin_connector
    SendResponseBackStage needs: logger
    ChatMessageHandler needs: telemetry, survey
    """
    app = FakeApp()

    # Real SDK entities keep plugin event validation meaningful.
    from langbot_plugin.api.entities.builtin.provider.session import Conversation, Session, LauncherTypes
    from langbot_plugin.api.entities.builtin.provider.prompt import Prompt

    mock_session = Session(launcher_type=LauncherTypes.PERSON, launcher_id=12345, sender_id=12345)
    mock_conversation = Conversation(
        prompt=Prompt(name='default', messages=[]),
        messages=[],
        pipeline_uuid='test-pipeline-uuid',
        bot_uuid='test-bot-uuid',
        uuid='test-conversation-uuid',
    )

    async def get_scoped_session(query):
        context = query._execution_context
        mock_session.instance_uuid = context.instance_uuid
        mock_session.workspace_uuid = context.workspace_uuid
        mock_session.placement_generation = context.placement_generation
        mock_session.bot_uuid = query.bot_uuid
        return mock_session

    app.sess_mgr.get_session = AsyncMock(side_effect=get_scoped_session)
    app.sess_mgr.get_conversation = AsyncMock(return_value=mock_conversation)

    # Model mock for PreProcessor
    mock_model = Mock()
    mock_model.model_entity = Mock()
    mock_model.model_entity.uuid = 'test-model-uuid'
    mock_model.model_entity.name = 'test-model'
    mock_model.model_entity.abilities = ['func_call', 'vision']
    app.model_mgr.get_model_by_uuid = AsyncMock(return_value=mock_model)

    # Tool manager mock
    app.tool_mgr.get_all_tools = AsyncMock(return_value=[])
    app.tool_mgr.get_resolved_tool_catalog = AsyncMock(return_value=[])
    app.workspace_service = AsyncMock()
    app.workspace_service.get_execution_binding.return_value = SimpleNamespace(
        instance_uuid='test-instance',
        workspace_uuid='test-workspace',
        placement_generation=1,
    )
    app.query_pool.remove_query = AsyncMock(return_value=True)
    app.bot_service = AsyncMock()
    app.bot_service.get_bot.return_value = {'name': 'Test bot'}
    app.monitoring_service = AsyncMock()
    app.monitoring_service.record_message.return_value = 'test-monitoring-message'

    # Telemetry mock (required by ChatMessageHandler)
    app.telemetry = Mock()
    app.telemetry.start_send_task = AsyncMock()

    # Survey mock
    app.survey = None

    return app


@pytest.fixture
def fake_platform_adapter():
    """Create a fake platform adapter for outbound capture."""
    platform = FakePlatform(stream_output_supported=False)
    adapter = mock_platform_adapter(platform)
    return adapter, platform


@pytest.fixture
def set_fake_runner(pipeline_app):
    """Attach a minimal AgentRunOrchestrator-compatible test double."""

    def _set_runner(runner_cls):
        runner = runner_cls()
        orchestrator = Mock()
        orchestrator.try_claim_steering_from_query = AsyncMock(return_value=False)

        orchestrator.observed_queries = []

        async def run_from_query(query):
            orchestrator.observed_queries.append(query)
            async for result in runner.run(query):
                yield result

        orchestrator.run_from_query = run_from_query
        orchestrator.resolve_runner_id_for_telemetry = Mock(return_value='plugin:langbot-team/LocalAgent/default')
        pipeline_app.agent_run_orchestrator = orchestrator

    return _set_runner


# ============== PIPELINE CONFIGURATION ==============


def create_minimal_pipeline_config():
    """Create minimal pipeline configuration for tests."""
    return {
        'ai': {
            'runner': {'id': 'plugin:langbot-team/LocalAgent/default', 'expire-time': 0},
            'runner_config': {
                'plugin:langbot-team/LocalAgent/default': {
                    'model': {'primary': 'test-model-uuid', 'fallbacks': []},
                    'prompt': 'default',
                    'knowledge-bases': [],
                },
            },
        },
        'output': {
            'force-delay': {'min': 0.0, 'max': 0.0},
            'misc': {
                'at-sender': False,
                'quote-origin': False,
                'track-function-calls': False,
                'exception-handling': 'show-hint',
                'failure-hint': 'Request failed.',
            },
        },
        'trigger': {
            'misc': {'combine-quote-message': False},
        },
    }


# ============== HELPER TO PROCESS COROUTINE/GENERATOR ==============


async def collect_processor_results(processor, query, stage_name):
    """
    Helper to handle the coroutine -> async_generator pattern.

    Processor.process() returns a coroutine that yields an async_generator.
    This helper handles both cases like RuntimePipeline does.
    """
    result = processor.process(query, stage_name)

    # Handle coroutine (await it to get async_generator)
    if asyncio.iscoroutine(result):
        result = await result

    # Now iterate over async_generator
    results = []
    async for item in result:
        results.append(item)

    return results


# ============== TESTS ==============


@pytest.mark.usefixtures('load_pipeline_modules')
class TestPipelineStageChainReal:
    """Tests for real pipeline stage chain."""

    @pytest.mark.asyncio
    async def test_import_pipeline_modules(self):
        """Verify we can import real pipeline modules."""
        from langbot.pkg.pipeline import stage, entities
        from langbot.pkg.pipeline import pipelinemgr

        assert hasattr(stage, 'PipelineStage')
        assert hasattr(stage, 'preregistered_stages')
        assert hasattr(entities, 'ResultType')
        assert hasattr(entities, 'StageProcessResult')
        assert hasattr(pipelinemgr, 'RuntimePipeline')
        assert hasattr(pipelinemgr, 'StageInstContainer')

    @pytest.mark.asyncio
    async def test_stage_preregistration(self):
        """Verify stages are preregistered after fixture imports them."""
        from langbot.pkg.pipeline import stage

        # Check that our target stages are registered
        assert 'PreProcessor' in stage.preregistered_stages
        assert 'MessageProcessor' in stage.preregistered_stages
        assert 'SendResponseBackStage' in stage.preregistered_stages


@pytest.mark.usefixtures('load_pipeline_modules')
class TestPreProcessorStage:
    """Tests for PreProcessor stage alone."""

    @pytest.mark.asyncio
    async def test_preproc_continues_on_valid_query(self, pipeline_app, fake_platform_adapter):
        """PreProcessor should return CONTINUE for valid text query."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.preproc import preproc

        adapter, platform = fake_platform_adapter

        # Create query with adapter
        query = text_query('hello')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()

        # Mock plugin_connector for PromptPreProcessing event
        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.default_prompt = []  # Real list
        mock_event_ctx.event.prompt = []  # Real list
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create PreProcessor stage
        preproc_stage = preproc.PreProcessor(pipeline_app)

        result = await preproc_stage.process(query, 'PreProcessor')

        assert result.result_type.value == entities.ResultType.CONTINUE.value
        assert result.new_query.session is not None
        assert result.new_query.user_message is not None

    @pytest.mark.asyncio
    async def test_preproc_sets_user_message(self, pipeline_app, fake_platform_adapter):
        """PreProcessor should set user_message from message_chain."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.preproc import preproc

        adapter, platform = fake_platform_adapter

        query = text_query('test message content')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()

        # Mock plugin_connector for PromptPreProcessing event
        mock_event_ctx = Mock()
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.default_prompt = []
        mock_event_ctx.event.prompt = []
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        preproc_stage = preproc.PreProcessor(pipeline_app)

        result = await preproc_stage.process(query, 'PreProcessor')

        assert result.result_type.value == entities.ResultType.CONTINUE.value
        # Check user_message content
        assert result.new_query.user_message is not None
        assert result.new_query.user_message.role == 'user'


@pytest.mark.usefixtures('load_pipeline_modules')
class TestProcessorStage:
    """Tests for MessageProcessor stage."""

    @pytest.mark.asyncio
    async def test_processor_calls_chat_handler(self, pipeline_app, fake_platform_adapter, set_fake_runner):
        """Processor should route to ChatMessageHandler for non-command messages."""
        adapter, platform = fake_platform_adapter

        # Set fake runner that returns pong
        fake_runner = FakeRunner().returns('LANGBOT_FAKE_PONG')
        set_fake_runner(fake_runner)

        # Create query
        query = text_query('hello')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()
        query.resp_messages = []

        # Mock plugin_connector to not prevent default
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.user_message_alter = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process

        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        # Collect results using helper
        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) >= 1
        # Check that resp_messages was populated
        assert len(query.resp_messages) >= 1

    @pytest.mark.asyncio
    async def test_processor_prevent_default_without_reply_interrupts(self, pipeline_app, fake_platform_adapter):
        """Processor should INTERRUPT when plugin prevents default without reply."""
        from langbot.pkg.pipeline import entities

        adapter, platform = fake_platform_adapter

        # Create query
        query = text_query('hello')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()

        # Mock plugin_connector to prevent default without reply
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=True)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.reply_message_chain = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process

        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type.value == entities.ResultType.INTERRUPT.value

    @pytest.mark.asyncio
    async def test_processor_prevent_default_with_reply_continues(self, pipeline_app, fake_platform_adapter):
        """Processor should CONTINUE when plugin prevents default with reply."""
        from langbot.pkg.pipeline import entities
        from tests.factories.message import text_chain

        adapter, platform = fake_platform_adapter

        # Create query
        query = text_query('hello')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()
        query.resp_messages = []

        # Create reply chain
        reply_chain = text_chain('plugin response')

        # Mock plugin_connector to prevent default with reply
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=True)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.reply_message_chain = reply_chain
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process

        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type.value == entities.ResultType.CONTINUE.value
        assert len(query.resp_messages) == 1
        assert query.resp_messages[0] == reply_chain


@pytest.mark.usefixtures('load_pipeline_modules')
class TestRunnerExceptionFlow:
    """Tests for runner exception handling."""

    @pytest.mark.asyncio
    async def test_runner_exception_yields_interrupt(self, pipeline_app, fake_platform_adapter, set_fake_runner):
        """Runner exception should yield INTERRUPT with error notices."""
        from langbot.pkg.pipeline import entities

        adapter, platform = fake_platform_adapter

        # Set fake runner that raises exception
        fake_runner = FakeRunner().raises(ValueError('API Error: rate limit exceeded'))
        set_fake_runner(fake_runner)

        # Create query with exception handling config
        config = create_minimal_pipeline_config()
        config['output']['misc']['exception-handling'] = 'show-hint'
        config['output']['misc']['failure-hint'] = 'Request failed.'

        query = text_query('hello')
        query.adapter = adapter
        query.pipeline_config = config

        # Mock plugin_connector to not prevent default
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.user_message_alter = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process

        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type.value == entities.ResultType.INTERRUPT.value
        assert results[0].user_notice == 'Request failed.'
        assert results[0].error_notice is not None

    @pytest.mark.asyncio
    async def test_runner_exception_show_error_mode(self, pipeline_app, fake_platform_adapter, set_fake_runner):
        """show-error mode should show actual exception message."""
        from langbot.pkg.pipeline import entities

        adapter, platform = fake_platform_adapter

        # Set fake runner that raises specific exception
        fake_runner = FakeRunner().raises(RuntimeError('Custom runtime error'))
        set_fake_runner(fake_runner)

        # Create query with show-error mode
        config = create_minimal_pipeline_config()
        config['output']['misc']['exception-handling'] = 'show-error'

        query = text_query('hello')
        query.adapter = adapter
        query.pipeline_config = config

        # Mock plugin_connector to not prevent default
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.user_message_alter = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process

        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type.value == entities.ResultType.INTERRUPT.value
        assert 'Custom runtime error' in results[0].user_notice

    @pytest.mark.asyncio
    async def test_runner_exception_hide_mode(self, pipeline_app, fake_platform_adapter, set_fake_runner):
        """hide mode should not show user notice."""
        from langbot.pkg.pipeline import entities

        adapter, platform = fake_platform_adapter

        # Set fake runner that raises exception
        fake_runner = FakeRunner().raises(Exception('Hidden error'))
        set_fake_runner(fake_runner)

        # Create query with hide mode
        config = create_minimal_pipeline_config()
        config['output']['misc']['exception-handling'] = 'hide'

        query = text_query('hello')
        query.adapter = adapter
        query.pipeline_config = config

        # Mock plugin_connector to not prevent default
        mock_event_ctx = Mock()
        mock_event_ctx.is_prevented_default = Mock(return_value=False)
        mock_event_ctx.event = Mock()
        mock_event_ctx.event.user_message_alter = None
        pipeline_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        # Create Processor stage
        from langbot.pkg.pipeline.process import process

        processor_stage = process.Processor(pipeline_app)
        await processor_stage.initialize(query.pipeline_config)

        results = await collect_processor_results(processor_stage, query, 'MessageProcessor')

        assert len(results) == 1
        assert results[0].result_type.value == entities.ResultType.INTERRUPT.value
        assert results[0].user_notice is None


@pytest.mark.usefixtures('load_pipeline_modules')
class TestSendResponseBackStage:
    """Tests for SendResponseBackStage."""

    @pytest.mark.asyncio
    async def test_send_response_calls_adapter(self, pipeline_app, fake_platform_adapter):
        """SendResponseBackStage should call adapter.reply_message."""
        from langbot.pkg.pipeline import entities
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain
        from langbot_plugin.api.entities.builtin.provider.message import Message

        adapter, platform = fake_platform_adapter

        # Create query with response message
        query = text_query('hello')
        query.adapter = adapter
        query.pipeline_config = create_minimal_pipeline_config()

        # Add response message
        query.resp_messages = [Message(role='assistant', content='test response')]
        query.resp_message_chain = [text_chain('test response')]

        # Create SendResponseBackStage
        respback_stage = respback.SendResponseBackStage(pipeline_app)

        result = await respback_stage.process(query, 'SendResponseBackStage')

        assert result.result_type.value == entities.ResultType.CONTINUE.value

        # Check that adapter was called
        outbound = platform.get_outbound_messages()
        assert len(outbound) == 1
        assert outbound[0]['type'] == 'reply'

    @pytest.mark.asyncio
    async def test_send_response_failure_notifies_plugin_diagnostic(self, pipeline_app):
        """Plugin-provided deferred replies should report delivery failures."""
        from langbot.pkg.pipeline import plugin_diagnostics
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain
        from langbot_plugin.api.entities.builtin.provider.message import Message

        query = text_query('hello')
        query.adapter.reply_message.side_effect = RuntimeError('send failed')
        query.pipeline_config = create_minimal_pipeline_config()
        query.current_stage_name = 'SendResponseBackStage'
        query.resp_messages = [Message(role='assistant', content='test response')]
        query.resp_message_chain = [text_chain('test response')]
        plugin_diagnostics.record_plugin_response_source(
            query,
            0,
            [
                {
                    'kind': 'reply_message_chain',
                    'plugin': {'author': 'tester', 'name': 'demo'},
                }
            ],
            [{'manifest': {'metadata': {'author': 'observer', 'name': 'not-reply-source'}}}],
            'NormalMessageResponded',
        )
        pipeline_app.plugin_connector.notify_plugin_diagnostic = AsyncMock()

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        with pytest.raises(RuntimeError, match='send failed'):
            await respback_stage.process(query, 'SendResponseBackStage')

        pipeline_app.plugin_connector.notify_plugin_diagnostic.assert_awaited_once()
        payload = pipeline_app.plugin_connector.notify_plugin_diagnostic.await_args.args[0]
        assert payload['code'] == 'response_delivery_failed'
        assert payload['plugin'] == {'author': 'tester', 'name': 'demo'}
        assert payload['query']['event_name'] == 'NormalMessageResponded'
        assert payload['delivery']['error_type'] == 'RuntimeError'
        assert 'attribution_warning' not in payload['details']

    @pytest.mark.asyncio
    async def test_send_response_failure_warns_for_old_runtime_attribution(self, pipeline_app):
        """Older plugin runtimes without response_sources should get approximate diagnostics."""
        from langbot.pkg.pipeline import plugin_diagnostics
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain
        from langbot_plugin.api.entities.builtin.provider.message import Message

        query = text_query('hello')
        query.adapter.reply_message.side_effect = RuntimeError('send failed')
        query.pipeline_config = create_minimal_pipeline_config()
        query.resp_messages = [Message(role='assistant', content='test response')]
        query.resp_message_chain = [text_chain('test response')]
        plugin_diagnostics.record_plugin_response_source(
            query,
            0,
            None,
            [{'manifest': {'metadata': {'author': 'tester', 'name': 'demo'}}}],
            'NormalMessageResponded',
        )
        pipeline_app.plugin_connector.notify_plugin_diagnostic = AsyncMock()

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        with pytest.raises(RuntimeError, match='send failed'):
            await respback_stage.process(query, 'SendResponseBackStage')

        payload = pipeline_app.plugin_connector.notify_plugin_diagnostic.await_args.args[0]
        assert payload['plugin'] == {'author': 'tester', 'name': 'demo'}
        assert 'attribution_warning' in payload['details']

    @pytest.mark.asyncio
    async def test_send_response_failure_ignores_query_variable_spoofing(self, pipeline_app):
        """Plugin-controlled query variables must not mask delivery failures."""
        from langbot.pkg.pipeline.respback import respback
        from tests.factories.message import text_chain
        from langbot_plugin.api.entities.builtin.provider.message import Message

        query = text_query('hello')
        query.adapter.reply_message.side_effect = RuntimeError('send failed')
        query.pipeline_config = create_minimal_pipeline_config()
        query.resp_messages = [Message(role='assistant', content='test response')]
        query.resp_message_chain = [text_chain('test response')]
        query.variables['_plugin_response_sources'] = {0: ['malformed']}
        pipeline_app.plugin_connector.notify_plugin_diagnostic = AsyncMock()

        respback_stage = respback.SendResponseBackStage(pipeline_app)

        with pytest.raises(RuntimeError, match='send failed'):
            await respback_stage.process(query, 'SendResponseBackStage')

        pipeline_app.plugin_connector.notify_plugin_diagnostic.assert_not_called()


@pytest.fixture
async def runtime_pipeline_factory(pipeline_app, load_pipeline_modules):
    """Use real dispatch and stages; fake only the surrounding services."""
    from langbot.pkg.pipeline import pipelinemgr
    from langbot.pkg.pipeline.preproc.preproc import PreProcessor
    from langbot.pkg.pipeline.process.process import Processor
    from langbot.pkg.pipeline.wrapper.wrapper import ResponseWrapper
    from langbot.pkg.pipeline.respback.respback import SendResponseBackStage

    async def create(query):
        context = query._execution_context
        query.instance_uuid = context.instance_uuid
        query.workspace_uuid = context.workspace_uuid
        query.placement_generation = context.placement_generation
        query.resp_message_chain = []
        query.adapter.on_monitoring_message_created = AsyncMock()
        stage_specs = [
            ('PreProcessor', PreProcessor),
            ('MessageProcessor', Processor),
            ('ResponseWrapper', ResponseWrapper),
            ('SendResponseBackStage', SendResponseBackStage),
        ]
        containers = []
        for name, cls in stage_specs:
            instance = cls(pipeline_app)
            await instance.initialize(query.pipeline_config)
            containers.append(pipelinemgr.StageInstContainer(name, instance))
        entity = SimpleNamespace(
            uuid=query.pipeline_uuid,
            workspace_uuid=context.workspace_uuid,
            name='Contract pipeline',
            config=query.pipeline_config,
            extensions_preferences={'enable_all_plugins': False, 'plugins': [{'author': 'test', 'name': 'observer'}]},
        )
        return pipelinemgr.RuntimePipeline(pipeline_app, entity, containers, context)

    return create


@pytest.fixture
def passthrough_plugin(pipeline_app):
    """Return real SDK contexts, like a plugin which does not intercept a call."""
    from langbot_plugin.api.entities.context import EventContext

    def context_for(event, _bound_plugins):
        return EventContext.from_event(event)

    pipeline_app.plugin_connector.emit_event.side_effect = context_for
    return context_for


@pytest.mark.usefixtures('load_pipeline_modules')
class TestStageChainIntegration:
    """Runtime dispatch must preserve input, output, plugin boundaries, and cleanup."""

    @pytest.mark.asyncio
    async def test_full_chain_text_message_flow(
        self, pipeline_app, fake_platform_adapter, set_fake_runner, runtime_pipeline_factory, passthrough_plugin
    ):
        adapter, platform = fake_platform_adapter
        set_fake_runner(FakeRunner.returns('LANGBOT_FAKE_PONG'))
        query = text_query('ping', pipeline_config=create_minimal_pipeline_config())
        query.pipeline_config['output']['misc']['quote-origin'] = True
        query.adapter = adapter
        runtime = await runtime_pipeline_factory(query)

        await runtime.run(query)

        assert pipeline_app.agent_run_orchestrator.observed_queries == [query]
        assert str(query.user_message.get_content_platform_message_chain()) == 'ping'
        assert [message.content for message in query.resp_messages] == ['LANGBOT_FAKE_PONG']
        assert [str(chain) for chain in query.resp_message_chain] == ['LANGBOT_FAKE_PONG']
        outbound = platform.get_outbound_messages()
        assert len(outbound) == 1, pipeline_app.logger.error.call_args_list
        assert outbound[0]['source'] is query.message_event
        assert str(outbound[0]['message']) == 'LANGBOT_FAKE_PONG'
        assert outbound[0]['quote_origin'] is True
        assert platform.get_outbound_chunks() == []
        assert not query.variables.get('_monitoring_has_error'), pipeline_app.logger.error.call_args_list
        pipeline_app.logger.error.assert_not_called()
        emitted = pipeline_app.plugin_connector.emit_event.await_args_list
        assert [call.args[0].event_name for call in emitted] == [
            'PersonMessageReceived',
            'PromptPreProcessing',
            'PersonNormalMessageReceived',
            'NormalMessageResponded',
        ]
        assert [call.args[1] for call in emitted] == [['test/observer']] * 4
        pipeline_app.query_pool.remove_query.assert_awaited_once_with(query)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        'blocked_event', ['PersonMessageReceived', 'PersonNormalMessageReceived', 'NormalMessageResponded']
    )
    async def test_chain_stops_on_interrupt(
        self,
        pipeline_app,
        fake_platform_adapter,
        set_fake_runner,
        runtime_pipeline_factory,
        passthrough_plugin,
        blocked_event,
    ):
        adapter, platform = fake_platform_adapter
        set_fake_runner(FakeRunner.returns('MUST_NOT_BE_DELIVERED'))
        query = text_query('hello', pipeline_config=create_minimal_pipeline_config())
        query.adapter = adapter
        runtime = await runtime_pipeline_factory(query)

        def intercept(event, bound_plugins):
            context = passthrough_plugin(event, bound_plugins)
            if event.event_name == blocked_event:
                context.prevent_default()
            return context

        pipeline_app.plugin_connector.emit_event.side_effect = intercept
        await runtime.run(query)

        event_names = [call.args[0].event_name for call in pipeline_app.plugin_connector.emit_event.await_args_list]
        assert event_names[-1] == blocked_event
        expected_runner_queries = [query] if blocked_event == 'NormalMessageResponded' else []
        assert pipeline_app.agent_run_orchestrator.observed_queries == expected_runner_queries
        assert query.resp_message_chain == []
        assert platform.get_outbound_messages() == []
        assert platform.get_outbound_chunks() == []
        assert not query.variables.get('_monitoring_has_error'), pipeline_app.logger.error.call_args_list
        pipeline_app.logger.error.assert_not_called()
        pipeline_app.query_pool.remove_query.assert_awaited_once_with(query)

    @pytest.mark.asyncio
    async def test_wrapper_plugin_reply_reaches_adapter(
        self, pipeline_app, fake_platform_adapter, set_fake_runner, runtime_pipeline_factory, passthrough_plugin
    ):
        from tests.factories.message import text_chain

        adapter, platform = fake_platform_adapter
        set_fake_runner(FakeRunner.returns('original runner answer'))
        query = text_query('hello', pipeline_config=create_minimal_pipeline_config())
        query.adapter = adapter
        runtime = await runtime_pipeline_factory(query)

        def alter_response(event, bound_plugins):
            context = passthrough_plugin(event, bound_plugins)
            if event.event_name == 'NormalMessageResponded':
                context.event.reply_message_chain = text_chain('plugin replacement')
            return context

        pipeline_app.plugin_connector.emit_event.side_effect = alter_response
        await runtime.run(query)

        outbound = platform.get_outbound_messages()
        assert len(outbound) == 1, pipeline_app.logger.error.call_args_list
        assert str(outbound[0]['message']) == 'plugin replacement'
        assert [str(chain) for chain in query.resp_message_chain] == ['plugin replacement']
        pipeline_app.query_pool.remove_query.assert_awaited_once_with(query)

    @pytest.mark.asyncio
    async def test_runner_failure_delivers_hint_and_cleans_up(
        self, pipeline_app, fake_platform_adapter, set_fake_runner, runtime_pipeline_factory, passthrough_plugin
    ):
        adapter, platform = fake_platform_adapter
        set_fake_runner(FakeRunner.raises(RuntimeError('provider unavailable')))
        query = text_query('hello', pipeline_config=create_minimal_pipeline_config())
        query.adapter = adapter
        runtime = await runtime_pipeline_factory(query)

        await runtime.run(query)

        outbound = platform.get_outbound_messages()
        assert len(outbound) == 1, pipeline_app.logger.error.call_args_list
        assert str(outbound[0]['message']) == 'Request failed.'
        assert query.variables['_monitoring_has_error'] is True
        assert query.resp_messages == []
        assert query.resp_message_chain == []
        assert [call.args[0].event_name for call in pipeline_app.plugin_connector.emit_event.await_args_list] == [
            'PersonMessageReceived',
            'PromptPreProcessing',
            'PersonNormalMessageReceived',
        ]
        pipeline_app.query_pool.remove_query.assert_awaited_once_with(query)

    @pytest.mark.asyncio
    async def test_streaming_chain_delivers_each_chunk_with_one_response_id(
        self, pipeline_app, set_fake_runner, runtime_pipeline_factory, passthrough_plugin
    ):
        from langbot_plugin.api.entities.builtin.provider.message import MessageChunk

        class StreamingRunner(FakeRunner):
            async def run(self, query):
                yield MessageChunk(role='assistant', content='first', all_content='first', is_final=False)
                yield MessageChunk(role='assistant', content=' second', all_content='first second', is_final=True)

        platform = FakePlatform(stream_output_supported=True)
        adapter = mock_platform_adapter(platform)
        adapter.create_message_card = AsyncMock(side_effect=platform.create_message_card)
        set_fake_runner(StreamingRunner)
        query = text_query('stream please', pipeline_config=create_minimal_pipeline_config())
        query.adapter = adapter
        runtime = await runtime_pipeline_factory(query)

        await runtime.run(query)

        chunks = platform.get_outbound_chunks()
        assert [(str(chunk['message']), chunk['is_final']) for chunk in chunks] == [
            ('first', False),
            ('first second', True),
        ], pipeline_app.logger.error.call_args_list
        assert all(chunk['source'] is query.message_event for chunk in chunks)
        response_ids = [chunk['bot_message'].resp_message_id for chunk in chunks]
        assert response_ids[0] and response_ids == [response_ids[0]] * 2
        adapter.create_message_card.assert_awaited_once_with(response_ids[0], query.message_event)
        assert [str(chain) for chain in query.resp_message_chain] == ['first second']
        assert platform.get_outbound_messages() == []
        assert pipeline_app.agent_run_orchestrator.observed_queries == [query]
        assert not query.variables.get('_monitoring_has_error'), pipeline_app.logger.error.call_args_list
        pipeline_app.logger.error.assert_not_called()
        pipeline_app.query_pool.remove_query.assert_awaited_once_with(query)
