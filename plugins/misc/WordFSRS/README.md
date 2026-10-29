# WordFSRS — Spaced-repetition vocabulary in your IM

A LangBot plugin built on the [FSRS spaced-repetition algorithm](https://github.com/open-spaced-repetition/py-fsrs) (the **same memory model behind Maimemo / 墨墨背单词**). Build your own vocabulary deck in any chat with the `!word` command and review on a scientifically scheduled forgetting curve.

[简体中文](readme/README_zh_Hans.md)

## Features

- **FSRS scheduling**: every card uses `py-fsrs` to compute its next review time — no more rigid fixed intervals.
- **Per-session isolation**: private chats and each group keep their own deck (keyed by `{launcher_type}:{launcher_id}`).
- **Daily new-card limit**: configurable, so you don't get flooded with new words at once.
- **Target retention**: configurable FSRS `desired_retention` (0.7–0.97).
- **Bilingual**: all messages available in English / Chinese via the `language` config.

## Commands

| Command | Description |
|---|---|
| `!word add <word> [meaning]` | Add a word |
| `!word review` | Pull the next due / new word to review (aliases `next`, `r`) |
| `!word show <word>` | Show a word's meaning (the answer; alias `answer`) |
| `!word grade <word> <1-4>` | Grade recall: 1 forgot / 2 hard / 3 good / 4 easy (aliases `g`, `rate`) |
| `!word stats` | Stats: total / due / new / today's new |
| `!word list [page]` | List the deck (sorted by next review; alias `ls`) |
| `!word del <word>` | Delete a word (aliases `rm`, `delete`) |
| `!word help` | Help |

Grades also accept English / Chinese aliases: `again/hard/good/easy`, `忘了/难/会/简单`.

## Typical flow

```
!word add apple apple
!word add ephemeral short-lived
!word review          → pulls one word and asks you
!word grade apple 3   → grade "good", FSRS schedules the next review
!word stats           → check progress
```

## Configuration

- `language` (default `zh_Hans`): language for all bot messages — `en_US` or `zh_Hans`.
- `daily_new_limit` (default 20): max new cards introduced per session per day; 0 = unlimited.
- `desired_retention` (default 0.9): FSRS target recall probability; higher = more frequent reviews.

## Data storage

Review progress is stored as JSON in the plugin KV store under
`deck:{instance_uuid}:{workspace_uuid}:{installation_uuid}:{session_id}` (binding-less
dedicated workers keep the historical `deck:{session_id}` row; existing rows are not
migrated). Each card keeps the full FSRS state (`Card.to_dict()`), so upgrading algorithm
parameters reads back losslessly.

## Shared runtime

This release declares `shared-runtime-v1` / `stateless-v1`: settings are read per
invocation and the deck read-modify-write is guarded per installation binding.
See [SHARED_RUNTIME.md](SHARED_RUNTIME.md) for the per-invocation and
revocation-scoped state and the known limits. It is not a certification claim.
