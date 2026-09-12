"""Announce only first-attempt stable releases; dispatch is read-only validation."""

import http.client
import json
import os
from pathlib import Path
import re
import sys

REPOSITORY = 'langbot-app/LangBot'
RELEASE_PREFIX = f'https://github.com/{REPOSITORY}/releases/tag/'
RECONCILE = (
    'Do not resend or bypass the run-attempt guard; manual reconciliation is required. '
    'Inspect the announcement channel and workflow logs before any manual recovery '
    '(see .github/discord-release/README.md).'
)


class AnnouncementError(Exception):
    """A safe, operator-facing error containing no webhook URL or response body."""


def release_payload(event, attempt):
    """Return a bounded, mention-safe payload, or None for draft/preview releases."""
    if not isinstance(event, dict) or event.get('action') != 'published':
        raise AnnouncementError('Only release.published events are accepted.')
    repository = event.get('repository')
    if not isinstance(repository, dict) or repository.get('full_name') != REPOSITORY:
        raise AnnouncementError('Unexpected release repository.')
    release = event.get('release')
    if not isinstance(release, dict) or any(type(release.get(key)) is not bool for key in ('draft', 'prerelease')):
        raise AnnouncementError('Invalid release flags.')
    if release['draft'] or release['prerelease']:
        return None
    if attempt != '1':
        raise AnnouncementError(f'Release reruns or missing run attempts are refused. {RECONCILE}')
    tag = release.get('tag_name')
    if not isinstance(tag, str) or len(tag) > 64 or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise AnnouncementError('Expected a stable release tag in vX.Y.Z format (at most 64 characters).')
    url = RELEASE_PREFIX + tag
    if release.get('html_url') != url:
        raise AnnouncementError('Release URL must be the canonical LangBot release URL matching its tag.')
    return {
        'content': f'@everyone LangBot {tag} is now available!\nRelease notes: {url}',
        'allowed_mentions': {'parse': ['everyone'], 'users': [], 'roles': [], 'replied_user': False},
        'tts': False,
        'flags': 0,
    }


def is_snowflake(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9]{1,20}', value) is not None


class DiscordWebhook:
    def __init__(self, url):
        if not url:
            raise AnnouncementError('DISCORD_RELEASE_WEBHOOK_URL is missing. Set the repository Actions secret.')
        match = re.fullmatch(r'https://discord\.com(/api/webhooks/([0-9]{1,20})/[A-Za-z0-9_-]+)', url)
        if not match:
            raise AnnouncementError('Invalid webhook URL; expected https://discord.com/api/webhooks/<id>/<token>.')
        self.path, self.id = match.groups()

    def _request(self, method, suffix='', payload=None):
        # Direct HTTPS, default certificate verification, no proxies or redirect/retry machinery.
        connection = http.client.HTTPSConnection('discord.com', timeout=20)
        try:
            body = json.dumps(payload).encode('utf-8') if payload is not None else None
            connection.request(
                method,
                self.path + suffix,
                body=body,
                headers={'Content-Type': 'application/json', 'User-Agent': 'LangBot-Release-Announcements/1.0'},
            )
            response = connection.getresponse()
            if response.status != 200:
                raise AnnouncementError(f'Discord {method} returned HTTP {response.status}; no retry was attempted.')
            raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                raise AnnouncementError('Discord response exceeded the size limit.')
            return json.loads(raw)
        except (OSError, http.client.HTTPException, ValueError, UnicodeError):
            # Exceptions and bodies can contain the token; never print them or chain them.
            raise AnnouncementError(
                f'Discord {method} failed or returned invalid JSON; no retry was attempted.'
            ) from None
        finally:
            connection.close()

    def validate(self):
        """GET only: verify an incoming webhook and return safe identifying fields."""
        webhook = self._request('GET')
        if (
            not isinstance(webhook, dict)
            or type(webhook.get('type')) is not int
            or webhook['type'] != 1
            or webhook.get('id') != self.id
            or not is_snowflake(webhook.get('guild_id'))
            or not is_snowflake(webhook.get('channel_id'))
        ):
            raise AnnouncementError('Expected an incoming (type 1) webhook with matching ID and guild/channel IDs.')
        return {key: webhook[key] for key in ('id', 'type', 'guild_id', 'channel_id')}

    def send(self, payload):
        """One POST, followed by exact message GET; never automatically retry a send."""
        webhook = self.validate()
        message_id = None
        try:
            sent = self._request('POST', '?wait=true', payload)
            if not isinstance(sent, dict) or not is_snowflake(sent.get('id')):
                raise AnnouncementError('Discord did not return a valid message ID.')
            message_id = sent['id']
            saved = self._request('GET', f'/messages/{message_id}')
            if (
                not isinstance(saved, dict)
                or saved.get('id') != message_id
                or saved.get('webhook_id') != self.id
                or saved.get('channel_id') != webhook['channel_id']
                or saved.get('content') != payload['content']
                or saved.get('mention_everyone') is not True
                or saved.get('mentions') != []
                or saved.get('mention_roles') != []
            ):
                raise AnnouncementError('Discord message readback did not match content, identity, or mentions.')
        except AnnouncementError as error:
            reference = f' Returned message ID: {message_id}.' if message_id else ''
            raise AnnouncementError(f'Delivery not confirmed. {error}{reference} {RECONCILE}') from None
        return message_id


def main(env=None):
    env = os.environ if env is None else env
    try:
        if env.get('GITHUB_REPOSITORY') != REPOSITORY:
            raise AnnouncementError('This workflow is restricted to langbot-app/LangBot.')
        name = env.get('GITHUB_EVENT_NAME')
        if name == 'workflow_dispatch':
            webhook = DiscordWebhook(env.get('DISCORD_RELEASE_WEBHOOK_URL')).validate()
            print(
                f'Validated incoming webhook: guild_id={webhook["guild_id"]} channel_id={webhook["channel_id"]}. No message sent.'
            )
            return 0
        if name != 'release':
            raise AnnouncementError('Only release and workflow_dispatch events are accepted by this helper.')
        try:
            event = json.loads(Path(env.get('GITHUB_EVENT_PATH', '')).read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeError):
            raise AnnouncementError('Cannot read a valid JSON release event from GITHUB_EVENT_PATH.') from None
        payload = release_payload(event, env.get('GITHUB_RUN_ATTEMPT'))
        if payload is None:
            print('Skipped draft or prerelease; no message sent.')
            return 0
        message_id = DiscordWebhook(env.get('DISCORD_RELEASE_WEBHOOK_URL')).send(payload)
        print(f'Announcement verified by exact message readback: message_id={message_id}.')
        return 0
    except AnnouncementError as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
