"""Pin the readiness contract at both deployment entrypoints."""

from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.response import addinfourl

from tools.entrypoints.regression_ci import ready
from tools.entrypoints.regression_job import Job
from tools.regression.observations import read_endpoint_snapshot

URL = 'http://localhost/healthz'


def response(body, status=200, content_type='application/json'):
    return addinfourl(BytesIO(body), {'Content-Type': content_type}, URL, status)


class ReadinessTests(unittest.TestCase):
    def test_both_entrypoints_wait_for_healthy_json(self):
        for wait in (Job.ready, lambda url: ready(url, [])):
            with self.subTest(wait=wait):
                responses = [
                    response(b'OK', content_type='text/plain'),
                    response(b'[]'),
                    response(b'{"ready":true}', status=202),
                    response(b'{"live":false}'),
                    response(b'{"ready":false}'),
                    response(b'{"code":1}'),
                    response(b'{"code":0,"ready":true}'),
                ]
                with (
                    patch('urllib.request.OpenerDirector.open', side_effect=responses) as request,
                    patch('time.sleep'),
                ):
                    wait(URL)
                self.assertEqual(request.call_count, len(responses))

    def test_generic_observation_accepts_plain_text(self):
        with patch('urllib.request.OpenerDirector.open', return_value=response(b'OK', content_type='text/plain')):
            self.assertEqual(read_endpoint_snapshot(URL, timeout_seconds=1)['http.ok'], 1)
