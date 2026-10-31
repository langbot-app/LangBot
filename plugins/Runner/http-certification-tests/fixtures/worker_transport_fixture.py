"""Vendor responses are local fixtures, while SDK parsing stays real."""

import runpy
import socket


def deny(*args, **kwargs):
    raise AssertionError("Fixture must not reach external network")


socket.create_connection = deny
if globals()["PLUGIN"] == "dashscope-agent":
    from dashscope import Application
    from dashscope.app.application import ApplicationResponse

    def call(**kwargs):
        return iter(
            [
                ApplicationResponse(
                    status_code=200,
                    request_id="fixture",
                    output={"text": "FIXTURE_OK", "session_id": "fixture-session", "finish_reason": "stop"},
                    usage={},
                )
            ]
        )

    Application.call = call
else:
    from tboxsdk.core.httpclient import HttpClient

    def post(self, path, **params):
        return {
            "errorCode": "0",
            "data": {"conversationId": "fixture-conversation", "result": [{"chunk": "FIXTURE_OK"}]},
        }

    HttpClient.post = post
runpy.run_path(globals()["WORKER"], run_name="__main__")
