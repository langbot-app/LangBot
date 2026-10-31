# ScheNotify

Schedule notifications with natural language

## Features

ScheNotify is a LangBot plugin that allows users to set timed reminders through natural language interaction with LLM.

### Main Features

- **Natural Language Interaction**: Understand user's scheduling intentions through LLM
- **Smart Time Parsing**: Automatically get current time and calculate reminder time
- **Multi-language Support**: Support Chinese and English reminder messages
- **Schedule Management Commands**: View and delete scheduled reminders
- **Automatic Notifications**: Automatically send reminder messages at scheduled time

## Configuration

### Language Setting

You can select the language for reminder messages in plugin configuration:

- `zh_Hans` (Simplified Chinese) - Default
- `en_US` (English)

## Usage

### 1. Schedule via LLM

Simply tell the LLM your schedule in natural language:

**Examples:**
```
Remind me to have a meeting at 3 PM tomorrow
Remind me to submit the report at 9 AM the day after tomorrow
Remind me to have lunch at 12 PM next Monday
Remind me about Christmas dinner at 2024-12-25 18:00
```

The LLM will automatically:
1. Call `get_current_time_str` to get current time
2. Parse your time expression and convert to standard format
3. Call `schedule_notify` to create reminder

### 2. View Scheduled Reminders

Use command to view all scheduled reminders:

```
!sche
```

Example output:
```
[Notify] Scheduled reminders:
#1 2024-12-25 18:00:00: Christmas dinner
#2 2024-12-26 09:00:00: Submit report
```

### 3. Delete Reminder

Use command to delete a specific reminder (using the number from `!sche`):

```
!dsche i <number>
```

Example:
```
!dsche i 1   # Delete the 1st reminder
```

## Components

### Tools

1. **get_current_time_str** - Get current time
   - Return format: `YYYY-MM-DD HH:MM:SS`
   - LLM must call this tool before setting reminders

2. **schedule_notify** - Schedule notification
   - Parameters: time string, reminder message
   - Automatically obtains session info from Tool's session parameter

### Commands

1. **sche** (alias: s) - List all scheduled reminders
2. **dsche** (alias: d) - Delete specified reminder

## Technical Details

- Check interval: Every 60 seconds
- Time precision: Minute level (checks every minute)
- Session info: Automatically obtained through Tool's session parameter
- Persistence: Currently uses in-memory storage (lost on restart)

## Example Conversation

**User:** Remind me to attend a meeting at 2 PM tomorrow

**LLM:** Sure, I'll set a reminder for you.

*[LLM calls get_current_time_str]*
*[LLM calls schedule_notify(time_str="2024-12-26 14:00:00", message="Attend meeting")]*

**LLM:** Done! I will remind you at 2024-12-26 14:00:00: Attend meeting

*[The next day at 2 PM]*

**Bot:** [Notify] Attend meeting

## Notes

- Reminder time must be in the future, past times will be rejected
- Reminder messages will be sent to the same session where the reminder was set
- Listing and deleting are scoped to the exact session that set the reminder (bot + person/group + target id), so reminders set from another bot or from a group with the same id are neither shown nor deleted
- At most 100 reminders can be pending per installation, and each message is limited to 2000 characters
- A reminder whose delivery fails stays queued and is retried on the next check
- Unsent reminders will be lost after plugin restart (persistence will be supported in future versions)

## Developer Info

- Author: RockChinQ
- Version: 0.2.0
- Plugin Type: LangBot Plugin v1

## License

Part of the LangBot plugin ecosystem.
