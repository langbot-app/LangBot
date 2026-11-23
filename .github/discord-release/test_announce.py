"""Offline contract tests; no Discord credentials or network required."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

try:
    import announce
except ModuleNotFoundError:
    announce = None

WEBHOOK = 'https://discord.com/api/webhooks/123456789012345678/fixture_token-ONLY'
WEBHOOK_ID = '123456789012345678'
GUILD_ID = '234567890123456789'
CHANNEL_ID = '345678901234567890'
MESSAGE_ID = '456789012345678901'
REPO = 'langbot-app/LangBot'
URL = f'https://github.com/{REPO}/releases/tag/v4.10.11'
CONTENT = f'@everyone LangBot v4.10.11 is now available!\nRelease notes: {URL}'


def event():
    return {
        'action': 'published',
        'repository': {'full_name': REPO},
        'release': {
            'draft': False,
            'prerelease': False,
            'tag_name': 'v4.10.11',
            'html_url': URL,
            'name': 'Hostile @everyone <@123> $(touch /tmp/unsafe)',
            'body': '@everyone @here <@123> <@&456> `hostile`',
        },
    }


def metadata():
    return {'id': WEBHOOK_ID, 'type': 1, 'guild_id': GUILD_ID, 'channel_id': CHANNEL_ID}


def message():
    return {
        'id': MESSAGE_ID,
        'webhook_id': WEBHOOK_ID,
        'channel_id': CHANNEL_ID,
        'content': CONTENT,
        'mention_everyone': True,
        'mentions': [],
        'mention_roles': [],
    }


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(announce, 'The release announcement helper must exist')


class PolicyTests(BaseTest):
    def test_payload_has_one_literal_everyone_and_no_untrusted_body(self):
        payload = announce.release_payload(event(), '1')
        self.assertEqual(payload['content'], CONTENT)
        self.assertEqual(json.dumps(payload).count('@everyone'), 1)
        self.assertEqual(
            payload['allowed_mentions'],
            {
                'parse': ['everyone'],
                'users': [],
                'roles': [],
                'replied_user': False,
            },
        )
        self.assertIs(payload['tts'], False)
        self.assertEqual(payload['flags'], 0)

    def test_drafts_and_prereleases_are_skipped(self):
        for flag in ('draft', 'prerelease'):
            with self.subTest(flag=flag):
                value = event()
                value['release'][flag] = True
                self.assertIsNone(announce.release_payload(value, '1'))

    def test_only_published_action_is_accepted(self):
        for action in ('edited', 'created', 'released', 'deleted', '', None):
            with self.subTest(action=action):
                value = event()
                value['action'] = action
                with self.assertRaises(announce.AnnouncementError):
                    announce.release_payload(value, '1')

    def test_reruns_and_missing_attempt_refuse_manual_reconciliation(self):
        for attempt in ('2', '3', '', None, '01', '0', '1\n'):
            with self.subTest(attempt=attempt):
                with self.assertRaisesRegex(announce.AnnouncementError, 'manual reconciliation'):
                    announce.release_payload(event(), attempt)

    def test_repository_must_match_exactly(self):
        for repo in ('evil/LangBot', 'langbot-app/langbot', None):
            value = event()
            value['repository']['full_name'] = repo
            with self.assertRaises(announce.AnnouncementError):
                announce.release_payload(value, '1')

    def test_hostile_and_noncanonical_tags_are_rejected(self):
        for tag in (
            'v1.2.3 @everyone',
            'v1.2.3\n',
            'v1.2.3/../../x',
            'v1.2.3?x=y',
            '$(id)',
            'v1.2.3-rc.1',
            'v１.2.3',
            'v1.2.3%0a',
            '<@123>',
            'v1.2.' + '3' * 100,
            '',
            None,
            123,
        ):
            with self.subTest(tag=tag):
                value = event()
                value['release']['tag_name'] = tag
                value['release']['html_url'] = f'https://github.com/{REPO}/releases/tag/{tag}'
                with self.assertRaises(announce.AnnouncementError):
                    announce.release_payload(value, '1')

    def test_release_url_must_be_canonical_and_match_tag(self):
        for url in (
            'https://evil.example/tag/v4.10.11',
            URL + '?x=y',
            URL + '#anchor',
            URL + '/',
            URL.replace('v4.10.11', 'v4.10.12'),
            URL.replace('github.com', 'github.com@evil.example'),
            URL.replace('https:', 'http:'),
            URL + '\n',
            None,
        ):
            with self.subTest(url=url):
                value = event()
                value['release']['html_url'] = url
                with self.assertRaises(announce.AnnouncementError):
                    announce.release_payload(value, '1')

    def test_malformed_events_fail_closed(self):
        for value in (None, [], {}, {'release': []}, {'repository': None}):
            with self.subTest(value=value):
                with self.assertRaises(announce.AnnouncementError):
                    announce.release_payload(value, '1')
        for flag in ('draft', 'prerelease'):
            for bad in (None, 'false', 0, 1):
                value = event()
                value['release'][flag] = bad
                with self.assertRaises(announce.AnnouncementError):
                    announce.release_payload(value, '1')


class DiscordTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.patch = patch('announce.http.client.HTTPSConnection')
        self.connection_class = self.patch.start()
        self.addCleanup(self.patch.stop)
        self.connection = self.connection_class.return_value

    def respond(self, *values):
        responses = []
        for value in values:
            response = MagicMock()
            response.status = 200
            response.read.return_value = json.dumps(value).encode()
            responses.append(response)
        self.connection.getresponse.side_effect = responses

    def methods(self):
        return [call.args[0] for call in self.connection.request.call_args_list]

    def test_webhook_validation_is_get_only_and_reports_ids(self):
        self.respond(metadata())
        result = announce.DiscordWebhook(WEBHOOK).validate()
        self.assertEqual(result, metadata())
        self.assertEqual(self.methods(), ['GET'])
        self.assertEqual(
            self.connection.request.call_args.args[:2], ('GET', f'/api/webhooks/{WEBHOOK_ID}/fixture_token-ONLY')
        )
        self.connection_class.assert_called_with('discord.com', timeout=20)
        self.connection.close.assert_called_once()

    def test_invalid_webhook_urls_are_rejected_before_network(self):
        for url in (
            '',
            None,
            WEBHOOK + '/',
            WEBHOOK + '?wait=true',
            WEBHOOK + '#x',
            WEBHOOK + '\n',
            ' ' + WEBHOOK,
            WEBHOOK.replace('https:', 'http:'),
            WEBHOOK.replace('discord.com', 'discord.com.evil.example'),
            WEBHOOK.replace('discord.com', 'discord.com@evil.example'),
            WEBHOOK.replace('discord.com', 'discord.com:443'),
            WEBHOOK.replace('/api/', '/api/v10/'),
            WEBHOOK.replace(WEBHOOK_ID, 'abc'),
            WEBHOOK + '/../../x',
            WEBHOOK.replace('fixture_token-ONLY', 'a%2Fb'),
        ):
            with self.subTest(url=url):
                with self.assertRaises(announce.AnnouncementError):
                    announce.DiscordWebhook(url)
        self.connection_class.assert_not_called()

    def test_webhook_metadata_requires_incoming_type_and_ids(self):
        invalid = [
            None,
            [],
            {},
            dict(metadata(), type=2),
            dict(metadata(), type=True),
            dict(metadata(), id='999'),
            dict(metadata(), channel_id=None),
            dict(metadata(), guild_id='::error::hostile'),
        ]
        for value in invalid:
            with self.subTest(value=value):
                self.respond(value)
                with self.assertRaises(announce.AnnouncementError):
                    announce.DiscordWebhook(WEBHOOK).validate()
        self.assertNotIn('POST', self.methods())

    def test_send_waits_and_reads_back_exact_returned_message(self):
        self.respond(metadata(), message(), message())
        result = announce.DiscordWebhook(WEBHOOK).send(announce.release_payload(event(), '1'))
        self.assertEqual(result, MESSAGE_ID)
        self.assertEqual(self.methods(), ['GET', 'POST', 'GET'])
        calls = self.connection.request.call_args_list
        self.assertEqual(calls[1].args[:2], ('POST', f'/api/webhooks/{WEBHOOK_ID}/fixture_token-ONLY?wait=true'))
        self.assertEqual(json.loads(calls[1].kwargs['body']), announce.release_payload(event(), '1'))
        self.assertEqual(
            calls[2].args[:2], ('GET', f'/api/webhooks/{WEBHOOK_ID}/fixture_token-ONLY/messages/{MESSAGE_ID}')
        )

    def test_readback_must_match_content_mentions_and_identity(self):
        for field, bad in (
            ('content', 'wrong'),
            ('mention_everyone', False),
            ('mention_everyone', 1),
            ('mentions', [{'id': '123'}]),
            ('mention_roles', ['123']),
            ('id', '999'),
            ('channel_id', '999'),
            ('webhook_id', '999'),
        ):
            with self.subTest(field=field, bad=bad):
                self.connection.reset_mock()
                self.respond(metadata(), message(), dict(message(), **{field: bad}))
                with self.assertRaisesRegex(announce.AnnouncementError, 'manual reconciliation'):
                    announce.DiscordWebhook(WEBHOOK).send(announce.release_payload(event(), '1'))
                self.assertEqual(self.methods().count('POST'), 1)

    def test_missing_readback_fields_fail_closed(self):
        for field in message():
            value = message()
            del value[field]
            self.respond(metadata(), message(), value)
            with self.assertRaises(announce.AnnouncementError):
                announce.DiscordWebhook(WEBHOOK).send(announce.release_payload(event(), '1'))

    def test_unsafe_post_message_id_never_becomes_get_path(self):
        for value in (None, {}, dict(message(), id='../evil'), dict(message(), id='123?x=y')):
            self.connection.reset_mock()
            self.respond(metadata(), value)
            with self.assertRaisesRegex(announce.AnnouncementError, 'manual reconciliation'):
                announce.DiscordWebhook(WEBHOOK).send(announce.release_payload(event(), '1'))
            self.assertEqual(self.methods(), ['GET', 'POST'])

    def test_post_failure_never_retries_and_never_logs_secret(self):
        for status in (301, 302, 307, 308, 400, 401, 403, 429, 500, 204):
            with self.subTest(status=status):
                self.connection.reset_mock()
                self.respond(metadata(), message())
                responses = list(self.connection.getresponse.side_effect)
                responses[1].status = status
                self.connection.getresponse.side_effect = responses
                with self.assertRaisesRegex(announce.AnnouncementError, 'manual reconciliation') as caught:
                    announce.DiscordWebhook(WEBHOOK).send(announce.release_payload(event(), '1'))
                self.assertNotIn('fixture_token', str(caught.exception))
                self.assertEqual(self.methods(), ['GET', 'POST'])

    def test_ambiguous_timeout_never_retries_or_echoes_exception(self):
        self.respond(metadata())
        first = next(self.connection.getresponse.side_effect)
        self.connection.getresponse.side_effect = [first, TimeoutError(WEBHOOK)]
        with self.assertRaisesRegex(announce.AnnouncementError, 'manual reconciliation') as caught:
            announce.DiscordWebhook(WEBHOOK).send(announce.release_payload(event(), '1'))
        self.assertNotIn('fixture_token', str(caught.exception))
        self.assertEqual(self.methods(), ['GET', 'POST'])

    def test_malformed_json_response_is_sanitized(self):
        self.respond(metadata())
        response = next(self.connection.getresponse.side_effect)
        response.read.return_value = WEBHOOK.encode()
        self.connection.getresponse.side_effect = [response]
        with self.assertRaises(announce.AnnouncementError) as caught:
            announce.DiscordWebhook(WEBHOOK).validate()
        self.assertNotIn('fixture_token', str(caught.exception))

    def test_get_redirect_is_not_followed(self):
        self.respond(metadata())
        response = next(self.connection.getresponse.side_effect)
        response.status = 302
        response.getheader.return_value = 'https://evil.example/'
        self.connection.getresponse.side_effect = [response]
        with self.assertRaises(announce.AnnouncementError):
            announce.DiscordWebhook(WEBHOOK).validate()
        self.assertEqual(self.methods(), ['GET'])


class EntrypointTests(BaseTest):
    def run_main(self, data=None, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'event.json'
            path.write_text(json.dumps(event() if data is None else data))
            env = {
                'GITHUB_EVENT_NAME': 'release',
                'GITHUB_EVENT_PATH': str(path),
                'GITHUB_REPOSITORY': REPO,
                'GITHUB_RUN_ATTEMPT': '1',
                'DISCORD_RELEASE_WEBHOOK_URL': WEBHOOK,
            }
            env.update(overrides)
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                result = announce.main(env)
            return result, output.getvalue()

    def test_dispatch_only_validates_even_if_event_contains_release(self):
        with patch('announce.DiscordWebhook') as client:
            client.return_value.validate.return_value = metadata()
            result, output = self.run_main(GITHUB_EVENT_NAME='workflow_dispatch')
        self.assertEqual(result, 0)
        client.return_value.validate.assert_called_once()
        client.return_value.send.assert_not_called()
        self.assertIn(GUILD_ID, output)
        self.assertIn(CHANNEL_ID, output)
        self.assertNotIn('fixture_token', output)

    def test_production_release_sends_once(self):
        with patch('announce.DiscordWebhook') as client:
            client.return_value.send.return_value = MESSAGE_ID
            result, output = self.run_main()
        self.assertEqual(result, 0)
        client.return_value.send.assert_called_once_with(announce.release_payload(event(), '1'))
        self.assertIn(MESSAGE_ID, output)

    def test_skipped_releases_need_no_secret_or_network(self):
        for flag in ('draft', 'prerelease'):
            value = event()
            value['release'][flag] = True
            with patch('announce.DiscordWebhook') as client:
                result, _ = self.run_main(value, DISCORD_RELEASE_WEBHOOK_URL='')
            self.assertEqual(result, 0)
            client.assert_not_called()

    def test_rerun_never_constructs_client(self):
        with patch('announce.DiscordWebhook') as client:
            result, output = self.run_main(GITHUB_RUN_ATTEMPT='2')
        self.assertEqual(result, 1)
        self.assertIn('manual reconciliation', output)
        client.assert_not_called()

    def test_unexpected_event_or_repository_cannot_send(self):
        for overrides in (
            {'GITHUB_EVENT_NAME': 'push'},
            {'GITHUB_EVENT_NAME': 'pull_request'},
            {'GITHUB_REPOSITORY': 'evil/LangBot'},
        ):
            with patch('announce.DiscordWebhook') as client:
                result, _ = self.run_main(**overrides)
            self.assertEqual(result, 1)
            client.assert_not_called()

    def test_missing_secret_fails_clearly_for_send_and_validation(self):
        for name in ('release', 'workflow_dispatch'):
            result, output = self.run_main(GITHUB_EVENT_NAME=name, DISCORD_RELEASE_WEBHOOK_URL='')
            self.assertEqual(result, 1)
            self.assertIn('DISCORD_RELEASE_WEBHOOK_URL is missing', output)

    def test_cli_reads_event_file_and_redacts_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'event.json'
            value = event()
            value['release']['tag_name'] = '::error::hostile @everyone'
            path.write_text(json.dumps(value))
            env = dict(
                os.environ,
                GITHUB_EVENT_NAME='release',
                GITHUB_EVENT_PATH=str(path),
                GITHUB_REPOSITORY=REPO,
                GITHUB_RUN_ATTEMPT='1',
                DISCORD_RELEASE_WEBHOOK_URL=WEBHOOK,
            )
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name('announce.py'))],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('hostile', result.stderr)
        self.assertNotIn('fixture_token', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_unreadable_event_fails_safely(self):
        result, output = self.run_main(GITHUB_EVENT_PATH='/nonexistent/event.json')
        self.assertEqual(result, 1)
        self.assertNotIn('Traceback', output)


if __name__ == '__main__':
    unittest.main()
