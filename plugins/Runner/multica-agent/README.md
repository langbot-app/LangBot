# Multica Agent

Chat with a selected [Multica](https://github.com/multica-ai/multica) agent directly from LangBot.

[简体中文](readme/README_zh_Hans.md)

Each LangBot conversation is bound to one Multica chat session. A user message is
posted to that session, which runs the selected Multica agent; the runner waits for
the agent's reply and sends it back to the chat. The same conversation is visible
in the Multica web app under **Chat**.

## Runner ID

`plugin:langbot-team/MulticaAgent/default`

## Setup

1. In Multica, create a personal access token (Settings → API tokens, `mul_...`).
   Chats are created as the token's owner, so that user must be able to use the agent.
2. Copy the workspace UUID and the agent UUID (`multica agent list --output json`
   prints both).
3. In a LangBot pipeline, choose the **Multica Agent** runner and fill in the fields
   below. The agent's runtime (Multica daemon) must be online to reply.

## Configuration

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| server-url | string | yes | https://api.multica.ai | Multica API URL; use your own server URL when self-hosting |
| api-token | secret | yes | '' | Multica personal access token (`mul_...`) |
| workspace-id | string | yes | '' | Multica workspace UUID |
| agent-id | string | no | '' | Default agent UUID; required unless users pick one with `use` |
| allow-agent-switch | boolean | no | true | Allow `<prefix> use` to pick an agent per conversation |
| command-prefix | string | no | /multica | Prefix of the runner's chat commands |
| timeout | integer | no | 600 | Seconds to wait for a reply |
| poll-interval | number | no | 2 | Seconds between reply checks |

## Chat commands

| Command | Effect |
| --- | --- |
| `/multica` | Show the current agent, session and commands |
| `/multica agents` | List the agents visible to the token |
| `/multica use <name or id>` | Switch this conversation to another agent (new Multica session) |
| `/multica new` | Start a new Multica chat session with the current agent |

## Behavior notes

- Replies are delivered once the agent finishes (no streaming). Agent runs can take
  minutes; when `timeout` expires the run fails but the task keeps running in
  Multica and its reply stays visible there.
- If the stored Multica session was deleted or archived, a new one is created and
  the message is resent once.
- An agent run that fails in Multica is reported as a failed LangBot run with the
  Multica failure text; a cancelled task reports `multica.no_reply`.
- Only text input is forwarded; attachments are not uploaded to Multica.
