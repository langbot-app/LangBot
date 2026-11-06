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
2. Copy the workspace UUID (`multica workspace list --output json`). For the agent,
   its name is enough; a UUID also works.
3. In a LangBot pipeline, choose the **Multica Agent** runner and fill in the fields
   below. The agent's runtime (Multica daemon) must be online to reply.

## Plugin settings

Set once per installation on the plugin's settings page.

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| language | select | no | en_US | Language of the plugin's own chat output: `en_US`, `zh_Hans`, `zh_Hant`, `ja_JP`, `es_ES`, `ru_RU`, `th_TH`, `vi_VN` |

- It only affects text this plugin writes: progress lines, command replies and error
  messages. The agent's answer and Multica's own error text are passed through as-is.
- It does not change LangBot's interface language, which is a Workspace setting.
- The 8 locales above are supported; any other value falls back to English. There is
  no "follow the Workspace language" option: that would need an extra Workspace
  permission that every installation must approve.

## Runner configuration

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| server-url | string | yes | https://api.multica.ai | Multica API URL; use your own server URL when self-hosting |
| api-token | secret | yes | '' | Multica personal access token (`mul_...`) |
| workspace-id | string | yes | '' | Multica workspace UUID |
| agent | string | no | '' | Default agent, **name or UUID**; required unless users pick one with `use` (see below) |
| agent-id | string | no | '' | **Deprecated** since 0.2.0. Agent UUID used as-is, only when `agent` is empty; existing 0.1.x pipelines keep working |
| allow-agent-switch | boolean | no | true | Allow `<prefix> use` to pick an agent per conversation |
| command-prefix | string | no | /multica | Prefix of the runner's chat commands |
| timeout | integer | no | 600 | Seconds to wait for a reply |
| poll-interval | number | no | 2 | Seconds between reply checks |
| progress-mode | select | no | messages | `messages`: each progress update is its own message, the answer comes last; `stream`: one message updated in place; `off`: only the answer (0.1.x behavior) |
| progress-interval | number | no | 15 | Minimum seconds (5-300) between "still running" updates |

### Choosing the agent by name

A UUID is used directly. Otherwise the runner looks up the token's unarchived agents
and picks the one whose name matches exactly (case-insensitive), or else the only
one whose name contains the text. The result is remembered for the conversation.
If several agents match, the run fails and lists numbered candidates; reply with
`/multica use <number>` or use the full ID. If none match, the first ten visible
agent names are listed.

## Chat commands

| Command | Effect |
| --- | --- |
| `/multica` | Show the current agent, session and commands |
| `/multica agents` | List the agents visible to the token, numbered, with short IDs |
| `/multica agents <keyword>` | List only agents whose name contains the keyword |
| `/multica find <keyword>` | Same as `agents <keyword>`; without a keyword it shows usage |
| `/multica use <name or id>` | Switch this conversation to another agent (new Multica session); an ambiguous name replies with numbered candidates |
| `/multica use <number>` | Pick by number from the latest `agents` / `find` / candidate list (valid for 10 minutes; the reply names the chosen agent) |
| `/multica new` | Start a new Multica chat session with the current agent |

`/multica` also shows the current `progress-mode` and `language`. A purely numeric `use` argument is
always read as a list number.

## Progress output

Multica exposes no task event stream: the runner can only observe the task lifecycle
(queued, running, finished) and how long it has waited. It cannot see which tools or
steps the agent is running, so progress never claims more than that.

With `progress-mode: messages` and `language: en_US`, a run looks like:

```
⏳ Submitted to Coder (task 3f2a9c1e)
▶️ Coder started
⏱ Still running · waited 45s
<the agent's answer, unprefixed>
```

A queued task reports `⏱ Queued · waited Ns` instead. "Still running" updates are sent
at most once per `progress-interval`, so a run produces at most
`3 + timeout / progress-interval` messages. On timeout, cancellation or failure a final
`⚠️ ...` line is sent before the run fails.

`progress-mode: stream` writes the same lines into one message and appends the answer
at its end. Platforms without streamed replies receive that message once, when the
run ends; use `messages` there.

## Behavior notes

- Agent runs can take minutes; when `timeout` expires the run fails but the task
  keeps running in Multica and its reply stays visible there.
- If the stored Multica session was deleted or archived, a new one is created and
  the message is resent once.
- An agent run that fails in Multica is reported as a failed LangBot run with the
  Multica failure text; a cancelled task reports `multica.no_reply`.
- Only text input is forwarded; attachments are not uploaded to Multica.
