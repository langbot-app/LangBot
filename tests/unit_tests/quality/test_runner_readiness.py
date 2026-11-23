"""A healthy Core HTTP endpoint can precede Runtime Runner discovery."""

import httpx

from tests.e2e import test_runner_plugin_runtime as runtime_tests


def test_runner_readiness_waits_for_options_after_restart(monkeypatch):
    selections = iter([{'name': 'id'}, {'name': 'id', 'options': [{'name': runtime_tests.QA_RUNNER_ID}]}])

    def metadata(request):
        return httpx.Response(
            200,
            json={
                'code': 0,
                'data': {'configs': [{'name': 'ai', 'stages': [{'name': 'runner', 'config': [next(selections)]}]}]},
            },
        )

    monkeypatch.setattr(runtime_tests.time, 'sleep', lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(metadata), base_url='http://core.test') as client:
        assert runtime_tests._wait_for_qa_runner(client, 'test-token') == {runtime_tests.QA_RUNNER_ID}
