# Keyword Alert

Monitor group chat messages for specific keywords and receive instant private message alerts.

## Features

- 🔔 Real-time keyword monitoring across group chats
- 📋 Configurable keyword lists (comma-separated)
- 🎯 Monitor specific groups or all groups
- 🤖 Choose which bot sends alerts
- ⏱️ Cooldown to prevent alert spam
- 🔤 Optional case-sensitive matching

## How It Works

1. Configure keywords you want to monitor (e.g., `bug,urgent,help`)
2. Set your user/session ID as the admin to receive alerts
3. When someone sends a message containing a keyword in a monitored group, you get a private message alert with the full context

## Configuration

| Option | Description | Default |
|---|---|---|
| Keywords | Comma-separated keywords to monitor | (required) |
| Group IDs | Comma-separated group IDs (empty = all) | All groups |
| Admin Session ID | Who receives the alerts | (required) |
| Alert Bot | Which bot sends the alert | First available |
| Case Sensitive | Case-sensitive matching | Off |
| Cooldown | Seconds between same-keyword alerts per group | 60 |

## Alert Format

```
🔔 关键词告警
━━━━━━━━━━━━━━
关键词: urgent
群组: 123456789
发送者: 987654321
━━━━━━━━━━━━━━
Hey, this is urgent, the server is down!
```
