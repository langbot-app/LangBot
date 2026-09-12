# Discord release announcements

This independent workflow announces new stable LangBot releases in the channel
selected by a dedicated Discord incoming webhook. It does not change the existing
release/build workflows, edit releases, run a persistent service, poll, or backfill.
Announcements run on publication, independently of artifact builds finishing.

## Setup and read-only validation

1. In the intended community **announcement channel**, create a dedicated incoming
   webhook (Channel Settings → Integrations → Webhooks). Copy its URL; do not reuse
   a webhook belonging to another automation.
2. In `langbot-app/LangBot` → Settings → Secrets and variables → Actions, create the
   **repository secret** `DISCORD_RELEASE_WEBHOOK_URL`. Its value must be exactly
   `https://discord.com/api/webhooks/<id>/<token>` — no query, trailing slash,
   API-version segment, or alternate domain. Treat the entire URL as a password.
3. Once this workflow is on `master`, open Actions → **Discord Release Announcement**
   → Run workflow, choosing `master`. Alternatively:

   ```sh
   gh workflow run discord-release.yml --repo langbot-app/LangBot --ref master
   ```

4. Inspect **Validate webhook (GET only, no message)**. It checks webhook type `1`
   and reports `guild_id` and `channel_id`; compare both with the intended server
   and channel using Discord Developer Mode → Copy ID. The secret determines the
   destination; no channel ID is guessed or overridden. The URL/token is never
   logged. Dispatch cannot send a test message or announce an old release, even
   when run again. Missing/invalid secrets fail validation clearly; offline tests
   do not need secrets.

GET validation confirms the webhook's identity, not delivery or notification
permissions. Verify those on the first genuine release. `mention_everyone=true`
confirms Discord parsed the mention; it cannot prove every member received a push
notification (member/server notification settings still apply).

## Activation and message

The workflow and `.github/discord-release/` helper **must be in the commit targeted
by each new release tag**. Merging to `master` does not enable announcements for
old tags whose commits lack these files. Manual dispatch becomes available when
the workflow is on the default branch. Only publish release tags from trusted,
reviewed commits: release workflows execute that tag's code with the secret.

Only `release` events with action `published`, `draft=false`, and
`prerelease=false` can send. Drafts and prereleases are skipped; release edits do
not trigger announcements. The helper requires the repository to be exactly
`langbot-app/LangBot`, a stable `vX.Y.Z` tag (ASCII digits, at most 64 characters),
and its exact canonical GitHub release URL. Other naming schemes fail closed.

Example message (the version and URL come from the validated event file):

```text
@everyone LangBot v4.10.11 is now available!
Release notes: https://github.com/langbot-app/LangBot/releases/tag/v4.10.11
```

The release title/body is never copied. There is one literal `@everyone`, explicit
`allowed_mentions.parse=["everyone"]`, empty user/role allowlists, and no reply
mention. TTS and notification-suppressing flags are disabled. Requests use HTTPS
only to `discord.com`, an explicit User-Agent, and no redirects or automatic
retries. After a webhook identity GET, one `POST ?wait=true` obtains a message ID;
an exact `/messages/<id>` GET verifies its ID, webhook/channel, content,
`mention_everyone=true`, and empty user/role mention arrays before success.

## Repeat guard and manual recovery

Production sending requires **`GITHUB_RUN_ATTEMPT == "1"`**. Any Actions rerun
(including “Re-run failed jobs”) refuses to POST and requires manual reconciliation,
even if the first attempt failed before sending. Read-only dispatch may be rerun.

This is a practical repeat guard, **not durable exactly-once delivery**. It cannot
prevent duplicates from a separate new run/event (for example deleting/recreating
a release), separate automation, or manual posting. It stores no durable dedupe
state and never modifies the release to mark delivery.

If a POST times out, returns an error, or readback fails, the message may already
exist. The workflow fails rather than blindly sending again. A returned message ID
is included in the safe error when available. A runner termination can also leave
an ambiguous send without that log line.

1. Inspect the announcement channel and the failed run logs. Locate the canonical
   release link and, if available, the returned message ID. A failed verification
   does **not** mean the message was absent.
2. If present, reconcile the existing message/mention problem manually; do not
   rerun, create another release event, or send a duplicate ping.
3. If an operator has positively confirmed no message exists, fix the secret or
   permission issue and use read-only dispatch to validate configuration. A
   maintainer may then post the announcement manually once in Discord and record
   the message link in the incident/run notes. Do not override the attempt guard
   or delete/recreate a release to force recovery.
4. If absence cannot be established, pause and reconcile rather than resending.

To stop future sends, disable **Discord Release Announcement** in Actions. Rotate
or delete the dedicated Discord webhook if the URL is exposed, and update the
secret before validation. No rollback of release artifacts is involved.

## Local checks

Requires Python 3.11+ and the standard library only:

```sh
python3 -m unittest discover -s .github/discord-release -p 'test_*.py' -v
python3 -m py_compile .github/discord-release/announce.py .github/discord-release/test_announce.py
```

Tests exercise policy, CLI/event-file handling, mention payloads, hostile inputs,
HTTP failures, exact message readback, and refusal to retry. Only the HTTPS
transport is mocked for Discord tests; no live Discord requests or messages are
made. Changes to this directory or its workflow run the offline tests on push and
pull request; tests also gate release sending and read-only dispatch validation.
