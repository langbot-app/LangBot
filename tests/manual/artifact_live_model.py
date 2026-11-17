"""Explicit, credentialed provider acceptance. Never auto-collect in routine suites."""

import os
import re
from urllib.parse import urlsplit

import pytest

from tests.e2e.test_local_runner_fake_provider import (
    FAKE_MODEL_UUID,
    LOCAL_RUNNER_ID,
    _inject_llm_model,
    _run_local_agent_probe,
    local_agent_e2e_config_path,  # noqa: F401 -- pytest fixture
    local_agent_e2e_port,  # noqa: F401 -- pytest fixture
    local_agent_e2e_tmpdir,  # noqa: F401 -- pytest fixture
    local_agent_runtime_ports,  # noqa: F401 -- pytest fixture
    local_agent_runtime_process,  # noqa: F401 -- pytest fixture
)
from tests.utils.artifact_media import make_artifact_media


@pytest.fixture(scope='session')
def live_profile():
    key = os.environ.get('LANGBOT_ARTIFACT_LIVE_API_KEY', '').strip()
    model = os.environ.get('LANGBOT_ARTIFACT_LIVE_MODEL', '').strip()
    provider = os.environ.get('LANGBOT_ARTIFACT_LIVE_PROVIDER', '').strip()
    base = os.environ.get('LANGBOT_ARTIFACT_LIVE_BASE_URL', '').strip()
    if not (key and model and provider and base):
        pytest.fail(
            'The explicitly requested live test needs all four LANGBOT_ARTIFACT_LIVE_* settings.', pytrace=False
        )
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query:
        pytest.fail(
            'Use the approved HTTPS provider endpoint without URL credentials or query parameters.', pytrace=False
        )
    return key, model, provider, base


def test_live_model_understands_artifact_body_after_tool_transport(
    live_profile,
    local_agent_e2e_tmpdir,  # noqa: F811 -- pytest fixture
    local_agent_e2e_config_path,  # noqa: F811 -- pytest fixture
    local_agent_runtime_process,  # noqa: F811 -- pytest fixture
):
    """Serial independent conversations distinguish payload delivery from semantic correctness."""
    from langbot.pkg.api.authz import Permission
    from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
    from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester

    del local_agent_e2e_config_path, local_agent_runtime_process
    key, model, provider, base = live_profile
    session = 'artifact-live-model'
    corpus = make_artifact_media(session)

    async def probe(ap):
        requester = LiteLLMRequester(
            ap,
            {'requester_name': 'litellm', 'custom_llm_provider': provider, 'base_url': base},
        )
        await requester.initialize()
        await _inject_llm_model(
            ap,
            requester,
            model_name=model,
            abilities=['func_call', 'vision', 'pdf_input'],
            ephemeral_token=key,
        )
        execution = await ap.plugin_connector._current_execution_context()
        request = RequestContext(
            instance_uuid=execution.instance_uuid,
            placement_generation=execution.placement_generation,
            request_id=session,
            auth_type='user-token',
            principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=session),
            workspace=WorkspaceContext(execution.workspace_uuid, None, None, frozenset(Permission)),
        )
        agent = await ap.agent_service.create_agent(
            request,
            {
                'name': 'Live artifact reader acceptance',
                'kind': 'agent',
                'config': {
                    'runner': {'id': LOCAL_RUNNER_ID},
                    'runner_config': {
                        LOCAL_RUNNER_ID: {
                            'model': {'primary': FAKE_MODEL_UUID, 'fallbacks': []},
                            'timeout': 120,
                            'box-enabled': False,
                        },
                    },
                    'allowed_platform_tools': [],
                    'allowed_tools': [],
                },
            },
        )
        outcomes = []
        for fixture, mode in zip(corpus, ('native', 'native', 'text', 'native'), strict=True):
            asset = await ap.artifact_service.create(request, fixture.filename, fixture.data, fixture.mime_type)
            prompt = (
                f'Use langbot_read_input_attachment with mode {mode} to read the provided attachment. '
                'What exact short code is printed on the page or image? Reply with the code only. '
                'If the required input type is unsupported, state that rather than guessing.'
            )
            assert fixture.marker not in prompt and fixture.marker not in str(asset)
            try:
                result = await ap.agent_service.debug_agent(
                    request,
                    agent['uuid'],
                    {
                        'conversation_id': f'{session}-{fixture.kind}',
                        'text': prompt,
                        'artifact_ids': [asset['id']],
                    },
                )
            except Exception as error:
                # Error messages can carry provider URLs and response text. Report
                # only the class/status classification, never credentials or payloads.
                label = _failure_label(str(error))
                outcomes.append(f'{fixture.kind}/{mode}: {label}')
                continue

            events = result['execution_events']
            tool_completed = any(
                event['type'] == 'tool.call.completed' and 'langbot_read_input_attachment' in str(event['data'])
                for event in events
            )
            answer = result['final_text']
            actual = re.findall(r'\bMEDIA-[A-F0-9]{12}\b', answer.upper())
            if tool_completed and actual == [fixture.marker]:
                outcomes.append(f'{fixture.kind}/{mode}: verified body')
            else:
                reason = _failure_label(answer + ' ' + str(events))
                outcomes.append(f'{fixture.kind}/{mode}: {reason}; attachment tool completed={tool_completed}')
        return outcomes

    outcomes = _run_local_agent_probe(local_agent_e2e_tmpdir, probe)
    print('\n'.join(outcomes))
    assert len(outcomes) == 4 and all(item.endswith(': verified body') for item in outcomes), outcomes


def _failure_label(value):
    lowered = value.lower()
    if any(part in lowered for part in ('rate limit', 'ratelimit', 'resource_exhausted', '429')):
        return 'upstream rate limit'
    if 'unsupported' in lowered or 'not support' in lowered:
        return 'unsupported capability'
    if any(part in lowered for part in ('timeout', 'timed out', 'exception', 'connection refused')):
        return 'provider or pipeline error'
    return 'unverified body'
